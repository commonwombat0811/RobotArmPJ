"""
ir_sensor.py
I2C接続の VL53L0X (Time-of-Flight) センサーから距離を読み取る
"""

import board
import busio
import adafruit_vl53l0x
import time

class IRSensor:
    def __init__(self):
        print("[IRSensor] I2CバスとVL53L0Xセンサーを初期化中...")
        try:
            # Raspberry Pi 5 の標準I2Cバス (SDA=GPIO2, SCL=GPIO3) を初期化
            self.i2c = busio.I2C(board.SCL, board.SDA)

            # センサーを初期化
            self.sensor = adafruit_vl53l0x.VL53L0X(self.i2c)

            # オプション: 高精度モードに設定 (速度は少し落ちる)
            self.sensor.measurement_timing_budget = 200000

            print("[IRSensor] VL53L0X センサー初期化完了。")

        except ValueError as e:
            print(f"[IRSensor] Error: I2Cバスの初期化に失敗。{e}")
            print("         (i2c-tools と raspi-config を確認してください)")
            self.sensor = None
        except Exception as e:
            print(f"[IRSensor] Error: VL53L0X センサーが見つかりません: {e}")
            self.sensor = None

    def get_distance_cm(self):
        """
        センサーから距離[cm]を取得する
        @return (float): 距離(cm) or -1.0 (エラー時)
        """
        if self.sensor:
            try:
                # 距離をmm単位で取得
                distance_mm = self.sensor.range

                # mmをcmに変換
                return float(distance_mm) / 10.0
            except RuntimeError as e:
                # センサーがタイムアウトした場合など
                print(f"[IRSensor] Warning: 距離の読み取りに失敗: {e}")
                return -1.0 # エラー値
        else:
            # --- センサー初期化失敗時のフォールバック (ダミー) ---
            # print("[IRSensor] センサー未接続。ダミー値 (20.0cm) を返します。")
            return 20.0
