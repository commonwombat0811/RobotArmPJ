/**
 * @file Integrated_Control.ino
 * @brief
 * Python側の全ての制御コマンド(0x01, 0x02, 0x03)に対応するための統合スケッチ。
 * サーボ制御 (6軸) と IRセンサー読み取りの両方に対応。
 * * ★ デバッグ修正点: 冗長な Serial.print をコメントアウトし、通信負荷を軽減 ★
 */

#include <Arduino.h>
#include <Wire.h>
#include "ServoController.h" // 6軸サーボ制御用
#include "Config.h"          // BAUD_RATEやサーボ設定用

// ServoControllerのインスタンス
ServoController g_servoController;

// --- 通信プロトコルの定義 ---
const uint8_t START_BYTE = 0xFF;
const uint8_t CMD_SET_ANGLE = 0x01;      // 単軸制御
const uint8_t CMD_GET_IR_SENSOR = 0x02;  // IRセンサー取得
const uint8_t CMD_SET_ALL_ANGLES = 0x03; // 6軸同時制御

// --- IRセンサーの設定 ---
const uint8_t IR_SENSOR_PIN = A1;

// --- ステートマシンの定義 ---
enum class SerialState
{
    WAITING_FOR_START,
    WAITING_FOR_COMMAND,
    // 単軸用
    WAITING_FOR_INDEX,
    WAITING_FOR_ANGLE,
    // 6軸同時制御用
    WAITING_FOR_ALL_ANGLES_0_5
};

SerialState currentState = SerialState::WAITING_FOR_START;
uint8_t tempServoIndex = 0;
uint8_t tempAngle = 0;
uint8_t allAngles[6];
uint8_t angleByteCount = 0;

void setup()
{
    Serial.begin(SERIAL_BAUDRATE);
    while (!Serial)
    {
        ;
    }
    Wire.begin();
    g_servoController.init();
    pinMode(IR_SENSOR_PIN, INPUT);

    Serial.println("Integrated Control: Ready.");
}

void processIncomingByte(uint8_t byte)
{
    switch (currentState)
    {
    case SerialState::WAITING_FOR_START:
        if (byte == START_BYTE)
        {
            currentState = SerialState::WAITING_FOR_COMMAND;
        }
        break;

    case SerialState::WAITING_FOR_COMMAND:
        if (byte == CMD_SET_ANGLE)
        {
            currentState = SerialState::WAITING_FOR_INDEX;
        }
        else if (byte == CMD_GET_IR_SENSOR) // ★ IRセンサーコマンド処理 ★
        {
            // --- ★ 修正点 1: 応答を返し、TX負荷をかける ★ ---
            int sensorValue = analogRead(IR_SENSOR_PIN);
            Serial.print("IR_READ:");
            Serial.println(sensorValue);
            // --- ★ 修正点 1 終わり ★ ---

            currentState = SerialState::WAITING_FOR_START; // 処理後リセット
        }
        else if (byte == CMD_SET_ALL_ANGLES)
        {
            angleByteCount = 0;
            currentState = SerialState::WAITING_FOR_ALL_ANGLES_0_5;
        }
        else
        {
            // 不明なコマンドを破棄
            // Serial.print("DEBUG: Unknown CMD="); Serial.println(byte); // デバッグコード (TX負荷軽減のため無効化)
            currentState = SerialState::WAITING_FOR_START;
        }
        break;

    case SerialState::WAITING_FOR_INDEX:
        tempServoIndex = byte;
        currentState = SerialState::WAITING_FOR_ANGLE;
        break;

    case SerialState::WAITING_FOR_ANGLE:
        tempAngle = byte;
        // --- ★ 修正点 2: 応答をコメントアウトし、TX負荷を軽減 ★ ---
        // Serial.print("Executing: Servo ");
        // Serial.print(tempServoIndex);
        // Serial.print(" to ");
        // Serial.println(tempAngle);
        // --- ★ 修正点 2 終わり ★ ---
        g_servoController.setAngle(tempServoIndex, tempAngle);
        currentState = SerialState::WAITING_FOR_START;
        break;

    case SerialState::WAITING_FOR_ALL_ANGLES_0_5:
        allAngles[angleByteCount] = byte;
        angleByteCount++;

        if (angleByteCount == 6)
        {
            // --- ★ 修正点 3: 応答をコメントアウトし、TX負荷を軽減 ★ ---
            // Serial.print("All servos set: ");
            // for (int i = 0; i < 6; i++)
            // {
            //     Serial.print(allAngles[i]);
            //     Serial.print(i == 5 ? "" : ", ");
            //     g_servoController.setAngle(i, allAngles[i]);
            // }
            // Serial.println();

            // 処理が成功したことだけを簡潔に Python に返す (TX LEDの連続点滅を防ぐ)
            Serial.println("All servos set: "); // 応答を極力短くする

            for (int i = 0; i < 6; i++)
            {
                g_servoController.setAngle(i, allAngles[i]);
            }
            // --- ★ 修正点 3 終わり ★ ---

            currentState = SerialState::WAITING_FOR_START;
        }
        break;
    }
}

void loop()
{
    while (Serial.available() > 0)
    {
        uint8_t incomingByte = (uint8_t)Serial.read();
        processIncomingByte(incomingByte);
    }
}
