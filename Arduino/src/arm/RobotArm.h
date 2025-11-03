/**
 * @file RobotArm.h
 * @brief Interface for the main RobotArm module.
 * * This file declares the public functions that the main Arduino.ino file
 * will call. It handles the initialization and the byte-by-byte
 * processing of incoming serial data using a state machine.
 */

#ifndef ROBOTARM_H
#define ROBOTARM_H

#include <stdint.h> // Required for uint8_t type

/**
 * @brief Initializes the RobotArm module and all its sub-modules (ServoController).
 * This should be called once from setup().
 */
void robotArmInit();

/**
 * @brief Processes a single byte of incoming serial data.
 * This function implements a state machine to parse the binary protocol.
 * * @param incomingByte The byte read from the serial port.
 */
void processRobotArmByte(uint8_t incomingByte);

#endif // ROBOTARM_H
