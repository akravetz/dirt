// MSW v2 request handlers.
//
// Each FE feature appends its own `http.{get,post,...}` handler to this
// array. See docs/references/msw-v2/handlers.md for the v2 resolver
// signature — `http.get("/api/x", ({ request, params, cookies }) =>
// HttpResponse.json(...))`, NOT the v1 `rest.get(..., (req, res, ctx) =>
// res(ctx.json(...)))` shape.
//
// This array is shared between browser-mode (dev via Service Worker)
// and node-mode (Vitest via setupServer). Keep handlers relative /
// same-origin where possible; prod serves the real endpoints on the
// same origin and MSW is tree-shaken out of the prod bundle.
import { HttpResponse, http, type RequestHandler } from "msw";

// ---------------------------------------------------------------------------
// frontend.login — /api/auth/{login,logout,me} fixture.
//
// The real backend feature (backend.auth) lands in parallel; until it
// merges, dev + tests rely on these handlers so the FE /login screen can
// be exercised end-to-end. In prod MSW is tree-shaken and these handlers
// never execute.
//
// Schema shapes below are inlined duck-typed mirrors of
// contracts/webapp-v1.yaml #/components/schemas/{LoginRequest,User,ErrorDetail}.
// The boundaries lint rule forbids mocks/ → api-client/, even for
// `import type`, so we can't reference the generated schema types
// directly. If the contract ever drifts, `pnpm typecheck` against the
// real endpoint consumers (routes/login.tsx etc.) surfaces the
// mismatch; the fixture staying locally typed keeps the mock surface
// cleanly separated from domain code.
//
// Session state is a module-level boolean: MSW's Service Worker can
// emit a `Set-Cookie: dirt_session=mock` header (handy for humans
// eyeballing devtools and for the acceptance-script cookie assertion),
// but the browser won't round-trip that cookie back into subsequent
// fetch requests because our real backend will issue it httponly and
// the SW can't set httponly cookies itself. An in-memory flag is the
// simplest fixture that keeps /api/auth/me's 200-after-login behaviour
// correct for both contexts (browser + Vitest node).
//
// Credentials baked into the fixture (planner contract for login.sh):
//   admin / changeme → 200 + User
//   everything else   → 401 + ErrorDetail
// ---------------------------------------------------------------------------

interface LoginRequestBody {
  username: string;
  password: string;
}
interface User {
  username: string;
}
interface ErrorDetail {
  detail: string;
}

let sessionUser: User | null = null;

