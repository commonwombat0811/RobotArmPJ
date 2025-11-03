### VSCode setting up

-   install the extensions below:

    -   Arduino Community Edition (published by vscode-arduino)

    -   arduino-snippets (published by Ronaldo Sena)

### ディレクトリ構造

-   概要: 内部的な処理は cpp ファイルに分離して、ハードウェアとの通信先の指定とか繋ぎとかあとはどの cpp ファイルないしクラスに処理を渡し、その結果をどこに返すかとかは ino ファイルで実装。イメージとして、メインの .ino が システム内 2 段階コントローラ層の上位のハンドラないしコントローラで、その下に下位のハンドラとしてその下の各個別の制御コントローラを配置、実質的な処理はその依存先の cpp ファイルとして実装管理。

-   ディレクトリ構造サンプル From AI（NOTE：品質と開発管理の関係から、本体の設計実装は自分で行う。あくまで参考用として。）

```text
MyArduinoProject/                   ← プロジェクトルート（スケッチフォルダかつVSCodeワークスペースルート）
│
├── .vscode/                       ← VSCode固有の設定フォルダ。自動生成されることが多い
│   ├── arduino.json               ← Arduino拡張用設定ファイル（ボード種類、COMポート、スケッチファイル指定など）
│   ├── c_cpp_properties.json     ← IntelliSenseや補完用のincludeパス設定ファイル
│   ├── settings.json             ← VSCodeのエディター固有設定ファイル
│   └── tasks.json                ← VSCodeのビルド・アップロードタスクの定義（任意）
│
├── MyArduinoProject.ino           ← メインスケッチファイル（必ずフォルダ名と同じ名前）
├── A_RobotArm.ino                 ← 上位のオーケストレータ的な.inoファイル。init, control呼び出し
├── B_InfraredSensor.ino           ← 赤外線センサの関連処理呼び出しとextern変数宣言など
├── C_CameraModule.ino             ← カメラ関連機能の初期化・制御呼び出し
├── D_VoiceInput.ino               ← 音声入力関連の初期化・処理呼び出し
│
├── src/                          ← 実処理を実装したcpp/hファイル群を置くディレクトリ
│   ├── RobotArm.h
│   ├── RobotArm.cpp
│   ├── InfraredSensor.h
│   ├── InfraredSensor.cpp
│   ├── CameraModule.h
│   ├── CameraModule.cpp
│   ├── VoiceInput.h
│   ├── VoiceInput.cpp
│   ├── Utils.h                   ← 共通ヘルパー関数
│   └── Utils.cpp
│
├── lib/                          ← 外部ライブラリや独立ライブラリ用フォルダ（存在しない場合も可）
│
├── README.md                     ← プロジェクト説明・ドキュメント
├── arduino-cli.yaml              ← Arduino CLI用設定ファイル（ボード種別やビルドオプション記述）
├── platformio.ini                ← PlatformIO使う場合の設定ファイル（使用しないなら不要）
└── .gitignore                    ← Git管理ファイル（必要なら）
```

### NOTE: AI（モデル：felo）の調査および推論による結果を添付

arduino-cli init コマンドは存在しないため、arduino-cli config init を使用して設定を初期化する必要があります。このコマンドは、Arduino CLI の設定ファイルを生成または更新し、グローバルな環境に影響を与える可能性があります。以下に、config init コマンドがどのような設定を行うのか、具体的に説明します。
設定ファイルの生成
arduino-cli config init を実行すると、以下のような設定が行われます：

-   設定ファイルの作成:
-   デフォルトでは、~/.arduino15/arduino-cli.yaml という YAML 形式の設定ファイルが生成されます。このファイルには、Arduino CLI の動作に関する設定が保存されます。
-   設定内容の分類: 設定ファイルには、以下のようなセクションが含まれます。
-   board_manager:
-   additional_urls: ボードマネージャーに追加の URL を指定するためのリスト。これにより、特定のボードやライブラリをインストールするためのリポジトリを追加できます。
-   directories:
-   data: ボードやライブラリのインデックスファイルを保存するディレクトリ。
-   downloads: ダウンロードしたアーカイブを一時的に保存するディレクトリ。
-   user: スケッチブックのディレクトリ。ライブラリマネージャーによるインストールはこのディレクトリ内の libraries サブディレクトリに行われます。
-   logging:
-   file: ログファイルの保存先。
-   level: ログの出力レベル（例: info, debug, error など）。
-   locale:
-   CLI が使用する言語設定。
-   updater:
-   enable_notification: 新しい Arduino CLI リリースの通知を有効または無効にする設定。
    グローバル環境への影響
    arduino-cli config init を実行することで、以下のような影響が考えられます：
-   設定の上書き:
-   既存の設定ファイルがある場合、--overwrite オプションを指定すると、その内容が上書きされます。これにより、以前の設定が失われる可能性があります。
-   環境変数の影響:
-   コマンドラインフラグや環境変数で設定したオプションが優先されるため、これらの設定が CLI の動作に影響を与えることがあります。
-   プロジェクトの初期化:
-   config init はプロジェクトの初期化を自動的には行いません。プロジェクトのディレクトリ構造やスケッチファイルは手動で設定する必要があります。
    具体的な設定例
    以下は、arduino-cli config init を使用して生成される設定ファイルの一例です：
    board_manager:
    additional_urls:

*   https://example.com/package_index.json
    directories:
    data: /home/user/.arduino15
    downloads: /home/user/Downloads
    user: /home/user/Arduino
    logging:
    file: /home/user/arduino-cli.log
    level: info
    locale: en_US
    updater:
    enable_notification: true
    このように、arduino-cli config init は Arduino CLI の動作に必要な設定を整備し、ユーザーが必要に応じてカスタマイズできるようにします。設定ファイルを適切に管理することで、CLI の動作を自分の環境に最適化することが可能です。
