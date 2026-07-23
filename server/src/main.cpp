#include <iostream>
#include <thread>
#include <cstring>
#include <csignal>
#include <atomic>

#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>

#include "striped_hashmap.h"
#include "protocol.h"

// thread-per-connection server. simple but works fine for this scale --
// production version would use epoll + a thread pool instead of spawning
// a thread per client.

static std::atomic<bool> running{true};

void handle_signal(int) { running = false; }

void handle_client(int client_fd, StripedHashMap& store) {
    char buffer[4096];
    std::string leftover;

    while (running) {
        ssize_t n = read(client_fd, buffer, sizeof(buffer) - 1);
        if (n <= 0) break;
        buffer[n] = '\0';
        leftover += buffer;

        size_t pos;
        while ((pos = leftover.find('\n')) != std::string::npos) {
            std::string line = leftover.substr(0, pos);
            leftover.erase(0, pos + 1);
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (line.empty()) continue;

            Command cmd = parse_command(line);
            std::string response;

            switch (cmd.type) {
                case Command::Type::SET:
                    store.set(cmd.key, cmd.value);
                    response = "+OK\n";
                    break;
                case Command::Type::GET: {
                    auto val = store.get(cmd.key);
                    response = val ? ("+" + *val + "\n") : "-NOTFOUND\n";
                    break;
                }
                case Command::Type::DEL:
                    response = store.remove(cmd.key) ? "+OK\n" : "-NOTFOUND\n";
                    break;
                default:
                    response = "-ERR unknown command\n";
            }
            write(client_fd, response.c_str(), response.size());
        }
    }
    close(client_fd);
}

int main(int argc, char** argv) {
    int port = argc > 1 ? std::atoi(argv[1]) : 7070;
    size_t num_stripes = argc > 2 ? std::atoi(argv[2]) : 64;

    signal(SIGINT, handle_signal);
    signal(SIGTERM, handle_signal);

    StripedHashMap store(num_stripes);

    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        std::cerr << "Failed to create socket\n";
        return 1;
    }

    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);

    if (bind(server_fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
        std::cerr << "Bind failed on port " << port << "\n";
        return 1;
    }

    if (listen(server_fd, 128) < 0) {
        std::cerr << "Listen failed\n";
        return 1;
    }

    std::cout << "kv-node listening on port " << port
              << " with " << num_stripes << " stripes\n";

    std::vector<std::thread> workers;
    while (running) {
        sockaddr_in client_addr{};
        socklen_t client_len = sizeof(client_addr);
        int client_fd = accept(server_fd, (sockaddr*)&client_addr, &client_len);
        if (client_fd < 0) {
            if (!running) break;
            continue;
        }
        workers.emplace_back(handle_client, client_fd, std::ref(store));
        workers.back().detach();
    }

    close(server_fd);
    std::cout << "kv-node shutting down\n";
    return 0;
}
