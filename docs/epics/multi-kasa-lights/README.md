# Epic: Multi Kasa Lights

Status: planning
Priority: high
Created: 2026-05-09

## Goal

Make Dirt control multiple Kasa EP10 light plugs from canonical database device identity, with independent local-time schedules per tent or light zone, and expose those schedules in both the local and hosted web UI.

## Scope

- Canonical Kasa plug identity in the local `device` table, including stable hardware identity and mutable network endpoint.
- Multi-device lights reconciliation in `dirt-hwd`.
- Local schedule APIs and generated webapp contracts.
- Gateway-to-cloud schedule sync and hosted read APIs.
- Web UI display of the active local-time light schedule for each selected tent.

## Acceptance Criteria

- The main tent, clone lights, and breeding tent lights can be represented as separate canonical Kasa devices.
- The lights service controls only DB-known plugs after verifying observed hardware identity.
- Each light device can follow its own enabled `schedule.kind='lights'` row.
- The local UI and hosted UI show the selected tent's active light schedule in that tent's local timezone.
- Gateway sync includes light schedules so hosted views do not infer schedules from stale or missing grow state.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:multi-kasa-lights"`
