# Epic: Camera Edge Nodes

Status: planning
Priority: high
Created: 2026-05-10

## Goal

Make Dirt support reusable camera edge nodes: small hosts with local cameras that capture tent images and publish them into the same scoped snapshot/asset model used by the main grow box. The first target is `dirt2`, which controls the breeding-tent camera and should upload breeding-tent photos as private hosted assets.

## Scope

- Shared camera-source abstractions for OBSBOT daemon, direct V4L2, RTSP/IP cameras, and future vendor PTZ drivers.
- Reusable snapshot capture/spool/publish code that can be used by `dirt-hwd` and a new edge camera service.
- Shared cloud asset upload code so camera services and `dirt-gateway` use the same sign/upload/complete contract.
- A `dirt2` camera-agent deployment path with systemd, environment, and operator docs.
- Focused tests proving current main-tent behavior remains unchanged while breeding-tent assets can upload independently.

## Acceptance Criteria

- `dirt2` can run a camera service that captures from its local camera and uploads private assets under `homebox/breeding`.
- Main-tent capture still works through the existing `dirt-hwd` service after being moved onto reusable shared code.
- Cloud asset uploads from both gateway and camera-agent use the same Pydantic request/response models in `dirt_shared.cloud_contract`.
- The hosted UI/API can retrieve latest breeding-tent assets through the existing signed-URL route.
- Agents have terse operational docs for SSH, service status, and camera diagnostics.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:camera-edge"`

## Plan

Canonical implementation plan: [ExecPlan.md](ExecPlan.md).
