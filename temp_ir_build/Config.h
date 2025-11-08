/**
 * @file Config.h
 * @brief Central configuration file for the Robot Arm.
 * * This file contains all hardware-specific settings and tuning parameters.
 * Adjust values here to calibrate the arm.
 */

#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>

// ---- 1. Serial Communication Settings ----
// Must match the Raspberry Pi's setting
#define SERIAL_BAUDRATE 115200

// ---- 2. Hardware Definitions ----
// Total number of servos in the arm
#define SERVO_COUNT 6

// 元の Config.h の以下の3行を、サーボの動作範囲を180度に広げるために変更します。

//     あなたの現在の Config.h の内容

//         C++

// #define PWM_FREQ 60

// #define MIN_PULSE 245
// #define MAX_PULSE 490
//     変更後の Config.h の内容

//         C++

// // 1. 周波数を 60Hz から 50Hz に変更 (SG90サーボの標準)
// #define PWM_FREQ 50

// // 2. 0度のパルス幅を小さく (最小パルス幅を確保)
// #define MIN_PULSE 120

// // 3. 180度のパルス幅を大きく (最大動作範囲を確保)
// #define MAX_PULSE 500

// ---- 3. PCA9685 Servo Driver Settings ----
// Set the PWM frequency (Hz) for the servos. 60Hz is common for analog (SG90).
#define PWM_FREQ 50

// --- SAFTEY CRITICAL: Pulse Width Settings (in 12-bit steps, NOT microseconds) ---
// These values are calculated for 60Hz frequency (1 step = 4.07us)
// Standard 1.0ms pulse (1000us) -> 1000 / 4.07 = 245
// Standard 2.0ms pulse (2000us) -> 2000 / 4.07 = 490
#define MIN_PULSE 120
#define MAX_PULSE 500

// ---- 初期角度設定 ----
// 電源投入時の「目標」角度
const uint8_t INIT_ANGLES[SERVO_COUNT] = {90, 90, 90, 90, 90, 90};

// ---- ★ 個体差調整（トリム）オフセット ★ ----
//
// ここが個体差調整の核心です。
// アームを組み立てた後、「90」と指示しても真っ直ぐにならないサーボの
// 補正値を「度」単位で設定します。
// (例: サーボ1が「90」の指示で「92度」の位置に行く場合、-2 を設定)
//
// {サーボ0, サーボ1, サーボ2, サーボ3, サーボ4, サーボ5}
const int8_t SERVO_TRIM_OFFSETS[SERVO_COUNT] = {
    0, // 0番: ロボットアームん先端のなんか掴むやつ
    0,
    0,
    0,
    0,
    0 // 5番: ロボットアームの1番下の横方向に回転するやつ
};
// ※最初はすべて 0 にしておき、アームの動作を見ながらこの値を調整します。

#endif // CONFIG_H
