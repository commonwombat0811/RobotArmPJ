/**
 * @file Temp_Servo_Test.ino
 * @brief
 * Raspberry Pi 5からの4バイトのバイナリコマンドをテストするための
 * 一時的なスケッチ。
 *
 * このスケッチは、あなたが作成した ServoController.h と ServoController.cpp が
 * 同じフォルダにあることを前提としています。
 *
 * プロトコル:
 * Byte 0: 0xFF (スタートバイト)
 * Byte 1: 0x01 (CMD_SET_ANGLE)
 * Byte 2: Servo Index (0-15)
 * Byte 3: Angle (0-180)
 */

#include <Arduino.h>
#include <Wire.h>
#include "ServoController.h" // あなたが作成したコントローラーをインクルード
#include "Config.h"          // BAUD_RATEやサーボ設定

// ServoControllerのインスタンスを作成
ServoController g_servoController;

// --- 通信プロトコルの定義 ---
enum class SerialState
{
    WAITING_FOR_START,
    WAITING_FOR_COMMAND,
    WAITING_FOR_INDEX,
    WAITING_FOR_ANGLE
};

const uint8_t START_BYTE = 0xFF;
const uint8_t CMD_SET_ANGLE = 0x01;

SerialState currentState = SerialState::WAITING_FOR_START;
uint8_t tempServoIndex = 0;
uint8_t tempAngle = 0;

void setup()
{
    Serial.begin(SERIAL_BAUDRATE); // Config.hの値を使用
    while (!Serial)
    {
        ; // 待機
    }
    Serial.println("Temporary Servo Tester: Initializing...");

    // I2Cを開始 (ServoControllerが内部でWireを使うため)
    Wire.begin();

    // あなたのサーボコントローラーを初期化
    g_servoController.init();

    Serial.println("Temporary Servo Tester: Ready.");
}

/**
 * @brief 1バイトを処理するシンプルなステートマシン
 */
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
        else
        {
            // 不明なコマンドならリセット
            currentState = SerialState::WAITING_FOR_START;
        }
        break;

    case SerialState::WAITING_FOR_INDEX:
        tempServoIndex = byte;
        currentState = SerialState::WAITING_FOR_ANGLE;
        break;

    case SerialState::WAITING_FOR_ANGLE:
        tempAngle = byte;

        // --- コマンド実行 ---
        Serial.print("Executing: Servo ");
        Serial.print(tempServoIndex);
        Serial.print(" to ");
        Serial.print(tempAngle);
        Serial.println(" deg");

        // あなたのコントローラーを使ってサーボを動かす
        g_servoController.setAngle(tempServoIndex, tempAngle);

        // ステートをリセットして次のコマンドを待つ
        currentState = SerialState::WAITING_FOR_START;
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
