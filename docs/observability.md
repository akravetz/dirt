# Observability

Read before calling `log_event()`, debugging across logs, writing tests that touch `var/logs/` or `var/sessions/`, or adding a new log stream. Logs are first-class diagnostic artifacts.

Two families with different contracts:

## `sessions/<channel>/YYYY-MM-DD.jsonl` — conversation records (long-lived)

What the user and agent said. Append-only, agent-readable. Kept indefinitely (ops cleanup only). One JSON object per line with channel-specific fields. Streams:

- `var/sessions/voice/` — voice channel turns (wake, conversation_end). See `wiki/hardware/voice-channel.md`.
- `var/sessions/telegram/` — telegram channel turns (future).

## `logs/<stream>/YYYY-MM-DD.jsonl` — operational instrumentation (short-lived)

Structured JSONL for debugging. Rotated by filename date on first write of the day. All events share one envelope: `{ts, conversation_id, stream, event, ...fields}`.

| Stream | What it records | Retention | Source |
|---|---|---|---|
| `wake_scores` | Every wake-model score ≥ `WAKE_NEAR_MISS_FLOOR` (`near_miss`) and every threshold-crossing wake (`wake_detected`). | 1 day | `apps/voice/src/dirt_voice/channels/voice.py:wait_for_wake` |
| `audio_rms` | Input amplitude (int16 RMS) at ~1 Hz during pipecat conversations. Only fires while a conversation is active; silent otherwise. | 1 day | `apps/voice/src/dirt_voice/channels/_audio_transport.py:SoundDeviceInputTransport` |
| `audio_playback` | Per-assistant-turn duration metric: `tts_stream_duration_s` (pipecat's "bot done speaking" time) vs `playback_duration_s` (speaker actually finished), and `excess_buffer_s` gap. Detects ring-buffer decoupling anomalies. | 1 day | `apps/voice/src/dirt_voice/channels/_audio_transport.py:SoundDeviceOutputTransport` |
| `pipecat_frames` | Every non-raw-data frame pushed through the pipeline — turn lifecycle (`BotSpeakingFrame`, `UserStartedSpeakingFrame`, …), STT/LLM/TTS signals (`TranscriptionFrame`, `TTSStoppedFrame`, `LLMRunFrame`, …), interruptions, errors. Denylist excludes `AudioRawFrame`, `ImageRawFrame`, `HeartbeatFrame`. | 1 day | `apps/voice/src/dirt_voice/channels/_observers.py:FrameFlowObserver` |
| `subagent_calls` | Full Claude Agent SDK trace per `ask_wiki` invocation — question, every tool_use/tool_result, final answer, usage, cost, duration. | 10 days | `apps/voice/src/dirt_voice/tools/wiki.py:_ask_wiki` |
| `humidifier` | Govee H7142 actuator transitions + watchdog events. `state_change` (power on/off; carries `power`, `level: 1..9 \| null`, allocated `u_pct`, `requested_u_pct`, PI `reason` ∈ {`pi_active`, `failsafe_stale_sensor`, `outside_lights_window`, `rh_ceiling`}, allocator `allocation_reason` such as `pi_request` / `fan_relief_first`, VPD/RH/fan/stage/band/lights context, `bucket_width_pct`); `level_change` (level transitions while on; `from_level`, `to_level`, allocated `u_pct`, `requested_u_pct`, `allocation_reason`); `lack_water` / `lack_water_cleared` (rising/falling edge of the H7142's `lackWaterEvent` empty-tank alarm; rising edge fires one Telegram per refill cycle); `device_offline` / `device_online` (Govee cloud reachability flips); `skip_offline` (per-tick when device is unreachable; PI and allocation ran but no actuation); `suspected_ineffective` (commanded mist for ≥`humidifier_ineffective_alert_after_s` with VPD drop <`humidifier_ineffective_min_vpd_drop_kpa` — atomization fouling / firmware glitch / mist-not-reaching-canopy); `rate_limited` (HTTP/code 429 from Govee; quiet — next tick retries); `error` (any other exception in the tick body). Loop targets the stage's VPD upper edge and forces off outside the allowed lights window (`lights_on − margin` through `lights_off − margin`) — see `wiki/hardware/humidifier-control.md`. | 30 days | `apps/hwd/src/dirt_hwd/services/humidifier.py:HumidifierLoopService.run` |
| `humidifier_shadow` | Per-tick PI + allocator output, decoupled from dispatch quantization for diagnosability. One `tick` event per ~30 s loop iteration with allocated `u_pct`, `requested_u_pct`, `plug_on_shadow`, `requested_plug_on`, `allocation_reason`, `target_level`, `naive_level`, `held_by_hysteresis`, `bucket_width_pct`, `level_hysteresis_pct`, `setpoint_kpa`, `error_kpa`, `p_term`, `i_term`, `integrator`, PI `reason` (`pi_active` / `failsafe_stale_sensor` / `outside_lights_window` / `rh_ceiling`), plus inputs (vpd, vpd_age_s, rh, fan_pct, fan_age_s, stage, band edges, lights state) and active gains (kc, ki, threshold). Pair with `humidifier` stream to see how allocated `u_pct` quantizes into discrete H7142 levels and when hysteresis suppresses a would-be level change. Analyzer + replay harness at `debug/humidifier-shadow/analyze.py`. | 14 days | `apps/hwd/src/dirt_hwd/services/humidifier.py:HumidifierLoopService.run` (calls `apps/hwd/src/dirt_hwd/services/humidifier_pi.py:compute`) |
| `lights` | State transitions of the Kasa plug driving the grow lights. One `state_change` event per on/off change with `reason` (`scheduled_on` / `scheduled_off`) and `minutes_until_off` / `minutes_until_on`. Also emits `error` events on loop exceptions. Schedule comes from the current scoped enabled `schedule` row with `kind='lights'`, interpreted in the schedule timezone. | 30 days | `apps/hwd/src/dirt_hwd/services/lights.py:LightsLoopService.run` |
| `fan_controller` | Supervisory exhaust fan trim. `tick` fires once per poll with `current_pct`, `target_pct`, `reason` (`pre_lights_off_drydown`, `humid_trim_up_high_rh`, `humid_trim_up_low_vpd`, `trim_down_high_vpd`, `trim_down_recovered`, hold/error reasons), VPD/RH, stage bands, and lights countdown context. `state_change` fires when the ESP32 `/fan` duty changes. Pre-lights-off dry-down is feedforward; normal trim steps fan upward when RH exceeds the stage ceiling or VPD drops below the stage floor, backs off faster when VPD is high and RH is below ceiling, then decays toward the configured floor after recovery. | 30 days | `apps/hwd/src/dirt_hwd/services/fan_controller.py:FanTrimLoopService.run` |
| `daily_report` | Per-phase markers for the daily report run (`run_started`, `capture_finished`, `validate_finished`, `snapshot_finished`, `synthesis_finished`, `deliver_finished`, `run_completed`, `run_failed`, `deliver_failed`). | 30 days | `apps/shared/src/dirt_shared/services/daily_report.py` |
| `device_status` | Offline/online transitions from the device watchdog. One `state_change` event per cross of the `offline` boundary in either direction (`name`, `kind`, `old`, `new`, `last_seen`). Cold-start seeds silently from `var/logs/device_watchdog/state.json` so a systemd restart doesn't replay every already-offline device. Also emits `error` events on loop exceptions. | 30 days | `apps/hwd/src/dirt_hwd/services/device_watchdog.py:DeviceWatchdogService.run` |
| `metric_freshness` | Per-device/capability dropout transitions. One `state_change` event per fresh↔stale flip for a persisted capability declared in `dirt_shared.sensor_contract.DEVICE_METRICS` (`site_id`, `tent_id`, `device_id`, `capability_id`, `metric`, `old`, `new`, `last_seen`). State keys are `device_id:capability_id` so repeated capability IDs such as plant `soil_moisture_raw` stay distinct. Gated on canonical `device.last_seen` so whole-device outages (handled by `device_status`) don't fan out into N metric alerts. Cold-start seeds from `var/logs/metric_freshness/state.json` to suppress first-seen replays. Also emits `error` events on loop exceptions. | 30 days | `apps/hwd/src/dirt_hwd/services/metric_freshness.py:MetricFreshnessService.run` |
| `sensor_quality` | Ingest-time physically-impossible sensor data rejection. `rejected` fires for every dropped payload with `device_id`, `rejected`, `reasons`, and raw `metrics`; `state_change` fires only on ok↔bad transitions and is what drives Telegram dedupe. State persists in `var/logs/sensor_quality/state.json`, so repeated 30 s bad reservoir posts do not spam alerts. | 30 days | `apps/hwd/src/dirt_hwd/services/sensor_quality.py:SensorQualityService.filter_metrics` |
| `camera_capture` | Mainbox periodic PTZ capture lifecycle from the shared capture publisher and `LocalSnapshotSink`. Emits `capture_started`, `snapshot_recorded`, `capture_skipped` (`reason='lights_off'` when the scoped DB light schedule is dark; `reason='policy_disabled'` when the camera policy disables capture), and `capture_policy_unresolved` when the local catalog is missing camera/schedule rows and capture fails open. Events carry site/tent/device scope. `capture_skipped` means no camera call, JPEG write, DB row, or gateway-visible asset was produced. | 30 days | `apps/shared/src/dirt_shared/services/camera_publisher.py` |
| `cloud_gateway` | Outbound hosted control-plane sync lifecycle. Emits `cycle_started` / `cycle_finished`, `dry_run`, `enqueued`, `delivered`, `delivery_failed`, and `asset_failure_report_failed` events with `site_id`, `gateway_id`, event type, idempotency key, backlog depth, attempt count, and error summaries. This stream is local-only operational telemetry; do not log cloud tokens or signed upload URLs. | 30 days | `apps/gateway/src/dirt_gateway/sync.py:GatewaySyncService` |
| `camera_agent` | Edge camera capture/upload lifecycle from the shared capture publisher and `CloudAssetSink`. Emits `capture_started`, `upload_completed`, `upload_failed`, `capture_skipped` (`reason='lights_off'` when the hosted catalog-derived lights policy is dark; `reason='policy_disabled'` when the hosted policy disables capture), `capture_policy_unresolved` when the hosted catalog is missing the camera or lights schedule and capture fails open, `capture_policy_fetch_failed` when the hosted policy cannot be fetched and the cached policy or fail-open behavior is used, `cycle_failed`, and `asset_failure_report_failed` with site/tent/gateway/device scope and asset identifiers. `capture_skipped` means no camera call, JPEG write, or upload was attempted. It must not log cloud tokens or signed upload URLs. | 30 days | `apps/camera-agent/src/dirt_camera_agent/service.py` |

## Adding a new log stream

Call `log_event(stream, event, **fields)` from `dirt_shared.observability`. It handles path, rotation, timestamp, and correlation ID. Register non-default retention in `_RETENTION` in `apps/shared/src/dirt_shared/observability.py`. That's the whole API — don't invent per-stream helpers.

## Test isolation

`logs_dir()` reads the `DIRT_LOGS_DIR` env var on every write. The autouse fixture in `conftest.py` at the repo root (`isolate_observability_logs`) sets it to a per-test `tmp_path / "logs"` so no test ever appends to the production log tree. Production code paths leave `DIRT_LOGS_DIR` unset and fall back to `settings.data_dir / "logs"` — which resolves to `var/logs/` by default (override the root via `DIRT_DATA_DIR`). Apply this pattern (env-var-based isolation + autouse fixture) when adding new modules that write to disk under `var/logs/`, `var/sessions/`, or similar shared locations.

## Correlation across streams

Every entry stamped with `conversation_id` (UUID generated per voice wake). To reconstruct a single user interaction:

```bash
CID=f1918a9c-1545-4033-beaa-9adc4f5b3dbf
jq -c "select(.conversation_id==\"$CID\")" \
  var/sessions/voice/*.jsonl var/logs/*/*.jsonl 2>/dev/null
```

## Free-text operational logs

Loguru output (voice service) goes to stderr → systemd journal:

```bash
journalctl --user -u dirt-voice -f           # live tail
journalctl --user -u dirt-voice --since "1 hour ago"
```

Retention is governed by systemd's journal config, not us. Use this for free-text tailing during a live incident; use the `logs/*/` JSONL streams for programmatic / agent-readable analysis.
