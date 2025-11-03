# arduino_com.py
# Arduinoと4バイトバイナリプロトコルで通信します。
# [HEADER, INDEX, ANGLE, CHECKSUM]

import serial
import time
import config

class ArduinoCommunicator:

    def __init__(self, port, baudrate, timeout=1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.header = config.PACKET_HEADER

    def connect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

        self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        print(f"[ArduinoCom] {self.port} 接続待機中 (リセット完了待ち)...")
        time.sleep(2)

        self.ser.flushInput()
        try:
            self.ser.readline()
            self.ser.readline()
            print(f"[ArduinoCom] Arduino Ready.")
        except Exception as e:
            print(f"[ArduinoCom] Warning: ArduinoのReadyメッセージ読み取り失敗: {e}")

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[ArduinoCom] 接続を切断しました。")

    def _calculate_checksum(self, header, index, angle):
        return (header + index + angle) & 0xFF

    def send_command(self, servo_index, angle):
        if not self.ser or not self.ser.is_open:
            print("[ArduinoCom] Error: Arduinoが接続されていません。")
            return False

        index_byte = int(servo_index) & 0xFF
        angle_byte = int(angle) & 0xFF

        if index_byte != servo_index or servo_index >= 6: # SERVO_COUNT (config.pyに持たせるべき)
            print(f"[ArduinoCom] Error: 無効なサーボ番号 {servo_index}")
            return False
        if angle_byte != angle or angle > 180:
            print(f"[ArduinoCom] Error: 無効な角度 {angle}")
            return False

        checksum = self._calculate_checksum(self.header, index_byte, angle_byte)
        packet = bytes([self.header, index_byte, angle_byte, checksum])

        try:
            self.ser.write(packet)

            # リアルタイム制御では、応答待ちは「遅延」になるため
            # 応答を待たない (Fire and Forget) か、
            # 非常に短いタイムアウトで読み捨てるのが望ましい
            # response = self.ser.readline().decode('utf-8').strip()
            # if response != "OK":
            #    print(f"[ArduinoCom] Error: Arduinoがエラーを返しました: {response}")
            #    return False

            return True # 送信成功 (応答は確認しない)

        except serial.SerialException as e:
            print(f"[ArduinoCom] Error: シリアル通信エラー: {e}")
            return False

