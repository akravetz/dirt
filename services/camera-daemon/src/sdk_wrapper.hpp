// Thread-safe wrapper around the OBSBOT libdev SDK.
// Owns the device session. Serializes all SDK calls via an internal mutex.
// Handles hotplug: tracks a connected flag, re-attaches on device-added events.
//
// All motor angles are in degrees. Pitch/yaw motor ranges are mount-dependent;
// the SDK silently clamps out-of-range commands. Use readback to verify.
#pragma once

#include <atomic>
#include <chrono>
#include <memory>
#include <mutex>
#include <string>

// Forward declarations so we don't pull the giant dev.hpp into headers.
class Device;

namespace dirt {

class Logger;

struct MotorPosition {
    float pitch = 0;
    float yaw = 0;
    float roll = 0;
};

struct ImuState {
    float pitch_euler = 0;
    float yaw_euler = 0;
    float roll_euler = 0;
};

struct MoveResult {
    bool ok = false;          // command reached the SDK at all
    float achieved_pitch = 0; // readback pitch
    float achieved_yaw = 0;   // readback yaw
    int sdk_rc = 0;           // raw SDK return code
};

struct ZoomResult {
    bool ok = false;
    float achieved_zoom = 0;
    int sdk_rc = 0;
};

class SdkWrapper {
public:
    explicit SdkWrapper(Logger* logger);
    ~SdkWrapper();

    // Starts SDK discovery, polls for up to 10s for a device to appear.
    // Returns true if a device is attached at return time.
    bool start();

    // Release the device and close the SDK. Idempotent.
    void stop();

    // True if a device is currently attached and usable.
    bool is_connected() const;

    // Fetch current motor angles (pitch, yaw, roll). Returns false if not connected.
    bool get_motor_position(MotorPosition& out);

    // Fetch current IMU euler angles. Returns false if not connected.
    bool get_imu(ImuState& out);

    // Fetch current zoom level (1.0–2.0 effective on Tiny 2 Lite).
    bool get_zoom(float& out);

    // Issue a single SDK move_to(pitch, yaw). Blocks until the move
    // should be complete (uses a distance-proportional wait) and returns
    // the readback in MoveResult.
    // Does NOT implement retry or step-through — that's commands.cpp's job.
    MoveResult move_motor_once(float pitch, float yaw);

    // Issue a single SDK set_zoom. Blocks briefly for the set to apply.
    ZoomResult set_zoom_once(float zoom);

    // Ticks called periodically from the main loop (every ~1s). Checks
    // the connected flag and retries reconnect on disconnect.
    void tick();

private:
    // Called from the SDK's hotplug thread — must not block.
    static void on_dev_changed_trampoline(std::string sn, bool connected, void* param);
    void on_dev_changed(const std::string& sn, bool connected);

    // Returns true if a device was successfully acquired.
    bool try_acquire_device();

    Logger* log_;
    std::mutex sdk_mu_;                     // serializes all SDK calls
    std::atomic<bool> connected_{false};    // set from hotplug cb + explicit checks
    std::shared_ptr<Device> dev_;           // held inside sdk_mu_
    std::string serial_;
    std::chrono::steady_clock::time_point last_reconnect_attempt_{};
};

} // namespace dirt
