import multiprocessing as mp
import cv2
import numpy as np
import time
import base64
from flask import Flask, render_template_string, Response, request, jsonify
import threading
import torch
import traceback
import json
from typing import List

# --- 必要なハードウェアモジュール ---
from src.hardware.camera import Camera
# (ArduinoCom と ir_sensor は RealTime プロセスが担当するので、ここではインポートしない)
import config

# ==============================================================================
# このプロセス専用のグローバル変数
# ==============================================================================

app = Flask(__name__)
camera = None
yolo_model = None
g_current_target = None
g_target_lock = threading.Lock()

task_queue_mp = None
ir_value_shared_mp = None

# --- ★★★ これがあなたの「作業ログ」です ★★★ ---
# 1. 逆回転の定義
INVERSE_ROTATION = {
    0: False,    # 0: 逆回転
    1: False,   # 1: 通常
    2: True,    # 2: 逆回転
    3: False,    # 3: 逆回転
    4: False,    # 4: 逆回転
    5: False    # 5: 通常
}

# 2. 物理的な可動域の定義 (GUIスライダーが送る値の範囲)
ANGLE_LIMITS = {
    0: [90, 180], # 0: 90-180
    1: [0, 180],  # 1: 0-180
    2: [30, 180], # 2: 30-180
    3: [90, 180], # 3: 90-180
    4: [90, 180], # 4: 90-180
    5: [0, 180]   # 5: 0-180
}
# --- ★★★ 修正ここまで ★★★ ---

def apply_servo_constraints(angle_list: List[int]) -> List[int]:
    """
    ユーザーが指定した物理的な制約（逆回転・可動域）を角度リストに適用する。
    返される角度は Arduino に送信される 0-180 の値。
    """
    processed_angles = []
    for i, angle in enumerate(angle_list):
        # 1. 可動域制限の適用 (マッピング前の角度でクリップ)
        min_angle, max_angle = ANGLE_LIMITS.get(i, [0, 180])
        # スライダーがこの範囲外の値を送ってきても、ここで丸められる
        safe_angle = max(min_angle, min(max_angle, angle))

        # 2. 逆回転の適用 (Arduinoへの送信角度に変換)
        if INVERSE_ROTATION.get(i, False):
            # (例: 90 -> 180-90=90 / 180 -> 180-180=0)
            final_angle = 180 - safe_angle
        else:
            final_angle = safe_angle

        processed_angles.append(int(final_angle))

    return processed_angles


# --- YOLOv5 処理とフレーム生成 (カメラ/YOLO担当) ---
@app.route('/video_feed')
def video_feed():
    """ カメラ映像のストリーム (M-JPEG) """
    return Response(generate_frames(),
                    mimetype = "multipart/x-mixed-replace; boundary=frame")

