import io
import os
import cv2
import time
import datetime
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from picamera2 import Picamera2

class CameraHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(INDEX_PAGE.encode('utf-8'))
        elif self.path == '/video_feed':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    with frame_lock:
                        frame = picam2.capture_array()
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    ret, jpeg = cv2.imencode('.jpg', frame_bgr)
                    if not ret:
                        time.sleep(0.1)
                        continue
                    self.wfile.write(b'--frame\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(jpeg.tobytes())))
                    self.end_headers()
                    self.wfile.write(jpeg.tobytes())
                    self.wfile.write(b'\r\n')
                    time.sleep(0.03)  # 約30fps
            except Exception as e:
                print(f"Streaming ended: {e}")
        else:
            self.send_error(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/capture_photo':
            dt_now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = os.path.join(save_dir, f"photo_{dt_now}.jpg")

            def take_photo():
                with frame_lock:
                    # カメラは停止しない。撮影だけcapture_fileで行う。
                    picam2.capture_file(filename)

            threading.Thread(target=take_photo).start()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = f'{{"message": "撮影成功", "filename": "{filename}"}}'
            self.wfile.write(response.encode('utf-8'))
        else:
            self.send_error(404)
            self.end_headers()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

INDEX_PAGE = '''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8" />
    <title>Raspberry Pi カメラ映像</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; }
        img { max-width: 80vw; height: auto; border: 1px solid #333; }
        button { font-size: 16px; padding: 10px 20px; margin-top: 10px; }
    </style>
</head>
<body>
    <h1>ライブカメラ映像</h1>
    <img id="video_feed" src="/video_feed" alt="ライブ映像" />
    <br />
    <button id="capture_btn">写真を撮る</button>
    <p id="message"></p>
    <script>
    const captureBtn = document.getElementById('capture_btn');
    const message = document.getElementById('message');

    captureBtn.onclick = async () => {
        message.textContent = "撮影中...";
        captureBtn.disabled = true;
        try {
            const response = await fetch("/capture_photo", { method: "POST" });
            const result = await response.json();
            if (result.message === "撮影成功") {
                message.textContent = "写真を保存しました: " + result.filename;
            } else {
                message.textContent = "撮影に失敗しました";
            }
        } catch (error) {
            message.textContent = "エラーが発生しました";
        }
        captureBtn.disabled = false;
    };
    </script>
</body>
</html>
'''

save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
os.makedirs(save_dir, exist_ok=True)
frame_lock = threading.Lock()
picam2 = Picamera2()
camera_config = picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (640, 480)}, queue=False)
picam2.configure(camera_config)
picam2.start()

def run(server_class=ThreadedHTTPServer, handler_class=CameraHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'サーバ起動 http://0.0.0.0:{port}')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        picam2.stop()
        print("サーバ停止")

if __name__ == "__main__":
    run()
