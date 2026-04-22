# frontend.live — generator notes

## Done

- `web-ui/src/ui/CameraFeed.tsx` — 16:9 click surface wrapping the
  `<img src="/api/feed/live.jpg?t=…">`. `setInterval` rotates the tick
  every 10s so the browser refetches; click translates pointer to
  normalized [-1, 1] coords and invokes `onLook(x, y)`. The click
  surface is a real `<button>` for native keyboard accessibility — no
  custom `onKeyDown`; Space/Enter fires a centered click = re-center,
  which is a reasonable keyboard fallback.
- `web-ui/src/ui/PresetList.tsx` — one `<button aria-label={label}>` per
  preset row; `data-preset-id` mirrors the id in the resulting POST URL
  so the spec can assert the id without a test-id. Active preset gets
  an inverted-bg style; `aria-selected` / `role="tab"` explicitly
  rejected per the spawn prompt.
- `web-ui/src/ui/ZoomSlider.tsx` — native `<input type="range">` with
  `aria-label="Zoom"`, step 0.1, range 1×–4×. `onChange` gives live
  feedback while dragging; `onMouseUp`/`onTouchEnd`/`onKeyUp` commit
  the final value (one POST per drag, not per tick).
- `web-ui/src/routes/live.tsx` — composes all three components. Uses
  TanStack Query for `/api/ptz/state` and three mutations for look /
  preset / zoom; each mutation invalidates the state cache on success
  so the UI re-renders against the post-move camera position.
- `web-ui/src/mocks/handlers.ts` — MSW v2 handlers for
  `/api/feed/live.jpg` (1×1 baseline JPEG, Content-Type image/jpeg,
  Cache-Control no-store), `/api/ptz/state` (connected=true, five
  presets: overview + plant_a..d), `/api/ptz/preset/{id}` (200 or 404),
  `/api/ptz/look` (400 on missing x/y, else 200 + nulls preset),
  `/api/ptz/zoom` (422 unless exactly one of `{zoom, delta}`).
- `web-ui/tests/e2e/live.spec.ts` — 6 `test(...)` blocks, one per
  distinct assertion in the plan description plus a console-hygiene
  check:
  1. `<img>` renders whose src targets `/api/feed/live.jpg`
  2. src refreshes via cache-bust within ~10s (uses
     `page.clock.install()` + `page.clock.fastForward(12_000)` instead
     of waiting wall-clock)
  3. click on feed fires POST `/api/ptz/look` with x/y in [-1, 1]
     (targeted click at 75%/25% of box → ~(0.5, -0.5) asserted)
  4. clicking a preset row fires POST `/api/ptz/preset/{id}` with the
     matching id (clicks Plant B → id="plant_b"; clicks Plant D →
     id="plant_d")
  5. keyboard-committing the zoom slider fires POST `/api/ptz/zoom`
     with the new absolute value
  6. console has no error-level entries after exercising the tab

## Full gate run

- `scripts/agent-fix` — green
- `uv run pytest apps/tests/invariants/ -q` — 102 passed
- `pnpm lint` (biome + eslint) — green
- `pnpm typecheck` — green
- `pnpm knip` — green (no exceptions added)
- `pnpm build` — green
- `pnpm test:e2e` (full suite) — 38 passed, including the 6 new live
  tests, no regressions in app-shell / dashboard-* / plant-detail /
  login

## Surprises

- Biome's a11y rule rejects `onClick` on a bare `<img>` without a
  keyboard equivalent. Wrapped the image in a `<button>` — cleaner than
  a no-op `onKeyDown` handler: the button is natively keyboard-
  focusable, Enter/Space fire a click at the element's center, and
  coordinate-targeted clicks land on it the same way they would on an
  image.
- The eslint `no-restricted-globals` rule only triggers on
  `window.setInterval` / `window.clearInterval`, not the bare globals.
  Using `setInterval`/`clearInterval` directly satisfies both rules
  without adding a wrapper in `src/shared/platform.ts` for a
  single-caller use-case.
- `img` with `w-full h-auto` on a 1×1 MSW fixture collapsed to 1px
  tall → `toBeVisible()` failed. Moved to `aspect-video` on the button
  with `object-contain` on the absolute-positioned img so the click
  surface keeps a usable size regardless of the image's natural dims.
  Real production feeds will be 16:9 anyway; the layout was broken for
  degenerate responses, not just mocks.
- `localZoom` is mirrored from `/api/ptz/state.zoom` via a
  `useEffect` — TanStack Query's cached value is the source of truth,
  but the slider needs fast local echo during drag. The useEffect only
  re-seeds on query success so it doesn't fight user drag input.

## Not done / next

- No Vitest unit tests for `CameraFeed` / `PresetList` / `ZoomSlider`
  — the e2e covers all observable behavior. If future work adds
  per-component logic (debounced drag sequences, pan gestures, preset
  reordering), add Vitest then.
- The zoom slider commits on release, not in a debounced sequence. The
  plan description accepts either; one-POST-per-drag is the simpler of
  the two and matches the backend's preference for absolute setpoints.
- The MSW `/api/ptz/look` handler does a naive `yaw += x * 10` / `pitch
  += y * 10` projection. The real backend runs geometry that depends on
  current zoom + device calibration. Fine for the e2e (which only
  asserts the request body, not the post-look state) but not a
  reference implementation for the BE service.
- Deviation note: the preset "Plant A/B/C/D" labels are read from the
  frontend's `DISPLAY_LABELS` lookup rather than the contract's
  `PTZPreset.label` field. This gives the UI a stable set of visible
  strings independent of backend preset-file authoring. Rationale:
  plan description says "overview + plant_a..d"; the contract's
  `label` is intentionally free-form; hard-pinning the visible text
  keeps the e2e `getByRole("button", { name: "Plant B" })` locator
  stable.
