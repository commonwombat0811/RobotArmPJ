import cv2
import numpy as np
import time
import base64
from flask import Flask, render_template_string, Response, request, jsonify
import threading
import torch
import traceback
import json # ★追加★: ロギング用
from typing import List # ★追加★: 型ヒント用

# カスタムモジュールのインポート
from src.hardware.camera import Camera
from src.hardware.arduino_com import ArduinoCom
from src.hardware.ir_sensor import get_ir_sensor_reading
import config # config.pyをインポート


# --- ロボットアームの物理的制約定義 ---
# (0: ベース, 1: 肩, 2: 肘, 3: 手首ピッチ, 4: 手首ロール, 5: グリッパー/手首ヨー)

# 逆回転フラグ: True なら 180 - Angle を送る
INVERSE_ROTATION = {
    0: True,    # 0軸は逆回転 (180->0 が 0->180)
    1: False,
    2: True,    # 2軸は逆回転
    3: True,    # 3軸は逆回転
    4: True,    # 4軸は逆回転
    5: False
}

# 角度制限 [MIN, MAX] (フロントエンドのスライダー値 (0-180) に適用)
ANGLE_LIMITS = {
    0: [90, 180], # 実際: 180->90 を 0->90 にマッピング。0軸は90-180のみ可動
    1: [0, 180],  # 1軸は全可動域
    2: [30, 180], # 2軸は30-180のみ可動 (逆回転で 180->30 が 0->150 に相当)
    3: [90, 180], # 3軸は90-180のみ可動 (逆回転で 0->90 に相当)
    4: [90, 180], # 4軸は90-180のみ可動 (逆回転で 0->90 に相当)
    5: [0, 180]   # 5軸は全可動域
}

def apply_servo_constraints(angle_list: List[int]) -> List[int]:
    """
    ユーザーが指定した物理的な制約（逆回転・可動域）を角度リストに適用する。
    返される角度は Arduino に送信される 0-180 の値。
    """
    processed_angles = []
    for i, angle in enumerate(angle_list):
        # 1. 可動域制限の適用 (マッピング前の角度でクリップ)
        min_angle, max_angle = ANGLE_LIMITS.get(i, [0, 180])

        # 角度をクリップ
        safe_angle = max(min_angle, min(max_angle, angle))

        # 2. 逆回転の適用 (Arduinoへの送信角度に変換)
        if INVERSE_ROTATION.get(i, False):
            # 180を最大値とし、0を最小値として反転
            final_angle = 180 - safe_angle
        else:
            final_angle = safe_angle

        processed_angles.append(int(final_angle))

    return processed_angles


# --- グローバル変数と初期化 ---
app = Flask(__name__)
# Arduinoのパスをconfigから取得
arduino_com = ArduinoCom(config.SERIAL_PORT, config.BAUD_RATE)
camera = None
yolo_model = None

# ★ グローバル変数追加 ★
g_last_ir_value = 0.0
g_sensor_lock = threading.Lock()
# 追跡とロギングのためのグローバル変数
g_current_target = None # {'x', 'y', 'distance_cm', 'ir_value', 'confidence', 'last_seen'}
g_target_lock = threading.Lock()


# YOLOv5モデルのロード (変更なし)
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


# ★ センサー値のバックグラウンド更新スレッド (変更なし) ★
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
            # 注: get_ir_sensor_reading はこのファイルには含まれていませんが、importにより存在します
            raw_val = get_ir_sensor_reading(arduino_com.ser)

            # 0.0 (タイムアウト) でない場合のみ値を更新する
            if raw_val > 0.0:
                with g_sensor_lock:
                    g_last_ir_value = raw_val

        # ポーリング間隔 (100ms)
        time.sleep(0.2)


