import cv2
import numpy as np
import time
import base64
from flask import Flask, render_template_string, Response, request, jsonify
import threading
import torch
import traceback

# ★ 追加 ★: スレッドセーフ化のために time をインポート
import time

# カスタムモジュールのインポート
from src.hardware.camera import Camera
from src.hardware.arduino_com import ArduinoCom
from src.hardware.ir_sensor import get_ir_sensor_reading
import config # config.pyをインポート


# --- グローバル変数と初期化 ---
app = Flask(__name__)
# Arduinoのパスをconfigから取得
arduino_com = ArduinoCom(config.SERIAL_PORT, config.BAUD_RATE)
camera = None
yolo_model = None

# ★ 追加 ★: スレッドセーフなセンサー値のためのグローバル変数
g_last_ir_value = 0.0
g_sensor_lock = threading.Lock()


# YOLOv5モデルのロード
try:
    yolo_model = torch.hub.load(
        '/home/yutoseki/robot_arm_project/yolov5',
        'custom',
        path='/home/yutoseki/robot_arm_project/models/best.pt',
        source='local',
        force_reload=True,
        verbose=False
    )
    yolo_model.eval()
except Exception:
    print("モデルロードエラー詳細:")
    traceback.print_exc()


# ★ 追加 ★: センサー値のバックグラウンド更新スレッド
def sensor_update_thread():
    """
    ArduinoからIRセンサーの値を読み取り続けるバックグラウンドスレッド。
    シリアルポートの競合を防ぐため、読み取りはこのスレッドに一元化する。
    """
    global g_last_ir_value
    print("[Sensor Thread] センサー読み取りスレッドを開始しました。")
    while True:
        if arduino_com.is_ready:
            # ir_sensor.py の関数を直接呼び出す
            raw_val = get_ir_sensor_reading(arduino_com.ser)

            # 0.0 (タイムアウト) でない場合のみ値を更新する
            if raw_val > 0.0:
                with g_sensor_lock:
                    g_last_ir_value = raw_val

        # ポーリング間隔 (100ms)
        time.sleep(0.1)


# --- アーム制御関数 (IKは省略し、サーボ0をターゲットに) ---
# (注: このテストではArduino側がIR専用のため、この関数は動作しません)
def move_arm_to_target_simple(servo_index: int, angle: int):
    """
    指定されたサーボを目標角度に動かす（IKは省略）
    """
    if arduino_com.is_ready:
        print(f"[Control] サーボ {servo_index} を {angle} 度へ (注: 現在IRテスト専用です)")
        # arduino_com.py に send_servo_command がないため、コメントアウト
        # arduino_com.send_servo_command(servo_index, angle)
    else:
        print("[Control] エラー: Arduinoが未接続です。")


