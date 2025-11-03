## 環境構築

# RPi 5 ロボットアーム制御システム

これは、Raspberry Pi 5 上で動作する、YOLOv5 と LLM を統合したマルチプロセス・ロボットアーム制御システムです。

## 1. Poetry のインストール

(Raspberry Pi OS 64x 上で実行)

```bash
# pipxを推奨 (なければ `pip install pipx`)
pipx install poetry


## システム設計

### 言語選定

-   AI モデル；リアルタイム物体検出モデル - Yolo v5

-   依存関係管理ツール・環境：poetry

-   OS 環境：Linux ベース debian 系 Raspberry Pi OS

-   サーバ本体：Python multiprocessing を利用。（Flask を立てず、OS レベルでプロセスを分離、クリーンかつ並行性が高い）

懸念点（API の遅延）への回答: Whisper や LLM API の呼び出し（数秒）が、リアルタイム制御（数十ミリ秒）をブロックしないよう、プロセスを完全に分離します。

懸念点（Python の計算速度）への回答: YOLOv5 の推論や逆運動学（IK）の計算は、C/C++で最適化されたライブラリ（ultralytics, numpy）が実行するため、Python 自体の実行速度はボトルネックになりません。

サーバーについての回答: この構成では、HTTP サーバー（Flask/FastAPI）は不要です。main.py が「リアルタイム制御プロセス」と「API 思考プロセス」の 2 つを起動・管理する**「メインランチャー（常駐サービス）」**として機能します。

ツールについての回答: venv + requirements.txt の代わりに、ご提示のあった poetry の使用を強く推奨します。pyproject.toml ファイルを提供します。

```
