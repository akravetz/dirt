#include "logger.hpp"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <fcntl.h>
#include <unistd.h>

namespace dirt {

Logger::Logger(const std::string& path) : path_(path), fd_(-1) {
    if (!path.empty()) {
        fd_ = ::open(path.c_str(),
                     O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC,
                     0644);
        if (fd_ < 0) {
            std::fprintf(stderr, "logger: could not open %s: %s\n",
                         path.c_str(), std::strerror(errno));
        }
    }
}

Logger::~Logger() {
    if (fd_ >= 0) ::close(fd_);
}

void Logger::write(const char* level, const std::string& msg) {
    auto now = std::chrono::system_clock::now();
    std::time_t t = std::chrono::system_clock::to_time_t(now);
    char ts[32];
    std::tm tm_utc;
    gmtime_r(&t, &tm_utc);
    std::strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &tm_utc);

    char line[1024];
    int n = std::snprintf(line, sizeof(line), "%s %s %s\n",
                          ts, level, msg.c_str());
    if (n < 0) return;
    if (n >= (int)sizeof(line)) n = sizeof(line) - 1;

    std::lock_guard<std::mutex> lock(mu_);
    int out_fd = fd_ >= 0 ? fd_ : 2; // stderr fallback
    ssize_t _ = ::write(out_fd, line, n);
    (void)_;
}

void Logger::info(const std::string& msg)  { write("INFO",  msg); }
void Logger::warn(const std::string& msg)  { write("WARN",  msg); }
void Logger::error(const std::string& msg) { write("ERROR", msg); }

} // namespace dirt
