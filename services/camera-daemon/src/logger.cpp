#include "logger.hpp"

#include <cctype>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <fcntl.h>
#include <unistd.h>

namespace dirt {

LogLevel parse_log_level(const std::string& s, bool* ok) {
    std::string lower;
    lower.reserve(s.size());
    for (char c : s) {
        lower.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }
    if (ok) *ok = true;
    if (lower == "error") return LogLevel::Error;
    if (lower == "warn")  return LogLevel::Warn;
    if (lower == "info")  return LogLevel::Info;
    if (lower == "debug") return LogLevel::Debug;
    if (ok) *ok = false;
    return LogLevel::Info;
}

Logger::Logger(const std::string& path, LogLevel level)
    : path_(path), fd_(-1), level_(level) {
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

void Logger::write(LogLevel level, const char* level_str, const std::string& msg) {
    if (static_cast<int>(level) > static_cast<int>(level_)) return;

    auto now = std::chrono::system_clock::now();
    std::time_t t = std::chrono::system_clock::to_time_t(now);
    char ts[32];
    std::tm tm_utc;
    gmtime_r(&t, &tm_utc);
    std::strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &tm_utc);

    char line[1024];
    int n = std::snprintf(line, sizeof(line), "%s %s %s\n",
                          ts, level_str, msg.c_str());
    if (n < 0) return;
    if (n >= (int)sizeof(line)) n = sizeof(line) - 1;

    std::lock_guard<std::mutex> lock(mu_);
    int out_fd = fd_ >= 0 ? fd_ : 2; // stderr fallback
    ssize_t _ = ::write(out_fd, line, n);
    (void)_;
}

void Logger::error(const std::string& msg) { write(LogLevel::Error, "ERROR", msg); }
void Logger::warn(const std::string& msg)  { write(LogLevel::Warn,  "WARN",  msg); }
void Logger::info(const std::string& msg)  { write(LogLevel::Info,  "INFO",  msg); }
void Logger::debug(const std::string& msg) { write(LogLevel::Debug, "DEBUG", msg); }

} // namespace dirt
