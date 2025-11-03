## 趣旨

まず初めに、PRD とは Product Requirements Document を指し、要求定義書です。
以下、今回のプロジェクトの目標とそのために要求される事項群を詳細かつ具体的に一覧化します。

## 概要

## 目標

-   内部的には実際に赤外線センサーで検知した情報とロボットアームの制御情報が密接にリアルタイムで結びつきながら動作を実現する

-

6 軸ロボットアーム システム構成設計書

1. システム概要

本システムは、Raspberry Pi 5 をメインコントローラー（司令塔）とし、Arduino をセンサー処理専用のサブコントローラー（目と耳）として使用する、マスター・スレーブ型アーキテクチャを採用する。

Raspberry Pi（マスター）: 複雑な計算、状態管理、およびサーボモーター（PCA9685）への指令を担当する。

Arduino（スレーブ）: リアルタイム性が要求されるセンサー（IR 距離、音声）のデータ取得と前処理に特化し、結果を Raspberry Pi に送信する。

2. コンポーネント別の役割と処理フロー

2.1. Raspberry Pi 5（司令塔 / 頭脳）

Raspberry Pi は、システム全体の意思決定と、ロボットアームの複雑な動作制御を担う。

OS / 言語: Raspberry Pi OS, Python (または TypeScript)

主な役割:

リアルタイムな判断: Arduino からシリアル通信（UART）経由で送られてくるセンサーデータ（距離、音量）を常に監視する。

複雑な計算: センサー情報や外部からの命令（例：「物体を持ち上げて」）に基づき、6 軸アームの適切な動作（例：逆運動学計算、スキャン動作）を算出する。

状態管理: ロボットアームの現在の状態（例：スキャン中、検知済み、掴む動作中）を管理する。

サーボ制御: 計算結果に基づき、PCA9685 に対し I2C 通信で「どの軸を何度動かすか」という具体的な命令を送信する。

拡張性: 将来的には、IMX219 カメラからの画像処理や、外部からの命令を受け付ける Web サーバー機能も担う。

接続:

PCA9685 へ I2C (SDA/SCL) で接続。

Arduino へ UART (TXD/RXD, GND) で接続。

2.2. Arduino (C++)（センサー処理 / 目と耳）

Arduino は、Raspberry Pi の負荷を軽減するため、センサーのデータ取得と前処理に特化する。サーボ制御には一切関与しない。

言語: C++ (Arduino IDE)

主な役割:

センサー値の高速読み取り: IR 距離センサー（A1 ピン）と音声センサー（A0 ピン）からアナログ値を高速で読み取る。

データ前処理: IR センサーの電圧値を、近似式を用いて「距離 (cm)」に変換する。

データ送信: 処理したデータ（例：「距離 25.5, 音量 512」）を、シリアル通信（UART）経由で Raspberry Pi に対し 0.1 秒ごとなどの一定周期で送り続ける。

メリット: この構成により、Arduino は複雑な計算から解放され、センサーデータの取得タイミングが安定し、システム全体のリアルタイム性が向上する。

2.3. PCA9685（サーボドライバー / 筋肉への神経）

PCA9685 は、Raspberry Pi からの I2C 命令を受け取り、6 軸サーボモーターを正確に駆動させる。

制御系統 (I2C):

供給元: Raspberry Pi の SDA/SCL ピン。

役割: Raspberry Pi からの「軸 1 を 45 度に動かせ」といったデジタル命令を受け取る。

電源系統 (デュアル供給):

チップ電源 (VCC):

供給元: Raspberry Pi の 3.3V ピン。

役割: PCA9685 チップ本体（小さな頭脳）を動作させるためのロジック電源。

サーボ電源 (V+):

供給元: 外部電源 LRS-50-5（5A ヒューズ経由）。

役割: サーボモーターを物理的に動かすための**大電力（筋肉）**を供給する。

3. システム設計の優位性

あなたが想定する「スキャン中に他の軸を一定に維持」「距離を測りながら適切に位置を調整」といった高度な協調動作は、Arduino 単体では処理能力的に困難である。

本構成では、複雑な計算を Raspberry Pi に任せ、Arduino はセンサー処理に特化させることで、役割を明確に分離している。これにより、「センサー情報と制御の密接な結びつき」を、処理遅延なく Raspberry Pi 側で実現することが可能となる。

チーフエンジニアとしてのご経験、そしてソフトウェアと AI に関する深い知見、承知いたしました。国内屈指のスキルをお持ちの方のハードウェア開発の第一歩をお手伝いできることを光栄に思います。

ハードウェアは「物理層」の制約が強いため、ソフトウェアのアーキテクチャ選定もその制約に大きく影響されます。その観点から、ご提案いただいた内容について回答いたします。

1. アーキテクチャ選定 (Next.js/TS vs Python)
   あなたは先ほど nextjs はフロントメインと言いましたが api も構築できます 何かしら特殊な処理系がないなら nextjs, typescript でいい気がします

