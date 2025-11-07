import serial
import time
import struct
import config

# --- Arduinoとの通信プロトコル定義 ---
START_BYTE = config.PACKET_HEADER
CMD_GET_IR_SENSOR = 0x02

def get_ir_sensor_reading(ser: serial.Serial) -> float:
    """
    ArduinoにIRセンサーの値要求コマンドを送信し、読み取り値を返す。
    Arduinoは "IR_READ:VALUE" の形式で応答することを期待する。
    """

    # ★★★ 修正点 1: シリアルポートの有効性チェック (これはOK) ★★★
    if ser is None or not ser.is_open:
        # print("[IR Sensor] 警告: シリアルポートが未接続 (None or closed)。")
        return 0.0

    # データを2バイトのバイナリとしてパックする
    packet = struct.pack('<BB', START_BYTE, CMD_GET_IR_SENSOR)

    try:
        # ★★★ 修正点 2: 積極的なバッファクリア ★★★
        # 溜まっている可能性のある古いデータをすべて捨てる
        ser.reset_input_buffer()

        # コマンドを送信
        ser.write(packet)

        # ★★★ 修正点 3: 目的の応答が来るまで読み飛ばす ★★★
        ser.timeout = 0.5 # 応答タイムアウト
        start_time = time.time()

        while time.time() - start_time < 0.5: # 最大0.5秒間試行
            response_line = ser.readline().decode('utf-8', errors='ignore').strip()

            if response_line.startswith("IR_READ:"):
                # センサー値を抽出 (0-1023の生の値)
                try:
                    raw_value = float(response_line.split(":")[1])
                    return raw_value
                except (ValueError, IndexError):
                    print(f"[IR Sensor] エラー: 'IR_READ:' の後の値が不正: {response_line}")
                    return 0.0

            # 期待しないデータ（起動時のゴミなど）が来た場合
            if response_line:
                print(f"[IR Sensor] 起動ノイズを破棄: {response_line}")

        # タイムアウトした場合
        print(f"[IR Sensor] 警告: タイムアウト（0.5秒）しました。")
        return 0.0

    except Exception as e:
        print(f"[IR Sensor] 通信エラー: {e}")
        return 0.0
