// v4l2 streaming + on-demand frame capture, owned by the daemon.
//
// Opens the UVC video node via v4l2, negotiates MJPG at the configured
// resolution and low framerate, and runs a background drainer thread that
// keeps the latest-decoded MJPG buffer in memory (mutex-protected). A
// capture_to_file() call copies that buffer to a JPEG tempfile under
// $XDG_RUNTIME_DIR/dirt-camera/ and sweeps anything older than ttl_seconds.
//
// Same-process coexistence with the OBSBOT SDK was proven 2026-04-15 via
// debug/obsbot_capture_probe.
#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace dirt {

class Logger;

struct CaptureResult {
    bool ok = false;
    std::string error;   // set when ok=false (e.g. "not_ready", "write_failed:...")
    std::string path;    // tempfile path
    size_t bytes = 0;
    int width = 0;
    int height = 0;
    int age_ms = 0;      // staleness of the selected frame
    int capture_ms = 0;  // wall time for capture_to_file()
};

struct CaptureConfig {
    std::string device = "/dev/webcam";
    int width = 1920;
    int height = 1080;
    int framerate = 5;          // low — bounds USB bandwidth; live feed polls every 15s
    int white_balance_k = 3000; // grow-LED spectrum fixes
    std::string tempdir;        // default: $XDG_RUNTIME_DIR/dirt-camera
    int ttl_seconds = 60;       // sweep files older than this on each capture
};

class CaptureService {
public:
    explicit CaptureService(Logger* logger);
    ~CaptureService();

    // Opens the device, starts streaming, spawns the drainer thread.
    // Returns true if streaming started. Non-blocking on first frame.
    bool start(const CaptureConfig& cfg);

    // Reverse of start(). Idempotent.
    void stop();

    // Thread-safe. Writes the latest buffered frame to a new tempfile.
    // Returns CaptureResult with ok=false and error set on failure.
    CaptureResult capture_to_file();

private:
    void drain_loop();
    bool open_device(bool verbose_errors = true);
    void close_device();
    void reconnect_device();
    void sweep_old_tempfiles();

    Logger* log_;
    CaptureConfig cfg_;

    int fd_ = -1;
    struct MappedBuf { void* start = nullptr; size_t length = 0; };
    std::vector<MappedBuf> bufs_;

    std::thread drainer_;
    std::atomic<bool> stop_{false};
    std::atomic<bool> streaming_{false};
    std::atomic<bool> have_frame_{false};

    std::mutex frame_mu_;
    std::vector<uint8_t> latest_frame_;
    std::chrono::steady_clock::time_point latest_ts_{};
};

} // namespace dirt
