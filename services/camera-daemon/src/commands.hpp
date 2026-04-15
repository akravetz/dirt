// Command dispatcher: parses text requests, calls into SdkWrapper, formats text responses.
//
// Protocol (line-oriented, one request / one response per line):
//
//   ping                              -> pong
//   health                            -> ok camera_connected=<bool> uptime_s=<int>
//   resync                            -> ok motor_pitch=... motor_yaw=... zoom=...
//   get_state                         -> ok motor_pitch=... motor_yaw=... imu_pitch=... imu_yaw=... zoom=... camera_connected=...
//   move_motor <pitch> <yaw>          -> ok|limit_reached|disconnected|error motor_pitch=... motor_yaw=... retries=<int> sdk_rc=<int>
//   set_zoom <zoom>                   -> ok|error zoom=... sdk_rc=<int>
//   capture                           -> ok path=<abspath> bytes=<N> width=<W> height=<H> age_ms=<M> capture_ms=<D>
//                                     -> error <reason>
//
// move_motor implements auto-retry with step-through: if the achieved position
// differs from commanded by more than 1°, the dispatcher retries by stepping
// through intermediate waypoints. Empirically, commanding a large pitch jump
// without stepping through a waypoint sometimes lands short. Up to MAX_RETRIES
// retries; final status is "limit_reached" if we can't close the gap.
#pragma once

#include <chrono>
#include <string>

namespace dirt {

class SdkWrapper;
class CaptureService;
class Logger;

class CommandDispatcher {
public:
    CommandDispatcher(SdkWrapper* sdk, CaptureService* capture, Logger* logger);

    // Parse and execute a single line. Returns the response line (no trailing newline).
    // Empty input returns empty output. Never throws.
    std::string dispatch(const std::string& line);

private:
    std::string handle_ping();
    std::string handle_health();
    std::string handle_get_state();
    std::string handle_resync();
    std::string handle_move_motor(float pitch, float yaw);
    std::string handle_set_zoom(float zoom);
    std::string handle_capture();

    std::string format_state_tail();
    std::string error(const std::string& msg);

    SdkWrapper* sdk_;
    CaptureService* capture_;
    Logger* log_;
    std::chrono::steady_clock::time_point started_at_;
};

} // namespace dirt
