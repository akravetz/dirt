// Vitest global setup — attaches MSW node-mode lifecycle for every test.
//
// `onUnhandledRequest: "error"` is deliberate: in tests we never want a
// silent fallthrough to the real network. If a test triggers a fetch not
// covered by a handler in src/mocks/handlers.ts (or a per-test override
// via `server.use(...)`), the test fails with a clear message pointing
// at the unmocked path.
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./mocks/server";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});
