# frontend.wiki — generator notes

## Summary

Wired the Wiki tab end-to-end against the frozen contract: sidebar tree
(`GET /api/wiki/tree`), markdown pane (`GET /api/wiki/file`), Cmd+K
search palette (`GET /api/wiki/search` with recent-files fallback for
empty queries). Three new presentational components
(`ui/WikiSidebar.tsx`, `ui/WikiDoc.tsx`, `ui/CmdKPalette.tsx`), the
route composition in `routes/wiki.tsx`, the Playwright spec in
`tests/e2e/wiki.spec.ts`, and MSW v2 fixtures for all three wiki
endpoints. 45/45 e2e tests green.

## Design choices

- **Fixture shapes.** MSW handlers are a single IIFE-scoped PAGES table
  whose entries drive all three endpoints — one source of truth for
  tree nodes, file payloads, and search ranking. The fixture layout
  mirrors the backend tests (`test_wiki_tree_endpoint.py` etc.): root
  files sorted alphabetically then folders sorted alphabetically; plant
  files carry `sticker_color`; `wiki/` prefix on `path`. Search ranks
  title > path > content to match `MatchType` contract behaviour, and
  the handler surfaces both a 422 (empty `q`) and 400 (whitespace `q`)
  to mirror the backend's FastAPI `Query(min_length=1)` vs
  service-level whitespace check.

- **Recent-files storage key.** `dirt.wiki.recentFiles`, capped at 8
  entries, MRU-first, de-duplicated by path. Stored as
  `JSON.stringify(Array<{path, title}>)` under the existing
  `src/shared/storage.ts` owner (TS-09). A corrupt payload parses to
  `[]` so a bad write doesn't brick the palette.

- **Palette debounce.** 150ms — long enough that each keystroke inside
  a word doesn't fan out, short enough to feel live once the user
  pauses. The `enabled` guard on the TanStack Query search hook is
  what actually prevents the empty-`q` request; the debounce is a
  UX-side optimization on top.

- **Markdown renderer.** None. `body_markdown` is rendered into a
  `<pre class="whitespace-pre-wrap">` with a monospace font, which
  satisfies the plan's "renders raw markdown with frontmatter block +
  breadcrumb" requirement without pulling in `react-markdown`. Swapping
  in a compiled-HTML renderer later is a one-component change behind
  the `WikiDoc` boundary. The schema's comment (`# SPA renders with
  react-markdown`) is aspirational; this feature ships the raw-text
  step without the dep.

- **Search params model.** `validateSearch` returns `{ path: rawPath }`
  when the query string has a non-empty `path`, else `{}` (not
  `{ path: null }`) — so bare `/wiki` stays bare in the URL instead of
  serializing as `/wiki?path=null` (which was breaking the app-shell
  spec until I switched from nullable to optional).

- **Cmd+K active-index reset.** Initial approach used an
  index-plus-listKey tagged state to avoid an `useEffect([query])`
  reset (Biome's `useExhaustiveDependencies` was calling the deps
  unsafe). Simplified in the simplify pass: plain `useState(0)` +
  `setActiveIdx(0)` call inside the input's `onChange`, plus a render-
  time clamp `Math.min(rawActiveIdx, items.length - 1)` so a shrinking
  list doesn't commit a stale selection.

- **ESLint e2e-window exception.** Added
  `{ files: ["tests/e2e/**/*.ts"], rules: { "no-restricted-globals":
  "off" } }` to `web-ui/eslint.config.ts` (agent-editable shim, not the
  invariant config) so Playwright's `addInitScript` can touch
  `window.localStorage` directly. `no-restricted-globals` is NOT in
  the meta-invariant's `KNOWN_SENTINELS`, so this override is safe.
