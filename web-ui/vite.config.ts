import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    TanStackRouterVite({ target: "react", autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    // Mirror the `@/*` → `./src/*` alias declared in tsconfig.json so
    // runtime imports resolve the same as type-checking does.
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    // WEBUI_DEV_PORT is set per-worktree by `../scripts/worktree-port`
    // via the package.json `dev` / `test:e2e` scripts. Bare runs in
    // main fall back to 5173.
    port: Number(process.env.WEBUI_DEV_PORT) || 5173,
    // Don't auto-increment to the next free port — explicit failure
    // is better than silently binding to a different port than
    // playwright.config.ts expects.
    strictPort: true,
  },
});
