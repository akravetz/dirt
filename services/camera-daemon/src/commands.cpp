#include "commands.hpp"
#include "capture.hpp"
#include "logger.hpp"
#include "sdk_wrapper.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <sstream>
#include <string>
#include <vector>

namespace dirt {

namespace {

constexpr float TOLERANCE_DEG = 1.0f;
constexpr int MAX_RETRIES = 3;

std::vector<std::string> split_ws(const std::string& s) {
    std::vector<std::string> out;
    std::istringstream iss(s);
    std::string tok;
    while (iss >> tok) out.push_back(tok);
    return out;
}

std::string fmt_float(float v) {
    char buf[32];
    std::snprintf(buf, sizeof(buf), "%.2f", v);
    return buf;
}

} // anonymous namespace

CommandDispatcher::CommandDispatcher(SdkWrapper* sdk, CaptureService* capture, Logger* logger)
    : sdk_(sdk), capture_(capture), log_(logger),
      started_at_(std::chrono::steady_clock::now()) {}

std::string CommandDispatcher::error(const std::string& msg) {
    return "error msg=" + msg;
}

std::string CommandDispatcher::format_state_tail() {
    MotorPosition mp;
    ImuState imu;
    float zoom = 0;
    bool have_motor = sdk_->get_motor_position(mp);
    bool have_imu   = sdk_->get_imu(imu);
    bool have_zoom  = sdk_->get_zoom(zoom);

    std::string s;
    s += " camera_connected=" + std::string(sdk_->is_connected() ? "true" : "false");
    if (have_motor) {
        s += " motor_pitch=" + fmt_float(mp.pitch);
        s += " motor_yaw="   + fmt_float(mp.yaw);
    }
    if (have_imu) {
        s += " imu_pitch="   + fmt_float(imu.pitch_euler);
        s += " imu_yaw="     + fmt_float(imu.yaw_euler);
    }
    if (have_zoom) {
        s += " zoom=" + fmt_float(zoom);
    }
    return s;
}

std::string CommandDispatcher::handle_ping() {
    return "pong";
}

std::string CommandDispatcher::handle_health() {
    auto uptime = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::steady_clock::now() - started_at_).count();
    std::string s = "ok camera_connected=";
    s += sdk_->is_connected() ? "true" : "false";
    s += " uptime_s=" + std::to_string(uptime);
    return s;
}

std::string CommandDispatcher::handle_get_state() {
    if (!sdk_->is_connected()) {
        return "disconnected" + format_state_tail();
    }
    return "ok" + format_state_tail();
}

std::string CommandDispatcher::handle_resync() {
    // Re-read everything; no SDK state change.
    return handle_get_state();
}

std::string CommandDispatcher::handle_move_motor(float target_pitch, float target_yaw) {
    if (!sdk_->is_connected()) {
        return "disconnected" + format_state_tail();
    }

    int retries = 0;
    int last_rc = 0;

    // Attempt 1: direct move to target.
    MoveResult r = sdk_->move_motor_once(target_pitch, target_yaw);
    last_rc = r.sdk_rc;
    float cur_pitch = r.achieved_pitch;
    float cur_yaw   = r.achieved_yaw;

    // If the direct move fell short (partial-move quirk, false floor), step through.
    // Each retry: move to the midpoint between current and target to "unstick"
    // the gimbal, then re-issue the direct target move.
    while ((std::fabs(target_pitch - cur_pitch) > TOLERANCE_DEG ||
            std::fabs(target_yaw   - cur_yaw)   > TOLERANCE_DEG) &&
           retries < MAX_RETRIES) {
        retries++;

        float mid_pitch = (cur_pitch + target_pitch) * 0.5f;
        float mid_yaw   = (cur_yaw   + target_yaw)   * 0.5f;
        sdk_->move_motor_once(mid_pitch, mid_yaw);

        MoveResult r2 = sdk_->move_motor_once(target_pitch, target_yaw);
        last_rc = r2.sdk_rc;
        cur_pitch = r2.achieved_pitch;
        cur_yaw   = r2.achieved_yaw;
    }

    float dp = std::fabs(target_pitch - cur_pitch);
    float dy = std::fabs(target_yaw - cur_yaw);
    std::string status = (dp <= TOLERANCE_DEG && dy <= TOLERANCE_DEG)
        ? "ok" : "limit_reached";

    std::string s = status;
    s += " motor_pitch=" + fmt_float(cur_pitch);
    s += " motor_yaw="   + fmt_float(cur_yaw);
    s += " requested_pitch=" + fmt_float(target_pitch);
    s += " requested_yaw="   + fmt_float(target_yaw);
    s += " retries=" + std::to_string(retries);
    s += " sdk_rc=" + std::to_string(last_rc);
    return s;
}

std::string CommandDispatcher::handle_capture() {
    if (!capture_) return error("capture_not_initialized");
    CaptureResult r = capture_->capture_to_file();
    if (!r.ok) return "error " + r.error;
    std::string s = "ok path=" + r.path;
    s += " bytes=" + std::to_string(r.bytes);
    s += " width=" + std::to_string(r.width);
    s += " height=" + std::to_string(r.height);
    s += " age_ms=" + std::to_string(r.age_ms);
    s += " capture_ms=" + std::to_string(r.capture_ms);
    return s;
}

std::string CommandDispatcher::handle_set_zoom(float target) {
    if (!sdk_->is_connected()) {
        return "disconnected" + format_state_tail();
    }
    // Soft-clamp to [1.0, 2.0] (Tiny 2 Lite effective range).
    float clamped = std::clamp(target, 1.0f, 2.0f);
    bool capped = (clamped != target);

    ZoomResult r = sdk_->set_zoom_once(clamped);
    std::string status = r.ok ? "ok" : "error";
    std::string s = status;
    s += " zoom=" + fmt_float(r.achieved_zoom);
    s += " requested_zoom=" + fmt_float(target);
    s += " zoom_capped=" + std::string(capped ? "true" : "false");
    s += " sdk_rc=" + std::to_string(r.sdk_rc);
    return s;
}

std::string CommandDispatcher::dispatch(const std::string& line) {
    if (log_) log_->info("req: " + line);

    auto toks = split_ws(line);
    if (toks.empty()) return "";

    std::string resp;
    try {
        if (toks[0] == "ping") {
            resp = handle_ping();
        } else if (toks[0] == "health") {
            resp = handle_health();
        } else if (toks[0] == "get_state") {
            resp = handle_get_state();
        } else if (toks[0] == "resync") {
            resp = handle_resync();
        } else if (toks[0] == "move_motor") {
            if (toks.size() != 3) {
                resp = error("usage_move_motor_pitch_yaw");
            } else {
                float p = std::stof(toks[1]);
                float y = std::stof(toks[2]);
                resp = handle_move_motor(p, y);
            }
        } else if (toks[0] == "set_zoom") {
            if (toks.size() != 2) {
                resp = error("usage_set_zoom_value");
            } else {
                float z = std::stof(toks[1]);
                resp = handle_set_zoom(z);
            }
        } else if (toks[0] == "capture") {
            resp = handle_capture();
        } else {
            resp = error("unknown_op_" + toks[0]);
        }
    } catch (const std::exception& e) {
        resp = error(std::string("exception_") + e.what());
    }

    if (log_) log_->info("resp: " + resp);
    return resp;
}

} // namespace dirt
