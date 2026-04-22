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