# --- YOLOv5 処理とフレーム生成 (追跡ロジックを追加) ---
def generate_frames():
    global camera, g_current_target

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
            time.sleep(0.2)
            continue

        # 1. YOLOv5 推論
        detections = []
        # ... (YOLO検出ロジックは変更なし。検出結果をdetectionsに入れる) ...
        if yolo_model:
            results = yolo_model(frame)
            df = results.pandas().xyxy[0]
            for _, row in df.iterrows():
                cls = int(row['class'])
                conf = float(row['confidence'])

                if cls == 0 and conf > 0.5:
                    x1, y1, x2, y2 = map(int, [row['xmin'], row['ymin'], row['xmax'], row['ymax']])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                    with g_sensor_lock:
                        raw_ir_value = g_last_ir_value

                    # 距離計算 (変更なし)
                    if raw_ir_value < 80:
                        distance_cm = 80.0
                    elif raw_ir_value > 550:
                        distance_cm = 10.0
                    else:
                        try:
                            distance_cm = (6762 / (raw_ir_value - 9)) - 4
                            if distance_cm > 80.0: distance_cm = 80.0
                            if distance_cm < 10.0: distance_cm = 10.0
                        except ZeroDivisionError:
                            distance_cm = 80.0

                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2

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

        # ★ 追跡ロジック (ターゲット状態の更新) ★
        with g_target_lock:
            if detections:
                # ターゲットが見つかった場合、ターゲットを更新
                new_target = detections[0]
                new_target['last_seen'] = time.time()
                g_current_target = new_target

                # カメラ中心にターゲットを描画
                cx = new_target['x']
                cy = new_target['y']
                cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1) # 青い点で最新の検出

            else:
                # ターゲットが見つからない場合、最後に検出したターゲットを保持するか判断
                if g_current_target is not None:
                    time_since_seen = time.time() - g_current_target.get('last_seen', 0)

                    # 0.5秒以上見失ったら、ターゲットをNoneに戻す
                    if time_since_seen > 0.5:
                        g_current_target = None
                    else:
                        # 0.5秒未満なら、最後の検出座標をフレームに描画（追跡の継続を視覚化）
                        cx = g_current_target['x']
                        cy = g_current_target['y']
                        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1) # 赤い点で追跡中を示す

        # 4. フレームをJPEGにエンコード (変更なし)
        (flag, encodedImage) = cv2.imencode(".jpg", frame)
        if not flag:
            continue

        # 5. ストリームとして返す (変更なし)
        yield(b'--frame\r\n'
              b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')

        time.sleep(0.01)


# --- Flask Routes ---
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype = "multipart/x-mixed-replace; boundary=frame")

@app.route('/api/move', methods=['POST'])
def api_move():
    """
    ★ 6軸同時制御API ★
    フロントエンドから受け取った角度を制約に適用し、Arduinoへ送信、ログを記録。
    """
    data = request.json
    # フロントエンドのスライダー角度 (0-180) のリスト
    user_angles = data.get('servo_angles', [90] * 6)

    # 1. 制約を適用して Arduino に送る角度に変換
    arduino_angles = apply_servo_constraints(user_angles)

    # 2. Arduino にコマンドを送信
    log_status = "FAILED"
    if arduino_com.is_ready:
        # 注: arduino_com.send_multi_servo_command は、arduino_com.pyに実装されている必要があります。
        if arduino_com.send_multi_servo_command(arduino_angles):
            log_status = "SUCCESS"
        else:
            log_status = "COMM_FAIL"
    else:
        log_status = "NOT_READY"

    # 3. ログ記録のための現在の状態を取得
    with g_target_lock:
        target_data = g_current_target.copy() if g_current_target else {}
    with g_sensor_lock:
        ir_raw = g_last_ir_value

    log_entry = {
        'timestamp': time.time(),
        'user_angles': user_angles,        # ユーザーが指定した角度 (ログ確認用)
        'arduino_angles': arduino_angles,  # Arduinoに送った角度
        'ir_raw': ir_raw,
        'target_detection': target_data,
        'move_status': log_status
    }

    # 4. ログをファイルに記録 (JSONL形式)
    try:
        with open('calibration_data_log.jsonl', 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        print(f"[API Move] 制御コマンド受信&ログ記録: {arduino_angles}")
        status_msg = 'ok'
        return_msg = f'Servos moved to {arduino_angles} and data logged. Status: {log_status}'
    except Exception as e:
        status_msg = 'warning'
        return_msg = f'Servos moved, but log file failed: {e}'
        print(f"[API Move] WARNING: ログファイル書き込みエラー: {e}")

    return jsonify({'status': status_msg, 'message': return_msg, 'log_entry': log_entry})


@app.route('/api/ir_value')
def api_ir_value():
    """
    IRセンサー値取得API (変更なし)
    """
    with g_sensor_lock:
        ir_value = g_last_ir_value

    return jsonify({'ir_raw': ir_value})


# --- HTML/GUI テンプレート (6軸スライダーとロギングボタン付き) ---


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
        /* スライダーの見た目を調整 */
        input[type=range].servo-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #4f46e5;
            cursor: pointer;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.3);
        }
    </style>
