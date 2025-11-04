#!/bin/bash

# このスクリプトは Mac 側で実行します。
# VSCodeのターミナルから ./deploy_to_uno.sh で実行してください。

# --- 🛑 ユーザー設定 (ご自身の環境に合わせてください) ---

# 1. ラズパイのSSH接続情報 (例: pi@raspberrypi.local)
REMOTE_USER_HOST="yutoseki@sy-pi-5.local"

# 2. Mac上のスケッチディレクトリのパス (このスクリプトからの相対パスも可)
#    (Temp_Servo_Test.ino や ServoController.cpp が入っているフォルダ)
LOCAL_SKETCH_DIR="./Temp_Servo_Test"

# 3. ラズパイ上の作業ディレクトリ (ここにスケッチが転送されます)
REMOTE_WORK_DIR="/home/pi/arduino_deploy"

# 4. Arduino Uno の設定
FQBN="arduino:avr:uno"         # Unoのボード定義
ARDUINO_PORT="/dev/ttyACM0"    # ラズパイがUnoを認識しているポート
# -----------------------------------------------------

set -e # エラーが発生したら即座に停止

# スケッチ名（ディレクトリ名）を抽出
SKETCH_NAME=$(basename "$LOCAL_SKETCH_DIR")
REMOTE_SKETCH_PATH="$REMOTE_WORK_DIR/$SKETCH_NAME"

echo "🎯 ターゲット: $REMOTE_USER_HOST"
echo "📂 ローカルソース: $LOCAL_SKETCH_DIR"
echo "🚢 リモートデプロイ先: $REMOTE_SKETCH_PATH"
echo "---"

# ステップ1: ラズパイ側の環境構築 (初回のみ時間がかかります)
echo " STEP 1: ラズパイ側の arduino-cli 環境を確認中..."
ssh "$REMOTE_USER_HOST" "mkdir -p $REMOTE_WORK_DIR"
ssh -t "$REMOTE_USER_HOST" << EOF
    # arduino-cli がインストールされているか確認
    if ! command -v arduino-cli &> /dev/null; then
        echo " arduino-cli が見つかりません。インストールします..."
        curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR=~/bin sh
        echo 'export PATH="\$PATH:\$HOME/bin"' >> ~/.bashrc
        echo " PATHを通しました。新しいターミナルで有効になります。"
        echo " スクリプトを再実行してください。"
        exit 1
    fi

    # AVRコア (Uno用) がインストールされているか確認
    if ! arduino-cli core list | grep "arduino:avr" &> /dev/null; then
        echo " arduino:avr コアが見つかりません。インストールします..."
        arduino-cli core update-index
        arduino-cli core install arduino:avr
    else
        echo " arduino:avr コアは導入済みです。"
    fi
EOF
echo "✅ 環境確認 完了。"


# ステップ2: ソースコードの転送 (Mac -> RPi)
echo " STEP 2: スケッチファイルを転送中..."
# rsync を使い、変更があったファイルだけ効率的に同期します
rsync -avz --delete "$LOCAL_SKETCH_DIR/" "$REMOTE_USER_HOST:$REMOTE_SKETCH_PATH/"
echo "✅ 転送 完了。"


# ステップ3: コンパイルとアップロード (RPi上)
echo " STEP 3: ラズパイ上でコンパイル＆アップロード開始..."
# -t オプションは、シリアルポートへのアクセス(upload)にほぼ必須です
ssh -t "$REMOTE_USER_HOST" << EOF
    echo "--- コンパイル実行 ---"
    arduino-cli compile --fqbn $FQBN "$REMOTE_SKETCH_PATH"

    echo "--- アップロード実行 (ポート: $ARDUINO_PORT) ---"
    arduino-cli upload -p $ARDUINO_PORT --fqbn $FQBN "$REMOTE_SKETCH_PATH"

    echo "--- 🚀 アップロード完了 ---"
EOF

echo -e "\n🎉 全プロセスが正常に完了しました。"
