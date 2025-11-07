#!/bin/bash

# このスクリプトは Mac 側で実行し、IRセンサーと6軸制御に必要なファイルをRPi 5に転送します。
# 転送後、Arduinoスケッチをコンパイル・アップロードします。

# --- 🛑 ユーザー設定 (ご自身の環境に合わせてください) ---
REMOTE_USER_HOST="yutoseki@192.168.3.5"
# RPi上のメイン作業ディレクトリ（Pythonスクリプトの実行場所）
REMOTE_WORK_DIR="/home/yutoseki/robot_arm_project"
FQBN="arduino:avr:uno"
ARDUINO_PORT="/dev/ttyACM0"
# -----------------------------------------------------

# --- スクリプトの自己位置特定 (Mac側パス) ---
# このスクリプトのディレクトリパス (setup_programs/test_integrated_sys)
# プロジェクトルートディレクトリのパス (YOLOコードベースの起点)
CWD=$(pwd)

# --- 一時的なビルドディレクトリの設定 (Arduino C++) ---
TEMP_BUILD_DIR="$CWD/temp_integrated_build"
SKETCH_NAME="integrated_control_sketch" # ビルド時のフォルダ名
REMOTE_SKETCH_PATH="$REMOTE_WORK_DIR/$SKETCH_NAME"

# --- 必須ファイルの絶対パス (Mac側) ---
# 1. Arduino C++ スケッチと依存ファイル (統合版を使用)
INO_FILE="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/setup_programs/test_integrated_sys/Integrated_Control.ino"
# Config.hとServoController.h/cppの絶対パスを正確に指定してください。
# ここでは例として、元のパスを仮定します。
CONFIG_FILE="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/Arduino/src/arm/Config.h"
SERVO_CONTROLLER_DIR="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/Arduino/src/arm" # ServoController.h/cppを含むディレクトリ

# 2. Python モジュール群 (最新の統合ファイルを使用)
APP_FILE_SRC="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/setup_programs/test_integrated_sys/app.py"
ARD_COM_FILE_SRC="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/setup_programs/test_integrated_sys/arduino_com.py"
IR_SENSOR_FILE_SRC="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/setup_programs/test_integrated_sys/ir_sensor.py"
CAMERA_MODULE_SRC="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/raspberrypi/src/hardware/camera.py" # (元のパスを維持)
PYTHON_CONFIG_SRC="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/raspberrypi/config.py" # (元のパスを維持)


# --- YOLOv5 パス (変更なし) ---
YOLO_CLONE_SRC="$REMOTE_WORK_DIR/yolov5" # RPi側で利用するパスに合わせて修正。Mac側のパスが必要です。
# Mac側のYOLOv5のローカルクローンディレクトリ
YOLO_CLONE_SRC_MAC="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/yolov5"
YOLO_CLONE_DEST="$REMOTE_WORK_DIR"
YOLO_MODEL_SRC="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/ai-models/object-detection/yolov5/tuned_model/exp3/weights/best.pt"
YOLO_MODEL_DEST="$REMOTE_WORK_DIR/models/best.pt"

# -----------------------------------

set -e # エラーで即停止

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


echo "---"
echo " STEP A: Mac上で一時ビルドディレクトリを作成・準備中..."
rm -rf "$TEMP_BUILD_DIR"
mkdir -p "$TEMP_BUILD_DIR"

# 依存ファイルを確認しながらコピー
if [ ! -f "$CONFIG_FILE" ] || [ ! -f "$INO_FILE" ]; then
    echo "エラー: Arduino Config.h または Integrated_Control.ino が見つかりません。"
    rm -rf "$TEMP_BUILD_DIR"
    exit 1
fi

# Arduino依存ファイルを一時ビルドディレクトリにコピー
cp "$CONFIG_FILE" "$TEMP_BUILD_DIR/"
cp "$INO_FILE" "$TEMP_BUILD_DIR/$SKETCH_NAME.ino"

# ↓ ↓ ↓ 修正部分: ServoControllerをスケッチ直下にコピーする ↓ ↓ ↓
# mkdir -p "$TEMP_BUILD_DIR/ServoController"
# cp "$SERVO_CONTROLLER_DIR/ServoController.h" "$TEMP_BUILD_DIR/ServoController/"
# cp "$SERVO_CONTROLLER_DIR/ServoController.cpp" "$TEMP_BUILD_DIR/ServoController/"

