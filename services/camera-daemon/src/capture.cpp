#include "capture.hpp"
#include "logger.hpp"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>

#include <dirent.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <sys/stat.h>
#include <unistd.h>

namespace fs = std::filesystem;
using namespace std::chrono;

namespace dirt {
namespace {

int xioctl(int fd, unsigned long req, void* arg) {
    int r;
    do { r = ioctl(fd, req, arg); } while (r == -1 && errno == EINTR);
    return r;
}

std::string default_tempdir() {
    const char* run = std::getenv("XDG_RUNTIME_DIR");
    if (run && *run) return std::string(run) + "/dirt-camera";
    return "/tmp/dirt-camera";
}

} // namespace

CaptureService::CaptureService(Logger* logger) : log_(logger) {}

CaptureService::~CaptureService() { stop(); }

bool CaptureService::start(const CaptureConfig& cfg) {
    cfg_ = cfg;
    if (cfg_.tempdir.empty()) cfg_.tempdir = default_tempdir();

    std::error_code ec;
    fs::create_directories(cfg_.tempdir, ec);
    if (ec) {
        if (log_) log_->error("capture: mkdir " + cfg_.tempdir + ": " + ec.message());
        return false;
    }

    if (!open_device()) return false;

    stop_.store(false);
    drainer_ = std::thread(&CaptureService::drain_loop, this);
    return true;
}

bool CaptureService::open_device(bool verbose_errors) {
    fd_ = ::open(cfg_.device.c_str(), O_RDWR | O_NONBLOCK, 0);
    if (fd_ < 0) {
        if (verbose_errors && log_) log_->error("capture: open " + cfg_.device + ": " +
                              std::strerror(errno));
        return false;
    }

    v4l2_format fmt = {};
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width = cfg_.width;
    fmt.fmt.pix.height = cfg_.height;
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
    fmt.fmt.pix.field = V4L2_FIELD_NONE;
    if (xioctl(fd_, VIDIOC_S_FMT, &fmt) < 0) {
        if (verbose_errors && log_) log_->error("capture: VIDIOC_S_FMT: " +
                              std::string(std::strerror(errno)));
        close_device();
        return false;
    }
    if (fmt.fmt.pix.pixelformat != V4L2_PIX_FMT_MJPEG) {
        if (verbose_errors && log_) log_->error("capture: driver did not grant MJPG");
        close_device();
        return false;
    }
    cfg_.width = fmt.fmt.pix.width;
    cfg_.height = fmt.fmt.pix.height;

    // Manual WB — grow-LED spectrum breaks AWB. Failures are non-fatal.
    v4l2_control ctrl = {};
    ctrl.id = V4L2_CID_AUTO_WHITE_BALANCE;
    ctrl.value = 0;
    if (xioctl(fd_, VIDIOC_S_CTRL, &ctrl) < 0) {
        if (log_) log_->warn("capture: disable AUTO_WB failed (ignoring)");
    }
    ctrl = {};
    ctrl.id = V4L2_CID_WHITE_BALANCE_TEMPERATURE;
    ctrl.value = cfg_.white_balance_k;
    if (xioctl(fd_, VIDIOC_S_CTRL, &ctrl) < 0) {
        if (log_) log_->warn("capture: set WB temperature failed (ignoring)");
    }

    // Framerate
    v4l2_streamparm parm = {};
    parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    parm.parm.capture.timeperframe.numerator = 1;
    parm.parm.capture.timeperframe.denominator = cfg_.framerate;
    if (xioctl(fd_, VIDIOC_S_PARM, &parm) < 0) {
        if (log_) log_->warn("capture: VIDIOC_S_PARM failed (driver default fps)");
    }

    v4l2_requestbuffers req = {};
    req.count = 4;
    req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    if (xioctl(fd_, VIDIOC_REQBUFS, &req) < 0) {
        if (verbose_errors && log_) log_->error("capture: VIDIOC_REQBUFS: " +
                              std::string(std::strerror(errno)));
        close_device();
        return false;
    }

    bufs_.resize(req.count);
    for (unsigned i = 0; i < req.count; i++) {
        v4l2_buffer b = {};
        b.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        b.memory = V4L2_MEMORY_MMAP;
        b.index = i;
        if (xioctl(fd_, VIDIOC_QUERYBUF, &b) < 0) {
            if (verbose_errors && log_) log_->error("capture: VIDIOC_QUERYBUF");
            close_device();
            return false;
        }
        bufs_[i].length = b.length;
        bufs_[i].start = mmap(nullptr, b.length, PROT_READ | PROT_WRITE,
                              MAP_SHARED, fd_, b.m.offset);
        if (bufs_[i].start == MAP_FAILED) {
            if (verbose_errors && log_) log_->error("capture: mmap failed");
            close_device();
            return false;
        }
        if (xioctl(fd_, VIDIOC_QBUF, &b) < 0) {
            if (verbose_errors && log_) log_->error("capture: VIDIOC_QBUF");
            close_device();
            return false;
        }
    }

    int type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (xioctl(fd_, VIDIOC_STREAMON, &type) < 0) {
        if (verbose_errors && log_) log_->error("capture: VIDIOC_STREAMON: " +
                              std::string(std::strerror(errno)));
        close_device();
        return false;
    }
    streaming_.store(true);

    if (log_) log_->info("capture: streaming " +
        std::to_string(cfg_.width) + "x" + std::to_string(cfg_.height) +
        " MJPG @ " + std::to_string(cfg_.framerate) + "fps, wb=" +
        std::to_string(cfg_.white_balance_k) + "K, tempdir=" + cfg_.tempdir);
    return true;
}

void CaptureService::close_device() {
    if (streaming_.load()) {
        int type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        xioctl(fd_, VIDIOC_STREAMOFF, &type);
        streaming_.store(false);
    }
    for (auto& b : bufs_) {
        if (b.start && b.start != MAP_FAILED) munmap(b.start, b.length);
    }
    bufs_.clear();
    if (fd_ >= 0) { ::close(fd_); fd_ = -1; }
}

// Release the current (bad) fd and retry open_device() with backoff until
// the device comes back or the service is asked to stop. Called from the
// drainer on any non-transient select/DQBUF failure (e.g. ENODEV when USB
// re-enumerates). Without this, a USB glitch leaves a stale fd and the
// drain loop hot-spins logging the same errno forever — see the 410GB
// incident on 2026-04-22.
void CaptureService::reconnect_device() {
    close_device();
    have_frame_.store(false);

    int attempts = 0;
    while (!stop_.load()) {
        std::this_thread::sleep_for(seconds(2));
        // Silent retries after the first; on recovery we log once below.
        if (open_device(/*verbose_errors=*/attempts == 0)) {
            if (log_) log_->info("capture: reacquired " + cfg_.device +
                                 " after " + std::to_string(attempts + 1) +
                                 " attempt(s)");
            return;
        }
        attempts++;
    }
}

void CaptureService::stop() {
    stop_.store(true);
    if (drainer_.joinable()) drainer_.join();
    close_device();
    std::lock_guard<std::mutex> lock(frame_mu_);
    latest_frame_.clear();
    have_frame_.store(false);
}

void CaptureService::drain_loop() {
    while (!stop_.load()) {
        if (!streaming_.load()) {
            std::this_thread::sleep_for(milliseconds(100));
            continue;
        }

        fd_set fds; FD_ZERO(&fds); FD_SET(fd_, &fds);
        timeval tv{1, 0};
        int r = select(fd_ + 1, &fds, nullptr, nullptr, &tv);
        if (r < 0) {
            if (errno == EINTR) continue;
            if (log_) log_->warn("capture: select: " +
                                 std::string(std::strerror(errno)) +
                                 " — resetting device");
            reconnect_device();
            continue;
        }
        if (r == 0) continue;  // timeout; loop check stop_

        v4l2_buffer b = {};
        b.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        b.memory = V4L2_MEMORY_MMAP;
        if (xioctl(fd_, VIDIOC_DQBUF, &b) < 0) {
            if (errno == EAGAIN) continue;
            if (log_) log_->warn("capture: VIDIOC_DQBUF: " +
                                 std::string(std::strerror(errno)) +
                                 " — resetting device");
            reconnect_device();
            continue;
        }

        {
            std::lock_guard<std::mutex> lock(frame_mu_);
            const uint8_t* src = static_cast<const uint8_t*>(bufs_[b.index].start);
            latest_frame_.assign(src, src + b.bytesused);
            latest_ts_ = steady_clock::now();
        }
        have_frame_.store(true);

        xioctl(fd_, VIDIOC_QBUF, &b);
    }
}

CaptureResult CaptureService::capture_to_file() {
    auto t0 = steady_clock::now();
    CaptureResult r;

    if (!streaming_.load()) {
        r.error = "stream_not_running";
        return r;
    }
    if (!have_frame_.load()) {
        r.error = "not_ready";
        return r;
    }

    std::vector<uint8_t> buf;
    steady_clock::time_point ts;
    {
        std::lock_guard<std::mutex> lock(frame_mu_);
        buf = latest_frame_;
        ts = latest_ts_;
    }

    r.age_ms = static_cast<int>(
        duration_cast<milliseconds>(steady_clock::now() - ts).count());

    // Unique path via monotonic clock.
    uint64_t mono_ns = duration_cast<nanoseconds>(
        steady_clock::now().time_since_epoch()).count();
    std::string path = cfg_.tempdir + "/cap-" + std::to_string(mono_ns) + ".jpg";
    std::string tmp_path = path + ".tmp";

    // Atomic write: write to .tmp, rename into place.
    {
        FILE* f = std::fopen(tmp_path.c_str(), "wb");
        if (!f) {
            r.error = std::string("open_failed:") + std::strerror(errno);
            return r;
        }
        size_t w = std::fwrite(buf.data(), 1, buf.size(), f);
        std::fclose(f);
        if (w != buf.size()) {
            ::unlink(tmp_path.c_str());
            r.error = "write_short";
            return r;
        }
    }
    if (std::rename(tmp_path.c_str(), path.c_str()) != 0) {
        ::unlink(tmp_path.c_str());
        r.error = std::string("rename_failed:") + std::strerror(errno);
        return r;
    }

    sweep_old_tempfiles();

    r.ok = true;
    r.path = path;
    r.bytes = buf.size();
    r.width = cfg_.width;
    r.height = cfg_.height;
    r.capture_ms = static_cast<int>(
        duration_cast<milliseconds>(steady_clock::now() - t0).count());
    return r;
}

void CaptureService::sweep_old_tempfiles() {
    DIR* d = opendir(cfg_.tempdir.c_str());
    if (!d) return;
    time_t cutoff = time(nullptr) - cfg_.ttl_seconds;
    int swept = 0;
    dirent* e;
    while ((e = readdir(d)) != nullptr) {
        if (e->d_name[0] == '.') continue;
        std::string p = cfg_.tempdir + "/" + e->d_name;
        struct stat st;
        if (stat(p.c_str(), &st) != 0) continue;
        if (st.st_mtime < cutoff) {
            if (::unlink(p.c_str()) == 0) swept++;
        }
    }
    closedir(d);
    if (swept && log_) log_->info("capture: swept " + std::to_string(swept) +
                                  " old tempfiles");
}

} // namespace dirt
