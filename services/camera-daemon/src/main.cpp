// dirt-camera-daemon entry point.
//
// Usage:
//   dirt-camera-daemon [--socket PATH] [--log PATH]
//
// Default socket:  $XDG_RUNTIME_DIR/dirt-camera.sock
//                  (fallback: /tmp/dirt-camera.sock if XDG_RUNTIME_DIR unset)
// Default log:     $HOME/.local/state/dirt/camera.log
//                  (auto-creates parent directory)

#include "commands.hpp"
#include "logger.hpp"
#include "sdk_wrapper.hpp"
#include "server.hpp"

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>
#include <thread>

namespace fs = std::filesystem;

namespace {

dirt::Server* g_server = nullptr;
std::atomic<bool> g_stop{false};

void on_signal(int) {
    g_stop.store(true);
    if (g_server) g_server->stop();
}

std::string default_socket_path() {
    const char* run = std::getenv("XDG_RUNTIME_DIR");
    if (run && *run) return std::string(run) + "/dirt-camera.sock";
    return "/tmp/dirt-camera.sock";
}

std::string default_log_path() {
    const char* home = std::getenv("HOME");
    if (!home || !*home) return ""; // stderr fallback
    std::string dir = std::string(home) + "/.local/state/dirt";
    std::error_code ec;
    fs::create_directories(dir, ec);
    return dir + "/camera.log";
}

} // namespace

int main(int argc, char* argv[]) {
    std::string socket_path = default_socket_path();
    std::string log_path = default_log_path();

    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--socket" && i + 1 < argc) {
            socket_path = argv[++i];
        } else if (a == "--log" && i + 1 < argc) {
            log_path = argv[++i];
        } else if (a == "--help" || a == "-h") {
            std::printf("Usage: %s [--socket PATH] [--log PATH]\n", argv[0]);
            return 0;
        } else {
            std::fprintf(stderr, "unknown arg: %s\n", a.c_str());
            return 2;
        }
    }

    dirt::Logger logger(log_path);
    logger.info("dirt-camera-daemon starting");
    logger.info("socket=" + socket_path);
    logger.info("log=" + log_path);

    dirt::SdkWrapper sdk(&logger);
    if (!sdk.start()) {
        logger.warn("no camera at startup — will retry via tick()");
    }

    dirt::CommandDispatcher dispatcher(&sdk, &logger);
    dirt::Server server(socket_path, &dispatcher, &logger);
    g_server = &server;

    if (!server.listen()) {
        logger.error("server.listen() failed, exiting");
        return 1;
    }

    // Install signal handlers AFTER server.listen() so we don't race.
    struct sigaction sa{};
    sa.sa_handler = on_signal;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT, &sa, nullptr);
    sigaction(SIGTERM, &sa, nullptr);
    // Ignore SIGPIPE from clients disconnecting mid-write.
    signal(SIGPIPE, SIG_IGN);

    // Background tick thread for hotplug reconnect.
    std::thread tick_thread([&]() {
        while (!g_stop.load()) {
            sdk.tick();
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    });

    logger.info("serving");
    server.serve();

    logger.info("shutting down");
    g_stop.store(true);
    tick_thread.join();
    sdk.stop();
    logger.info("clean exit");
    return 0;
}