# 【修正後】 サーボコントローラーファイルをスケッチ直下にコピー
cp "$SERVO_CONTROLLER_DIR/ServoController.h" "$TEMP_BUILD_DIR/"
cp "$SERVO_CONTROLLER_DIR/ServoController.cpp" "$TEMP_BUILD_DIR/"
# ↑ ↑ ↑ 修正部分終わり ↑ ↑ ↑

echo "✅ ビルド準備 完了。 ($TEMP_BUILD_DIR)"
echo "---"

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
RSYNC_CMD="sshpass -e ssh $SSH_OPTS"

# ステップ1: ラズパイ側に作業ディレクトリと依存フォルダを作成
echo " STEP 1: RPi側に作業ディレクトリと依存フォルダを作成中..."
# src/hardware と models フォルダを作成
sshpass -e ssh $SSH_OPTS "$REMOTE_USER_HOST" "mkdir -p $REMOTE_WORK_DIR/src/hardware $REMOTE_WORK_DIR/models"
echo "✅ ディレクトリ確認 完了。"

# ステップ2: ファイル転送 (Mac -> RPi)
echo " STEP 2: 全システムファイルをRPiに転送中..."

# 2a. Arduino C++ スケッチ転送 (ServoControllerのサブフォルダも含めて転送)
echo " - Arduino C++ スケッチ転送..."
# この rsync で Config.h, INOファイル, ServoController.h/cpp が RPiの $REMOTE_SKETCH_PATH/ 直下に入る
rsync -avz --delete -e "$RSYNC_CMD" "$TEMP_BUILD_DIR/" "$REMOTE_USER_HOST:$REMOTE_SKETCH_PATH/"

# 2b. Python コアファイル群の転送
REMOTE_HARDWARE_PATH="$REMOTE_WORK_DIR/src/hardware"

echo " - Python コアファイル転送 (src/hardware)..."
# app.py, arduino_com.py, ir_sensor.py, camera.py を src/hardware に転送
rsync -avz -e "$RSYNC_CMD" \
    "$ARD_COM_FILE_SRC" \
    "$IR_SENSOR_FILE_SRC" \
    "$CAMERA_MODULE_SRC" \
    "$REMOTE_USER_HOST:$REMOTE_HARDWARE_PATH/"

echo " - Python メインアプリ (app.py) をルートに転送し、main_full_test.pyとしてリネーム..."
# メインの app.py を RPiの $REMOTE_WORK_DIR/main_full_test.py へ転送
rsync -avz -e "$RSYNC_CMD" "$APP_FILE_SRC" "$REMOTE_USER_HOST:$REMOTE_WORK_DIR/"
sshpass -e ssh $SSH_OPTS "$REMOTE_USER_HOST" "mv $REMOTE_WORK_DIR/app.py $REMOTE_WORK_DIR/main_full_test.py"


echo " - Python 設定ファイル (config.py) 転送..."
rsync -avz -e "$RSYNC_CMD" "$PYTHON_CONFIG_SRC" "$REMOTE_USER_HOST:$REMOTE_WORK_DIR/"

# 2c. YOLOv5 モデルとコードベース転送
echo " - YOLOv5 コードベース転送..."
# /home/yutoseki/robot_arm_project/yolov5 が作成される
sshpass -e ssh $SSH_OPTS "$REMOTE_USER_HOST" "mkdir -p $REMOTE_WORK_DIR/yolov5"
rsync -avz --delete -e "$RSYNC_CMD" "$YOLO_CLONE_SRC_MAC/" "$REMOTE_USER_HOST:$YOLO_CLONE_DEST/yolov5/"

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
echo "次に、SSHでラズパイに接続し、Pythonサーバーを起動してください:"
echo "------------------------------------------------------------------------------------------------"
echo "1. SSH接続: ssh yutoseki@192.168.3.5"
echo "2. フォルダ移動: cd $REMOTE_WORK_DIR"
# このスクリプトの実行後、Pythonファイルが揃った状態でサーバーを起動できます
echo "3. 実行: python3 main_full_test.py"
echo "4. ブラウザアクセス: http://192.168.3.5:5000"
echo "------------------------------------------------------------------------------------------------"
