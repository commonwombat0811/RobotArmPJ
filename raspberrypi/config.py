"""
config.py
プロジェクト全体の不変な設定値（定数）を管理します。
"""

import os
import numpy as np

# --- 1. OpenAI API (必須) ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY_HERE")
if OPENAI_API_KEY == "YOUR_API_KEY_HERE":
    print("警告: config.py に OpenAI APIキーが設定されていません。")

# --- 2. Arduino 通信設定 ---
SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200
PACKET_HEADER = 0xFF

# --- 3. ハードウェア設定 (カメラ) ---
CAMERA_ID = 0
CAMERA_RESOLUTION_WIDTH = 640
CAMERA_RESOLUTION_HEIGHT = 480

# --- 4. カメラキャリブレーションパラメータ (最重要) ---
# (これらは使用するレンズに依存する「仮値」。必ずキャリブレーションしてください)
CAMERA_FOCAL_LENGTH_X = 650.0 # X軸の焦点距離 (ピクセル単位)
CAMERA_FOCAL_LENGTH_Y = 650.0 # Y軸の焦点距離 (ピクセル単位)
CAMERA_CENTER_X = CAMERA_RESOLUTION_WIDTH / 2.0
CAMERA_CENTER_Y = CAMERA_RESOLUTION_HEIGHT / 2.0

# ★★★ 要件3対応 (新規追加) ★★★
# カメラ座標系 -> アーム座標系 への変換オフセット
# (アームの土台(0,0,0)から見て、カメラがどこに設置されているか [cm])
# (例: 土台の30cm上、20cm手前、Y軸(左右)は中央)
CAMERA_MOUNT_OFFSET_CM = np.array([
    20.0,  # X (手前/奥)
    0.0,   # Y (左/右)
    30.0   # Z (上/下)
])

# --- 5. AI / 処理設定 ---
# 作業ディレクトリとは異なり、実際に Raspberry Pi 5の方にファイルをマウントするときに関連づけるというか実際に配置をするパスを適切に指定することで対応。
YOLO_MODEL_PATH = "models/best.pt" # (学習済みモデルへのパス)

# --- 6. 音声入力設定 ---
AUDIO_SAMPLE_RATE = 16000 # 16kHz (Whisper推奨)
AUDIO_CHANNELS = 1
AUDIO_SILENCE_THRESHOLD = 0.01
AUDIO_SILENCE_DURATION = 2.0

# --- 7. 逆運動学 (IK) 設定 (要件3対応) ---
# (※あなたのアームの物理的な長さに合わせて変更必須)
ARM_BASE_HEIGHT_CM = 10.0 # 地面からサーボ1(肩)の回転軸までの高さ [cm]
ARM_L1_CM = 15.0  # 肩(サーボ1)から肘(サーボ2)までの長さ [cm]
ARM_L2_CM = 10.0  # 肘(サーボ2)から手首(サーボ3)までの長さ [cm]



# --- 8. アーム制御定数 (Arduino側の定義と一致させる) ---
SERVO_COUNT = 6

# ★★★ あなたの定義 (2025/11/03) に基づいて修正 ★★★
# (PCA9685のピン番号と、アームの関節を一致させます)

SERVO_ID_GRIPPER = 0      # 0番: グリッパー (掴むやつ)
SERVO_ID_SHOULDER = 4     # 4番: 肩
SERVO_ID_ELBOW = 3        # 3番: 肘
SERVO_ID_WRIST = 2        # 2番: 手首
SERVO_ID_BASE = 5         # 5番: 土台 (1番下の横回転)
SERVO_ID_WRIST_ROTATE = 1 # (残りのピン: 1番)

# 待機位置 (全6サーボの角度)
# {0:グリッパー, 1:手首回転, 2:手首, 3:肘, 4:肩, 5:土台} の順番で定義
HOME_POSITION_ANGLES = [
    90,  # 0: グリッパー (開)
    90,  # 1: 手首回転 (中央)
    90,  # 2: 手首 (水平)
    30,  # 3: 肘 (曲げる)
    150, # 4: 肩 (上にあげる)
    90   # 5: 土台 (中央)
]

# ★★★ 要件2対応 (探索ポーズ) ★★★
# (ピン定義に合わせて順番を変更)
SEARCH_POSE_ANGLES = [
    config.HOME_POSITION_ANGLES[SERVO_ID_GRIPPER],      # 0: グリッパー (開)
    config.HOME_POSITION_ANGLES[SERVO_ID_WRIST_ROTATE], # 1: 手首回転 (固定)
    90,                                                 # 2: 手首 (水平)
    90,                                                 # 3: 肘 (90度)
    90,                                                 # 4: 肩 (水平)
    config.HOME_POSITION_ANGLES[SERVO_ID_BASE]          # 5: 土台 (これは探索時に上書き)
]

# グリッパーの角度
GRIPPER_OPEN_ANGLE = 90
GRIPPER_CLOSED_ANGLE = 30

# 「置く」動作の定義 (アーム座標系での X, Y, Z [cm])
PLACE_TARGET_COORDS_ARM = (15.0, 0.0, 5.0) # (X=15cm, Y=0cm, Z=5cm)

# 探索ルーチン (土台サーボ)
SEARCH_RANGE_MIN = 45  # 45度
SEARCH_RANGE_MAX = 135 # 135度
SEARCH_STEP_PER_LOOP = 0.5
