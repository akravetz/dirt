# dirt-camera-daemon

Persistent daemon wrapping the OBSBOT Tiny 2 Lite SDK. Speaks a line-oriented text protocol over a Unix socket. The `scripts/camera` CLI (or any client) sends commands in motor-frame; the daemon handles SDK lifecycle, hotplug recovery, and auto-retry for the known partial-move quirk.

## Architecture

```
┌───────────────────┐   Unix socket   ┌──────────────────────────┐
│  scripts/camera   │  ────────────▶  │  dirt-camera-daemon      │
│  (Python, thin)   │  line-oriented  │  (C++, long-lived)       │
└───────────────────┘    text proto   └──────────────────────────┘
                                               │
                                         vendor/libdev
                                               │
                                           OBSBOT
```

Responsibility split:
- **Daemon**: SDK session, motor-frame primitives, auto-retry for partial-move, hotplug.
- **CLI**: config (`~/.config/dirt/camera.json`), user-frame ↔ motor-frame translation, preset lookup.

## Wire protocol

Line-oriented; one request / one response per line.

```
ping                                    -> pong
health                                  -> ok camera_connected=<bool> uptime_s=<int>
get_state                               -> ok camera_connected=... motor_pitch=... motor_yaw=... imu_pitch=... imu_yaw=... zoom=...
resync                                  -> (same as get_state; no SDK state change)
move_motor <pitch> <yaw>                -> ok|limit_reached motor_pitch=... motor_yaw=... requested_pitch=... requested_yaw=... retries=<n> sdk_rc=<rc>
set_zoom <zoom>                         -> ok|error zoom=... requested_zoom=... zoom_capped=<bool> sdk_rc=<rc>
```

Responses when the camera is unplugged: `disconnected camera_connected=false` with whatever state the daemon has cached.

Auto-retry: `move_motor` issues the direct command, then retries up to 3 times via step-through (move to midpoint, then target) when the initial achieved position is more than 1° from the requested position. This handles the empirical "false floor" where large pitch jumps clamp at an intermediate value.

## Build

```bash
cd services/camera-daemon
./build.sh
```

Output: `./dirt-camera-daemon` (~60 KB, statically links nothing — dynamic link against vendored `libdev.so.1.0.3` via `$ORIGIN/vendor/libdev/lib` rpath).

## Run manually (for testing)

```bash
./dirt-camera-daemon                               # default socket + log paths
./dirt-camera-daemon --socket /tmp/test.sock \
                     --log /tmp/test.log
```

- Default socket: `$XDG_RUNTIME_DIR/dirt-camera.sock` (fallback `/tmp/dirt-camera.sock`)
- Default log:    `$HOME/.local/state/dirt/camera.log`

## Install as a systemd user service

```bash
# 1. Build the daemon (see above).

# 2. Install the service unit.
mkdir -p ~/.config/systemd/user
cp ../../systemd/dirt-camera.service ~/.config/systemd/user/

# 3. Enable + start (runs on user login).
systemctl --user daemon-reload
systemctl --user enable --now dirt-camera

# 4. Survive reboot even when not logged in.
sudo loginctl enable-linger $USER

# 5. Check status.
systemctl --user status dirt-camera
journalctl --user -u dirt-camera -f  # follow logs (systemd also captures stderr)
```

## Logs

Two destinations:

1. Structured app log: `~/.local/state/dirt/camera.log` — what the daemon writes via its internal logger. ISO8601 timestamps, every request/response/event.
2. SDK stderr: captured by systemd via journald. The libdev SDK prints its own `d-d:`/`d-i:` diagnostic spam to stderr.

### Log rotation

Weekly rotation, 4 weeks retained, compressed:

```bash
# Install logrotate config (it's a config file, not a cron entry).
# Then add to user crontab:
(crontab -l 2>/dev/null; echo "0 3 * * 0  /usr/sbin/logrotate -s $HOME/.local/state/dirt/logrotate.status $HOME/code/dirt/config/logrotate.conf") | crontab -
```

## Hotplug behavior

- The daemon registers the SDK's `setDevChangedCallback`.
- On disconnect: logs `hotplug: DISCONNECTED`, clears the device reference, sets `camera_connected=false`. Commands return `disconnected`.
- Periodic `tick()` (every ~1s from main) checks for re-enumeration. On reconnect, logs `acquired device: <serial>` and resumes.
- No restart needed across USB unplug/replug.

## Known behavior / quirks

- **Partial-move retry** — large pitch/yaw jumps sometimes clamp short. Daemon retries up to 3× via step-through. Exposed as `retries=<n>` in the move response.
- **Zoom cap** — Tiny 2 Lite effective max is ~2.0x. Requests above are clamped and reported as `zoom_capped=true`.
- **Mount-dependent axes** — the daemon is mount-agnostic. "Which motor direction is 'left' in the user's view" is the CLI's job (via `sign_map` in the config).

## Files

```
services/camera-daemon/
├── README.md                   # this file
├── build.sh                    # g++ invocation
├── dirt-camera-daemon          # compiled binary (gitignored; run build.sh)
├── src/
│   ├── main.cpp                # entry + signal handling
│   ├── server.{cpp,hpp}        # Unix socket server
│   ├── commands.{cpp,hpp}      # request dispatch + retry logic
│   ├── sdk_wrapper.{cpp,hpp}   # libdev wrapper + hotplug
│   └── logger.{cpp,hpp}        # file logger
└── vendor/
    └── libdev/                 # OBSBOT SDK v2.1.0_8 (vendored)
        ├── VERSION
        ├── include/dev/        # headers
        └── lib/libdev.so*      # shared libs
```

## Related docs

- `config/camera.json.example` — CLI config template (sign map, presets).
- `scripts/camera` — Python thin client.
- `debug/README.md` — historical camera calibration notes (predates the daemon).