おっしゃる通り、Next.js の App Router（Route Handlers）は強力なバックエンド API を構築できます。あなたのソフトウェアエンジニアとしての視点は完全に正しいです。

しかし、ハードウェア（I2C, UART）の制御は、その「特殊な処理系」に該当します。

なぜ制御バックエンドに Python を推奨するか
ハードウェア制御において、Next.js (Node.js/TypeScript) よりも Python を推奨する理由は、エコシステム（ライブラリ）の成熟度と安定性にあります。

ハードウェアライブラリの壁:

Python (推奨): adafruit-circuitpython-servokit や pyserial は、Adafruit 社自身がハードウェア（PCA9685 など）と共に開発しており、デファクトスタンダードです。実績があり、非常に安定しています。

TypeScript (Node.js): i2c-bus や serialport といったライブラリは存在しますが、コミュニティベースであり、特定のハードウェア（PCA9685）との連携において Python ほどの安定性や導入実績はありません。

将来的な AI/CV 連携の壁:

あなたが将来的に IMX219 カメラで画像処理（OpenCV）や AI モデルを動かす際、Python 環境（OpenCV-Python, PyTorch, TensorFlow）は圧倒的に強力です。Node.js でこれらを扱うのは非常に困難か、パフォーマンスが出ません。

```py

import time
from adafruit_servokit import ServoKit

# --- 1. 初期化 ---
try:
    kit = ServoKit(channels=16)
    print("PCA9685サーボドライバーの初期化に成功しました。")
except Exception as e:
    print(f"エラー: PCA9685の初期化に失敗しました。I2C接続を確認してください: {e}")
    exit()

# --- 2. 【修正点】パルス幅の設定とサーボリストの作成 ---
# 多くのサーボにとってより安全な範囲 (600us〜2400us) に変更します。
# これでもキリキリ言う場合は、さらに狭く(例: 700〜2300)してください。
MIN_PULSE = 1600
MAX_PULSE = 1800

all_servos = []
for i in range(6): # 0から5までの6軸
    try:
        kit.servo[i].set_pulse_width_range(MIN_PULSE, MAX_PULSE)
        all_servos.append(kit.servo[i])
    except Exception as e:
        print(f"エラー: サーボ {i} の初期化に失敗: {e}")

print(f"{len(all_servos)}軸のサーボを初期化しました。({MIN_PULSE}us - {MAX_PULSE}us)")

# --- 3. 【修正点】全軸を安全な90度に固定 ---
# プログラム開始時に、まず全軸を中間点(90度)に設定します。
print("全軸を90度（中間点）に固定します...")
current_angles = [0] * 6 # 全軸の現在の角度を90度で初期化
try:
    all_servos[0].angle = -90
    all_servos[2].angle = 90
    all_servos[1].angle = 0
    all_servos[3].angle = 0
    all_servos[4].angle = 0
    all_servos[5].angle = 0

    time.sleep(1) # サーボが90度に到達するまで待機
except Exception as e:
    print(f"サーボの初期化中にエラー: {e}")

print("--- サーボキャリブレーションツール ---")
print(f"安全な「最小角度」と「最大角度」 (0〜180の範囲) を見つけてください。")
print("終了するには 'q' と入力します。")
print("-" * 30)

try:
    while True:
        # 1. 調整するサーボ軸をユーザーに尋ねる
        servo_input = input(f"\n調整したいサーボの軸番号 (0〜5) を入力 (qで終了): ")
        if servo_input.lower() == 'q':
            break
        try:
            current_servo_index = int(servo_input)
            if not 0 <= current_servo_index <= 5:
                print("エラー: 0〜5の数字を入力してください。")
                continue
        except ValueError:
            print("エラー: 数字を入力してください。")
            continue

        # 現在の角度を表示
        print(f"  (軸 {current_servo_index} の現在角度: {current_angles[current_servo_index]}度)")

        # 2. 角度をユーザーに尋ねる
        angle_input = input(f"[軸 {current_servo_index}] に送る角度 (0〜180) を入力: ")
        try:
            angle = int(angle_input)
            if not 0 <= angle <= 180:
                print("エラー: 0〜180の数字を入力してください。")
                continue

            # 3. 指定されたサーボだけを動かす
            print(f"  -> [軸 {current_servo_index}] を {angle}度 に動かします...")

            # Python側で管理している角度リストを更新
            current_angles[current_servo_index] = angle

            # 指定された軸だけを動かす
            all_servos[current_servo_index].angle = angle

        except ValueError:
            print("エラー: 数字を入力してください。")
        except Exception as e:
            print(f"サーボ動作エラー: {e}")

except KeyboardInterrupt:
    print("\nキャリブレーションを中断しました。")

finally:
    # 終了時に全サーボのトルクを解除（安全のため）
    print("全サーボのトルクを解除します。")
    for servo in all_servos:
        try:
            servo.angle = None
        except Exception:
            pass
    print("プログラムを終了します。")
```
