// Minimum-viable shared helpers for the e2e suite.
//
// GROWTH RULE: do NOT pre-build helpers here. Add a helper only when a
// second spec genuinely needs it — otherwise you end up with a pile of
// single-call-site abstractions that obscure what each spec is
// actually doing. When in doubt, inline the Playwright primitive in
// the spec; factor out only on second use.
import type { ConsoleMessage, Page } from "@playwright/test";

/**
 * Collect every `console.error` / `console.warning.level === "error"`
 * entry emitted by `page` between the time this helper is called and
 * the returned `read()` is invoked.
 *
 * Why this exists: the app-shell acceptance (and every future FE
 * feature's acceptance) must assert a clean console. Playwright does
 * not buffer console events — if you call `page.on("console", ...)`
 * after the navigation that produced them, you miss the entries. Wire
 * this up BEFORE `page.goto(...)`.
 *
 * Pageerror ("uncaught exception") entries are also captured: they
 * surface as `Error` instances in the DevTools console at error level,
 * so a clean-console assertion should treat them as errors too.
 */
export function collectConsoleErrors(page: Page): { read: () => string[] } {
  const errors: string[] = [];
  const onConsole = (msg: ConsoleMessage) => {
    if (msg.type() === "error") {
      errors.push(msg.text());
    }
  };
  const onPageError = (err: Error) => {
    errors.push(`pageerror: ${err.message}`);
  };
  page.on("console", onConsole);
  page.on("pageerror", onPageError);
  return {
    read: () => [...errors],
  };
}
