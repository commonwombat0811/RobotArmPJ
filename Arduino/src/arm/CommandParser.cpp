// /**
//  * @file CommandParser.cpp
//  * @brief Implementation of the CommandParser specialist.
//  * * Uses C standard library functions (strtok, atoi) for efficient
//  * and memory-safe (no heap allocation) string parsing.
//  */

// #include "CommandParser.h"
// #include "Config.h" // For SERVO_COUNT (validation)
// #include <string.h> // For strncpy(), strtok()
// #include <stdlib.h> // For atoi()

// /**
//  * @brief Parses a command string into servo index and angle.
//  */
// bool CommandParser::parseCommand(const char *input, uint8_t &servoIndex, uint8_t &angle)
// {
//     // 1. Copy the (const) input string to our internal (non-const) buffer.
//     //    strtok() modifies the string it parses, so we must use a copy.
//     strncpy(buffer, input, PARSER_BUFFER_SIZE - 1);
//     // Ensure null-termination, as strncpy might not if src is too long
//     buffer[PARSER_BUFFER_SIZE - 1] = '\0';

//     // 2. Get the first token (part before the comma)
//     //    Example: "2,90" -> "2"
//     char *indexStr = strtok(buffer, ",");
//     if (indexStr == NULL)
//     {
//         // No comma found, or string is empty
//         return false;
//     }

//     // 3. Get the second token (part after the comma)
//     //    Example: "90"
//     char *angleStr = strtok(NULL, ","); // NULL tells strtok to continue
//     if (angleStr == NULL)
//     {
//         // Comma was found, but nothing after it (e.g., "2,")
//         return false;
//     }

//     // 4. Convert tokens (text) to integers
//     //    atoi (ASCII to Integer) is fast. It returns 0 for invalid text (e.g., "abc").
//     long rawIndex = atol(indexStr); // Use atol for wider range checking
//     long rawAngle = atol(angleStr);

//     // 5. Validation (First safety check)

//     // Check index bounds (e.g., 0 to 5 for SERVO_COUNT 6)
//     if (rawIndex < 0 || rawIndex >= SERVO_COUNT)
//     {
//         return false; // Invalid servo index
//     }

//     // Check angle bounds (0 to 180)
//     if (rawAngle < 0 || rawAngle > 180)
//     {
//         return false; // Invalid angle
//     }

//     // (Note: atoi("abc") == 0, which is a valid angle/index.
//     // This is a tradeoff for speed. "0,90" is a valid command.)

//     // 6. Parsing successful. Store results in the output parameters.
//     servoIndex = (uint8_t)rawIndex;
//     angle = (uint8_t)rawAngle;

//     return true;
// }
