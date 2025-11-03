
"""
camera.py
OpenCVを使ったカメラ制御クラス。
"""

import cv2
import config

class Camera:
    def __init__(self, camera_id, width, height):
        print(f"[Camera] カメラ {camera_id} を初期化中...")
        self.cap = cv2.VideoCapture(camera_id)

        if not self.cap.isOpened():
            raise IOError(f"カメラ {camera_id} を開けません。")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[Camera] 解像度: {self.width}x{self.height}")

    def get_frame(self):
        ret, frame = self.cap.read()
        return ret, frame

    def release(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()
            print("[Camera] リソースを解放しました。")
