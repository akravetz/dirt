#!/usr/bin/env bash
# Acceptance check for frontend.app.shell.
#
# Drives the live web-ui on :5173 via agent-browser. Asserts:
#   - dirt. brand heading renders
#   - Dashboard / Live / Wiki tabs render (exactly 3)
#   - theme toggle renders
#   - clicking each tab changes the URL to the expected route
#   - clicking each tab marks its tab "active" in the accessibility tree
#
# Exit 0 → pass. Any failed assertion prints "FAIL: ..." and exits non-zero.
# The evaluator re-verifies each assertion independently; this script is
# a documented checklist, not the source of truth.

set -euo pipefail

BASE=${BASE_URL:-http://localhost:5173}

fail() { echo "FAIL: $*" >&2; exit 1; }

agent-browser open "$BASE/"
agent-browser wait 500

snap=$(agent-browser snapshot)

# Brand
grep -q 'heading "dirt."' <<<"$snap" || fail "brand heading \"dirt.\" not in snapshot"

# Exactly 3 tab buttons
tab_count=$(grep -Ec 'button "(Dashboard|Live|Wiki)"' <<<"$snap" || true)
[ "$tab_count" = "3" ] || fail "expected 3 tab buttons (Dashboard/Live/Wiki), saw $tab_count"

# Theme toggle — accept common labels
grep -Eq 'button "(Theme|Toggle theme|Light|Dark)"' <<<"$snap" \
  || fail "theme toggle button not in snapshot"

# Navigate each tab + verify URL and active marker
for pair in "Dashboard=/" "Live=/live" "Wiki=/wiki"; do
  label=${pair%=*}
  expected=${pair#*=}

  agent-browser eval "Array.from(document.querySelectorAll('button,a')).find(el => el.textContent.trim()==='$label').click()"
  agent-browser wait 400

  url=$(agent-browser eval "location.pathname" | tail -1 | tr -d '"')
  [ "$url" = "$expected" ] || fail "$label click → pathname=$url (expected $expected)"

  # Active-tab marker: the clicked tab should carry aria-current="page" or
  # a data-active / aria-selected indicator. Check the a11y tree for any
  # of those on the matching button/link.
  agent-browser snapshot | grep -Eq "\"$label\".*(current|selected|active)" \
    || fail "$label tab not marked active after click"
done

# Console must be clean
errs=$(agent-browser console | grep -iE '\b(error|uncaught)\b' || true)
[ -z "$errs" ] || fail "console errors present: $errs"

echo "PASS"