def generate_frames():
    global camera, g_current_target, yolo_model

    if camera is None:
        try:
            camera = Camera(
                config.CAMERA_ID,
                config.CAMERA_RESOLUTION_WIDTH,
                config.CAMERA_RESOLUTION_HEIGHT
            )
            print("[Orchestrator] カメラ初期化完了。")
        except Exception as e:
            print(f"[Orchestrator] [FATAL] カメラ初期化エラー: {e}")
            return

    while True:
        ret, frame = camera.get_frame()
        if not ret:
            print("[Orchestrator] カメラフレーム取得失敗。")
            time.sleep(0.2)
            continue

        # 1. YOLOv5 推論
        detections = []
        if yolo_model:
            try:
                results = yolo_model(frame)
                df = results.pandas().xyxy[0]
                raw_ir_value = ir_value_shared_mp.value

                for _, row in df.iterrows():
                    cls = int(row['class'])
                    conf = float(row['confidence'])

                    if cls == 0 and conf > 0.5:
                        x1, y1, x2, y2 = map(int, [row['xmin'], row['ymin'], row['xmax'], row['ymax']])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                        # 距離計算
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
            except Exception as e:
                print(f"[Orchestrator] YOLO推論エラー: {e}")
                traceback.print_exc()


        # 2. 追跡ロジック (ターゲット状態の更新)
        with g_target_lock:
            if detections:
                new_target = detections[0]
                new_target['last_seen'] = time.time()
                g_current_target = new_target
                cx, cy = new_target['x'], new_target['y']
                cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)
            else:
                if g_current_target is not None:
                    time_since_seen = time.time() - g_current_target.get('last_seen', 0)
                    if time_since_seen > 0.5:
                        g_current_target = None
                    else:
                        cx, cy = g_current_target['x'], g_current_target['y']
                        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

        # 3. フレームをJPEGにエンコード
        (flag, encodedImage) = cv2.imencode(".jpg", frame)
        if not flag:
            continue

        # 4. ストリームとして返す
        yield(b'--frame\r\n'
              b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')

        time.sleep(0.01) # 映像ストリームの負荷軽減


# --- Flask Routes (API) ---
@app.route('/api/move_only', methods=['POST'])
def api_move_only():
    """ 新API: アームを動かす指示のみ (ログ記録なし) """
    global task_queue_mp

    data = request.json
    user_angles = data.get('servo_angles', [90] * 6)

    # 1. 制約を適用
    arduino_angles = apply_servo_constraints(user_angles)

    # 2. RealTimeプロセスにコマンドを送信 (キューに入れるだけ)
    try:
        task_queue_mp.put(arduino_angles)
        status_msg = 'ok'
        return_msg = f'Move command sent to queue: {arduino_angles}'
    except Exception as e:
        status_msg = 'error'
        return_msg = f'Failed to send command to queue: {e}'

    # ログ記録は次の専用APIに移譲
    return jsonify({'status': status_msg, 'message': return_msg})


@app.route('/api/snapshot_log', methods=['POST'])
def api_snapshot_log():
    """ 新API: 現在の状態をスナップショットとしてログに記録 """

    # このAPIが呼ばれた時点の最新のユーザー角度を取得
    data = request.json
    user_angles = data.get('user_angles', [90] * 6)

    # 1. 共有リソースから最新の状態を取得
    with g_target_lock:
        target_data = g_current_target.copy() if g_current_target else {}

    ir_raw = ir_value_shared_mp.value
    arduino_angles = apply_servo_constraints(user_angles)

    log_entry = {
        'timestamp': time.time(),
        'user_angles': user_angles,
        'arduino_angles': arduino_angles, # ログ記録時に最終的な物理角度も記録
        'ir_raw': ir_raw,
        'target_detection': target_data,
        'log_type': 'MANUAL_SNAPSHOT'
    }

    # 2. ログをファイルに記録
    try:
        with open('calibration_data_log.jsonl', 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        status_msg = 'ok'
        return_msg = 'Snapshot logged successfully.'
    except Exception as e:
        status_msg = 'error'
        return_msg = f'Log file failed: {e}'
        print(f"[API Log] WARNING: ログファイル書き込みエラー: {e}")

    return jsonify({'status': status_msg, 'message': return_msg, 'log_entry': log_entry})


@app.route('/api/ir_value')
def api_ir_value():
    """ IRセンサー値取得API (共有メモリから読むだけ) """
    ir_value = ir_value_shared_mp.value
    return jsonify({'ir_raw': ir_value})


@app.route('/')
def index():
    """ メインのウェブUIページ """
    return render_template_string(HTML_TEMPLATE)

# --- HTML/GUI テンプレート (★ 完全に修正済み ★) ---
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
                    <p class="text-sm text-red-500 mb-4 font-bold">⚠️ スライダーは物理的可動域に制限されています。</p>

                    <div class="space-y-3" id="servo-controls">

                        <label class="block text-sm font-medium text-gray-700">サーボ0 (グリッパー): <span id="angle-0">180</span>° (可動域: 90-180) (逆)</label>
                        <input type="range" min="90" max="180" value="180" data-servo-id="0" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <label class="block text-sm font-medium text-gray-700">サーボ1 (手首回転): <span id="angle-1">90</span>° (可動域: 0-180)</label>
                        <input type="range" min="0" max="180" value="90" data-servo-id="1" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <label class="block text-sm font-medium text-gray-700">サーボ2 (手首): <span id="angle-2">90</span>° (可動域: 30-180) (逆)</label>
                        <input type="range" min="30" max="180" value="90" data-servo-id="2" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <label class="block text-sm font-medium text-gray-700">サーボ3 (肘): <span id="angle-3">90</span>° (可動域: 90-180) (逆)</label>
                        <input type="range" min="90" max="180" value="90" data-servo-id="3" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <label class="block text-sm font-medium text-gray-700">サーボ4 (肩): <span id="angle-4">90</span>° (可動域: 90-180) (逆)</label>
                        <input type="range" min="90" max="180" value="90" data-servo-id="4" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <label class="block text-sm font-medium text-gray-700">サーボ5 (土台): <span id="angle-5">90</span>° (可動域: 0-180)</label>
                        <input type="range" min="0" max="180" value="90" data-servo-id="5" class="servo-slider w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">

                        <div class="flex space-x-2 mt-4">
                            <button id="send-angles-btn"
                                    class="flex-1 bg-indigo-500 hover:bg-indigo-600 text-white font-bold py-2 px-4 rounded-lg transition duration-150 shadow-md">
                                角度を送信
                            </button>
                            <button id="snapshot-btn"
                                    class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-lg transition duration-150 shadow-md">
                                状態を記録
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
        const snapshotBtn = document.getElementById('snapshot-btn');
        const homeBtn = document.getElementById('set-home-btn');
        const statusDisplay = document.getElementById('control-status');

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

        sliders.forEach(slider => {
            slider.addEventListener('input', (e) => {
                const id = e.target.dataset.servoId;
                document.getElementById(`angle-${id}`).textContent = e.target.value;
            });
        });

        function getServoAngles() {
            return Array.from(sliders).map(slider => parseInt(slider.value));
        }

        async function sendAnglesOnly() {
            const angles = getServoAngles();
            statusDisplay.textContent = 'アームに角度を送信中...';
            statusDisplay.className = 'text-center text-sm mt-2 text-gray-700 font-bold';
            try {
                const response = await fetch('/api/move_only', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ servo_angles: angles })
                });
                const data = await response.json();
                if (data.status === 'ok') {
                    statusDisplay.textContent = `✅ 角度指示キューに送信完了。`;
                    statusDisplay.className = 'text-center text-sm mt-2 text-indigo-600 font-bold';
                } else {
                    statusDisplay.textContent = `⚠️ 送信エラー: ${data.message}`;
                    statusDisplay.className = 'text-center text-sm mt-2 text-red-600 font-bold';
                }
            } catch (error) {
                statusDisplay.textContent = '❌ 通信エラー（アーム）。サーバーを確認してください。';
                statusDisplay.className = 'text-center text-sm mt-2 text-red-600 font-bold';
            }
        }

        async function recordSnapshot() {
            const currentAngles = getServoAngles();
            statusDisplay.textContent = '状態スナップショットを記録中...';
            statusDisplay.className = 'text-center text-sm mt-2 text-gray-700 font-bold';

            try {
                const response = await fetch('/api/snapshot_log', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_angles: currentAngles }) // 現在の角度を記録APIに送る
                });
                const data = await response.json();
                if (data.status === 'ok') {
                    statusDisplay.textContent = `🟢 ログ記録成功！ファイルに状態を保存しました。`;
                    statusDisplay.className = 'text-center text-sm mt-2 text-green-600 font-bold';
                } else {
                    statusDisplay.textContent = `⚠️ ログ記録警告: ${data.message}`;
                    statusDisplay.className = 'text-center text-sm mt-2 text-yellow-600 font-bold';
                }
            } catch (error) {
                statusDisplay.textContent = '❌ 通信エラー（ログ）。サーバーを確認してください。';
                statusDisplay.className = 'text-center text-sm mt-2 text-red-600 font-bold';
            }
        }


        function setHomeAngles() {
            sliders.forEach(slider => {
                const id = slider.dataset.servoId;
                const min = parseInt(slider.min);
                const max = parseInt(slider.max);

                // 90°が可動域内にあるか確認
                let resetValue = 90;
                if (resetValue < min) { resetValue = min; }
                if (resetValue > max) { resetValue = max; }

                slider.value = resetValue;
                document.getElementById(`angle-${id}`).textContent = resetValue;
            });
            sendAnglesOnly();
        }

        sendBtn.addEventListener('click', sendAnglesOnly);
        snapshotBtn.addEventListener('click', recordSnapshot);
        homeBtn.addEventListener('click', setHomeAngles);
    </script>
</body>
</html>
"""

# ==============================================================================
# --- プロセスクラスの定義 ---
# ==============================================================================

class OrchestratorProcess(mp.Process):
    """
    オーケストレータープロセス (頭脳)
    - Flaskサーバー、YOLO推論、カメラ処理を担当
    """
    def __init__(self, task_queue, ir_value_shared):
        super().__init__()
        self.task_queue = task_queue
        self.ir_value_shared = ir_value_shared

    def run(self):
        """ プロセスのメイン実行内容 """
        global yolo_model, task_queue_mp, ir_value_shared_mp

        task_queue_mp = self.task_queue
        ir_value_shared_mp = self.ir_value_shared

        print("[Orchestrator] YOLOv5モデルをロード中...")
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
            print("[Orchestrator] YOLOv5モデル ロード完了。")
        except Exception:
            print("[Orchestrator] [FATAL] YOLOv5モデル ロード失敗:")
            traceback.print_exc()
            return

        print("[Orchestrator] Web GUIを起動します (http://0.0.0.0:5000)...")
        try:
            app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
        except Exception as e:
            print(f"[Orchestrator] [FATAL] Flaskサーバーの起動に失敗: {e}")
