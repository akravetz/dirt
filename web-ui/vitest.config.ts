// Merges vite.config so tests see the same `@/*` alias + plugin setup
// as dev/build. jsdom is the env so component tests against
// @testing-library/react work; node-mode MSW (setupServer) is started
// from src/test-setup.ts.
import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test-setup.ts"],
      include: ["src/**/*.{test,spec}.{ts,tsx}"],
    },
  }),
);
