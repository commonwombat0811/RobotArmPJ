#!/bin/bash

# このスクリプトは Mac 側で実行します。

# --- 🛑 ユーザー設定 (ご自身の環境に合わせてください) ---
REMOTE_USER_HOST="yutoseki@192.168.3.5"
REMOTE_WORK_DIR="/home/yutoseki/arduino_deploy"
FQBN="arduino:avr:uno"
ARDUINO_PORT="/dev/ttyACM0"
# -----------------------------------------------------

# --- スクリプトの自己位置特定 ---
SCRIPT_DIR=$(dirname "$0") # これが /setup_programs/test_servo_180_0 の絶対パスを取得する
CWD=$(pwd) # 実行場所（robot-arm-pj ルート）を取得

# --- 一時的なビルドディレクトリの設定 ---
TEMP_BUILD_DIR="$CWD/temp_arduino_build"
SKETCH_NAME="temp_arduino_build"

# --- 必須ファイルのパス定義 (CWD = robot-arm-pj 直下を基準) ---
INO_FILE="$SCRIPT_DIR/Temp_Servo_Test.ino"
# Config.h, ServoController.cpp/h は robot-arm-pj 直下にあることを仮定
CPP_FILE="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/Arduino/src/arm/ServoController.cpp"
H_FILE="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/Arduino/src/arm/ServoController.h"
CONFIG_FILE="/Users/yutoseki/develop/private-dev/iot-pj/robot-arm-pj/Arduino/src/arm/Config.h"
PYTHON_SCRIPT="$SCRIPT_DIR/test_servo.py"

# --- sshpass の確認 ---
if ! command -v sshpass &> /dev/null; then
    echo "エラー: sshpass が見つかりません。"
    echo "Macのターミナルで 'brew install sshpass' を実行してください。"
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

# 必須ファイルが $CWD にあるか確認しながらコピー
if [ ! -f "$CPP_FILE" ] || [ ! -f "$H_FILE" ] || [ ! -f "$CONFIG_FILE" ]; then
    echo "エラー: ServoController.cpp, ServoController.h, Config.h が"
    echo "現在のディレクトリ ($CWD) に見つかりません。パスを確認してください。"
    rm -rf "$TEMP_BUILD_DIR"
    exit 1
fi
cp "$CPP_FILE" "$TEMP_BUILD_DIR/"
cp "$H_FILE" "$TEMP_BUILD_DIR/"
cp "$CONFIG_FILE" "$TEMP_BUILD_DIR/"
cp "$INO_FILE" "$TEMP_BUILD_DIR/$SKETCH_NAME.ino"

echo "✅ ビルド準備 完了。 ($TEMP_BUILD_DIR)"
echo "---"

# --- リモート側のパス設定 ---
REMOTE_SKETCH_PATH="$REMOTE_WORK_DIR/$SKETCH_NAME"

echo "🎯 ターゲット: $REMOTE_USER_HOST"
echo "📂 ローカルソース: $TEMP_BUILD_DIR (一時ディレクトリ)"
echo "🚢 リモートデプロイ先: $REMOTE_SKETCH_PATH"
echo "---"

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

# ステップ1: ラズパイ側に作業ディレクトリを作成
echo " STEP 1: ラズパイ側に作業ディレクトリを作成中..."
sshpass -e ssh $SSH_OPTS "$REMOTE_USER_HOST" "mkdir -p $REMOTE_WORK_DIR"
echo "✅ ディレクトリ確認 完了。"

# ステップ2: ソースコードの転送 (Mac -> RPi)
echo " STEP 2: スケッチファイル(一時)とPythonスクリプトを転送中..."
RSYNC_CMD="sshpass -e ssh $SSH_OPTS"
rsync -avz --delete -e "$RSYNC_CMD" "$TEMP_BUILD_DIR/" "$REMOTE_USER_HOST:$REMOTE_SKETCH_PATH/"
rsync -avz -e "$RSYNC_CMD" "$PYTHON_SCRIPT" "$REMOTE_USER_HOST:$REMOTE_WORK_DIR/"
echo "✅ 転送 完了。"

# ステップ3: コンパイルとアップロード (RPi上)
echo " STEP 3: ラズパイ上でライブラリインストール、コンパイル＆アップロード開始..."
sshpass -e ssh $SSH_OPTS "$REMOTE_USER_HOST" << EOF
    export PATH="\$PATH:\$HOME/bin"

    # <<< 修正: ライブラリのインストールを追加
    echo "--- Adafruit PWMライブラリをインストール中 ---"
    arduino-cli lib install "Adafruit PWM Servo Driver Library"

    echo "--- コンパイル実行 ($REMOTE_SKETCH_PATH) ---"
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
echo "次に、SSHでラズパイに接続し、以下を実行してください:"
echo "cd $REMOTE_WORK_DIR"
echo "python3 test_servo.py 0 90"
