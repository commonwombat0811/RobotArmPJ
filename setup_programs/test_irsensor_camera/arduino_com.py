import serial
import time
import struct
import config
from typing import List

# --- Arduinoとの通信プロトコル定義 ---
START_BYTE = config.PACKET_HEADER
CMD_SET_ANGLE = 0x01
# CMD_GET_IR_SENSOR は ir_sensor.py で定義

class ArduinoCom:
    """
    Arduinoとのシリアル通信を管理し、コマンドを送信するクラス
    """
    def __init__(self, port, baud_rate):
        self.port = port
        self.baud_rate = baud_rate
        self.ser = None
        self.is_ready = False

    def open_and_wait_for_ready(self):
        """
        ポートを開き、不安定なリセットを回避し、Arduinoからの 'Ready.' 信号を待機する。
        """
        if self.is_ready:
            return True

        print(f"[ArduinoCom] ポート {self.port} 接続シーケンス開始...")

        # 1. リセット信号だけ送ってすぐに閉じる (DTRリセット回避)
        try:
            temp_ser = serial.Serial(self.port, self.baud_rate, timeout=0.1)
            temp_ser.close()
        except serial.SerialException as e:
            print(f"[ArduinoCom] エラー: 初期リセットポートオープン失敗: {e}")
            return False

        time.sleep(5) # Arduinoがリセットから回復するのを待つ

        # 2. ポートを再度開き、Ready信号を待機
        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=15)
            self.ser.flushInput()

            ready = False
            start_time = time.time()
            self.ser.timeout = 0.5

            while time.time() - start_time < 15:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()

                if "Ready." in line:
                    ready = True
                    print(f"[ArduinoCom] 接続確立: {line}")
                    break

                if line:
                    print(f"[ArduinoCom] 起動ログ: {line}")

                time.sleep(0.1)

            if not ready:
                print("[ArduinoCom] エラー: 'Ready.' 信号を15秒以内に受信できませんでした。")
                self.ser.close()
                self.ser = None
                return False

            self.is_ready = True
            return True

        except serial.SerialException as e:
            print(f"[ArduinoCom] エラー: ポート再オープン失敗または通信エラー: {e}")
            return False

    def send_servo_command(self, servo_index: int, angle: int) -> bool:
        """
        単一のサーボ角度コマンドを送信し、Arduinoの実行応答を待つ。
        """
        if not self.ser or not self.is_ready:
            print("[ArduinoCom] エラー: 通信が確立されていません。")
            return False

        # サーボの角度をトリムする（オプション、ここでは直接送信）
        angle = max(0, min(180, angle))

        packet = struct.pack(
            '<BBBB',
            START_BYTE,
            CMD_SET_ANGLE,
            servo_index,
            angle
        )

        try:
            self.ser.flushInput()
            self.ser.write(packet)

            # Arduinoからの実行応答を待つ
            self.ser.timeout = 1
            response = self.ser.readline().decode('utf-8').strip()

            if response.startswith(f"Executing: Servo {servo_index}"):
                print(f"[ArduinoCom] 実行完了: {response}")
                return True
            else:
                print(f"[ArduinoCom] 警告: 予期せぬ応答: {response}")
                return False

        except Exception as e:
            print(f"[ArduinoCom] 送信エラー: {e}")
            return False

    def close(self):
        if self.ser:
            self.ser.close()
            self.is_ready = False
            print("[ArduinoCom] シリアルポートを閉じました。")
