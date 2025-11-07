#!/bin/bash

# このスクリプトは Mac 側で実行し、IRセンサーテストとGUIに必要なファイルをRPi 5に転送します。

# --- 🛑 ユーザー設定 (ご自身の環境に合わせてください) ---
REMOTE_USER_HOST="yutoseki@192.168.3.5"
# RPi上のメイン作業ディレクトリ（Pythonスクリプトの実行場所）
REMOTE_WORK_DIR="/home/yutoseki/robot_arm_project"
FQBN="arduino:avr:uno"
ARDUINO_PORT="/dev/ttyACM0"
# -----------------------------------------------------

# --- スクリプトの自己位置特定 (Mac側パス) ---
# このスクリプトのディレクトリパス: setup_programs/test_irsensor_camera
SCRIPT_DIR=$(dirname "$0")
# プロジェクトルートディレクトリ (robot-arm-pj)
CWD=$(pwd)

# --- 一時的なビルドディレクトリの設定 (Arduino C++) ---
TEMP_BUILD_DIR="$CWD/temp_ir_build"
SKETCH_NAME="temp_ir_build"
REMOTE_SKETCH_PATH="$REMOTE_WORK_DIR/$SKETCH_NAME"

# --- 必須ファイルの絶対パス (Mac側) ---
# 1. Arduino C++ スケッチと依存ファイル
INO_FILE="$SCRIPT_DIR/Temp_IR_Test.ino"
CONFIG_FILE="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/Arduino/src/arm/Config.h"

# 2. Python モジュール群 (Raspberry Piのディレクトリ構造に合わせる)
CAMERA_MODULE_SRC="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/raspberrypi/src/hardware/camera.py"
PYTHON_CONFIG_SRC="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/raspberrypi/config.py"

# --- 追加: YOLOv5 コードベースのパス ---
YOLO_CLONE_SRC="$CWD/yolov5" # Macのrobot-arm-pj/yolov5 (git clone済みであること)
# ★★★ 修正点: 転送先を $REMOTE_WORK_DIR (親フォルダ) に変更 ★★★
YOLO_CLONE_DEST="$REMOTE_WORK_DIR" # RPi上の /home/yutoseki/robot_arm_project/
# -----------------------------------

YOLO_MODEL_SRC="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/ai-models/object-detection/yolov5/tuned_model/exp3/weights/best.pt"
YOLO_MODEL_DEST="$REMOTE_WORK_DIR/models/best.pt"

# --- sshpass の確認 ---
if ! command -v sshpass &> /dev/null; then
    echo "エラー: sshpass が見つかりません。 'brew install sshpass' を実行してください。"
    exit 1
fi

# --- パスワード要求 ---
echo -n "[$REMOTE_USER_HOST] のパスワードを入力: "
read -s SSH_PASSWORD_INPUT
export SSHPASS="$SSH_PASSWORD_INPUT"
echo ""

set -e # エラーで即停止

echo "---"
echo " STEP A: Mac上で一時ビルドディレクトリを作成・準備中..."
rm -rf "$TEMP_BUILD_DIR"
mkdir -p "$TEMP_BUILD_DIR"

# Config.h がローカルに存在するか確認しながらコピー
if [ ! -f "$CONFIG_FILE" ]; then
    echo "エラー: Arduino Config.h が指定された絶対パスに存在しません。"
    rm -rf "$TEMP_BUILD_DIR"
    exit 1
fi
cp "$CONFIG_FILE" "$TEMP_BUILD_DIR/"
cp "$INO_FILE" "$TEMP_BUILD_DIR/$SKETCH_NAME.ino"

echo "✅ ビルド準備 完了。 ($TEMP_BUILD_DIR)"
echo "---"

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
RSYNC_CMD="sshpass -e ssh $SSH_OPTS"
REMOTE_SKETCH_PATH="$REMOTE_WORK_DIR/$SKETCH_NAME"

# ステップ1: ラズパイ側に作業ディレクトリと依存フォルダを作成
echo " STEP 1: RPi側に作業ディレクトリと依存フォルダを作成中..."
# src/hardware と models フォルダを作成
sshpass -e ssh $SSH_OPTS "$REMOTE_USER_HOST" "mkdir -p $REMOTE_WORK_DIR/src/hardware $REMOTE_WORK_DIR/models"
echo "✅ ディレクトリ確認 完了。"