export const handlers: RequestHandler[] = [
  http.post("/api/auth/login", async ({ request }) => {
    const body = (await request.json()) as Partial<LoginRequestBody>;
    if (body?.username === "admin" && body?.password === "changeme") {
      const user: User = { username: body.username };
      sessionUser = user;
      return HttpResponse.json(user, {
        headers: { "Set-Cookie": "dirt_session=mock; Path=/" },
      });
    }
    const err: ErrorDetail = { detail: "invalid_credentials" };
    return HttpResponse.json(err, { status: 401 });
  }),

  http.post("/api/auth/logout", () => {
    sessionUser = null;
    return new HttpResponse(null, {
      status: 204,
      headers: {
        "Set-Cookie": "dirt_session=; Path=/; Max-Age=0",
      },
    });
  }),

  http.get("/api/auth/me", () => {
    if (sessionUser) return HttpResponse.json(sessionUser);
    const err: ErrorDetail = { detail: "unauthorized" };
    return HttpResponse.json(err, { status: 401 });
  }),

  // -------------------------------------------------------------------------
  // frontend.dashboard.gauges — /api/sensors/current + /api/grow/current
  //
  // Fixtures for the five-gauge dashboard. Shapes duck-typed against
  // contracts/webapp-v1.yaml #/components/schemas/{SensorsCurrent,GrowCurrent}
  // (boundaries forbids mocks/ → api-client/, so no `import type` from
  // generated schema — any drift gets caught by route/component typecheck
  // against the real api-client types, not here).
  //
  // Values chosen to land inside the veg-stage STAGE_TARGETS bands (see
  // apps/shared/src/dirt_shared/services/grow_state.py) so band_status =
  // "ok" for every metric. The e2e spec's status-color assertion counts
  // on that: five "ok" tiles → one deterministic status badge to match.
  //
  // Bands per metric:
  //   temperature_f: (70, 82)    → 76 is mid-band
  //   humidity_pct:  (45, 55)    → 50 is mid-band
  //   vpd_kpa:       (0.8, 1.2)  → 1.0 is mid-band
  //   fan_pct, reservoir_in: no band (null target) — gauge renders without
  //   an arc, status is "ok" by band_status(value, null) convention.
  // -------------------------------------------------------------------------

  http.get("/api/sensors/current", () => {
    const ts = "2026-04-21T17:00:00Z";
    return HttpResponse.json({
      ts,
      stale: false,
      metrics: {
        temperature_f: {
          value: 76,
          unit: "°F",
          target: [70, 82],
          status: "ok",
          ts,
        },
        humidity_pct: {
          value: 50,
          unit: "%",
          target: [45, 55],
          status: "ok",
          ts,
        },
        vpd_kpa: {
          value: 1.0,
          unit: "kPa",
          target: [0.8, 1.2],
          status: "ok",
          ts,
        },
        fan_pct: {
          value: 48,
          unit: "%",
          target: null,
          status: "ok",
          ts,
        },
        reservoir_in: {
          value: 9.2,
          unit: "in",
          target: null,
          status: "ok",
          ts,
        },
      },
    });
  }),

  // -------------------------------------------------------------------------
  // frontend.dashboard.sparklines — /api/sensors/history
  //
  // Fixture for the five-sparkline strip. Shape duck-typed against
  // contracts/webapp-v1.yaml #/components/schemas/SensorsHistoryResponse
  // (boundaries forbids mocks/ → api-client/, so no `import type` from
  // generated schema — any drift gets caught by consumer typecheck).
  //
  // Contract:
  //   range ∈ {"1h","24h","7d"}, metric ∈ {"temperature_f","humidity_pct",
  //     "vpd_kpa","fan_pct","reservoir_in"}.
  //   points[] length depends on range so the e2e can observe bucket
  //   count changes per range (1h → 12, 24h → 48, 7d → 168).
  //   Values are deterministic per (range, metric) — a triangle wave
  //   with per-metric amplitude around a per-metric baseline. Same
  //   (range, metric) pair → identical series across fetches, so the
  //   crosshair/tooltip assertions are stable.
  //   unit mirrors the /api/sensors/current envelope per metric.
  // -------------------------------------------------------------------------

  http.get("/api/sensors/history", ({ request }) => {
    const url = new URL(request.url);
    const range = url.searchParams.get("range");
    const metric = url.searchParams.get("metric");

    // (bucket count, window ms) per range. Anchor the series end-ts to
    // a fixed point so snapshots don't drift per test run.
    const RANGE_SPEC: Record<string, { count: number; windowMs: number }> = {
      "1h": { count: 12, windowMs: 60 * 60 * 1000 },
      "24h": { count: 48, windowMs: 24 * 60 * 60 * 1000 },
      "7d": { count: 168, windowMs: 7 * 24 * 60 * 60 * 1000 },
    };
    const METRIC_SPEC: Record<string, { base: number; amp: number; unit: string }> = {
      temperature_f: { base: 76, amp: 4, unit: "°F" },
      humidity_pct: { base: 50, amp: 5, unit: "%" },
      vpd_kpa: { base: 1.0, amp: 0.2, unit: "kPa" },
      fan_pct: { base: 48, amp: 10, unit: "%" },
      reservoir_in: { base: 9.2, amp: 0.5, unit: "in" },
    };

    const rangeSpec = range ? RANGE_SPEC[range] : undefined;
    if (!range || !rangeSpec) {
      return HttpResponse.json({ detail: "bad_range" }, { status: 400 });
    }
    const metricSpec = metric ? METRIC_SPEC[metric] : undefined;
    if (!metric || !metricSpec) {
      return HttpResponse.json({ detail: "bad_metric" }, { status: 400 });
    }

    const { count, windowMs } = rangeSpec;
    const stepMs = windowMs / count;
    const endMs = Date.parse("2026-04-21T17:00:00Z");

    // Deterministic triangle wave keyed on bucket index; same
    // (range, metric) → identical series across fetches.
    const points = Array.from({ length: count }, (_, i) => {
      const pos = count === 1 ? 0 : i / (count - 1);
      const tri = Math.abs(2 * pos - 1); // 1 → 0 → 1
      const value = metricSpec.base + metricSpec.amp * (tri - 0.5) * 2;
      const rounded = Math.round(value * 100) / 100;
      const ts = new Date(endMs - (count - 1 - i) * stepMs).toISOString();
      return { ts, value: rounded };
    });

    return HttpResponse.json({
      range,
      metric,
      unit: metricSpec.unit,
      points,
    });
  }),

  // -------------------------------------------------------------------------
  // frontend.dashboard.humidifier — /api/humidifier/state + /api/humidifier/history
  //
  // Fixtures for the dashboard humidifier tile + duty-cycle strip. Shapes
  // duck-typed against contracts/webapp-v1.yaml
  // #/components/schemas/{HumidifierState,HumidifierHistory,HumidifierTransition}
  // (boundaries forbids mocks/ → api-client/, so no `import type` from
  // generated schema — consumer typecheck catches drift).
  //
  // /api/humidifier/state — stable "on since ~2h ago, 8 cycles in the
  // last 24h" fixture. `since` anchored to a fixed timestamp so the
  // duration-text assertion isn't a moving target as test time advances.
  //
  // /api/humidifier/history — range-dependent transition counts so the
  // e2e can observe the strip re-rendering when the user switches ranges.
  // Bucket counts per range (chosen distinct and not too large):
  //   1h  → 4 transitions
  //   24h → 12 transitions
  //   7d  → 28 transitions
  // Transitions alternate on/off, first transition = on=true. Same
  // (range) → identical points[] so rectangle-count assertions are stable.
  // -------------------------------------------------------------------------

  http.get("/api/humidifier/state", () => {
    const ts = "2026-04-21T17:00:00Z";
    // `since` = ts - 7200s (two hours ago) so duration_s = 7200
    const since = "2026-04-21T15:00:00Z";
    return HttpResponse.json({
      on: true,
      since,
      duration_s: 7200,
      cycles_24h: 8,
      ts,
    });
  }),

  http.get("/api/humidifier/history", ({ request }) => {
    const url = new URL(request.url);
    const range = url.searchParams.get("range");

    const RANGE_COUNT: Record<string, { count: number; windowMs: number }> = {
      "1h": { count: 4, windowMs: 60 * 60 * 1000 },
      "24h": { count: 12, windowMs: 24 * 60 * 60 * 1000 },
      "7d": { count: 28, windowMs: 7 * 24 * 60 * 60 * 1000 },
    };
    const spec = range ? RANGE_COUNT[range] : undefined;
    if (!range || !spec) {
      return HttpResponse.json({ detail: "bad_range" }, { status: 400 });
    }
    const { count, windowMs } = spec;
    const endMs = Date.parse("2026-04-21T17:00:00Z");
    const stepMs = windowMs / count;
    // Transitions evenly spaced across the window; alternate on/off with
    // first point on=true. Deterministic — same range → same points.
    const points = Array.from({ length: count }, (_, i) => ({
      ts: new Date(endMs - (count - 1 - i) * stepMs).toISOString(),
      on: i % 2 === 0,
    }));
    return HttpResponse.json({ range, points });
  }),

  // -------------------------------------------------------------------------
  // frontend.dashboard.plants_strip — /api/plants
  //
  // Fixture for the dashboard plants strip (four A/B/C/D cards). Shape
  // duck-typed against contracts/webapp-v1.yaml
  // #/components/schemas/{PlantsResponse,Plant,PlantStickerColor,PlantStatus}
  // (boundaries forbids mocks/ → api-client/, so no `import type` from
  // generated schema — consumer typecheck catches drift).
  //
  // Sticker colours: one per plant, matching the mockup reference
  // (docs/plans/refs/dashboard.png) — A yellow, B orange, C pink, D blue.
  // `moisture_pct` chosen distinct per plant so the spec can match each
  // card's moisture-bar width to its plant's reading without ambiguity.
  // -------------------------------------------------------------------------

  http.get("/api/plants", () => {
    const ts = "2026-04-21T17:00:00Z";
    return HttpResponse.json({
      day: 38,
      plants: [
        {
          code: "a",
          name: "Plant A",
          sticker_color: "yellow",
          status: "primary",
          purple: false,
          moisture_pct: 62,
          moisture_ts: ts,
        },
        {
          code: "b",
          name: "Plant B",
          sticker_color: "orange",
          status: "primary",
          purple: false,
          moisture_pct: 48,
          moisture_ts: ts,
        },
        {
          code: "c",
          name: "Plant C",
          sticker_color: "pink",
          status: "primary",
          purple: true,
          moisture_pct: 54,
          moisture_ts: ts,
        },
        {
          code: "d",
          name: "Plant D",
          sticker_color: "blue",
          status: "primary",
          purple: false,
          moisture_pct: 66,
          moisture_ts: ts,
        },
      ],
    });
  }),

  // -------------------------------------------------------------------------
  // frontend.plant_detail — /api/plants/{code} + /api/plants/{code}/moisture
  //
  // Fixtures for the plant-detail drawer (header + moisture hero +
  // timeline + note) and its 24h moisture history chart. Shapes
  // duck-typed against contracts/webapp-v1.yaml
  // #/components/schemas/{PlantDetail,PlantMoistureCurrent,TimelineEntry,
  //                       PlantNote,PlantMoistureHistory}.
  //
  // Per-plant metadata mirrors /api/plants above (sticker A=yellow,
  // B=orange, C=pink, D=blue; moisture 62/48/54/66) so the drawer agrees
  // with the card the user clicked. Timeline + note strings are static
  // per plant — deterministic so the e2e's row-count + header-text
  // assertions are stable across runs.
  // -------------------------------------------------------------------------

  http.get("/api/plants/:code", ({ params }) => {
    const code = String(params.code);
    const DETAILS: Record<
      string,
      {
        name: string;
        sticker_color: "yellow" | "orange" | "pink" | "blue";
        purple: boolean;
        label: string;
        moisture_pct: number;
      }
    > = {
      a: {
        name: "Plant A",
        sticker_color: "yellow",
        purple: false,
        label: "Primary · bushy",
        moisture_pct: 62,
      },
      b: {
        name: "Plant B",
        sticker_color: "orange",
        purple: false,
        label: "Primary · upright",
        moisture_pct: 48,
      },
      c: {
        name: "Plant C",
        sticker_color: "pink",
        purple: true,
        label: "Primary · purple",
        moisture_pct: 54,
      },
      d: {
        name: "Plant D",
        sticker_color: "blue",
        purple: false,
        label: "Primary · standard",
        moisture_pct: 66,
      },
    };
    const meta = DETAILS[code];
    if (!meta) {
      return HttpResponse.json({ detail: "not_found" }, { status: 404 });
    }
    const ts = "2026-04-21T17:00:00Z";
    // Six timeline entries per plant so .length is a single crisp
    // target for the spec's row-count assertion.
    const timeline = [
      {
        date: "2026-04-21",
        day: 38,
        text: "First canopy nudge; ~6 true-node pairs.",
        highlight: true,
      },
      {
        date: "2026-04-19",
        day: 36,
        text: "Transplanted into Airpot 3L.",
        highlight: false,
      },
      {
        date: "2026-04-17",
        day: 34,
        text: "Purple stem; likely anthocyanin stress.",
        highlight: false,
      },
      {
        date: "2026-04-14",
        day: 31,
        text: "Yellow-chlorosis margins; dialled nutrients up.",
        highlight: false,
      },
      {
        date: "2026-04-10",
        day: 27,
        text: "Second watering.",
        highlight: false,
      },
      {
        date: "2026-04-04",
        day: 21,
        text: "Recovery 38° — monitoring for two-node rebound.",
        highlight: false,
      },
    ] as const;
    return HttpResponse.json({
      code,
      name: meta.name,
      sticker_color: meta.sticker_color,
      status: "primary",
      purple: meta.purple,
      day: 38,
      label: meta.label,
      moisture: {
        current_pct: meta.moisture_pct,
        target: [50, 70],
        status: "ok",
        ts,
      },
      timeline,
      note: {
        text: `Day 38 was the right call — ${meta.name} had visible life node emerging, soon diameter strong; recovery margins comfortable before the day 40 LST target.`,
        updated: "2026-04-21",
      },
      wiki_path: `/wiki/plants/${code}.md`,
    });
  }),

  http.get("/api/plants/:code/moisture", ({ request, params }) => {
    const code = String(params.code);
    const url = new URL(request.url);
    const range = url.searchParams.get("range") ?? "24h";
    const RANGE_SPEC: Record<string, { count: number; windowMs: number }> = {
      "1h": { count: 12, windowMs: 60 * 60 * 1000 },
      "24h": { count: 48, windowMs: 24 * 60 * 60 * 1000 },
      "7d": { count: 168, windowMs: 7 * 24 * 60 * 60 * 1000 },
    };
    const spec = RANGE_SPEC[range];
    if (!spec) {
      return HttpResponse.json({ detail: "bad_range" }, { status: 400 });
    }
    const endMs = Date.parse("2026-04-21T17:00:00Z");
    const stepMs = spec.windowMs / spec.count;
    // Sawtooth: drops from high to low over each 6-bucket cycle to
    // imitate irrigation → drawdown. Deterministic per (range, code).
    const points = Array.from({ length: spec.count }, (_, i) => {
      const phase = i % 6;
      const value = 70 - phase * 3;
      const ts = new Date(endMs - (spec.count - 1 - i) * stepMs).toISOString();
      return { ts, value };
    });
    return HttpResponse.json({
      code,
      range,
      unit: "%",
      target: [50, 70],
      points,
      irrigation_events_24h: 4,
    });
  }),

  // -------------------------------------------------------------------------
  // frontend.dashboard.system_table — /api/system/devices
  //
  // Fixture for the dashboard system table (one row per device). Shape
  // duck-typed against contracts/webapp-v1.yaml
  // #/components/schemas/{DevicesResponse,DeviceStatus,DeviceStatusKind}
  // (boundaries forbids mocks/ → api-client/, so no `import type` from
  // generated schema — consumer typecheck catches drift).
  //
  // Eight devices chosen to cover the full DeviceStatusKind enum
  // (ok|listening|warn|offline) — at least one row per status — so the
  // e2e spec can assert that each row's badge text matches the fixture's
  // status value for that row. Ordering is stable so the spec can pair
  // rows to fixture entries by index.
  // -------------------------------------------------------------------------

  http.get("/api/system/devices", () => {
    const ts = "2026-04-21T17:00:00Z";
    return HttpResponse.json({
      ts,
      devices: [
        {
          name: "Env sensor · tent",
          kind: "env_sensor",
          status: "ok",
          last_seen: ts,
          note: null,
        },
        {
          name: "Moisture · Plant A",
          kind: "moisture_node",
          status: "ok",
          last_seen: ts,
          note: null,
        },
        {
          name: "Moisture · Plant B",
          kind: "moisture_node",
          status: "warn",
          last_seen: ts,
          note: "weak signal",
        },
        {
          name: "Moisture · Plant C",
          kind: "moisture_node",
          status: "offline",
          last_seen: null,
          note: "no heartbeat 2h",
        },
        {
          name: "Moisture · Plant D",
          kind: "moisture_node",
          status: "ok",
          last_seen: ts,
          note: null,
        },
        {
          name: "PTZ camera",
          kind: "camera",
          status: "ok",
          last_seen: ts,
          note: null,
        },
        {
          name: "Claudia voice",
          kind: "voice",
          status: "listening",
          last_seen: ts,
          note: null,
        },
        {
          name: "Humidifier plug",
          kind: "actuator",
          status: "ok",
          last_seen: ts,
          note: null,
        },
      ],
    });
  }),

  // -------------------------------------------------------------------------
  // frontend.live — /api/feed/live.jpg, /api/ptz/{state,preset/{id},look,zoom}
  //
  // Fixtures for the Live tab (camera feed + PTZ controls). Shapes duck-
  // typed against contracts/webapp-v1.yaml
  // #/components/schemas/{PTZState,PTZPreset,PTZApplied,PTZLookRequest,
  //                       PTZZoomRequest,PTZZoomResponse}.
  //
  // /api/feed/live.jpg — returns a tiny 1×1 baseline JPEG so the Live
  //   route's <img src="/api/feed/live.jpg?t=…"> actually loads in dev +
  //   e2e. A real binary JPEG byte-sequence (not a placeholder PNG) so
  //   Content-Type: image/jpeg is truthful. Cache-Control: no-store so
  //   the browser's HTTP cache doesn't hide the ~10s cache-bust refresh.
  //
  // PTZ state: module-level mutable. /api/ptz/state returns the current
  //   position; preset/look/zoom mutate it and echo back PTZApplied /
  //   PTZZoomResponse so the UI's onSuccess → invalidate → refetch sees
  //   the updated values.
  //
  // Preset ids baked in: overview + plant_a..d (matches the mockup
  // reference docs/plans/refs/live.png).
  // -------------------------------------------------------------------------

  // A 1×1 baseline JPEG, produced offline and inlined as bytes. 125 bytes
  // total — the smallest valid JPEG (SOI + APP0 + SOF0 + DQT + DHT × 4 +
  // SOS + EOI is too large, so this uses a minimal grayscale baseline
  // encoder's output). The exact bytes don't matter for the e2e — the
  // spec asserts the <img src> pattern + the network request fires, not
  // image pixel content.
  // biome-ignore format: keep the table columnar for review.
  http.get("/api/feed/live.jpg", () => {
    const bytes = new Uint8Array([
      0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01,
      0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff, 0xdb, 0x00, 0x43,
      0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
      0x09, 0x08, 0x0a, 0x0c, 0x14, 0x0d, 0x0c, 0x0b, 0x0b, 0x0c, 0x19, 0x12,
      0x13, 0x0f, 0x14, 0x1d, 0x1a, 0x1f, 0x1e, 0x1d, 0x1a, 0x1c, 0x1c, 0x20,
      0x24, 0x2e, 0x27, 0x20, 0x22, 0x2c, 0x23, 0x1c, 0x1c, 0x28, 0x37, 0x29,
      0x2c, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1f, 0x27, 0x39, 0x3d, 0x38, 0x32,
      0x3c, 0x2e, 0x33, 0x34, 0x32, 0xff, 0xc0, 0x00, 0x0b, 0x08, 0x00, 0x01,
      0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xff, 0xc4, 0x00, 0x1f, 0x00, 0x00,
      0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
      0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
      0x09, 0x0a, 0x0b, 0xff, 0xc4, 0x00, 0xb5, 0x10, 0x00, 0x02, 0x01, 0x03,
      0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7d,
      0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
      0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xa1, 0x08,
      0x23, 0x42, 0xb1, 0xc1, 0x15, 0x52, 0xd1, 0xf0, 0x24, 0x33, 0x62, 0x72,
      0x82, 0xff, 0xda, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3f, 0x00, 0xfb,
      0xd3, 0xff, 0xd9,
    ]);
    return new HttpResponse(bytes, {
      status: 200,
      headers: {
        "Content-Type": "image/jpeg",
        "Cache-Control": "no-store",
      },
    });
  }),

  // Preset table — exactly matches the five rows the Live route renders.
  // `sticker_color` null on overview, non-null per plant (mirrors the
  // contract's optional PTZPreset.sticker_color field).
  ...(() => {
    // All PTZ shapes below are inlined duck-typed mirrors of
    // contracts/webapp-v1.yaml #/components/schemas/{PTZState,PTZPreset,
    // PTZApplied,PTZLookRequest,PTZZoomRequest,PTZZoomResponse}. The
    // boundaries lint rule forbids mocks/ → api-client/ (even for
    // `import type`); consumer typecheck against the real api-client
    // types (routes/live.tsx) catches drift.
    interface LocalPreset {
      id: string;
      label: string;
      description: string;
      yaw: number;
      pitch: number;
      zoom: number;
      sticker_color: "yellow" | "orange" | "pink" | "blue" | null;
    }

    const PRESETS: readonly LocalPreset[] = [
      {
        id: "overview",
        label: "Overview",
        description: "Whole tent, center",
        yaw: 0,
        pitch: 0,
        zoom: 1,
        sticker_color: null,
      },
      {
        id: "plant_a",
        label: "Plant A",
        description: "Front-left",
        yaw: -30,
        pitch: -5,
        zoom: 1.8,
        sticker_color: "yellow",
      },
      {
        id: "plant_b",
        label: "Plant B",
        description: "Front-right",
        yaw: 30,
        pitch: -5,
        zoom: 1.8,
        sticker_color: "orange",
      },
      {
        id: "plant_c",
        label: "Plant C",
        description: "Back-left",
        yaw: -20,
        pitch: 10,
        zoom: 1.6,
        sticker_color: "pink",
      },
      {
        id: "plant_d",
        label: "Plant D",
        description: "Back-right",
        yaw: 20,
        pitch: 10,
        zoom: 1.6,
        sticker_color: "blue",
      },
    ];

    // Module-scoped mutable position. Each mutation updates this; the
    // next /api/ptz/state read reflects the change.
    const state = {
      connected: true,
      yaw: 0,
      pitch: 0,
      zoom: 1,
      preset: "overview" as string | null,
    };

    const snapshot = () => ({
      connected: state.connected,
      yaw: state.yaw,
      pitch: state.pitch,
      zoom: state.zoom,
      preset: state.preset,
      presets: PRESETS,
    });

    return [
      http.get("/api/ptz/state", () => HttpResponse.json(snapshot())),

      http.post("/api/ptz/preset/:id", ({ params }) => {
        const id = String(params.id);
        const preset = PRESETS.find((p) => p.id === id);
        if (!preset) {
          return HttpResponse.json({ detail: "preset_not_found" }, { status: 404 });
        }
        state.yaw = preset.yaw;
        state.pitch = preset.pitch;
        state.zoom = preset.zoom;
        state.preset = preset.id;
        return HttpResponse.json({
          ok: true,
          yaw: state.yaw,
          pitch: state.pitch,
          zoom: state.zoom,
          preset: state.preset,
        });
      }),

      http.post("/api/ptz/look", async ({ request }) => {
        const body = (await request.json()) as Partial<{ x: number; y: number }>;
        if (typeof body?.x !== "number" || typeof body?.y !== "number") {
          return HttpResponse.json({ detail: "bad_coords" }, { status: 400 });
        }
        // Naive look → yaw/pitch projection for the fixture. The real
        // service does geometry; the mock just records that a click-to-
        // look fired and nulls the active preset (per PTZApplied.preset
        // = null after manual moves).
        state.yaw += body.x * 10;
        state.pitch += body.y * 10;
        state.preset = null;
        return HttpResponse.json({
          ok: true,
          yaw: state.yaw,
          pitch: state.pitch,
          zoom: state.zoom,
          preset: state.preset,
        });
      }),

      http.post("/api/ptz/zoom", async ({ request }) => {
        const body = (await request.json()) as Partial<{
          zoom?: number;
          delta?: number;
        }>;
        const hasZoom = typeof body?.zoom === "number";
        const hasDelta = typeof body?.delta === "number";
        if (hasZoom === hasDelta) {
          // Contract: exactly one of {zoom, delta} must be provided.
          return HttpResponse.json(
            { detail: "provide_exactly_one_of_zoom_or_delta" },
            { status: 422 },
          );
        }
        if (hasZoom && typeof body.zoom === "number") {
          state.zoom = body.zoom;
        } else if (hasDelta && typeof body.delta === "number") {
          state.zoom += body.delta;
        }
        return HttpResponse.json({ ok: true, zoom: state.zoom });
      }),
    ];
  })(),

  // -------------------------------------------------------------------------
  // frontend.wiki — /api/wiki/{tree,file,search}
  //
  // Fixtures for the Wiki tab (sidebar tree + markdown pane + Cmd+K search
  // palette). Shapes duck-typed against contracts/webapp-v1.yaml
  // #/components/schemas/{WikiTreeResponse,WikiTreeNode,WikiTreeFile,
  //                       WikiTreeFolder,WikiFile,WikiBacklink,
  //                       WikiSearchResponse,WikiSearchResult,PlantStickerColor}
  // (boundaries forbids mocks/ → api-client/, so no `import type` from
  // generated schema — consumer typecheck catches drift).
  //
  // /api/wiki/tree — a realistic three-folder layout:
  //   overview.md + index.md (root files)
  //   plants/ (plant-a..d.md, each with the matching PlantStickerColor)
  //   concepts/ (topping.md, anthocyanin.md, lst.md)
  //   daily/ (one entry per recent grow day)
  // CLAUDE.md is excluded server-side; we mirror that by not emitting it
  // at all. Sorting: root files first (alphabetical), then folders
  // (alphabetical) — same order the backend's `get_tree` produces.
  //
  // /api/wiki/file — a small path → page registry. plant-a.md is the
  // headline page the e2e exercises; it carries a frontmatter block with
  // `type`, `status`, `strain` plus a markdown body that contains a
  // subtitle (first italic line) and more than one heading so the render
  // assertions are non-trivial. Missing paths → 404, traversal → 400.
  //
  // /api/wiki/search — a title/path/content matcher against the same
  // registry. Empty/whitespace q → 400 (mirrors the backend contract).
  // -------------------------------------------------------------------------

  ...(() => {
    // Wiki content registry. One entry per on-disk .md file the fixture
    // exposes. `folder` drives the tree layout; `sticker_color` is only
    // meaningful inside `plants/`. Body is a raw-markdown string whose
    // first paragraph (after the H1) begins with `*…*` when we want a
    // subtitle surfaced on /api/wiki/file.
    interface WikiEntry {
      folder: string | null;
      name: string;
      title: string;
      sticker_color: "yellow" | "orange" | "pink" | "blue" | null;
      frontmatter: Record<string, unknown>;
      subtitle: string | null;
      body: string;
    }

    const PAGES: readonly WikiEntry[] = [
      {
        folder: null,
        name: "index.md",
        title: "Wiki Index",
        sticker_color: null,
        frontmatter: { title: "Wiki Index" },
        subtitle: null,
        body: "# Wiki Index\n\nTop-level pointers into the grow wiki.\n",
      },
      {
        folder: null,
        name: "overview.md",
        title: "Grow Overview",
        sticker_color: null,
        frontmatter: { title: "Grow Overview" },
        subtitle: null,
        body: "# Grow Overview\n\nSirius Black × BS01, four plants in a closet tent.\n",
      },
      {
        folder: "plants",
        name: "plant-a.md",
        title: "Plant A — Purple Keeper Candidate",
        sticker_color: "yellow",
        frontmatter: {
          title: "Plant A — Purple Keeper Candidate",
          type: "plant",
          status: "primary",
          strain: "Sirius Black × BS01",
        },
        subtitle: "Formerly labeled Plant 1.",
        body:
          "# Plant A — Purple Keeper Candidate\n\n" +
          "*Formerly labeled Plant 1.*\n\n" +
          "## Current State\n\n" +
          "Topped on Day 38 (Apr 21); now in recovery. Cut above node 4. " +
          "Most vigorous plant of the four, with D about a day behind. " +
          "Applied topping above node 4 and observed the 5th node emerging " +
          "when we cut.\n\n" +
          "## Notes\n\n" +
          "Day 38 was the right call — plant had visible life node emerging.\n",
      },
      {
        folder: "plants",
        name: "plant-b.md",
        title: "Plant B",
        sticker_color: "orange",
        frontmatter: { title: "Plant B", type: "plant" },
        subtitle: null,
        body: "# Plant B\n\nUpright structure; trailing A by ~a day.\n",
      },
      {
        folder: "plants",
        name: "plant-c.md",
        title: "Plant C",
        sticker_color: "pink",
        frontmatter: { title: "Plant C", type: "plant" },
        subtitle: null,
        body: "# Plant C\n\nPurple stem; likely anthocyanin stress.\n",
      },
      {
        folder: "plants",
        name: "plant-d.md",
        title: "Plant D",
        sticker_color: "blue",
        frontmatter: { title: "Plant D", type: "plant" },
        subtitle: null,
        body: "# Plant D\n\nStandard sibling; mirrors A at ~one day behind.\n",
      },
      {
        folder: "concepts",
        name: "topping.md",
        title: "Topping",
        sticker_color: null,
        frontmatter: { title: "Topping" },
        subtitle: null,
        body:
          "# Topping\n\n" +
          "Prune the apical meristem above a node to force two dominant " +
          "shoots. See [Plant A](../plants/plant-a.md) for a worked example.\n",
      },
      {
        folder: "concepts",
        name: "anthocyanin.md",
        title: "Purple Pigment Biology",
        sticker_color: null,
        frontmatter: { title: "Purple Pigment Biology" },
        subtitle: null,
        body: "# Purple Pigment Biology\n\nCold-stress signal; unrelated body text.\n",
      },
      {
        folder: "concepts",
        name: "lst.md",
        title: "Low-Stress Training",
        sticker_color: null,
        frontmatter: { title: "Low-Stress Training" },
        subtitle: null,
        body: "# Low-Stress Training\n\nBend-and-tie; complements topping.\n",
      },
      {
        folder: "daily",
        name: "2026-04-18.md",
        title: "2026-04-18 · d29",
        sticker_color: null,
        frontmatter: { title: "2026-04-18 · d29" },
        subtitle: null,
        body: "# 2026-04-18 · d29\n\nDaily entry.\n",
      },
      {
        folder: "daily",
        name: "2026-04-17.md",
        title: "2026-04-17 · d28",
        sticker_color: null,
        frontmatter: { title: "2026-04-17 · d28" },
        subtitle: null,
        body: "# 2026-04-17 · d28\n\nDaily entry.\n",
      },
    ];

    const relPath = (e: WikiEntry): string =>
      e.folder === null ? e.name : `${e.folder}/${e.name}`;
    const fullPath = (e: WikiEntry): string => `wiki/${relPath(e)}`;

    const buildTree = () => {
      const rootFiles = PAGES.filter((e) => e.folder === null)
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((e) => ({
          type: "file" as const,
          name: e.name,
          path: fullPath(e),
          title: e.title,
          sticker_color: e.sticker_color,
        }));

      const folderNames = Array.from(
        new Set(PAGES.filter((e) => e.folder !== null).map((e) => e.folder as string)),
      ).sort((a, b) => a.localeCompare(b));

      const folders = folderNames.map((folder) => ({
        type: "folder" as const,
        name: folder,
        children: PAGES.filter((e) => e.folder === folder)
          .slice()
          .sort((a, b) => a.name.localeCompare(b.name))
          .map((e) => ({
            type: "file" as const,
            name: e.name,
            path: fullPath(e),
            title: e.title,
            sticker_color: e.sticker_color,
          })),
      }));

      return [...rootFiles, ...folders];
    };

    // Accept both `foo/bar.md` and `wiki/foo/bar.md` forms (matches the
    // backend's path normalization).
    const lookupEntry = (raw: string): WikiEntry | null => {
      const normalized = raw.startsWith("wiki/") ? raw.slice("wiki/".length) : raw;
      return PAGES.find((e) => relPath(e) === normalized) ?? null;
    };

    // Naive-but-stable backlink derivation: any page whose body contains
    // a markdown link `(…/target.md)` counts as a backlink to the target.
    // Same rule the backend's service uses in spirit; not exhaustive,
    // just enough for the e2e's backlinks-rendered assertion to be
    // verifiable if it ever wants it.
    const backlinksFor = (target: WikiEntry) => {
      const tail = target.name;
      return PAGES.filter((p) => p !== target && p.body.includes(`/${tail})`)).map(
        (p) => ({ path: fullPath(p), title: p.title }),
      );
    };

    const rankSearch = (q: string) => {
      const needle = q.toLowerCase();
      const results: Array<{
        path: string;
        title: string;
        match_type: "title" | "path" | "content";
        snippet: string | null;
        // Lower rank sorts first; ties broken by path for determinism.
        rank: number;
      }> = [];
      for (const page of PAGES) {
        const title = page.title.toLowerCase();
        const path = relPath(page).toLowerCase();
        const body = page.body.toLowerCase();
        if (title.includes(needle)) {
          results.push({
            path: fullPath(page),
            title: page.title,
            match_type: "title",
            snippet: null,
            rank: 0,
          });
        } else if (path.includes(needle)) {
          results.push({
            path: fullPath(page),
            title: page.title,
            match_type: "path",
            snippet: null,
            rank: 1,
          });
        } else if (body.includes(needle)) {
          const idx = body.indexOf(needle);
          const start = Math.max(0, idx - 30);
          const end = Math.min(page.body.length, idx + needle.length + 30);
          results.push({
            path: fullPath(page),
            title: page.title,
            match_type: "content",
            snippet: page.body.slice(start, end).replace(/\s+/g, " ").trim(),
            rank: 2,
          });
        }
      }
      return results
        .sort((a, b) => a.rank - b.rank || a.path.localeCompare(b.path))
        .map(({ rank: _rank, ...rest }) => rest);
    };

    return [
      http.get("/api/wiki/tree", () => HttpResponse.json({ tree: buildTree() })),

      http.get("/api/wiki/file", ({ request }) => {
        const url = new URL(request.url);
        const path = url.searchParams.get("path");
        if (path === null || path.length === 0) {
          return HttpResponse.json({ detail: "missing_path" }, { status: 422 });
        }
        // Reject traversal before any lookup — matches backend 400.
        if (path.includes("..")) {
          return HttpResponse.json({ detail: "path_traversal" }, { status: 400 });
        }
        const entry = lookupEntry(path);
        if (!entry) {
          return HttpResponse.json({ detail: "not_found" }, { status: 404 });
        }
        return HttpResponse.json({
          path: fullPath(entry),
          title: entry.title,
          subtitle: entry.subtitle,
          frontmatter: entry.frontmatter,
          body_markdown: entry.body,
          backlinks: backlinksFor(entry),
        });
      }),

      http.get("/api/wiki/search", ({ request }) => {
        const url = new URL(request.url);
        const q = url.searchParams.get("q");
        if (q === null || q.length === 0) {
          // Backend: FastAPI min_length=1 → 422.
          return HttpResponse.json({ detail: "missing_q" }, { status: 422 });
        }
        if (q.trim().length === 0) {
          // Backend: whitespace-only → 400.
          return HttpResponse.json({ detail: "empty_q" }, { status: 400 });
        }
        return HttpResponse.json({ q, results: rankSearch(q.trim()) });
      }),
    ];
  })(),

  http.get("/api/grow/current", () => {
    // germination_date authoritative in CLAUDE.md: 2026-03-15 (veg).
    // day_number for today (2026-04-21) = 38; grow_week_number = 6.
    return HttpResponse.json({
      germination_date: "2026-03-15",
      flower_start_date: null,
      day_number: 38,
      grow_week_number: 6,
      flower_week_number: null,
      stage: "veg",
      strain: "Sirius Black × BS01",
      location: "Denver, MT · closet tent",
      plant_count: 4,
      lights: {
        on: true,
        on_local: "05:00:00",
        off_local: "23:00:00",
        minutes_until_on: 0,
        minutes_until_off: 360,
      },
    });
  }),
];