# --- YOLOv5 処理とフレーム生成 ---
def generate_frames():
    """
    カメラからフレームを読み込み、YOLOで処理し、JPEGにエンコードして返すジェネレーター
    """
    global camera
    if camera is None:
        try:
            # config.py から解像度を使用
            camera = Camera(
                config.CAMERA_ID,
                config.CAMERA_RESOLUTION_WIDTH,
                config.CAMERA_RESOLUTION_HEIGHT
            )
            print("[Camera] カメラ初期化完了。")
        except Exception as e:
            print(f"[Camera] カメラ初期化エラー: {e}")
            return

    while True:
        ret, frame = camera.get_frame()
        if not ret:
            time.sleep(0.1)
            continue

        # 1. YOLOv5 推論
        detections = []
        if yolo_model:
            # ★ 修正点 3: YOLOv5 (torch.hub) 形式の推論 ★ (変更なし)
            results = yolo_model(frame)

            # 結果の処理 (v5形式のpandas()を使用)
            df = results.pandas().xyxy[0]
            for _, row in df.iterrows():
                cls = int(row['class'])
                conf = float(row['confidence'])

                # 'ship' ラベル (クラスID 0) のみ処理 (data.yamlに基づき正しい)
                if cls == 0 and conf > 0.5:
                    x1, y1, x2, y2 = map(int, [row['xmin'], row['ymin'], row['xmax'], row['ymax']])

                    # バウンディングボックス描画
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                    # 2. 距離計算と座標推定

                    # ★ 修正 ★: get_ir_sensor_reading を直接呼ばず、グローバル変数を参照
                    with g_sensor_lock:
                        raw_ir_value = g_last_ir_value

                    # ★ 修正 ★: GP2Y0A21YK0F (10-80cm) のための変換
                    # 300-350 の入力で 0.0 になる不適切な式を修正
                    if raw_ir_value < 80: # 80cm以上は信頼できない
                        distance_cm = 80.0
                    elif raw_ir_value > 550: # 10cm以下は信頼できない
                        distance_cm = 10.0
                    else:
                        try:
                            # 逆数モデルの近似式 (要キャリブレーション)
                            # 例: (6762 / (325 - 9)) - 4 = 17.4cm (妥当な値)
                            distance_cm = (6762 / (raw_ir_value - 9)) - 4

                            # 計算結果が範囲外になった場合もクリップ
                            if distance_cm > 80.0: distance_cm = 80.0
                            if distance_cm < 10.0: distance_cm = 10.0
                        except ZeroDivisionError:
                            distance_cm = 80.0 # 異常値 (raw_ir_valueが9の場合)
                    # ★★★ 修正ここまで ★★★

                    # バウンディングボックス中央座標
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2

                    # 3. 画面上に結果を表示 (distance_cm が実測値になる)
                    label = f"Ship: {conf:.2f} | IR:{raw_ir_value:.0f} | D:{distance_cm:.1f}cm"
                    cv2.putText(frame, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                    detections.append({
                        'x': center_x,
                        'y': center_y,
                        'distance_cm': distance_cm,
                        'ir_value': raw_ir_value,
                        'confidence': conf
                    })

        # 4. フレームをJPEGにエンコード
        (flag, encodedImage) = cv2.imencode(".jpg", frame)
        if not flag:
            continue

        # 5. ストリームとして返す
        yield(b'--frame\r\n'
              b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')

        time.sleep(0.01) # CPU負荷軽減


# --- Flask Routes ---


@app.route('/')
def index():
    """
    メインのウェブUIページ
    """
    return render_template_string(HTML_TEMPLATE)


@app.route('/video_feed')
def video_feed():
    """
    カメラ映像のストリーム
    """
    return Response(generate_frames(),
                    mimetype = "multipart/x-mixed-replace; boundary=frame")


@app.route('/api/move', methods=['POST'])
def api_move():
    """
    アーム制御API (注: 現在のArduinoスケッチでは機能しません)
    """
    data = request.json
    servo_id = data.get('servo_id', 0)
    angle = data.get('angle', 90)

    # send_servo_command が arduino_com.py に存在しないため、ここではロギングのみ
    print(f"[API Move] 受信 (無効): Servo {servo_id} to {angle} deg.")
    return jsonify({'status': 'ok', 'message': f'Servo {servo_id} command received (Note: Arduino is IR-Only).'})



@app.route('/api/ir_value')
def api_ir_value():
    """
    IRセンサー値取得API
    """
    # ★ 修正 ★: get_ir_sensor_reading を直接呼ばず、グローバル変数を参照
    with g_sensor_lock:
        ir_value = g_last_ir_value

    return jsonify({'ir_raw': ir_value})


# --- HTML/GUI テンプレート ---


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>リアルタイム物体検出 & ロボットアーム制御</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .video-container {
            max-width: 90vw;
            margin: auto;
            border-radius: 12px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            overflow: hidden;
        }
        #videoElement {
            width: 100%;
            height: auto;
            border-radius: 12px;
        }
    </style>
</head>
<body class="bg-gray-100 p-4 md:p-8 font-sans">

    <div class="max-w-4xl mx-auto">
        <h1 class="text-3xl font-extrabold text-gray-900 mb-6 border-b pb-2">
            🤖 RPi-Arm: YOLOv5 & センサー統合テスト
        </h1>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

            <div class="lg:col-span-2 bg-white p-4 rounded-xl shadow-lg">
                <h2 class="text-xl font-semibold text-gray-700 mb-3">ライブカメラフィード (YOLOv5)</h2>
                <div class="video-container border-2 border-gray-300">
                    <img id="videoElement" src="{{ url_for('video_feed') }}" alt="リアルタイムカメラフィード">
                </div>
            </div>

            <div class="lg:col-span-1 space-y-6">

                <div class="bg-white p-4 rounded-xl shadow-lg">
                    <h2 class="text-xl font-semibold text-gray-700 mb-3">センサー & 距離推定</h2>
                    <p class="text-sm text-gray-500 mb-2">ArduinoとIRセンサーからのリアルタイムデータ。</p>
                    <div id="ir-data" class="text-2xl font-bold text-indigo-600">
                        IR RAW: <span id="ir-raw-value">---</span>
                    </div>
                    <div id="distance-data" class="text-xl font-medium text-green-600 mt-1">
                        距離推定: <span id="distance-cm">---</span> cm
                    </div>
                </div>

                <div class="bg-white p-4 rounded-xl shadow-lg opacity-50">
                    <h2 class="text-xl font-semibold text-gray-700 mb-3">アーム制御 (現在無効)</h2>
                    <p class="text-sm text-gray-500 mb-4">注: 現在のテストではIRセンサーのみ有効です。</p>

                    <div class="space-y-3">
                        <input type="range" min="0" max="180" value="90" id="servo-angle" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer range-lg" disabled>
                        <p class="text-lg font-medium">角度: <span id="current-angle">90</span>°</p>

                        <div class="flex space-x-2">
                            <button onclick="alert('サーボ制御は現在無効です')"
                                    class="flex-1 bg-indigo-500 hover:bg-indigo-600 text-white font-bold py-2 px-4 rounded-lg transition duration-150 shadow-md" disabled>
                                角度送信
                            </button>
                            <button onclick="alert('サーボ制御は現在無効です')"
                                    class="bg-gray-400 hover:bg-gray-500 text-white font-bold py-2 px-4 rounded-lg transition duration-150" disabled>
                                中央(90°)
                            </button>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <script>
        const irRawDisplay = document.getElementById('ir-raw-value');
        const distanceCmDisplay = document.getElementById('distance-cm');

        // (サーボ関連のJSは、ボタンが無効化されているため削除または省略)

        async function updateSensorData() {
            try {
                const response = await fetch('/api/ir_value');
                const data = await response.json();

                // IR生の値
                const rawValue = data.ir_raw;
                irRawDisplay.textContent = rawValue.toFixed(0);

                // ★ 修正 ★: JS側でもIRセンサーの変換ロジックを反映 ★
                let estimatedDistance = "---";
                if (rawValue < 80) { // 80cm以上は信頼できない
                    estimatedDistance = "80.0+";
                } else if (rawValue > 550) { // 10cm以下は信頼できない
                    estimatedDistance = "<10.0";
                } else {
                    try {
                        // (Python側と同じ近似式)
                        let dist = (6762 / (rawValue - 9)) - 4;
                        if (dist > 80.0) dist = 80.0;
                        if (dist < 10.0) dist = 10.0;
                        estimatedDistance = dist.toFixed(1);
                    } catch (e) {
                        estimatedDistance = "Calc Err";
                    }
                }
                // ★★★ 修正ここまで ★★★

                distanceCmDisplay.textContent = estimatedDistance;

            } catch (error) {
                console.error("Error fetching sensor data:", error);
                irRawDisplay.textContent = "COMM ERROR";
                distanceCmDisplay.textContent = "COMM ERROR";
            }
        }

        // センサーデータのポーリング
        setInterval(updateSensorData, 500);

    </script>
</body>
</html>
"""


# --- サーバー起動ロジック ---
if __name__ == '__main__':
    # ★ 修正点 6: Arduino接続の競合回避 ★ (変更なし)
    # サーバー起動の *前* に、メインスレッドでArduinoの接続を完了させる
    print("[Main] Arduino接続待機中...")
    if arduino_com.open_and_wait_for_ready():
        print("[Main] Arduino接続完了。")

        # ★ 追加 ★: センサー読み取りスレッドを開始
        print("[Main] センサー読み取りスレッドを開始します。")
        sensor_thread = threading.Thread(target=sensor_update_thread, daemon=True)
        sensor_thread.start()

        # RPiのローカルアドレスで起動 (Macのブラウザからアクセス可能にする)
        print("-----------------------------------------------------------------")
        print(f"Web GUIを起動します。Raspberry PiのIPアドレスを使ってアクセスしてください。")
        print(f"例: http://192.168.3.5:5000/")
        print("-----------------------------------------------------------------")
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        print("\n[FATAL ERROR] Arduinoの接続に失敗しました。")
        print("USB接続とArduinoのC++コード（Temp_IR_Test.ino）を確認してください。")
