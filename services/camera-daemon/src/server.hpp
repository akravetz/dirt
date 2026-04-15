// Unix domain socket server. Accepts connections, reads line-oriented
// requests, dispatches to CommandDispatcher, writes line-oriented responses.
//
// Single-threaded accept loop + thread-per-connection. CommandDispatcher
// holds its own mutex around SDK calls, so concurrent clients are safe
// but serialize at the SDK boundary.
#pragma once

#include <atomic>
#include <string>

namespace dirt {

class CommandDispatcher;
class Logger;

class Server {
public:
    Server(const std::string& socket_path,
           CommandDispatcher* dispatcher,
           Logger* logger);
    ~Server();

    // Create + bind socket. Returns false on error (socket path already in use
    // by a live process, permission denied, etc.). Stale socket files are
    // unlinked automatically.
    bool listen();

    // Run the accept loop until stop() is called. Blocks the calling thread.
    void serve();

    // Signal the serve() loop to exit. Safe to call from signal handler
    // (only uses async-signal-safe operations: writes to a self-pipe).
    void stop();

private:
    void handle_client(int fd);

    std::string path_;
    CommandDispatcher* dispatcher_;
    Logger* log_;
    int listen_fd_ = -1;
    int wake_rd_ = -1;
    int wake_wr_ = -1;
    std::atomic<bool> stopping_{false};
};

} // namespace dirt
