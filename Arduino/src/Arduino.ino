/**
 * @file Arduino.ino
 * @brief Main entry point for the Robot Arm Controller (Binary Protocol Version)
 * * This file contains the main setup() and loop() functions.
 * It initializes the serial port and the robot arm module.
 * The loop() continuously reads single bytes from the serial port
 * and passes them to the RobotArm module's state machine for processing.
 * (This file replaces the String/char[] parsing logic)
 */

#include <Arduino.h>
#include "RobotArm.h" // Include the robot arm module interface
#include "Config.h"   // Include configuration for SERIAL_BAUDRATE

/**
 * @brief Initialization function. Runs once at startup.
 */
void setup()
{
    // Initialize serial communication at the speed defined in Config.h
    Serial.begin(SERIAL_BAUDRATE);

    // Wait for the serial port to connect. (Needed for native USB ports)
    while (!Serial)
    {
        ; // Wait
    }

    Serial.println("Robot Arm Controller: Initializing (Binary Mode)...");

    // Initialize the RobotArm module (which initializes ServoController, etc.)
    robotArmInit();

    Serial.println("Robot Arm Controller: Ready.");
}

/**
 * @brief Main loop function. Runs repeatedly.
 */
void loop()
{
    // Process serial data as long as bytes are available
    while (Serial.available() > 0)
    {
        // Read one byte from the serial buffer
        uint8_t incomingByte = (uint8_t)Serial.read();

        // Pass the byte to the RobotArm module's state machine
        processRobotArmByte(incomingByte);
    }
}
