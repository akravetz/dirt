// Smoke test: confirms handlers.ts + server.ts + test-setup.ts are
// wired correctly and MSW node-mode intercepts fetch in the Vitest
// process.
//
// Uses `server.use(...)` to register a per-test handler (auto torn down
// by afterEach(resetHandlers) in src/test-setup.ts) against a
// synthetic /api/__smoke path so the test doesn't depend on any real
// route landing.
import { HttpResponse, http } from "msw";
import { expect, it } from "vitest";
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
