#!/usr/bin/env bash
# Acceptance check for frontend.login.
#
# Runs against a live `pnpm dev` on :5173 (or BASE_URL). Dev mode means
# MSW is active in the browser — FE's /api/auth/login handler MUST
# return 200 for username="admin"/password="changeme" and 401 for
# anything else. Those are the contract between this script and the
# FE generator's MSW fixture.
#
# State-reading convention: `agent-browser eval` + DOM queries, not
# `agent-browser snapshot` + grep. See
# docs/plans/evaluator-checks/app-shell.sh for the doctrine. Same
# rationale applies: aria-invalid / aria-describedby / visible error
# text is what real Playwright tests read, and what real screen readers
# announce.
#
# Asserts:
#   - /login route renders (pathname == /login, not redirected away).
#   - Form has username + password + submit (button or input[type=submit]).
#   - Field-notes block renders with the hardcoded copy
#     (grow / day / plants / loc / agent tokens).
#   - Submitting with "bad"/"wrong" produces a visible error indicator
#     (role=alert OR aria-invalid=true OR text matching /invalid|incorrect|failed|error/i).
#   - Submitting with "admin"/"changeme" navigates to /.
#   - Console is clean.
#
# Exit 0 on pass. Any failed assertion prints "FAIL: ..." and exits
# non-zero. Evaluator re-verifies assertions independently.

set -euo pipefail

BASE=${BASE_URL:-http://localhost:5173}

fail() { echo "FAIL: $*" >&2; exit 1; }

# See app-shell.sh for the helper rationale.
ab_eval() {
    agent-browser eval "$1" | awk 'NF' | tail -1 | sed -e 's/^"//' -e 's/"$//'
}

agent-browser open "$BASE/login"
agent-browser wait 800

# Route rendered (and not redirected to / by a premature auth check).
path=$(ab_eval "location.pathname")
[ "$path" = "/login" ] || fail "not on /login after open (saw: \"$path\")"

# Form fields. Accept either <input name="..."> or <input id="..."> —
# HTML-form convention is name; either works for assistive tech.
has_username=$(ab_eval "
  !!(document.querySelector('input[name=username]') || document.querySelector('input[id=username]'))
")
[ "$has_username" = "true" ] || fail "username input not found"

has_password=$(ab_eval "
  !!(document.querySelector('input[name=password]') || document.querySelector('input[id=password]'))
")
[ "$has_password" = "true" ] || fail "password input not found"

has_submit=$(ab_eval "
  !!Array.from(document.querySelectorAll('button, input[type=submit]'))
    .find(el => /sign in|log in|submit|enter/i.test(el.textContent || el.value || ''))
")
[ "$has_submit" = "true" ] || fail "submit control (button or input[type=submit]) not found"

# Field-notes hardcoded copy.
body_text=$(ab_eval "document.body.textContent")
for tok in grow day plants loc agent; do
    echo "$body_text" | grep -qi "$tok" \
      || fail "field-notes block missing token: $tok"
done

# Bad credentials → error indicator.
agent-browser eval "
(() => {
  const u = document.querySelector('input[name=username]') || document.querySelector('input[id=username]');
  const p = document.querySelector('input[name=password]') || document.querySelector('input[id=password]');
  u.value = 'bad';
  p.value = 'wrong';
  u.dispatchEvent(new Event('input', { bubbles: true }));
  p.dispatchEvent(new Event('input', { bubbles: true }));
  const form = u.closest('form');
  if (form && form.requestSubmit) form.requestSubmit();
  else if (form) form.submit();
  else {
    const btn = Array.from(document.querySelectorAll('button, input[type=submit]'))
      .find(el => /sign in|log in|submit|enter/i.test(el.textContent || el.value || ''));
    btn && btn.click();
  }
})()
" > /dev/null
agent-browser wait 1000

err_visible=$(ab_eval "
  Array.from(document.querySelectorAll('[role=alert], [aria-invalid=true], [aria-describedby]'))
    .some(el => el.offsetParent !== null && (el.textContent || '').trim().length > 0)
  || /invalid|incorrect|failed|error|unauthor/i.test(document.body.textContent)
")
[ "$err_visible" = "true" ] || fail "bad creds did not produce a visible error indicator"

# Still on /login (bad creds must not navigate away).
path_after_bad=$(ab_eval "location.pathname")
[ "$path_after_bad" = "/login" ] || fail "bad creds navigated away from /login (saw: \"$path_after_bad\")"

# Clear fields + good credentials → navigate to /.
agent-browser eval "
(() => {
  const u = document.querySelector('input[name=username]') || document.querySelector('input[id=username]');
  const p = document.querySelector('input[name=password]') || document.querySelector('input[id=password]');
  u.value = 'admin';
  p.value = 'changeme';
  u.dispatchEvent(new Event('input', { bubbles: true }));
  p.dispatchEvent(new Event('input', { bubbles: true }));
  const form = u.closest('form');
  if (form && form.requestSubmit) form.requestSubmit();
  else if (form) form.submit();
  else {
    const btn = Array.from(document.querySelectorAll('button, input[type=submit]'))
      .find(el => /sign in|log in|submit|enter/i.test(el.textContent || el.value || ''));
    btn && btn.click();
  }
})()
" > /dev/null
agent-browser wait 1500

path_after_good=$(ab_eval "location.pathname")
[ "$path_after_good" = "/" ] || fail "good creds did not navigate to / (saw: \"$path_after_good\")"

# Console clean.
errs=$(agent-browser console | grep -iE '\b(error|uncaught)\b' || true)
[ -z "$errs" ] || fail "console errors present: $errs"

echo "PASS"
