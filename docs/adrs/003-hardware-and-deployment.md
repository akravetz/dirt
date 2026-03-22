# ADR 003: Hardware and Deployment Decisions

## Status

Accepted

## Context

We need to pin down the runtime environment, capture method, secrets management, and network assumptions before writing application code.

## Decision

**Runtime environment:** x86_64 Intel i5-12500T (6-core, 12-thread), Debian-based Linux. Application runs directly on the host — no containers.

**Webcam:** Logitech C920 Pro HD at `/dev/video0`. Captured via OpenCV (`cv2`) using V4L2 backend. Periodic snapshots (not video streaming).

**Sensors:** TBD — hardware not yet available. Architecture will include a sensor service interface so the implementation can be plugged in later.

**Authentication:** Single-user, credentials stored in `.env` file managed by `direnv`. `python-dotenv` loads them at runtime. `.env` is gitignored; `.env.example` is committed with placeholder values.

**Network:** Local network only. No TLS, no public exposure. Auth is a convenience barrier, not a security boundary.

## Consequences

- OpenCV adds a large dependency (~50MB) but is well-supported on x86_64 and handles the C920 reliably.
- No containerization means simpler deployment but manual dependency management on the host.
- Local-only network means we can skip TLS and use simple session auth without hardening concerns.
- Sensor interface must be designed before hardware arrives so we can build the dashboard against mock data.
