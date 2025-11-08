import multiprocessing as mp
import time

# --- 必要なハードウェアモジュール ---
from src.hardware.arduino_com import ArduinoCom
from src.hardware.ir_sensor import get_ir_sensor_reading
import config

class RealTimeControlProcess(mp.Process):
    """
    リアルタイム制御プロセス (脊髄)
    - Arduinoとのシリアル通信を専有する
    - Orchestrator (頭脳) からの角度指示をキューで待つ
    - IRセンサーの値を定期的に読み取り、共有メモリに書き込む
    """
    def __init__(self, task_queue, ir_value_shared):
        super().__init__()
        self.task_queue = task_queue
        self.ir_value_shared = ir_value_shared
        self.arduino_com = None

    def setup(self):
        """ Arduinoの接続をセットアップ """
        print("[RealTime] Arduino接続待機中...")
        self.arduino_com = ArduinoCom(config.SERIAL_PORT, config.BAUD_RATE)

        # 10秒待機バージョンを使用 (安定化のため)
        if self.arduino_com.open_and_wait_for_ready():
            print("[RealTime] Arduino接続完了。")
            return True
        else:
            print("[RealTime] [FATAL ERROR] Arduinoの接続に失敗しました。")
            return False

    def run(self):
        """ プロセスのメイン実行ループ """
        if not self.setup():
            return # Arduino接続失敗時はプロセス終了

        print("[RealTime] メインループ開始。")

        loop_counter = 0

        try:
            while True:
                # --- 1. Orchestratorからの指示 (サーボ角度) を処理 ---
                try:
                    # キューに指示があれば、ブロックせずに取得
                    angles_to_set = self.task_queue.get(block=False)

                    if angles_to_set and len(angles_to_set) == 6:
                        # Arduinoに6軸同時制御コマンドを送信
                        self.arduino_com.send_multi_servo_command(angles_to_set)
                        # print(f"[RealTime] アーム動作実行: {angles_to_set}") # デバッグ用

                except mp.queues.Empty:
                    # キューが空なら何もしない (エラーではない)
                    pass

                # --- 2. IRセンサーの値を読み取り、Orchestratorと共有 ---
                # センサーポーリングは 200ms ごと (50ms * 4)
                if loop_counter % 4 == 0:
                    raw_val = get_ir_sensor_reading(self.arduino_com.ser)
                    if raw_val > 0.0:
                        # 共有メモリの値をアトミックに更新
                        self.ir_value_shared.value = raw_val

                loop_counter += 1

                # ループは 50ms ごと (20Hz)
                time.sleep(0.05)

        except KeyboardInterrupt:
            pass # メインプロセスからの終了シグナルでループを抜ける

        finally:
            if self.arduino_com:
                self.arduino_com.close()
            print("[RealTime] プロセスを終了しました。")
