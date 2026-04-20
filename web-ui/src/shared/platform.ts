// web-ui/src/shared/platform.ts
//
// Single-ownership wrapper around `window`. TS-10 (invariant) pins this
// file as the ONLY place in the app allowed to touch `window` / its
// sub-objects. Everywhere else imports typed methods from here.
//
// Why: the browser global is implicitly mutable and not present in SSR
// / unit-test environments. Funneling every access through one module
// gives tests a single mock surface and keeps the rest of the app
// platform-agnostic.

export const platform = {
  async copyToClipboard(value: string): Promise<void> {
    await window.navigator.clipboard.writeText(value);
  },
  reload(): void {
    window.location.reload();
  },
  getOrigin(): string {
    return window.location.origin;
  },
} as const;
