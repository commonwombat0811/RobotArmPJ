ファイル名,責務
Config.h,[安定化の核心 1] ハードウェア定義。アームの物理的・電気的制約をすべて定義。 _ PCA9685 のアドレスと周波数（例: 50Hz）。 _ 各サーボ（6 軸分）の 最小/最大パルス幅（例: 500-2500 μs）。 _ 各サーボの 回転角制限（例: 0〜180 度）。 _ アームのリンク長（逆運動学(IK)計算用）。
ServoController.h / .cpp,"[安定化の核心 2] 低レベルサーボ制御。PCA9685 ライブラリを直接操作するラッパークラス。 _ 責務: 「指定された角度に、安全かつ正確にサーボを動かす」。 _ void setAngle(uint8_t servoID, float angle): 角度（度数）を受け取り、Config.h のパルス幅/角度制限を厳密に遵守しながら PCA9685 に PWM 信号を送信する。過剰回転を防ぐためのリミッターを内蔵する。"
RobotArm.h / .cpp,アーム全体（6 軸）の協調制御。ServoController を利用する高レベルクラス。 _ 責務: 「アーム全体としての動作を実現する」。 _ 逆運動学 (IK) ロジックを実装し、ホスト PC から送られてくる XYZ 座標（と姿勢）を 6 軸の角度に変換する。 _ void moveToAngles(float angles[6]): 6 軸すべての角度を（滑らかに）設定する。 _ void moveToXYZ(...): IK 計算を実行し、moveToAngles を呼び出す。 _ float_ getCurrentAngles(): 現在のサーボ角度（設定値）を返す（ホスト PC への FB 用）。
CommandParser.h / .cpp,"ホスト PC との通訳。RobotArm を操作する。 _ 責務: 「シリアルで受信した文字列コマンドを解釈し、対応する RobotArm の関数を呼び出す」。 _ 例: ""MOVE_XYZ:10.5,5.2,8.0,0,90,0"" → robotArm.moveToXYZ(...) \* 例: ""SET_ANGLES:90,90,45,0,0,0"" → robotArm.moveToAngles(...)"
