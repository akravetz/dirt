#!/usr/bin/env bash
# Acceptance check for frontend.app.shell.
#
# Convention (applies to every script in docs/plans/evaluator-checks/):
# read STATE via `agent-browser eval` + DOM queries, NOT via
# `agent-browser snapshot` + grep. The Playwright-style simplified a11y
# tree strips aria-current / aria-selected / aria-pressed off native
# <button>, which pushes components toward ugly sr-only-tablist
# workarounds whose sole purpose is to make the test harness detect
# state. DOM queries read the real thing; real Playwright / Cypress /
# Testing Library tests read the real thing too, so the same markup
# carries forward to e2e.
#
# Asserts:
#   - "dirt." brand heading renders
#   - Exactly 3 tab buttons — Dashboard / Live / Wiki
#   - Theme toggle button present (accessible name matches /theme|light|dark/i)
#   - Clicking each tab navigates to the expected route
#   - Clicked tab carries aria-current="page" (the idiomatic ARIA
#     pattern for primary-nav active state)
#   - Console is clean
#
# Exit 0 on pass. Any failed assertion prints "FAIL: ..." and exits
# non-zero. The evaluator re-verifies each assertion independently;
# this script is the documented rubric, not the ultimate authority.

set -euo pipefail

BASE=${BASE_URL:-http://localhost:5173}

fail() { echo "FAIL: $*" >&2; exit 1; }

# agent-browser eval prints the return value on stdout after any status
# lines. Filter blanks, take the last non-empty line, strip surrounding
# JSON string quotes. Works for strings, numbers, booleans, null.
ab_eval() {
    agent-browser eval "$1" | awk 'NF' | tail -1 | sed -e 's/^"//' -e 's/"$//'
}

agent-browser open "$BASE/"
agent-browser wait 500

# Brand heading. Accept either "dirt" or "dirt." so the trailing glyph
# can be a styled <span> without breaking the grep.
brand=$(ab_eval "document.querySelector('h1')?.textContent?.trim() ?? ''")
[[ "$brand" == *"dirt"* ]] || fail "brand \"dirt.\" not in <h1> (saw: \"$brand\")"

# Exactly 3 tab buttons whose visible label is Dashboard / Live / Wiki.
tab_count=$(ab_eval "
  Array.from(document.querySelectorAll('button'))
    .filter(el => ['Dashboard','Live','Wiki'].includes(el.textContent.trim()))
    .length
")
[ "$tab_count" = "3" ] || fail "expected 3 tab buttons (Dashboard/Live/Wiki), saw $tab_count"

# Theme toggle: any button whose accessible name (aria-label or visible
# text) matches /theme|light|dark/i.
has_theme_toggle=$(ab_eval "
  Array.from(document.querySelectorAll('button')).some(el => {
    const name = (el.getAttribute('aria-label') || el.textContent || '').trim();
    return /theme|light|dark/i.test(name);
  })
")
[ "$has_theme_toggle" = "true" ] || fail "theme toggle button not found"

# Click each tab; verify URL + aria-current=page on the clicked button.
for pair in "Dashboard=/" "Live=/live" "Wiki=/wiki"; do
    label=${pair%=*}
    expected=${pair#*=}

    # IIFE because agent-browser eval reuses the global scope across
    # calls — bare `const btn` on the second iteration would collide
    # with the first. A fresh arrow-function scope sidesteps it.
    agent-browser eval "
      (() => {
        const btn = Array.from(document.querySelectorAll('button'))
          .find(el => el.textContent.trim() === '$label');
        if (!btn) throw new Error('tab button not found: $label');
        btn.click();
      })()
    " > /dev/null
    agent-browser wait 400

    url=$(ab_eval "location.pathname")
    [ "$url" = "$expected" ] || fail "$label click → pathname=$url (expected $expected)"

    current=$(ab_eval "
      Array.from(document.querySelectorAll('button'))
        .find(el => el.textContent.trim() === '$label')
        ?.getAttribute('aria-current') ?? ''
    ")
    [ "$current" = "page" ] || fail "$label tab not marked aria-current=page after click (saw: \"$current\")"
done

# Console must be clean — no error/uncaught entries.
errs=$(agent-browser console | grep -iE '\b(error|uncaught)\b' || true)
[ -z "$errs" ] || fail "console errors present: $errs"

echo "PASS"
