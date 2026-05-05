// Smoke test: confirms handlers.ts + server.ts + test-setup.ts are
// wired correctly and MSW node-mode intercepts fetch in the Vitest
// process.
//
// Uses `server.use(...)` to register a per-test handler (auto torn down
// by afterEach(resetHandlers) in src/test-setup.ts) against a
// synthetic /api/__smoke path so the test doesn't depend on any real
// route landing.
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../server";

it("MSW intercepts a registered fetch and returns the mocked body", async () => {
  server.use(
    http.get("http://localhost/api/__smoke", () =>
      HttpResponse.json({ ok: true, from: "msw" }),
    ),
  );

  const res = await fetch("http://localhost/api/__smoke");
  expect(res.status).toBe(200);
  const body = (await res.json()) as { ok: boolean; from: string };
  expect(body).toEqual({ ok: true, from: "msw" });
});

describe("hosted cloud fixtures", () => {
  it("returns live gateway and metric state", async () => {
    const sync = await getJson<CloudSyncStatus>(
      "https://api.test/api/sync/status?cloud_fixture=live",
    );
    expect(sync.status).toBe("live");
    expect(sync.command_backlog_depth).toBe(0);

    const metrics = await getJson<CloudMetric[]>(
      "https://api.test/api/tents/main/metrics/current?cloud_fixture=live",
    );
    expect(metrics).toHaveLength(6);
    expect(metrics.every((metric) => metric.source_updated_at !== null)).toBe(true);
  });

  it("returns stale gateway and stale metric source times", async () => {
    const sync = await getJson<CloudSyncStatus>(
      "https://api.test/api/sync/status?cloud_fixture=stale",
    );
    expect(sync.status).toBe("stale");
    expect(sync.command_backlog_depth).toBe(2);

    const metrics = await getJson<CloudMetric[]>(
      "https://api.test/api/tents/main/metrics/current?cloud_fixture=stale",
    );
    expect(
      Date.now() - Date.parse(metrics[0]?.source_updated_at ?? ""),
    ).toBeGreaterThan(120_000);
  });

  it("returns offline gateway state with backlog", async () => {
    const sync = await getJson<CloudSyncStatus>(
      "https://api.test/api/sync/status?cloud_fixture=offline",
    );
    expect(sync.status).toBe("offline");
    expect(sync.gateway_last_seen_at).toBeNull();
    expect(sync.command_backlog_depth).toBe(4);
  });

  it("returns an empty breeding tent fixture", async () => {
    const tents = await getJson<CloudTent[]>(
      "https://api.test/api/tents?site_id=homebox&cloud_fixture=empty",
    );
    expect(tents.find((tent) => tent.tent_id === "breeding")?.is_active).toBe(false);

    const metrics = await getJson<CloudMetric[]>(
      "https://api.test/api/tents/breeding/metrics/current?cloud_fixture=empty",
    );
    const devices = await getJson<CloudDevice[]>(
      "https://api.test/api/tents/breeding/devices?cloud_fixture=empty",
    );
    expect(metrics).toEqual([]);
    expect(devices).toEqual([]);
  });

  it("returns asset-unavailable state for private asset failures", async () => {
    const response = await fetch(
      "https://api.test/api/tents/main/assets/latest?cloud_fixture=asset-unavailable",
    );
    expect(response.status).toBe(503);
    const body = (await response.json()) as { detail: string };
    expect(body.detail).toBe("asset_unavailable");
  });
});

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  expect(response.status).toBe(200);
  return (await response.json()) as T;
}

interface CloudSyncStatus {
  site_id: string;
  gateway_last_seen_at: string | null;
  last_catalog_sync_at: string | null;
  command_backlog_depth: number;
  status: "live" | "stale" | "offline";
}

interface CloudMetric {
  metric: string;
  value: number;
  source_updated_at: string;
}

interface CloudTent {
  tent_id: string;
  is_active: boolean;
}

interface CloudDevice {
  device_id: string;
}
