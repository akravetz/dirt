// web-ui/src/shared/storage.ts
//
// Single-ownership wrapper around localStorage / sessionStorage.
// TS-09 (invariant) pins this file as the ONLY place in the app allowed
// to touch those globals. Everywhere else — components, routes,
// features, api-client — imports from here.
//
// Why: tests get one mock surface; SSR / non-browser environments get
// one shim surface; the rest of the app stays storage-agnostic.

export const storage = {
  get(key: string): string | null {
    return localStorage.getItem(key);
  },
  set(key: string, value: string): void {
    localStorage.setItem(key, value);
  },
  remove(key: string): void {
    localStorage.removeItem(key);
  },
  session: {
    get(key: string): string | null {
      return sessionStorage.getItem(key);
    },
    set(key: string, value: string): void {
      sessionStorage.setItem(key, value);
    },
    remove(key: string): void {
      sessionStorage.removeItem(key);
    },
  },
} as const;

// ---------------------------------------------------------------------------
// Wiki recent-files list — frontend.wiki
//
// Cmd+K palette's empty-query state shows the user's recently-opened wiki
// pages. Kept MRU (most-recent first), de-duplicated by path, capped at
// RECENT_WIKI_FILES_MAX entries. Stored as a JSON array of
// {path, title} under a stable key; malformed/legacy payloads parse to
// the empty list so a bad write doesn't brick the palette.
// ---------------------------------------------------------------------------

const RECENT_WIKI_FILES_KEY = "dirt.wiki.recentFiles";
const RECENT_WIKI_FILES_MAX = 8;

export interface RecentWikiFile {
  path: string;
  title: string;
}

function isRecentWikiFile(value: unknown): value is RecentWikiFile {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.path === "string" && typeof v.title === "string";
}

export function readRecentWikiFiles(): RecentWikiFile[] {
  const raw = storage.get(RECENT_WIKI_FILES_KEY);
  if (raw === null) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isRecentWikiFile).slice(0, RECENT_WIKI_FILES_MAX);
  } catch {
    return [];
  }
}

export function pushRecentWikiFile(entry: RecentWikiFile): RecentWikiFile[] {
  const current = readRecentWikiFiles().filter((e) => e.path !== entry.path);
  const next = [entry, ...current].slice(0, RECENT_WIKI_FILES_MAX);
  storage.set(RECENT_WIKI_FILES_KEY, JSON.stringify(next));
  return next;
}
