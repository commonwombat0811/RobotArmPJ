// /**
//  * @file CommandParser.h
//  * @brief Interface for the CommandParser specialist.
//  * * This class is responsible for safely parsing C-style
//  * command strings (char*) into integer values.
//  */

// #ifndef COMMAND_PARSER_H
// #define COMMAND_PARSER_H

// #include <stdint.h> // Required for uint8_t type

// // Define a buffer size for parsing. Must be large enough
// // to hold a copy of the command string from Arduino.ino
// #define PARSER_BUFFER_SIZE 32

// class CommandParser
// {
// public:
//     /**
//      * @brief Parses a command string into servo index and angle.
//      * This is the main function of this class.
//      * * @param input The null-terminated C-style string (e.g., "2,90").
//      * @param servoIndex [out] Reference to store the parsed index.
//      * @param angle [out] Reference to store the parsed angle.
//      * @return true if parsing was successful, false otherwise.
//      */
//     bool parseCommand(const char *input, uint8_t &servoIndex, uint8_t &angle);

// private:
//     // Internal buffer to hold a non-const copy of the command
//     // for strtok() to modify.
//     char buffer[PARSER_BUFFER_SIZE];
// };

// #endif // COMMAND_PARSER_H
