// Minimal sd_notify(3) subset for Type=notify service integration.
// Avoids a libsystemd link dependency — the protocol is just a datagram
// to $NOTIFY_SOCKET. No-op when NOTIFY_SOCKET is unset (e.g. running
// the daemon outside systemd for dev/debug).
#pragma once

#include <string>

namespace dirt {

// One-time init. Safe to call unconditionally; logs nothing.
void notify_init();

// Send a notify message. Common payloads:
//   "READY=1"             — once, after the daemon can serve requests
//   "WATCHDOG=1"          — periodically, < WatchdogSec apart
//   "STATUS=<free text>"  — human-readable status (optional)
//   "STOPPING=1"          — once, on graceful shutdown (optional)
void notify_send(const std::string& msg);

} // namespace dirt
