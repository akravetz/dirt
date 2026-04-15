#include "server.hpp"
#include "commands.hpp"
#include "logger.hpp"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <string>
#include <thread>

#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

namespace dirt {

namespace {

// Try a zero-byte connect to check if another process is listening.
bool socket_is_live(const std::string& path) {
    int fd = ::socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (fd < 0) return false;
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    std::strncpy(addr.sun_path, path.c_str(), sizeof(addr.sun_path) - 1);
    bool live = (::connect(fd, (sockaddr*)&addr, sizeof(addr)) == 0);
    ::close(fd);
    return live;
}

ssize_t write_all(int fd, const void* buf, size_t n) {
    const char* p = (const char*)buf;
    size_t left = n;
    while (left > 0) {
        ssize_t w = ::write(fd, p, left);
        if (w < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        p += w;
        left -= (size_t)w;
    }
    return (ssize_t)n;
}

} // namespace

Server::Server(const std::string& socket_path,
               CommandDispatcher* dispatcher,
               Logger* logger)
    : path_(socket_path), dispatcher_(dispatcher), log_(logger) {}

Server::~Server() {
    if (listen_fd_ >= 0) ::close(listen_fd_);
    if (wake_rd_ >= 0) ::close(wake_rd_);
    if (wake_wr_ >= 0) ::close(wake_wr_);
    if (!path_.empty()) ::unlink(path_.c_str());
}

bool Server::listen() {
    // Self-pipe for waking serve() on stop().
    int pipefd[2];
    if (::pipe2(pipefd, O_CLOEXEC | O_NONBLOCK) != 0) {
        if (log_) log_->error(std::string("pipe2 failed: ") + std::strerror(errno));
        return false;
    }
    wake_rd_ = pipefd[0];
    wake_wr_ = pipefd[1];

    // Handle stale socket.
    struct stat st;
    if (::stat(path_.c_str(), &st) == 0) {
        if (socket_is_live(path_)) {
            if (log_) log_->error("socket " + path_ + " is live (another daemon running?)");
            return false;
        }
        if (log_) log_->warn("unlinking stale socket: " + path_);
        ::unlink(path_.c_str());
    }

    listen_fd_ = ::socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (listen_fd_ < 0) {
        if (log_) log_->error(std::string("socket() failed: ") + std::strerror(errno));
        return false;
    }

    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    std::strncpy(addr.sun_path, path_.c_str(), sizeof(addr.sun_path) - 1);

    if (::bind(listen_fd_, (sockaddr*)&addr, sizeof(addr)) != 0) {
        if (log_) log_->error(std::string("bind() failed: ") + std::strerror(errno));
        return false;
    }
    // 0600 perms — local user only.
    ::chmod(path_.c_str(), 0600);

    if (::listen(listen_fd_, 16) != 0) {
        if (log_) log_->error(std::string("listen() failed: ") + std::strerror(errno));
        return false;
    }
    if (log_) log_->info("listening on " + path_);
    return true;
}

void Server::serve() {
    while (!stopping_.load()) {
        pollfd pfds[2];
        pfds[0].fd = listen_fd_; pfds[0].events = POLLIN;
        pfds[1].fd = wake_rd_;   pfds[1].events = POLLIN;

        int rc = ::poll(pfds, 2, -1);
        if (rc < 0) {
            if (errno == EINTR) continue;
            if (log_) log_->error(std::string("poll() failed: ") + std::strerror(errno));
            break;
        }
        if (pfds[1].revents & POLLIN) break; // stop signal

        if (pfds[0].revents & POLLIN) {
            int cfd = ::accept4(listen_fd_, nullptr, nullptr, SOCK_CLOEXEC);
            if (cfd < 0) {
                if (errno == EINTR || errno == EAGAIN) continue;
                if (log_) log_->warn(std::string("accept4 failed: ") + std::strerror(errno));
                continue;
            }
            std::thread(&Server::handle_client, this, cfd).detach();
        }
    }
    if (log_) log_->info("serve loop exited");
}

void Server::stop() {
    stopping_.store(true);
    if (wake_wr_ >= 0) {
        char c = '.';
        ssize_t _ = ::write(wake_wr_, &c, 1);
        (void)_;
    }
}

void Server::handle_client(int fd) {
    std::string buf;
    buf.reserve(1024);
    char chunk[512];

    while (true) {
        ssize_t n = ::read(fd, chunk, sizeof(chunk));
        if (n <= 0) break;
        buf.append(chunk, (size_t)n);

        // Process complete lines.
        size_t pos;
        while ((pos = buf.find('\n')) != std::string::npos) {
            std::string line = buf.substr(0, pos);
            buf.erase(0, pos + 1);

            // Strip trailing CR if any.
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (line.empty()) continue;

            std::string resp = dispatcher_->dispatch(line);
            resp += "\n";
            if (write_all(fd, resp.data(), resp.size()) < 0) {
                if (log_) log_->warn("client write failed, closing");
                ::close(fd);
                return;
            }
        }
    }
    ::close(fd);
}

} // namespace dirt