# ステップ2: ファイル転送 (Mac -> RPi)
echo " STEP 2: 全システムファイルをRPiに転送中..."

# 2a. Arduino C++ スケッチ転送
echo " - Arduino C++ スケッチ転送..."
rsync -avz --delete -e "$RSYNC_CMD" "$TEMP_BUILD_DIR/" "$REMOTE_USER_HOST:$REMOTE_SKETCH_PATH/"

# 2b. Python コアファイル群とGUIアプリの転送 (SSH接続をバッチ化)
echo " - Python コアファイル転送 (src/hardware)..."

REMOTE_HARDWARE_PATH="$REMOTE_WORK_DIR/src/hardware" # RPi側の src/hardware ディレクトリ

# 3つのファイルを1回のrsyncで転送
rsync -avz -e "$RSYNC_CMD" \
    "$SCRIPT_DIR/ir_sensor.py" \
    "$SCRIPT_DIR/arduino_com.py" \
    "$CAMERA_MODULE_SRC" \
    "$REMOTE_USER_HOST:$REMOTE_HARDWARE_PATH/"

echo " - Python コアファイル転送 (ルート)..."
# 2つのファイルを1回のrsyncで転送
rsync -avz -e "$RSYNC_CMD" \
    "$PYTHON_CONFIG_SRC" \
    "$SCRIPT_DIR/real_time_gui.py" \
    "$REMOTE_USER_HOST:$REMOTE_WORK_DIR/"

# メインGUIアプリをリネーム
sshpass -e ssh $SSH_OPTS "$REMOTE_USER_HOST" "mv $REMOTE_WORK_DIR/real_time_gui.py $REMOTE_WORK_DIR/main_full_test.py"


# 2c. YOLOv5 モデルとコードベース転送
echo " - YOLOv5 コードベース転送..."
# ★★★ 修正点: $YOLO_CLONE_SRC/ (スラッシュ追加) -> $YOLO_CLONE_DEST/yolov5/ (転送先指定) ★★★
# これで /home/yutoseki/robot_arm_project/yolov5 が作成される
sshpass -e ssh $SSH_OPTS "$REMOTE_USER_HOST" "mkdir -p $REMOTE_WORK_DIR/yolov5"
rsync -avz --delete -e "$RSYNC_CMD" "$YOLO_CLONE_SRC/" "$REMOTE_USER_HOST:$YOLO_CLONE_DEST/yolov5/"

echo " - YOLOv5 モデル (best.pt) 転送..."
rsync -avz -e "$RSYNC_CMD" "$YOLO_MODEL_SRC" "$REMOTE_USER_HOST:$YOLO_MODEL_DEST"

echo "✅ 転送 完了。"


# ステップ3: コンパイルとアップロード (RPi上)
echo " STEP 3: ラズパイ上でコンパイル＆アップロード開始..."
sshpass -e ssh $SSH_OPTS "$REMOTE_USER_HOST" << EOF
    export PATH="\$PATH:\$HOME/bin"

    echo "--- コンパイル実行 ($REMOTE_SKETCH_PATH) ---"
    # Config.h へのパスを通すためにビルドフラグを直接設定
    arduino-cli compile --fqbn $FQBN "$REMOTE_SKETCH_PATH"

    echo "--- アップロード実行 (ポート: $ARDUINO_PORT) ---"
    arduino-cli upload -p $ARDUINO_PORT --fqbn $FQBN "$REMOTE_SKETCH_PATH"

    echo "--- 🚀 アップロード完了 ---"
EOF

# ステップ4: Mac上の一時ファイルをクリーンアップ
echo "---"
echo " STEP 4: Mac上の一時ビルドディレクトリを削除中..."
rm -rf "$TEMP_BUILD_DIR"
echo "✅ クリーンアップ 完了。"

echo -e "\n🎉 全プロセスが正常に完了しました。"
echo "次に、SSHでラズパイに接続し、Python依存をインストールし、サーバーを起動してください:"
echo "------------------------------------------------------------------------------------------------"
echo "1. SSH接続: ssh yutoseki@192.168.3.5"
echo "2. フォルダ移動: cd $REMOTE_WORK_DIR"
echo "3. 依存インストール: pip install Flask pyserial numpy picamera2 ultralytics opencv-python pandas seaborn"
echo "4. 実行: python3 main_full_test.py"
echo "5. ブラウザアクセス: http://192.168.3.5:5000"
echo "------------------------------------------------------------------------------------------------"
```eof
