import os
from flask import Flask, Response, render_template, request, jsonify
from picamera2 import Picamera2
import cv2
import time
import datetime
import threading

app = Flask(__name__)
picam2 = Picamera2()

# プレビュー設定（バッファキュー無効で安定化）
camera_config = picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (640, 480)}, queue=False)
picam2.configure(camera_config)
picam2.start()

# 画像保存用ディレクトリ（スクリプトのある場所のimagesフォルダ）
save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
os.makedirs(save_dir, exist_ok=True)

frame_lock = threading.Lock()

def generate_frames():
    while True:
        with frame_lock:
            frame = picam2.capture_array()
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        ret, jpeg = cv2.imencode(".jpg", frame_bgr)
        if not ret:
            time.sleep(0.1)
            continue
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n\r\n")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/capture_photo", methods=["POST"])
def capture_photo():
    dt_now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = os.path.join(save_dir, f"photo_{dt_now}.jpg")

    def take_photo():
        with frame_lock:
            # 撮影時は一旦停止し高解像度設定に切り替え
            picam2.stop()
            still_config = picam2.create_still_configuration(main={"size": picam2.sensor_resolution}, queue=False)
            picam2.configure(still_config)
            picam2.start()
            picam2.capture_file(filename)
            # プレビュー設定に戻す
            picam2.stop()
            picam2.configure(camera_config)
            picam2.start()

    # 撮影を非同期実行（動画配信を止めない）
    threading.Thread(target=take_photo).start()

    return jsonify({"message": "撮影成功", "filename": filename})

if __name__ == "__main__":
    print("サーバ起動 http://<RPi IP>:8000")
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
