/**
 * @file ServoController.h
 * @brief Interface for the ServoController specialist.
 * * This class is responsible for abstracting all direct communication
 * with the PCA9685 PWM driver chip.
 */

#ifndef SERVO_CONTROLLER_H
#define SERVO_CONTROLLER_H

#include <stdint.h>
#include <Adafruit_PWMServoDriver.h> // Include the driver library
#include "Config.h"                  // Include project settings

class ServoController
{
public:
    /**
     * @brief Default constructor.
     * Initializes the PCA9685 driver instance (using default I2C address 0x40).
     */
    ServoController();

    /**
     * @brief Initializes the PCA9685 chip.
     * Must be called once in setup().
     */
    void init();

    /**
     * @brief Sets a specific servo to a target angle (0-180).
     * This function automatically applies trim offsets and safety checks.
     * * @param servoIndex The index of the servo (0 to SERVO_COUNT-1).
     * @param angle The target angle (0 to 180).
     */
    void setAngle(uint8_t servoIndex, uint8_t angle);

    /**
     * @brief Gets the last *commanded* angle for a servo.
     * Note: This does not read the servo's actual physical position.
     * * @param servoIndex The index of the servo.
     * @return The last commanded angle (0-180).
     */
    uint8_t getAngle(uint8_t servoIndex);

    /**
     * @brief Disables all servo outputs (stops sending pulses).
     * This is useful for saving power or manually moving the arm.
     */
    void disableAll();

private:
    /**
     * @brief Converts an angle (0-180) to a 12-bit pulse value.
     * Uses MIN_PULSE and MAX_PULSE from Config.h for mapping.
     * * @param angle The angle (0-180) to convert.
     * @return The 12-bit pulse value (e.g., 245 to 490).
     */
    uint16_t angleToPulse(uint8_t angle);

    // Private instance of the Adafruit driver
    Adafruit_PWMServoDriver pca9685;

    // Array to store the last commanded angle for each servo
    uint8_t currentAngles[SERVO_COUNT];
};

#endif // SERVO_CONTROLLER_H
