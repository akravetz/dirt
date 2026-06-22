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
