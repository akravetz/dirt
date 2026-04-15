#include "sdk_wrapper.hpp"
#include "logger.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <thread>

#include <dev/devs.hpp>

namespace dirt {

using namespace std::chrono_literals;
using clock_type = std::chrono::steady_clock;

SdkWrapper::SdkWrapper(Logger* logger) : log_(logger) {}

SdkWrapper::~SdkWrapper() { stop(); }

void SdkWrapper::on_dev_changed_trampoline(std::string sn, bool connected, void* param) {
    auto* self = static_cast<SdkWrapper*>(param);
    if (self) self->on_dev_changed(sn, connected);
}

void SdkWrapper::on_dev_changed(const std::string& sn, bool connected) {
    if (connected) {
        if (log_) log_->info("hotplug: CONNECTED sn=" + sn);
        // Don't acquire the device here — the SDK isn't fully ready yet.
        // We'll pick it up on the next tick().
    } else {
        if (log_) log_->warn("hotplug: DISCONNECTED sn=" + sn);
        connected_.store(false);
        // Drop our device reference; the SDK's internal state
        // will re-enumerate on reconnect.
        std::lock_guard<std::mutex> lock(sdk_mu_);
        dev_.reset();
    }
}

bool SdkWrapper::try_acquire_device() {
    // Caller holds sdk_mu_.
    auto& devices = Devices::get();
    size_t n = devices.getDevNum();
    if (n == 0) return false;

    auto list = devices.getDevList();
    if (list.empty()) return false;

    dev_ = list.front();
    serial_ = dev_->devName();
    connected_.store(true);
    if (log_) log_->info("acquired device: " + serial_ +
                         " fw=" + dev_->devVersion());
    return true;
}

bool SdkWrapper::start() {
    auto& devices = Devices::get();
    devices.setDevChangedCallback(&SdkWrapper::on_dev_changed_trampoline, this);

    // Poll up to 10s for a device to appear.
    for (int i = 0; i < 100; i++) {
        std::this_thread::sleep_for(100ms);
        if (devices.getDevNum() > 0) {
            std::this_thread::sleep_for(500ms); // let device finish init
            std::lock_guard<std::mutex> lock(sdk_mu_);
            return try_acquire_device();
        }
    }
    if (log_) log_->warn("start(): no device found after 10s");
    return false;
}

void SdkWrapper::stop() {
    std::lock_guard<std::mutex> lock(sdk_mu_);
    if (dev_) {
        dev_.reset();
    }
    connected_.store(false);
    Devices::get().close();
}

bool SdkWrapper::is_connected() const {
    return connected_.load();
}

void SdkWrapper::tick() {
    // If we're disconnected but the SDK sees a device, try to re-acquire.
    if (connected_.load()) return;

    auto now = clock_type::now();
    if (now - last_reconnect_attempt_ < 5s) return;
    last_reconnect_attempt_ = now;

    std::lock_guard<std::mutex> lock(sdk_mu_);
    if (Devices::get().getDevNum() > 0) {
        try_acquire_device();
    }
}

bool SdkWrapper::get_motor_position(MotorPosition& out) {
    std::lock_guard<std::mutex> lock(sdk_mu_);
    if (!dev_) return false;
    float xyz[3] = {0};
    int rc = dev_->gimbalGetAttitudeInfoR(xyz);
    if (rc != 0) {
        if (log_) log_->warn("gimbalGetAttitudeInfoR rc=" + std::to_string(rc));
        return false;
    }
    out.roll = xyz[0];
    out.pitch = xyz[1];
    out.yaw = xyz[2];
    return true;
}

bool SdkWrapper::get_imu(ImuState& out) {
    std::lock_guard<std::mutex> lock(sdk_mu_);
    if (!dev_) return false;
    Device::AiGimbalStateInfo info;
    int rc = dev_->aiGetGimbalStateR(&info);
    if (rc != 0) {
        if (log_) log_->warn("aiGetGimbalStateR rc=" + std::to_string(rc));
        return false;
    }
    out.roll_euler = info.roll_euler;
    out.pitch_euler = info.pitch_euler;
    out.yaw_euler = info.yaw_euler;
    return true;
}

bool SdkWrapper::get_zoom(float& out) {
    std::lock_guard<std::mutex> lock(sdk_mu_);
    if (!dev_) return false;
    float z = 0;
    int rc = dev_->cameraGetZoomAbsoluteR(z);
    if (rc != 0) {
        if (log_) log_->warn("cameraGetZoomAbsoluteR rc=" + std::to_string(rc));
        return false;
    }
    out = z;
    return true;
}

MoveResult SdkWrapper::move_motor_once(float pitch, float yaw) {
    MoveResult r;
    std::lock_guard<std::mutex> lock(sdk_mu_);
    if (!dev_) {
        r.ok = false;
        return r;
    }

    // Read current position to estimate travel time.
    float before[3] = {0};
    dev_->gimbalGetAttitudeInfoR(before);

    // Issue the move. Speeds clamped to -90..+90 deg/s; 30 is a safe default.
    int rc = dev_->gimbalSetSpeedPositionR(0, pitch, yaw, 0, 30, 30);
    r.sdk_rc = rc;

    // Wait for the move to complete. At 30 deg/s, a 60° swing needs 2s;
    // add 500ms margin. Cap at 4s to avoid pathological waits.
    float dp = std::fabs(pitch - before[1]);
    float dy = std::fabs(yaw - before[2]);
    float travel_s = std::max(dp, dy) / 30.0f;
    int wait_ms = std::min(4000, std::max(500, (int)(travel_s * 1000) + 500));
    std::this_thread::sleep_for(std::chrono::milliseconds(wait_ms));

    // Read back.
    float after[3] = {0};
    dev_->gimbalGetAttitudeInfoR(after);
    r.achieved_pitch = after[1];
    r.achieved_yaw = after[2];
    r.ok = (rc == 0);
    return r;
}

ZoomResult SdkWrapper::set_zoom_once(float zoom) {
    ZoomResult r;
    std::lock_guard<std::mutex> lock(sdk_mu_);
    if (!dev_) {
        r.ok = false;
        return r;
    }
    int rc = dev_->cameraSetZoomAbsoluteR(zoom);
    r.sdk_rc = rc;

    // Brief wait for the zoom set to apply (digital zoom is fast).
    std::this_thread::sleep_for(400ms);

    float after = 0;
    dev_->cameraGetZoomAbsoluteR(after);
    r.achieved_zoom = after;
    r.ok = (rc == 0);
    return r;
}

} // namespace dirt
