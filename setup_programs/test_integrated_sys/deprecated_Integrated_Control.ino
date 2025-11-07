/**
 * @file Integrated_Control.ino
 * @brief
 * Python側の全ての制御コマンド(0x01, 0x02, 0x03)に対応するための統合スケッチ。
 * サーボ制御 (6軸) と IRセンサー読み取りの両方に対応。
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
            int sensorValue = analogRead(IR_SENSOR_PIN);
            Serial.print("IR_READ:");
            Serial.println(sensorValue);
            currentState = SerialState::WAITING_FOR_START; // 処理後リセット
        }
        else if (byte == CMD_SET_ALL_ANGLES)
        {
            angleByteCount = 0;
            currentState = SerialState::WAITING_FOR_ALL_ANGLES_0_5;
        }
        else
        {
            // 不明なコマンド
            currentState = SerialState::WAITING_FOR_START;
        }
        break;

    case SerialState::WAITING_FOR_INDEX:
        tempServoIndex = byte;
        currentState = SerialState::WAITING_FOR_ANGLE;
        break;

    case SerialState::WAITING_FOR_ANGLE:
        tempAngle = byte;
        Serial.print("Executing: Servo ");
        Serial.print(tempServoIndex);
        Serial.print(" to ");
        Serial.println(tempAngle);
        g_servoController.setAngle(tempServoIndex, tempAngle);
        currentState = SerialState::WAITING_FOR_START;
        break;

    case SerialState::WAITING_FOR_ALL_ANGLES_0_5:
        allAngles[angleByteCount] = byte;
        angleByteCount++;

        if (angleByteCount == 6)
        {
            // 6バイトすべて受信完了
            Serial.print("All servos set: ");
            for (int i = 0; i < 6; i++)
            {
                Serial.print(allAngles[i]);
                Serial.print(i == 5 ? "" : ", ");
                g_servoController.setAngle(i, allAngles[i]);
            }
            Serial.println();
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
