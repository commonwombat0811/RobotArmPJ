"""
real_time_control.py (プロセスA)
「反射」を担当する、高速・ノンブロッキングなプロセス。
(カメラ -> YOLO -> IR -> 3D座標変換 -> 3D-IK -> Arduino) のループを回す。

★★★ ロジック追加修正版 ★★★
- PICKUPステートが、近距離でGRABステートに移行するよう修正
- GRAB (掴む), LIFT (持ち上げ), IDLE_HOLDING (待機) ステートを追加
"""

import multiprocessing as mp
import time
import cv2
from ultralytics import YOLO
import numpy as np
import config
from src.hardware.arduino_com import ArduinoCommunicator
from src.hardware.camera import Camera
from src.hardware.ir_sensor import IRSensor
from src.hardware.kinematics import KinematicsSolver # ★ 3D-IKソルバーをインポート

class RealTimeControlProcess(mp.Process):

    def __init__(self, task_queue):
        super().__init__()
        self.task_queue = task_queue

        # --- ステート管理 ---
        self.current_task = {"command": "STOP"} # 初期状態はSTOP

        # --- 探索用変数 ---
        self.search_angle = config.HOME_POSITION_ANGLES[config.SERVO_ID_BASE]
        self.search_direction = config.SEARCH_STEP_PER_LOOP

        # --- FPS計算用 ---
        self.frame_count = 0
        self.last_fps_time = time.time()

        print(f"[RealTime] プロセスA (PID: {self.pid}) を初期化")

    def initialize_hardware(self):
        """
        このプロセス専用のハードウェアとAIモデルを初期化する
        """
        print("[RealTime] ハードウェアを初期化中...")
        try:
            self.arduino = ArduinoCommunicator(config.SERIAL_PORT, config.BAUD_RATE)
            self.arduino.connect()

            self.cam = Camera(config.CAMERA_ID, config.CAMERA_RESOLUTION_WIDTH, config.CAMERA_RESOLUTION_HEIGHT)
            self.ir = IRSensor()

            # ★★★ 要件3対応 (DI) ★★★
            # 3D-IKソルバーに、configから「アームの物理形状」を渡す
            self.ik = KinematicsSolver(
                config.ARM_L1_CM,
                config.ARM_L2_CM,
                config.ARM_BASE_HEIGHT_CM
            )

            # カメラパラメータをクラス変数として保持
            self.fx = config.CAMERA_FOCAL_LENGTH_X
            self.fy = config.CAMERA_FOCAL_LENGTH_Y
            self.cx = config.CAMERA_CENTER_X
            self.cy = config.CAMERA_CENTER_Y
            # カメラの取り付け位置オフセット(numpy配列)
            self.cam_offset = config.CAMERA_MOUNT_OFFSET_CM

            print("[RealTime] YOLOモデルをロード中...")
            self.yolo_model = YOLO(config.YOLO_MODEL_PATH)
            print("[RealTime] 全ての初期化が完了。")
            return True
        except Exception as e:
            print(f"[RealTime] Error: 初期化に失敗: {e}")
            return False

    def check_for_new_task(self):
        """プロセスBからの指示をノンブロッキングで確認"""
        try:
            # 掴んで待機中(IDLE_HOLDING)は、"PLACE"以外の指示を無視する
            if self.current_task.get("command") == "IDLE_HOLDING":
                new_task = self.task_queue.get_nowait()
                if new_task and new_task.get("command") == "PLACE":
                     print(f"[RealTime] 新タスク受信: {new_task}")
                     self.current_task = new_task
                # PLACE以外の指示 (例: PICKUP, STOP) は無視
            else:
                # 通常のタスク受付
                new_task = self.task_queue.get_nowait()
                if new_task:
                    print(f"[RealTime] 新タスク受信: {new_task}")
                    self.search_angle = config.HOME_POSITION_ANGLES[config.SERVO_ID_BASE]
                    self.current_task = new_task
        except mp.queues.Empty:
            pass

    def find_target_in_results(self, results, target_name):
        """YOLOの推論結果から、指定された物体を探す"""
        best_confidence = 0.0
        best_box_center = None

        target_class_id = -1
        class_names = results[0].names
        for class_id, name in class_names.items():
            if name.lower() == target_name.lower():
                target_class_id = class_id
                break
        if target_class_id == -1: return None

        for r in results:
            for box in r.boxes:
                if box.cls == target_class_id and box.conf > best_confidence:
                    best_confidence = box.conf
                    x1, y1, x2, y2 = box.xyxy[0]
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    best_box_center = (int(center_x), int(center_y))
        return best_box_center

    # --- ★★★ 要件3対応: FBループの「調整」部分 ★★★ ---
    def pixel_to_arm_coords(self, pixel_coords, distance_cm):
        """
        YOLOの(px, py)とIRの(distance)を、アーム基準の(X, Y, Z)に変換する
        """
        px, py = pixel_coords
        Z_cam = distance_cm # IRセンサーの距離をカメラのZ軸(奥行き)とする

        # 1. ピンホールモデルで「カメラ座標系」での (X, Y) を計算
        X_cam = ((px - self.cx) * Z_cam) / self.fx
        Y_cam = ((py - self.cy) * Z_cm) / self.fy

        # (X_cam, Y_cam, Z_cam) の3Dベクトルを作成
        cam_coords = np.array([X_cam, Y_cam, Z_cam])

        # 2. アーム座標系に変換
        # 理由: アームのIK計算は、アームの土台(0,0,0)を基準に
        #       計算する必要があるため、カメラの取り付け位置の
        #       オフセット(config.pyで定義)を考慮する。
        # (※これは最も単純な「並進」のみの変換。
        #    カメラが傾いている場合は、ここで「回転行列」も必要)
        arm_coords = cam_coords - self.cam_offset

        # (X_arm, Y_arm, Z_arm) を返す
        return (arm_coords[0], arm_coords[1], arm_coords[2])

    def _calculate_and_print_fps(self, loop_start_time_ms):
        """1秒ごとにFPSとループ処理時間をコンソールに出力する"""
        self.frame_count += 1
        current_time = time.time()
        elapsed_time = current_time - self.last_fps_time
        if elapsed_time >= 1.0:
            fps = self.frame_count / elapsed_time
            print(f"[RealTime] State: {self.current_task['command']} | Loop: {loop_start_time_ms:.1f} ms (FPS: {fps:.1f})")
            self.last_fps_time = current_time
            self.frame_count = 0

    # --- ★★★ 要件2対応: 探索ルーチン ★★★ ---
    def _execute_search_routine(self):
        """ (実装) 目標が見つからない場合、土台を回転させ、他を固定 """

        # 1. 土台の角度を更新
        self.search_angle += self.search_direction
        if self.search_angle >= config.SEARCH_RANGE_MAX:
            self.search_angle = config.SEARCH_RANGE_MAX
            self.search_direction = -config.SEARCH_STEP_PER_LOOP
        elif self.search_angle <= config.SEARCH_RANGE_MIN:
            self.search_angle = config.SEARCH_RANGE_MIN
            self.search_direction = config.SEARCH_STEP_PER_LOOP

        # 2. 全サーボに「探索ポーズ」の角度を送信
        # 理由: 土台(5)以外を固定角に保ち、地面を探索させる (要件2)

        # グリッパー (0)
        self.arduino.send_command(config.SERVO_ID_GRIPPER, config.SEARCH_POSE_ANGLES[config.SERVO_ID_GRIPPER])
        # 肩 (1)
        self.arduino.send_command(config.SERVO_ID_SHOULDER, config.SEARCH_POSE_ANGLES[config.SERVO_ID_SHOULDER])
        # 肘 (2)
        self.arduino.send_command(config.SERVO_ID_ELBOW, config.SEARCH_POSE_ANGLES[config.SERVO_ID_ELBOW])
        # 手首 (3)
        self.arduino.send_command(config.SERVO_ID_WRIST, config.SEARCH_POSE_ANGLES[config.SERVO_ID_WRIST])
        # 手首回転 (4)
        self.arduino.send_command(config.SERVO_ID_WRIST_ROTATE, config.SEARCH_POSE_ANGLES[config.SERVO_ID_WRIST_ROTATE])

        # 土台 (5) - 探索角度で上書き
        self.arduino.send_command(config.SERVO_ID_BASE, int(self.search_angle))

    def _execute_place_routine(self):
        """ (実装) 事前に定義された位置にアームを移動させ、グリッパーを開く """
        print("[RealTime] PLACEルーチン実行...")

        # 1. configで定義された「置く場所」の (X, Y, Z) 座標を取得
        x, y, z = config.PLACE_TARGET_COORDS_ARM

        # 2. 3D-IK計算
        angles_dict = self.ik.calculate_ik(x, y, z)

        if angles_dict:
            # 3. アームを移動 (IKが計算した3軸)
            self.arduino.send_command(config.SERVO_ID_BASE, angles_dict["base"])
            self.arduino.send_command(config.SERVO_ID_SHOULDER, angles_dict["shoulder"])
            self.arduino.send_command(config.SERVO_ID_ELBOW, angles_dict["elbow"])
            # (手首とグリッパーはホームポジションの角度を使う)
            self.arduino.send_command(config.SERVO_ID_WRIST, config.HOME_POSITION_ANGLES[config.SERVO_ID_WRIST])
            self.arduino.send_command(config.SERVO_ID_GRIPPER, config.GRIPPER_CLOSED_ANGLE) # 掴んだまま移動

            time.sleep(1.0) # 移動待機

            # 4. グリッパー(サーボ0)を開く
            self.arduino.send_command(config.SERVO_ID_GRIPPER, config.GRIPPER_OPEN_ANGLE)
            print("[RealTime] グリッパーを開きました。")
            time.sleep(0.5)

            # 5. 完了後、STOP (ホームポジションに戻る) タスクに移行
            print("[RealTime] PLACE完了。STOPタスクに移行します。")
            self.current_task = {"command": "STOP"}
        else:
            print("[RealTime] Error: PLACE座標に到達できません。")
            self.current_task = {"command": "STOP"}

    def _execute_stop_routine(self):
        """ (実装) アームを安全な「ホームポジション」に戻す """
        print("[RealTime] STOPルーチン実行。ホームポジションに戻ります...")

        for i in range(config.SERVO_COUNT):
            self.arduino.send_command(i, config.HOME_POSITION_ANGLES[i])
            time.sleep(0.05)

        print("[RealTime] ホームポジションに移動完了。IDLE状態になります。")
        self.current_task = {"command": "IDLE"}

    # --- メイン実行ループ ---
    def run(self):
        if not self.initialize_hardware():
            print("[RealTime] 初期化失敗のためプロセスを終了します。")
            return

        print(f"[RealTime] 制御ループ実行中 (PID: {self.pid})...")

        try:
            while True:
                start_time = time.time()
                self.check_for_new_task()
                command = self.current_task.get("command", "IDLE") # デフォルトはIDLE

                if command == "PICKUP":
                    target_name = self.current_task.get("target")
                    if not target_name:
                        self.current_task = {"command": "STOP"}
                        continue

                    # (A) センサー群から情報を取得
                    ret, frame = self.cam.get_frame()
                    ir_distance = self.ir.get_distance_cm()
                    if not ret or ir_distance < 0:
                        continue

                    # (B) YOLOv5 推論
                    results = self.yolo_model(frame, verbose=False)
                    pixel_coords = self.find_target_in_results(results, target_name)

                    if pixel_coords:
                        # (D) ★要件3: 座標変換 (FBループ)★
                        world_coords_arm = self.pixel_to_arm_coords(pixel_coords, ir_distance)

                        # (E) ★要件3: 3D-IK計算★
                        angles_dict = self.ik.calculate_ik(world_coords_arm[0], world_coords_arm[1], world_coords_arm[2])

                        if angles_dict:
                            # (F) ★要件1: Arduinoにコマンド送信★

                            # IKが計算した3軸を送信
                            self.arduino.send_command(config.SERVO_ID_BASE, angles_dict["base"])
                            self.arduino.send_command(config.SERVO_ID_SHOULDER, angles_dict["shoulder"])
                            self.arduino.send_command(config.SERVO_ID_ELBOW, angles_dict["elbow"])

                            # 手首とグリッパーは固定角
                            self.arduino.send_command(config.SERVO_ID_WRIST, config.SEARCH_POSE_ANGLES[config.SERVO_ID_WRIST]) # 水平維持
                            self.arduino.send_command(config.SERVO_ID_WRIST_ROTATE, config.HOME_POSITION_ANGLES[config.SERVO_ID_WRIST_ROTATE])
                            self.arduino.send_command(config.SERVO_ID_GRIPPER, config.GRIPPER_OPEN_ANGLE) # 掴むまで開く

                            # IRセンサーの距離が「掴むしきい値」(configで定義)より近くなったら
                            # (ここでは生のIR距離をそのまま使う)
                            if ir_distance <= config.GRAB_DISTANCE_THRESHOLD_CM:
                                print(f"[RealTime] ターゲット捕捉 (距離: {ir_distance}cm)。GRABステートに移行します。")
                                self.current_task = {"command": "GRAB", "target": target_name} # targetを維持

                        else:
                            # リーチ外 (対象に近づくよう促すなど)
                            pass
                    else:
                        # (G) ★目標見失う★ 探索ステートに移行
                        print(f"[RealTime] {target_name} を見失いました。SEARCHステートに移行します。")
                        self.current_task = {"command": "SEARCH", "target": target_name}

                elif command == "SEARCH":
                    # ★要件2: 探索ルーチン実行★
                    self._execute_search_routine()

                    # (カメラで再探索)
                    target_name = self.current_task.get("target")
                    ret, frame = self.cam.get_frame()
                    if not ret: continue

                    results = self.yolo_model(frame, verbose=False)
                    pixel_coords = self.find_target_in_results(results, target_name)

                    if pixel_coords:
                        print(f"[RealTime] {target_name} を再発見！ PICKUPステートに移行します。")
                        self.current_task = {"command": "PICKUP", "target": target_name}


                elif command == "GRAB":
                    # 役割: グリッパーを閉じる
                    print(f"[RealTime] GRAB実行: {self.current_task.get('target')} を掴みます。")

                    # 1. グリッパーを閉じる
                    self.arduino.send_command(config.SERVO_ID_GRIPPER, config.GRIPPER_CLOSED_ANGLE)
                    time.sleep(0.5) # グリッパーが閉じるのを待つ
                    print("[RealTime] グリッパーを閉じました。")

                    # 2. LIFTステートに移行
                    self.current_task = {"command": "LIFT"}

                elif command == "LIFT":
                    # 役割: 掴んだ物体を安全な高さまで持ち上げる
                    print("[RealTime] LIFT実行: 物体を持ち上げます。")

                    # 1. 安全な「持ち上げ」角度に移動 (ホームの肩/肘の角度を流用)
                    self.arduino.send_command(config.SERVO_ID_SHOULDER, config.HOME_POSITION_ANGLES[config.SERVO_ID_SHOULDER])
                    self.arduino.send_command(config.SERVO_ID_ELBOW, config.HOME_POSITION_ANGLES[config.SERVO_ID_ELBOW])
                    self.arduino.send_command(config.SERVO_ID_WRIST, config.HOME_POSITION_ANGLES[config.SERVO_ID_WRIST])
                    # (土台とグリッパーは現在の角度を維持)

                    time.sleep(1.0) # 持ち上げ待機

                    # 2. 持ち上げ完了。PLACE指示を待つIDLE状態に。
                    print("[RealTime] 持ち上げ完了。PLACE指示を待機します。")
                    self.current_task = {"command": "IDLE_HOLDING"}

                elif command == "IDLE_HOLDING":
                    # 役割: 物体を掴んだまま、次の指示(PLACE)を待つ
                    # (何もしない。ループで待機)
                    pass

                elif command == "PLACE":
                    self._execute_place_routine()

                elif command == "STOP":
                    self._execute_stop_routine()

                elif command == "IDLE":
                    pass

                loop_ms = (time.time() - start_time) * 1000
                self._calculate_and_print_fps(loop_ms)

        except KeyboardInterrupt:
            print("[RealTime] 終了シグナル受信。")
        finally:
            print("[RealTime] シャットダウン中... アームをホームポジションに戻します。")
            self._execute_stop_routine()
            time.sleep(1.0)

            if hasattr(self, 'arduino'):
                self.arduino.disconnect()
            if hasattr(self, 'cam'):
                self.cam.release()
            print("[RealTime] ハードウェアを解放しました。")
