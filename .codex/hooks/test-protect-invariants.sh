#!/usr/bin/env bash
# Regression harness for Codex protected-path hooks.
# Run: bash .codex/hooks/test-protect-invariants.sh

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BASH_HOOK="$HERE/protect-invariants-bash.sh"
PATCH_HOOK="$HERE/protect-invariants-apply-patch.sh"

pass=0
fail=0

check_hook() {
  local hook="$1"
  local expect="$2"
  local payload="$3"
  local desc="$4"

  local output got
  output=$(jq -n --arg c "$payload" '{tool_input: {command: $c}}' | bash "$hook")

  got="clean"
  if echo "$output" | grep -q '"permissionDecision": "deny"\|"permissionDecision":"deny"'; then
    got="deny"
  fi

  if [ "$got" = "$expect" ]; then
    pass=$((pass + 1))
    printf "  [PASS] %s\n" "$desc"
  else
    fail=$((fail + 1))
    printf "  [FAIL] %s\n         expected=%s got=%s\n         payload: %s\n" "$desc" "$expect" "$got" "$payload"
  fi
}

check_bash() {
  check_hook "$BASH_HOOK" "$@"
}

check_patch() {
  check_hook "$PATCH_HOOK" "$@"
}

echo "=== Bash reads that must NOT trigger ==="
check_bash clean "uv run pytest apps/tests/invariants/test_import_boundaries.py -v" "pytest path"
check_bash clean "cat apps/tests/invariants/_helpers.py" "cat read"
check_bash clean "git diff --stat -- apps/tests/invariants/" "git diff"

echo ""
echo "=== Bash writes that MUST deny ==="
check_bash deny "rm apps/tests/invariants/test_foo.py" "rm file"
check_bash deny "echo 'x' > apps/tests/invariants/new.py" "redirect"
check_bash deny "tee -a .githooks/pre-commit" "tee"
check_bash deny "touch web-ui/src/api-client/generated/marker" "generated"

echo ""
echo "=== apply_patch clean cases ==="
check_patch clean $'*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch' "unprotected update"

echo ""
echo "=== apply_patch protected cases ==="
check_patch deny $'*** Begin Patch\n*** Update File: apps/tests/invariants/test_foo.py\n@@\n-old\n+new\n*** End Patch' "invariant update"
check_patch deny $'*** Begin Patch\n*** Add File: .githooks/pre-commit\n+#!/usr/bin/env bash\n*** End Patch' "githook add"
check_patch deny $'*** Begin Patch\n*** Delete File: web-ui/invariants/README.md\n*** End Patch' "web-ui invariant delete"
check_patch deny $'*** Begin Patch\n*** Update File: tmp.txt\n*** Move to: web-ui/src/api-client/generated/tmp.txt\n*** End Patch' "generated move"

echo ""
echo "=============================================="
echo "  $pass passed, $fail failed"
echo "=============================================="
if [ "$fail" -gt 0 ]; then
  exit 1
fi
