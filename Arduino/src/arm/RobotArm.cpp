/**
 * @file RobotArm.cpp
 * @brief Implementation of the RobotArm module (Binary Protocol State Machine).
 * * This file contains the core logic for parsing the 4-byte binary protocol
 * using a finite state machine. It validates packets and controls the
 * ServoController. This replaces the CommandParser.
 */

#include "RobotArm.h"
#include "ServoController.h" // Include the servo control specialist
#include "Config.h"          // Include settings (SERVO_COUNT, INIT_ANGLES)
#include <Arduino.h>         // Required for Serial.println()

// ---- Module-Private (static) Instances ----

// Create an instance of the servo controller
static ServoController servoController;

// ---- Binary Protocol Definitions ----

// Define the "magic number" that starts every packet
#define PACKET_HEADER 0xFF

// Define the states for our finite state machine
enum PacketReadState
{
    WAITING_FOR_HEADER, // State 0: Waiting for 0xFF
    READING_INDEX,      // State 1: Waiting for Servo Index byte
    READING_ANGLE,      // State 2: Waiting for Angle byte
    READING_CHECKSUM    // State 3: Waiting for Checksum byte
};

// ---- Module-Private (static) Variables ----

// Variable to hold the current state of the state machine
static PacketReadState currentState = WAITING_FOR_HEADER;

// Buffer to store the 4 bytes of an incoming packet
// [0] = Header (0xFF)
// [1] = Servo Index (0-5)
// [2] = Angle (0-180)
// [3] = Checksum
static uint8_t packet_buffer[4];

// ---------------------------------
// ---- Public Function Implementations ----
// ---------------------------------

/**
 * @brief Initializes the RobotArm module.
 */
void robotArmInit()
{
    // Initialize the servo controller specialist
    servoController.init();

    // Set all servos to their initial angles defined in Config.h
    for (uint8_t i = 0; i < SERVO_COUNT; i++)
    {
        // setAngle() will automatically apply trim/offsets
        servoController.setAngle(i, INIT_ANGLES[i]);
    }

    // Ensure the state machine starts from the beginning
    currentState = WAITING_FOR_HEADER;
}

/**
 * @brief Processes a single byte of incoming serial data (State Machine).
 */
void processRobotArmByte(uint8_t incomingByte)
{
    // Run logic based on the current state
    switch (currentState)
    {
    /**
     * State 0: Waiting for the packet header (0xFF)
     */
    case WAITING_FOR_HEADER:
        if (incomingByte == PACKET_HEADER)
        {
            // Header found! Store it and move to the next state.
            packet_buffer[0] = incomingByte;
            currentState = READING_INDEX;
        }
        // If it's not the header, we just ignore it and stay in this state.
        break;

    /**
     * State 1: Waiting for the Servo Index
     */
    case READING_INDEX:
        // This is the 2nd byte (Servo Index)
        packet_buffer[1] = incomingByte;
        currentState = READING_ANGLE; // Move to the next state
        break;

    /**
     * State 2: Waiting for the Angle
     */
    case READING_ANGLE:
        // This is the 3rd byte (Angle)
        packet_buffer[2] = incomingByte;
        currentState = READING_CHECKSUM; // Move to the next state
        break;

    /**
     * State 3: Waiting for the Checksum (Packet is complete)
     */
    case READING_CHECKSUM:
        // This is the 4th and final byte (Checksum)
        packet_buffer[3] = incomingByte;

        // --- Packet is now complete. Time to verify. ---

        // 1. Calculate the expected checksum
        // (Header + Index + Angle), truncated to 8 bits
        uint8_t calculated_checksum = (packet_buffer[0] + packet_buffer[1] + packet_buffer[2]) & 0xFF;

        // 2. Compare calculated checksum with the received checksum
        if (calculated_checksum == packet_buffer[3])
        {
            // --- CHECKSUM PASS ---

            // 3. Get the data from the buffer
            uint8_t servoIndex = packet_buffer[1];
            uint8_t angle = packet_buffer[2];

            // 4. Final data validation (Safety Check)
            if (servoIndex < SERVO_COUNT && angle <= 180)
            {
                // --- VALIDATION PASS ---

                // 5. Execute the command
                servoController.setAngle(servoIndex, angle);

                // 6. Send "OK" back to Raspberry Pi
                Serial.println("OK");
            }
            else
            {
                // Data was valid checksum, but invalid range (e.g., servo 10)
                Serial.println("ERR: Invalid data range");
            }
        }
        else
        {
            // --- CHECKSUM FAIL ---
            // Data was corrupted in transit. Discard the packet.
            Serial.println("ERR: Checksum mismatch");
        }

        // 7. Reset the state machine to wait for the next packet header
        currentState = WAITING_FOR_HEADER;
        break;

    /**
     * Default case (should never happen)
     */
    default:
        // In case of a bug, reset the state machine
        currentState = WAITING_FOR_HEADER;
        break;
    }
}
