/**
 * @file ServoController.cpp
 * @brief Implementation of the ServoController specialist.
 * * This file contains the logic for applying trim, safety checks,
 * and converting angles to PWM pulse values for the PCA9685.
 */

#include "ServoController.h"
#include <Arduino.h> // For constrain() and map()

/**
 * @brief Default constructor.
 * Initializes the pca9685 object using the default I2C address (0x40).
 * It communicates with the Wire (I2C) library.
 */
ServoController::ServoController() : pca9685(Adafruit_PWMServoDriver())
{
    // Constructor body (can be empty if initialization is done in init())
}

/**
 * @brief Initializes the PCA9685 chip.
 */
void ServoController::init()
{
    pca9685.begin();
    // Set the PWM frequency based on Config.h
    pca9685.setPWMFreq(PWM_FREQ);

    // Initialize current angles array (optional, good practice)
    for (uint8_t i = 0; i < SERVO_COUNT; i++)
    {
        currentAngles[i] = 90; // Default startup angle
    }
}

/**
 * @brief Sets a specific servo to a target angle (0-180).
 * Applies trim offsets and safety checks.
 */
void ServoController::setAngle(uint8_t servoIndex, uint8_t angle)
{
    // Safety check: ensure servoIndex is within bounds
    if (servoIndex >= SERVO_COUNT)
    {
        return; // Invalid index, do nothing
    }

    // 1. Apply Individual Trim Offset (from Config.h)
    // We use int16_t to handle potential negative results (e.g., 0 + (-2) = -2)
    int16_t trimmedAngle = (int16_t)angle + SERVO_TRIM_OFFSETS[servoIndex];

    // 2. Apply Final Safety Clamp (constrain)
    // Ensure the final angle is strictly within 0-180
    // This is the "second safety check"
    uint8_t safeAngle = constrain(trimmedAngle, 0, 180);

    // 3. Convert the safe angle to a 12-bit pulse value
    uint16_t pulse = angleToPulse(safeAngle);

    // 4. Send the command to the PCA9685 chip
    pca9685.setPWM(servoIndex, 0, pulse);

    // 5. Store the *original commanded* angle (not the trimmed one)
    // This makes getAngle() more intuitive
    currentAngles[servoIndex] = angle;
}

/**
 * @brief Gets the last *commanded* angle for a servo.
 */
uint8_t ServoController::getAngle(uint8_t servoIndex)
{
    if (servoIndex < SERVO_COUNT)
    {
        return currentAngles[servoIndex];
    }
    return 0; // Return 0 for an invalid index
}

/**
 * @brief Disables all servo outputs.
 */
void ServoController::disableAll()
{
    for (uint8_t i = 0; i < SERVO_COUNT; i++)
    {
        // Setting the pulse to 0 disables the channel
        pca9685.setPWM(i, 0, 0);
    }
}

/**
 * @brief Converts an angle (0-180) to a 12-bit pulse value.
 * (Private helper method)
 */
uint16_t ServoController::angleToPulse(uint8_t angle)
{
    // Use Arduino's map() function to linearly interpolate
    // (angle, from_min, from_max, to_min, to_max)
    return map(angle, 0, 180, MIN_PULSE, MAX_PULSE);
}
