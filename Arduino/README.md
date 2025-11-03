## プロジェクトとしての制約

-   本ファイルがあるディレクトリが Arduino のビルドルートとなるため、.ino ファイル群はここに配置する必要がある。

-   ルール: .ino ファイルはスケッチフォルダ直下に置くこと

-   管理の関係から、.cpp, .h ファイルは s（スケッチフォルダ）/src/\*に配置し管理する。

.ino ファイル結合仕様
Arduino IDE や Arduino CLI は、スケッチフォルダ内のすべての.ino ファイルを単一の.cpp ファイルに変換・結合してからビルドを行います。
結合順序は、概ね以下のルールに基づきます（詳細はバージョンごとに異なる面もあるが）：

スケッチフォルダ名と同じ名前のメイン.ino ファイルが先頭。

残りの.ino ファイルはアルファベット順で結合されることが多い。

ただし、関数のプロトタイプは自動生成されるため、関数定義の順番に細かな影響は少ない。

コンパイラの実行制限ではない
この仕様はコンパイラ自体の制限ではなく、Arduino のビルドシステム（変換＆結合ツール）の設計によるものです。
GCC などの C++コンパイラは複数の.cpp/.h ファイルを正しくリンクする機能を持っていますが、Arduino IDE は.ino ファイルを一つの cpp に変換する工程を挟むため、この結合動作になります。

影響

ファイル間の依存順序をファイル名で管理しないと宣言の前後関係でエラーが起きることがある。

.ino ファイルは同一名前空間にすべて統合されるため、グローバル名の衝突に注意必要。

複数.ino よりは.cpp/.h でモジュール管理するほうが推奨される。

## Setup

-   project setting up command ー
    ```shell
    arduino-cli init
    ```

## 基本的な Arduino 知識確認

-   ボード：電子回路が組み込まれた基盤（ハードウェア）、マイクロコントローラー（マイコン）を搭載。センサーやモーターなどの外部電子機器と接続し、プログラムによって制御。例： Arduino Uno 等

## プロジェクト管理方式

### Arduino の言語仕様

-   C++ ベースの oop ライクな開発環境を提供

### 開発方針・環境管理方式

-   OOP ベースでの開発、モジュール管理方式を採用

## クリーンアーキテクチャ的設計適用

### 層構造（分割案）

-   エントリ層（.ino）：setup()/loop()のみ

-   インターフェース層：抽象クラス。依存逆転

-   ユースケース/ビジネスロジック層：機能毎のクラス（ArmController, SensorManager…）

-   データアクセス/抽象化層：ハード依存の IO 処理をクラス内に隠蔽（Serial, I2C, SPI など）

### 疎結合実現ポイント

-   クラス化＋ interface 化（例：IArmControl 純粋仮想クラス）

-   依存クラスのインスタンス生成時に引数で注入

-   #include、インスタンス隔離で再利用性 up

### サンプルコードと疎結合性についてのメモ説明

```cpp

// src/IArmController.h
class IArmController {
public:
  virtual void moveAxis(int axis, int pos) = 0;
  virtual ~IArmController() {};
};
// src/ArmController.h / ArmController.cpp
#include "IArmController.h"
class ArmController : public IArmController {
  // 実装詳細
};

```
