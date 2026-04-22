// MSW v2 node server for Vitest.
//
// Lifecycle (listen / resetHandlers / close) is attached in
// web-ui/src/test-setup.ts, referenced from vitest.config.ts
// test.setupFiles.
//
// `onUnhandledRequest: "error"` in the test process so any fetch that
// isn't explicitly mocked fails loudly — in dev we use "bypass", but in
// tests an unmocked fetch is always a bug.
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
