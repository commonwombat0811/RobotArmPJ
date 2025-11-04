"""
camera.py
Raspberry Pi 5 (libcamera) ネイティブ対応版。
picamera2ライブラリを使用してカメラを制御します。
OpenCVのVideoCapture(V4L2)は使用しません。
"""

import cv2
import time
from picamera2 import Picamera2

class Camera:
    def __init__(self, camera_id, width, height):
        # camera_id は picamera2 では 0, 1... で指定する
        print(f"[Camera] Picamera2 (libcamera) を初期化中 (ID: {camera_id})...")
        self.picam2 = Picamera2(camera_id)

        # プレビュー設定（リアルタイム処理用）
        # XRGB8888 はNumpy配列に最速で変換できるフォーマット
        config = self.picam2.create_preview_configuration(
            main={"format": 'XRGB8888', "size": (width, height)},
            queue=False # 低遅延モード
        )
        self.picam2.configure(config)

        # センサー解像度を取得して設定が反映されたか確認
        # (picamera2ではsetとgetが分離していない)
        self.width = int(self.picam2.camera_controls['ScalerCrop'][2])
        self.height = int(self.picam2.camera_controls['ScalerCrop'][3])

        if self.width != width or self.height != height:
             print(f"[Camera] 警告: 要求解像度 {width}x{height} と異なります。")
             print(f"[Camera] センサークロップ: {self.width}x{self.height}")

        self.picam2.start()
        print(f"[Camera] プレビューストリーム開始。解像度: {self.width}x{self.height}")
        # 起動直後は不安定なため少し待つ
        time.sleep(0.5)

    def get_frame(self):
        """
        picamera2からフレームを取得し、OpenCV (BGR) 形式のNumpy配列で返す
        """
        try:
            # capture_array() は "main" ストリームからRGB配列を取得する
            frame_rgb = self.picam2.capture_array("main")

            # YOLO (OpenCV) は BGR 形式を期待するので変換する
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

            return True, frame_bgr

        except Exception as e:
            print(f"[Camera] Error: フレームのキャプチャに失敗: {e}")
            return False, None

    def release(self):
        """
        カメラを停止し、リソースを解放する
        """
        if self.picam2:
            self.picam2.stop()
            self.picam2.close()
            print("[Camera] Picamera2 リソースを解放しました。")
            self.picam2 = None