</head>
<body class="bg-gray-100 p-4 md:p-8 font-sans">

    <div class="max-w-4xl mx-auto">
        <h1 class="text-3xl font-extrabold text-gray-900 mb-6 border-b pb-2">
            🤖 RPi-Arm: 統合制御 & データ収集
        </h1>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

            <div class="lg:col-span-2 bg-white p-4 rounded-xl shadow-lg">
                <h2 class="text-xl font-semibold text-gray-700 mb-3">ライブカメラフィード (YOLOv5 & 追跡)</h2>
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

                <div class="bg-white p-4 rounded-xl shadow-lg">
                    <h2 class="text-xl font-semibold text-gray-700 mb-3">🛠️ 6軸手動制御 & データ収集</h2>
                    <p class="text-sm text-red-500 mb-4 font-bold">⚠️ スライダー値は 0-180。物理的制約はPythonで自動適用されます。</p>

                    <div class="space-y-3" id="servo-controls">
                        <label class="block text-sm font-medium text-gray-700">サーボ0 (ベース): <span id="angle-0">90</span>° (可動域: 90-180)</label>
                        <input type="range" min="0" max="180" value="90" data-servo-id="0" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <label class="block text-sm font-medium text-gray-700">サーボ1 (肩): <span id="angle-1">90</span>° (可動域: 0-180)</label>
                        <input type="range" min="0" max="180" value="90" data-servo-id="1" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <label class="block text-sm font-medium text-gray-700">サーボ2 (肘): <span id="angle-2">90</span>° (可動域: 30-180)</label>
                        <input type="range" min="0" max="180" value="90" data-servo-id="2" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <label class="block text-sm font-medium text-gray-700">サーボ3 (手首P): <span id="angle-3">90</span>° (可動域: 90-180)</label>
                        <input type="range" min="0" max="180" value="90" data-servo-id="3" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <label class="block text-sm font-medium text-gray-700">サーボ4 (手首R): <span id="angle-4">90</span>° (可動域: 90-180)</label>
                        <input type="range" min="0" max="180" value="90" data-servo-id="4" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <label class="block text-sm font-medium text-gray-700">サーボ5 (グリッパー): <span id="angle-5">90</span>° (可動域: 0-180)</label>
                        <input type="range" min="0" max="180" value="90" data-servo-id="5" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <div class="flex space-x-2 mt-4">
                            <button id="send-angles-btn"
                                    class="flex-1 bg-indigo-500 hover:bg-indigo-600 text-white font-bold py-2 px-4 rounded-lg transition duration-150 shadow-md">
                                角度を送信 & ログ記録
                            </button>
                            <button id="set-home-btn"
                                    class="bg-gray-400 hover:bg-gray-500 text-white font-bold py-2 px-4 rounded-lg transition duration-150">
                                中央 (90°) に戻す
                            </button>
                        </div>
                        <p id="control-status" class="text-center text-sm mt-2 font-bold"></p>
                    </div>
                </div>


            </div>
        </div>
    </div>

    <script>
        const irRawDisplay = document.getElementById('ir-raw-value');
        const distanceCmDisplay = document.getElementById('distance-cm');
        const sliders = document.querySelectorAll('.servo-slider');
        const sendBtn = document.getElementById('send-angles-btn');
        const homeBtn = document.getElementById('set-home-btn');
        const statusDisplay = document.getElementById('control-status');

        // --- センサーデータ更新 (変更なし) ---
        async function updateSensorData() {
            try {
                const response = await fetch('/api/ir_value');
                const data = await response.json();
                const rawValue = data.ir_raw;
                irRawDisplay.textContent = rawValue.toFixed(0);

                let estimatedDistance = "---";
                if (rawValue < 80) { estimatedDistance = "80.0+"; }
                else if (rawValue > 550) { estimatedDistance = "<10.0"; }
                else {
                    try {
                        let dist = (6762 / (rawValue - 9)) - 4;
                        if (dist > 80.0) dist = 80.0;
                        if (dist < 10.0) dist = 10.0;
                        estimatedDistance = dist.toFixed(1);
                    } catch (e) {
                        estimatedDistance = "Calc Err";
                    }
                }
                distanceCmDisplay.textContent = estimatedDistance;
            } catch (error) {
                irRawDisplay.textContent = "COMM ERROR";
                distanceCmDisplay.textContent = "COMM ERROR";
            }
        }
        setInterval(updateSensorData, 500);

        // --- ★ 6軸制御のためのJS関数 (新規追加) ★ ---

        sliders.forEach(slider => {
            slider.addEventListener('input', (e) => {
                const id = e.target.dataset.servoId;
                document.getElementById(`angle-${id}`).textContent = e.target.value;
            });
        });

        function getServoAngles() {
            // スライダーの現在の角度をリストで取得
            return Array.from(sliders).map(slider => parseInt(slider.value));
        }

        async function sendAnglesAndLog() {
            const angles = getServoAngles();
            statusDisplay.textContent = 'コマンド送信中...';
            statusDisplay.className = 'text-center text-sm mt-2 text-gray-700 font-bold';

            try {
                const response = await fetch('/api/move', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ servo_angles: angles })
                });
                const data = await response.json();

                if (data.status === 'ok') {
                    statusDisplay.textContent = `✅ ログ記録成功。送出角度: ${data.log_entry.arduino_angles.join(', ')}`;
                    statusDisplay.className = 'text-center text-sm mt-2 text-green-600 font-bold';
                } else {
                    statusDisplay.textContent = `⚠️ ログ記録警告: ${data.message}`;
                    statusDisplay.className = 'text-center text-sm mt-2 text-yellow-600 font-bold';
                }
            } catch (error) {
                statusDisplay.textContent = '❌ 通信エラー。サーバーを確認してください。';
                statusDisplay.className = 'text-center text-sm mt-2 text-red-600 font-bold';
            }
        }

        function setHomeAngles() {
            // 全てのサーボを90°にリセット
            sliders.forEach(slider => {
                const id = slider.dataset.servoId;
                slider.value = 90;
                document.getElementById(`angle-${id}`).textContent = 90;
            });
            sendAnglesAndLog(); // 中央に戻したら、動かしてログも記録
        }

        sendBtn.addEventListener('click', sendAnglesAndLog);
        homeBtn.addEventListener('click', setHomeAngles);

    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)



# --- サーバー起動ロジック (変更なし) ---
if __name__ == '__main__':
    print("[Main] Arduino接続待機中...")
    # 注: arduino_com.open_and_wait_for_ready は、arduino_com.pyに実装されている必要があります。
    if arduino_com.open_and_wait_for_ready():
        print("[Main] Arduino接続完了。")
        print("[Main] センサー読み取りスレッドを開始します。")
        sensor_thread = threading.Thread(target=sensor_update_thread, daemon=True)
        sensor_thread.start()
        print("-----------------------------------------------------------------")
        print(f"Web GUIを起動します。Raspberry PiのIPアドレスを使ってアクセスしてください。")
        print(f"例: http://192.168.3.5:5000/")
        print("-----------------------------------------------------------------")
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        print("\n[FATAL ERROR] Arduinoの接続に失敗しました。")
        print("USB接続とArduinoのC++コードを確認してください。")
