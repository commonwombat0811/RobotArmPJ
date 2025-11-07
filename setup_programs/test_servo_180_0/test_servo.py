import serial
import time
import struct
import sys

# Arduinoが接続されているシリアルポート
# RPi 5の場合、/dev/ttyACM0 や /dev/ttyUSB0 の可能性が高い
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 115200 # ArduinoのConfig.hで設定した値に合わせる

# --- 送信するコマンドの定義 ---
# 1. 同期用のスタートバイト (常に 0xFF)
START_BYTE = 0xFF
# 2. コマンドの種類 (例: 0x01 = 角度設定)
CMD_SET_ANGLE = 0x01

def send_servo_command(ser, servo_index, angle):
    """
    サーボに角度コマンドを送信する
    プロトコル: [START_BYTE, CMD_SET_ANGLE, servo_index, angle] (計4バイト)
    """
    print(f"Sending command: Servo {servo_index} to {angle} degrees")

    # データを4バイトのバイナリとしてパックする
    # B = 符号なし1バイト整数
    packet = struct.pack(
        '<BBBB',
        START_BYTE,
        CMD_SET_ANGLE,
        int(servo_index),
        int(angle)
    )

    ser.write(packet)

def main():
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <servo_index> <angle>")
        print("Example: python test_servo.py 0 90")
        return

    servo_index = int(sys.argv[1])
    angle = int(sys.argv[2])

    if not (0 <= angle <= 180):
        print("Error: Angle must be between 0 and 180")
        return

    if not (0 <= servo_index < 16): # PCA9685は最大16
        print("Error: Servo index must be between 0 and 15")
        return

    try:
        # --- 1. ポートを一度開けて閉じ、リセット信号だけ送ってArduinoに起動時間を与える ---
        try:
            # ポートを開くとArduinoにリセットがかかる
            temp_ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
            temp_ser.close()
            print(f"Port {SERIAL_PORT} reset signal sent.")
        except serial.SerialException:
            # ポートが開けなかった場合はここでエラーを出力
            print(f"Error: Could not open port {SERIAL_PORT} for initial reset. Check connection.")
            return

        # 2. Arduinoがリセットから確実に回復するのを待つ（5秒に延長）
        time.sleep(5)

        # 3. 再びポートを開き、通信を確立する
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=15) as ser:
            print(f"Serial port {SERIAL_PORT} successfully re-opened at {BAUD_RATE} bps.")

            # --- Arduinoの「Ready」信号を待機ロジック ---
            ser.timeout = 0.5 # 読み込みタイムアウトを0.5秒に設定
            ser.flushInput() # リセット後の起動メッセージを全てクリア

            ready = False
            start_time = time.time()
            # 最大15秒待機
            while time.time() - start_time < 15:
                line = ser.readline().decode('utf-8', errors='ignore').strip()

                # 起動完了メッセージを確認
                if "Ready." in line:
                    ready = True
                    print(f"Arduino is ready: {line}")
                    break

                # Arduinoからのメッセージがあれば表示（デバッグ用）
                if line:
                    print(f"Arduino startup: {line}")

                # 受信がなければ少しスリープしてCPU負荷を下げる
                time.sleep(0.1)

            if not ready:
                print("Error: Arduino did not send 'Ready.' signal within 15 seconds. Giving up.")
                return

            # --- 起動確認後、コマンドを送信 ---
            ser.timeout = 1 # コマンド送信後の応答待ちに戻す
            send_servo_command(ser, servo_index, angle)

            print("Command sent. Waiting for Arduino response (if any)...")
            response = ser.readline().decode('utf-8').strip()
            if response:
                print(f"Arduino says: {response}")

    except serial.SerialException as e:
        print(f"Error: Could not open serial port {SERIAL_PORT}.")
        print("Is the Arduino connected? Do you have permission?")
        print(f"Details: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
