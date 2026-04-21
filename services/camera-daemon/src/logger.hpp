// Simple file logger with ISO8601 timestamps and a level threshold.
// Thread-safe: serializes log writes via internal mutex.
#pragma once

#include <string>
#include <mutex>

namespace dirt {

enum class LogLevel {
    Error = 0,
    Warn  = 1,
    Info  = 2,
    Debug = 3,
};

// Parse "error" | "warn" | "info" | "debug" (case-insensitive).
// On unknown input, returns Info and sets *ok = false if ok is non-null.
LogLevel parse_log_level(const std::string& s, bool* ok = nullptr);

class Logger {
public:
    // Open a log file for append. If path is empty or cannot be opened,
    // logs fall back to stderr. `level` is the threshold: messages more
    // verbose than this are dropped.
    explicit Logger(const std::string& path, LogLevel level = LogLevel::Info);
    ~Logger();

    // Log a line at the named level. Automatically prepends
    // "YYYY-MM-DDTHH:MM:SSZ LEVEL ".
    void error(const std::string& msg);
    void warn(const std::string& msg);
    void info(const std::string& msg);
    void debug(const std::string& msg);

private:
    void write(LogLevel level, const char* level_str, const std::string& msg);

    std::string path_;
    int fd_;
    std::mutex mu_;
    LogLevel level_;
};

} // namespace dirt
