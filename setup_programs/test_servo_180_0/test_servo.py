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
        # シリアルポートを開く
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            time.sleep(2) # Arduinoのリセット待ち
            print(f"Serial port {SERIAL_PORT} opened at {BAUD_RATE} bps")

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
