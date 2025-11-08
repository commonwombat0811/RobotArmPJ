import multiprocessing as mp
import time
import sys

# --- プロセスクラスのインポート ---
# (同じディレクトリにあることを前提とします)
try:
    from orchestrator_process import OrchestratorProcess
    from real_time_control_process import RealTimeControlProcess
except ImportError:
    print("[Main] エラー: orchestrator_process.py または real_time_control_process.py が見つかりません。")
    sys.exit(1)


def main():
    print("[Main] システムを起動します...")

    # プロセス間で通信するための共有リソースを作成

    # 1. Orchestrator -> RealTime への「腕を動かせ」指示用キュー
    task_queue = mp.Queue()

    # 2. RealTime -> Orchestrator への「IRセンサー値」共有用メモリ
    # 'd' = double (浮動小数点数)
    ir_value_shared = mp.Value('d', 0.0)

    try:
        # --- プロセスA (リアルタイム制御/脊髄) の作成 ---
        process_a = RealTimeControlProcess(task_queue, ir_value_shared)

        # --- プロセスB (API・思考/頭脳) の作成 ---
        process_b = OrchestratorProcess(task_queue, ir_value_shared)

        print("[Main] 両プロセスを開始します...")
        process_a.start()
        process_b.start()

        # 両方のプロセスが終了するまで待機
        while process_a.is_alive() and process_b.is_alive():
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[Main] Ctrl+Cを検出。全プロセスに終了を通知します...")

    finally:
        # --- 安全なシャットダウン処理 ---
        print("[Main] シャットダウン処理開始...")

        # terminate() はプロセスを強制終了するため、
        # join() で終了を待機します。

        if 'process_b' in locals() and process_b.is_alive():
            print("[Main] Orchestratorプロセスを終了します...")
            process_b.terminate()
            process_b.join(timeout=3)

        if 'process_a' in locals() and process_a.is_alive():
            print("[Main] RealTime Controlプロセスを終了します...")
            process_a.terminate()
            process_a.join(timeout=3)

        print("[Main] システムをシャットダウンしました。")

if __name__ == "__main__":
    # マルチプロセスを安全に起動するためのおまじない (特にmacOS/Windowsで必須)
    # RPi (Linux) では "fork" がデフォルトですが、"spawn" の方が安全です。
    try:
        mp.set_start_method("spawn")
    except RuntimeError:
        print("[Main] set_start_methodが既に設定されているか、サポートされていません。")

    main()
