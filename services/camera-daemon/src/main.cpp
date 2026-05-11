// dirt-camera-daemon entry point.
//
// Usage:
//   dirt-camera-daemon [--socket PATH] [--log PATH] [--device PATH]
//                      [--log-level error|warn|info|debug]
//
// Default socket:    $XDG_RUNTIME_DIR/dirt-camera.sock
//                    (fallback: /tmp/dirt-camera.sock if XDG_RUNTIME_DIR unset)
// Default log:       $HOME/.local/state/dirt/camera.log
//                    (auto-creates parent directory)
// Default device:    /dev/webcam (overridable via DIRT_CAMERA_VIDEO_DEVICE
//                    env or --device flag).
// Default log level: info (overridable via DIRT_CAMERA_LOG_LEVEL env
//                    or --log-level flag). req/resp lines log at
//                    DEBUG and are suppressed by default — a client
//                    hammering the socket must not fill the disk.

#include "capture.hpp"
#include "commands.hpp"
#include "logger.hpp"
#include "sd_notify.hpp"
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
    std::string capture_device = "/dev/webcam";
    if (const char* env = std::getenv("DIRT_CAMERA_VIDEO_DEVICE"); env && *env) {
        capture_device = env;
    }

    dirt::LogLevel level = dirt::LogLevel::Info;
    if (const char* env = std::getenv("DIRT_CAMERA_LOG_LEVEL"); env && *env) {
        bool ok = false;
        dirt::LogLevel parsed = dirt::parse_log_level(env, &ok);
        if (ok) {
            level = parsed;
        } else {
            std::fprintf(stderr,
                "DIRT_CAMERA_LOG_LEVEL=%s not recognized; using info\n", env);
        }
    }

    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--socket" && i + 1 < argc) {
            socket_path = argv[++i];
        } else if (a == "--log" && i + 1 < argc) {
            log_path = argv[++i];
        } else if (a == "--device" && i + 1 < argc) {
            capture_device = argv[++i];
        } else if (a == "--log-level" && i + 1 < argc) {
            bool ok = false;
            dirt::LogLevel parsed = dirt::parse_log_level(argv[++i], &ok);
            if (!ok) {
                std::fprintf(stderr,
                    "--log-level: want error|warn|info|debug\n");
                return 2;
            }
            level = parsed;
        } else if (a == "--help" || a == "-h") {
            std::printf("Usage: %s [--socket PATH] [--log PATH] "
                        "[--device PATH] "
                        "[--log-level error|warn|info|debug]\n", argv[0]);
            return 0;
        } else {
            std::fprintf(stderr, "unknown arg: %s\n", a.c_str());
            return 2;
        }
    }

    dirt::notify_init();

    dirt::Logger logger(log_path, level);
    logger.info("dirt-camera-daemon starting");
    logger.info("socket=" + socket_path);
    logger.info("log=" + log_path);
    logger.info("capture_device=" + capture_device);

    dirt::SdkWrapper sdk(&logger);
    if (!sdk.start()) {
        logger.warn("no camera at startup — will retry via tick()");
    }

    dirt::CaptureService capture(&logger);
    dirt::CaptureConfig cap_cfg;  // defaults: 1920x1080, 5fps, 3000K
    cap_cfg.device = capture_device;
    if (!capture.start(cap_cfg)) {
        logger.warn("capture: start failed — `capture` command will error until restart");
    }

    dirt::CommandDispatcher dispatcher(&sdk, &capture, &logger);
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

    // Systemd watchdog heartbeat. Pings WATCHDOG=1 every 10s iff the
    // capture drain loop produced a frame within the last 15s. A stuck
    // daemon (drain spinning in error, or reconnect loop unable to
    // reacquire the device) stops pinging and systemd SIGABRTs us per
    // WatchdogSec — which counts as a failure and eventually trips
    // StartLimitBurst so we surface as `failed` instead of silently
    // half-working. No-op when NOTIFY_SOCKET is unset (dev runs).
    dirt::notify_send("READY=1");
    std::thread watchdog_thread([&]() {
        using namespace std::chrono;
        while (!g_stop.load()) {
            std::this_thread::sleep_for(10s);
            if (g_stop.load()) break;
            if (capture.last_frame_within(15s)) {
                dirt::notify_send("WATCHDOG=1");
            }
        }
    });

    logger.info("serving");
    server.serve();

    logger.info("shutting down");
    dirt::notify_send("STOPPING=1");
    g_stop.store(true);
    watchdog_thread.join();
    tick_thread.join();
    capture.stop();
    sdk.stop();
    logger.info("clean exit");
    return 0;
}
