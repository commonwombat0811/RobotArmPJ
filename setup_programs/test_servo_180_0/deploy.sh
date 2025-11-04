#!/bin/bash
# deploy.sh
# Mac側から実行するデプロイスクリプト

set -e # エラーが発生したら即座に停止

# --- 設定 ---
RPI_USER="yutoseki"
RPI_HOST="sy-pi-5.local" # RPiのIPまたはホスト名
PROJECT_DIR_REMOTE="/home/pi/robot_arm_project" # RPi 5側のパス
PROJECT_DIR_LOCAL="." # このスクリプトがある場所
ARDUINO_SKETCH_DIR="arduino_sketch" # Arduino.ino があるフォルダ
# ------------

echo ">>> [1/3] Mac から RPi 5 へ全ファイルをrsyncで同期中..."

rsync -avz \
  --exclude="venv/" \
  --exclude=".git/" \
  --exclude="*.pyc" \
  --exclude="__pycache__/" \
  "$PROJECT_DIR_LOCAL/" \
  "$RPI_USER@$RPI_HOST:$PROJECT_DIR_REMOTE"

echo ">>> [2/3] RPi 5 にSSH接続してセットアップを実行中..."

# SSH経由で、RPi 5側で実行させたいコマンド群をヒアドキュメントで渡す
ssh "$RPI_USER@$RPI_HOST" << EOF
    set -e # RPi側でもエラーで即停止

    echo "--- RPi 5 側: Python venv をセットアップします ---"
    cd "$PROJECT_DIR_REMOTE"
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install -r requirements.txt --extra-index-url https://www.piwheels.org/simple

    echo "--- RPi 5 側: Arduinoスケッチをコンパイル＆アップロードします ---"
    export PATH="$HOME/bin:$PATH" # arduino-cli のPATH

    # Arduinoが接続されているか確認
    if [ ! -c "/dev/ttyACM0" ]; then
        echo "エラー: Arduinoが /dev/ttyACM0 に見つかりません。"
        exit 1
    fi

    arduino-cli compile --fqbn arduino:avr:uno "$ARDUINO_SKETCH_DIR"
    arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno "$ARDUINO_SKETCH_DIR"

    echo "--- RPi 5 側: デプロイ完了 ---"
EOF

echo ">>> [3/3] デプロイが正常に完了しました。"
echo "RPi 5 にSSH接続し、venvを有効化して python3 main.py を実行してください。"
echo "(例: ssh $RPI_USER@$RPI_HOST)"
echo "(RPi 5側: cd $PROJECT_DIR_REMOTE && source venv/bin/activate && export OPENAI_API_KEY=... && python3 main.py)"
