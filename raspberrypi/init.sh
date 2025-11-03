#!/bin/zsh

# プロジェクトのルートディレクトリ
PROJECT_DIR="."

# ディレクトリ構造を作成
mkdir -p "$PROJECT_DIR/models"
mkdir -p "$PROJECT_DIR/src/core"
mkdir -p "$PROJECT_DIR/src/hardware"
mkdir -p "$PROJECT_DIR/src/processing"

# 空のファイルを作成
touch "$PROJECT_DIR/.gitignore"
touch "$PROJECT_DIR/pyproject.toml"
touch "$PROJECT_DIR/README.md"
touch "$PROJECT_DIR/main.py"
touch "$PROJECT_DIR/config.py"
touch "$PROJECT_DIR/models/.gitkeep"
touch "$PROJECT_DIR/src/__init__.py"
touch "$PROJECT_DIR/src/core/__init__.py"
touch "$PROJECT_DIR/src/core/real_time_control.py"
touch "$PROJECT_DIR/src/core/orchestrator.py"
touch "$PROJECT_DIR/src/hardware/__init__.py"
touch "$PROJECT_DIR/src/hardware/arduino_com.py"
touch "$PROJECT_DIR/src/hardware/camera.py"
touch "$PROJECT_DIR/src/hardware/audio.py"
touch "$PROJECT_DIR/src/hardware/ir_sensor.py"
touch "$PROJECT_DIR/src/processing/__init__.py"
touch "$PROJECT_DIR/src/processing/kinematics.py"
touch "$PROJECT_DIR/src/processing/llm_parser.py"

echo "ディレクトリとファイルの作成が完了しました。"
