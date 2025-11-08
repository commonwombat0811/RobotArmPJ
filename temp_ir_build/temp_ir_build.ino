/**
 * @file Temp_IR_Test.ino
 * @brief
 * IRセンサーの読み取りとシリアル通信テストに特化したスケッチ。
 * サーボ制御およびI2C通信ロジックを排除。
 * (堅牢なステートマシン方式に修正)
 */

#include <Arduino.h>
#include "Config.h" // BAUD_RATEを含む

// --- IRセンサーの設定 ---
const uint8_t IR_SENSOR_PIN = A1; // A1ピンを仮定

// --- 通信プロトコルの定義 ---
const uint8_t START_BYTE = 0xFF;
const uint8_t CMD_GET_IR_SENSOR = 0x02;

// ★★★ ステート（状態）の定義 ★★★
enum class SerialState
{
    WAITING_FOR_START,
    WAITING_FOR_COMMAND
};
SerialState currentState = SerialState::WAITING_FOR_START;

void setup()
{
    Serial.begin(SERIAL_BAUDRATE);
    while (!Serial)
    {
        ; // Wait
    }
    delay(500);

    pinMode(IR_SENSOR_PIN, INPUT);
    Serial.println("IR Sensor Test: Ready.");
}

// ★★★ loop() からロジックを分離 ★★★
void processIncomingByte(uint8_t byte)
{
    switch (currentState)
    {
    // --- 状態1: スタートバイト(0xFF)を待っている ---
    case SerialState::WAITING_FOR_START:
        if (byte == START_BYTE)
        {
            // スタートバイトが来たので、次のバイトはコマンドのはず
            currentState = SerialState::WAITING_FOR_COMMAND;
        }
        break;

    // --- 状態2: コマンドバイト(0x02)を待っている ---
    case SerialState::WAITING_FOR_COMMAND:
        if (byte == CMD_GET_IR_SENSOR)
        {
            // --- IRセンサーコマンド実行 ---
            int sensorValue = analogRead(IR_SENSOR_PIN);

            // シリアルで値を送信
            Serial.print("IR_READ:");
            Serial.println(sensorValue);
        }
        // (else if (byte == 0x01) { ... } など、他のコマンドもここに追加できる)

        // コマンド処理が終わったら、次のスタートバイト待機状態に戻る
        currentState = SerialState::WAITING_FOR_START;
        break;
    }
}

void loop()
{
    // ★★★ 1バイトずつステートマシンに渡す ★★★
    while (Serial.available() > 0)
    {
        uint8_t incomingByte = (uint8_t)Serial.read();
        processIncomingByte(incomingByte);
    }
}
