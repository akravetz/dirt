// Cmd+K search palette for the /wiki route.
//
// Controlled: the parent owns `query`, debounces it into a TanStack
// Query key, and passes `results` + `recents` in as props. The palette
// is pure UI — keyboard nav (ArrowUp/Down + Enter + Escape), open/close
// visibility, and the filename-vs-recent rendering rule ("empty q →
// recents; non-empty → results"). No data fetching, no localStorage
// access here (TS-09 routes that through shared/storage via the route).
//
// Boundaries: ui/ → ui/ + shared/ only. The SearchResult / RecentItem
// types mirror contracts/webapp-v1.yaml #/components/schemas/
// WikiSearchResult and web-ui/src/shared/storage.ts#RecentWikiFile —
// drift surfaces in routes/wiki.tsx's typecheck.
import { useEffect, useRef, useState } from "react";

export interface PaletteSearchResult {
  path: string;
  title: string;
  match_type: "title" | "path" | "content";
  snippet?: string | null;
}
interface PaletteRecentItem {
  path: string;
  title: string;
}
type PaletteItem =
  | { kind: "result"; item: PaletteSearchResult }
  | { kind: "recent"; item: PaletteRecentItem };

interface CmdKPaletteProps {
  open: boolean;
  query: string;
  onQueryChange: (next: string) => void;
  onClose: () => void;
  onSelect: (path: string, title: string) => void;
  // Non-empty-query results (already fetched by the parent's TanStack
  // Query hook, so the palette stays presentational).
  results: readonly PaletteSearchResult[];
  // Empty-query fallback — shown instead of running a search for "".
  recents: readonly PaletteRecentItem[];
}

export function CmdKPalette({
  open,
  query,
  onQueryChange,
  onClose,
  onSelect,
  results,
  recents,
}: CmdKPaletteProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [rawActiveIdx, setActiveIdx] = useState(0);

  // Focus-on-open. useEffect here is DOM-focus lifecycle (not data-
  // fetching) so TS-06 does not apply.
  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  if (!open) return null;

  const items: PaletteItem[] =
    query.trim().length === 0
      ? recents.map((r) => ({ kind: "recent" as const, item: r }))
      : results.map((r) => ({ kind: "result" as const, item: r }));

  // Clamp the index to the current list so transient states (list
  // shrank, user cleared the query) don't commit a stale selection.
  const activeIdx = items.length === 0 ? 0 : Math.min(rawActiveIdx, items.length - 1);

  const commit = (idx: number) => {
    const entry = items[idx];
    if (!entry) return;
    onSelect(entry.item.path, entry.item.title);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIdx((i) => (items.length === 0 ? 0 : Math.min(i + 1, items.length - 1)));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      commit(activeIdx);
    }
  };

  return (
    <div
      data-testid="cmdk-overlay"
      className="fixed inset-0 z-50 flex items-start justify-center bg-ink/30 pt-24"
    >
      <button
        type="button"
        aria-label="Close search"
        tabIndex={-1}
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-transparent"
      />
      <div
        role="dialog"
        aria-label="Search wiki"
        data-testid="cmdk-palette"
        onKeyDown={handleKeyDown}
        className="relative flex w-[min(640px,90vw)] flex-col border border-rule bg-paper shadow-lg"
      >
        <div className="flex items-center gap-3 border-b border-rule px-4 py-3">
          <span className="font-mono text-xs uppercase tracking-caps text-ink-3">
            Search
          </span>
          <input
            ref={inputRef}
            type="text"
            aria-label="Search wiki"
            placeholder="filename or content…"
            value={query}
            onChange={(e) => {
              setActiveIdx(0);
              onQueryChange(e.target.value);
            }}
            className="flex-1 bg-transparent font-sans text-sm text-ink outline-none placeholder:text-ink-3"
          />
          <kbd className="font-mono text-xs uppercase tracking-caps text-ink-3">
            ESC
          </kbd>
        </div>

        {items.length === 0 ? (
          <p className="px-4 py-4 font-mono text-xs uppercase tracking-caps text-ink-3">
            {query.trim().length === 0 ? "No recent files" : "No matches"}
          </p>
        ) : (
          <ul className="flex max-h-80 list-none flex-col overflow-auto">
            {items.map((entry, idx) => {
              const active = idx === activeIdx;
              const tag = entry.kind === "recent" ? "RECENT" : entry.item.match_type;
              return (
                <li key={`${entry.kind}:${entry.item.path}`}>
                  <button
                    type="button"
                    data-testid="cmdk-item"
                    data-kind={entry.kind}
                    data-path={entry.item.path}
                    onMouseEnter={() => {
                      setActiveIdx(idx);
                    }}
                    onClick={() => {
                      commit(idx);
                    }}
                    className={
                      active
                        ? "flex w-full items-center justify-between gap-3 border-l-2 border-accent-magenta bg-rule/30 px-4 py-2 text-left"
                        : "flex w-full items-center justify-between gap-3 border-l-2 border-transparent px-4 py-2 text-left hover:bg-rule/30"
                    }
                  >
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate text-sm text-ink">
                        {entry.item.title}
                      </span>
                      {entry.kind === "result" && entry.item.snippet ? (
                        <span className="truncate font-mono text-xs text-ink-3">
                          {entry.item.snippet}
                        </span>
                      ) : null}
                    </span>
                    <span className="flex items-center gap-2 font-mono text-xs uppercase tracking-caps text-ink-3">
                      <span className="truncate">{entry.item.path}</span>
                      <span className="border border-rule px-1.5 py-0.5">{tag}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <footer className="flex items-center justify-between border-t border-rule px-4 py-2 font-mono text-xs uppercase tracking-caps text-ink-3">
          <span>↑↓ NAVIGATE · ↵ OPEN · ESC CLOSE</span>
          <span>
            {items.length} {items.length === 1 ? "RESULT" : "RESULTS"}
          </span>
        </footer>
      </div>
    </div>
  );
}
