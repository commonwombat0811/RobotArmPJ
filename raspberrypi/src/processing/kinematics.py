"""
kinematics.py (要件3対応)
逆運動学 (Inverse Kinematics, IK) を計算します。
アームの (X, Y, Z) 座標から、土台・肩・肘の3軸の角度を計算します。
"""

import numpy as np

class KinematicsSolver:
    def __init__(self, arm_l1_cm, arm_l2_cm, arm_base_height_cm):
        """
        3軸 (土台, 肩, 肘) のIKソルバー
        @param arm_l1_cm: 肩から肘の長さ (L1)
        @param arm_l2_cm: 肘から手首の長さ (L2)
        @param arm_base_height_cm: 地面から肩の軸までの高さ
        """
        self.l1 = float(arm_l1_cm)
        self.l2 = float(arm_l2_cm)
        self.base_height = float(arm_base_height_cm)

        self.l1_plus_l2 = self.l1 + self.l2
        self.l1_minus_l2_abs = abs(self.l1 - self.l2)

        # (L1^2 + L2^2) は計算中によく使うので先に計算しておく
        self.l1_sq_plus_l2_sq = self.l1**2 + self.l2**2

        print(f"[IK] 3D Kinematics Solver 初期化完了 (L1:{self.l1}, L2:{self.l2})")

    def calculate_ik(self, target_x_arm, target_y_arm, target_z_arm):
        """
        目標の(X, Y, Z)座標 [cm] (アーム基準) から、
        サーボ0(土台), 1(肩), 2(肘)の角度を計算する

        @return (dict): {"base": int, "shoulder": int, "elbow": int}
                       または計算不能な場合 None
        """
        try:
            # --- 1. 土台の角度 (サーボ5) の計算 (Req 1) ---
            # (X, Y) 平面での角度を計算
            # 理由: X軸(前方)を0度、Y軸(左)を90度とするため、arctan2(y, x) を使用
            theta_0_rad = np.arctan2(target_y_arm, target_x_arm)
            theta_0_deg = np.degrees(theta_0_rad)

            # --- 2. 肩と肘の角度 (サーボ1, 2) の計算 ---

            # (X,Y)平面での水平リーチ長 (r) を計算
            r = np.sqrt(target_x_arm**2 + target_y_arm**2)

            # 肩の軸(0,0,base_height)から見た、目標の相対的な高さ (z_prime)
            z_prime = target_z_arm - self.base_height

            # 肩の軸から目標までの「直線距離」 (d)
            # (ピタゴラスの定理: d^2 = r^2 + z_prime^2)
            d_squared = r**2 + z_prime**2
            d = np.sqrt(d_squared)

            # (A) リーチチェック: そもそもアームが届くか？
            if d > self.l1_plus_l2:
                # print("[IK] リーチ外 (遠すぎ)")
                return None # 遠すぎる
            if d < self.l1_minus_l2_abs:
                # print("[IK] リーチ外 (近すぎ)")
                return None # 近すぎる (肘が曲がりきれない)

            # (B) 肘の角度 (サーボ2) - 余弦定理
            # 理由: L1, L2, d の3辺からなる三角形の角度(phi_2)を求める
            cos_phi_2_arg = (self.l1**2 + self.l2**2 - d_squared) / (2 * self.l1 * self.l2)
            # 浮動小数点誤差で 1.00001 などになるのを防ぐ
            cos_phi_2_arg = np.clip(cos_phi_2_arg, -1.0, 1.0)

            phi_2_rad = np.arccos(cos_phi_2_arg)

            # 理由: サーボの角度定義 (0=まっすぐ, 180=折りたたみ) に合わせる
            theta_2_rad = np.pi - phi_2_rad
            theta_2_deg = np.degrees(theta_2_rad)

            # (C) 肩の角度 (サーボ1) - 余弦定理
            # 理由: 水平線からの角度(alpha)と、L1とdがなす角度(beta)の合計

            # 角度 alpha (水平線(r)と、肩-目標の直線(d)がなす角度)
            alpha_rad = np.arctan2(z_prime, r)

            # 角度 beta (L1とdがなす角度)
            cos_beta_arg = (self.l1**2 + d_squared - self.l2**2) / (2 * self.l1 * d)
            cos_beta_arg = np.clip(cos_beta_arg, -1.0, 1.0)

            beta_rad = np.arccos(cos_beta_arg)

            # 理由: 0度=水平(前方)
            theta_1_rad = alpha_rad + beta_rad
            theta_1_deg = np.degrees(theta_1_rad)

            # --- 3. 最終結果の整形 ---
            # 角度が 0-180 の範囲に収まっているか最終クリップ
            final_angles = {
                "base":     int(np.clip(theta_0_deg, 0, 180)),
                "shoulder": int(np.clip(theta_1_deg, 0, 180)),
                "elbow":    int(np.clip(theta_2_deg, 0, 180))
            }

            return final_angles

        except Exception as e:
            print(f"[IK] Error: 逆運動学の計算中にエラー: {e}")
            return None
