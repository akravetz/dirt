// Simple file logger with ISO8601 timestamps.
// Thread-safe: serializes log writes via internal mutex.
#pragma once

#include <string>
#include <mutex>

namespace dirt {

class Logger {
public:
    // Open a log file for append. If path is empty or cannot be opened,
    // logs fall back to stderr.
    explicit Logger(const std::string& path);
    ~Logger();

    // Log a line at INFO/WARN/ERROR level. Automatically prepends
    // "YYYY-MM-DDTHH:MM:SSZ LEVEL ".
    void info(const std::string& msg);
    void warn(const std::string& msg);
    void error(const std::string& msg);

private:
    void write(const char* level, const std::string& msg);

    std::string path_;
    int fd_;
    std::mutex mu_;
};

} // namespace dirt
