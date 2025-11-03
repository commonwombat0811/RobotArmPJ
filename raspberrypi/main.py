import multiprocessing as mp
import time
from src.core.orchestrator import OrchestratorProcess
from src.core.real_time_control import RealTimeControlProcess

# TODO どこにサーボによるアームの各角度というか物理的位置情報とirセンサーおよびカメラワークとの相対位置を調整し、一致させるロジック部分が存在するか；下記メモから調整実施
# 数値調整計算要件
# 1. カメラから検知される物体の左右位置は5番軸(1番下のサーボの横回転軸により実現) → カメラ検出の物体の水平方向相対位置をベースに調整（基本的にカメラ検知の左右中道に物体のフレームの中央が一致するように；こっちは簡単なはず）
# 2. 縦方向: 2, 3, 4番軸において探索時一定角度を保つようにしないと地面上の物体を探索することができないので探索時にはその角度で固定というかその角度および固定情報はそこらへんで固定していくみたいな感じでいいかな
# 3. 地面とアームの軸の長さを固定で数値化して、入れる → アームの軸として回転角からの第5軸の回転軸の横方向の中心位置からのアームが物体を掴める距離情報 + 地面からのアームの高さ情報 として変換して適切に計算できるように設計実装する必要がある。 → 内部計算モジュールの初期化じにdiとしてアームおよび各軸の高さ情報および軸が折り曲がっているときの個別の軸の曲がり情報とそれに対応する地面からのアーム先端の高さ + 5軸中心軸からの地面水平方向の距離を算出して適切に調整できるように → irセンサーと連動して距離情報とあとは位置の調整fbを構成する（これについて内部制御情報についてより精度が出るように調整）

def main():
    print("[Main] システムを起動します...")
    # プロセス間で通信するためのキューを作成
    # Orchestrator (B) -> RealTime (A) への指示用
    task_queue = mp.Queue()

    try:
        # --- プロセスA (リアルタイム制御) の作成 ---
        process_a = RealTimeControlProcess(task_queue)

        # --- プロセスB (API・思考) の作成 ---
        process_b = OrchestratorProcess(task_queue)

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
        if 'process_b' in locals() and process_b.is_alive():
            print("[Main] Orchestratorプロセスに終了を要求...")
            process_b.terminate() # (より安全な終了フラグを推奨)
            process_b.join(timeout=2)
            if process_b.is_alive():
                process_b.kill()

        if 'process_a' in locals() and process_a.is_alive():
            print("[Main] RealTime Controlプロセスに終了を要求...")
            process_a.terminate() # (より安全な終了フラグを推奨)
            process_a.join(timeout=2)
            if process_a.is_alive():
                process_a.kill()

        print("[Main] システムをシャットダウンしました。")

if __name__ == "__main__":
    # マルチプロセスを安全に起動するためのおまじない
    mp.set_start_method("spawn")
    main()
