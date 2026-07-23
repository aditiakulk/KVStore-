#pragma once

#include <string>
#include <sstream>
#include <vector>

// dead simple line protocol, not RESP:
//   SET <key> <value>\n   -> +OK\n
//   GET <key>\n           -> +<value>\n   or   -NOTFOUND\n
//   DEL <key>\n           -> +OK\n         or   -NOTFOUND\n

struct Command {
    enum class Type { GET, SET, DEL, UNKNOWN } type = Type::UNKNOWN;
    std::string key;
    std::string value;
};

inline Command parse_command(const std::string& line) {
    std::istringstream iss(line);
    std::string op;
    iss >> op;

    Command cmd;
    if (op == "GET") {
        cmd.type = Command::Type::GET;
        iss >> cmd.key;
    } else if (op == "SET") {
        cmd.type = Command::Type::SET;
        iss >> cmd.key;
        std::getline(iss, cmd.value);
        if (!cmd.value.empty() && cmd.value[0] == ' ') cmd.value.erase(0, 1);
    } else if (op == "DEL") {
        cmd.type = Command::Type::DEL;
        iss >> cmd.key;
    }
    return cmd;
}
