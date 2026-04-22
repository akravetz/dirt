#!/bin/bash
# Regression harness for .claude/hooks/protect-invariants-bash.sh
# Run: bash .claude/hooks/test-protect-invariants-bash.sh
#
# Exits 0 on pass, non-zero on any case mis-decision.
# Each case declares the input command and whether the hook should ASK
# or EXIT CLEAN. Feeds the command to the hook via the same JSON shape
# Claude Code emits (PreToolUse envelope) and checks the output.

HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/protect-invariants-bash.sh"

pass=0
fail=0
check() {
  local expect="$1"  # "ask" or "clean"
  local cmd="$2"
  local desc="$3"

  local input
  input=$(jq -n --arg c "$cmd" '{tool_input: {command: $c}}')
  local output
  output=$(echo "$input" | bash "$HOOK")

  local got="clean"
  if echo "$output" | grep -q '"permissionDecision":"ask"'; then
    got="ask"
  fi

  if [ "$got" = "$expect" ]; then
    pass=$((pass + 1))
    printf "  [PASS] %s\n" "$desc"
  else
    fail=$((fail + 1))
    printf "  [FAIL] %s\n         cmd: %s\n         expected=%s got=%s\n" "$desc" "$cmd" "$expect" "$got"
  fi
}

echo "=== Reads that must NOT trigger ==="
check clean "uv run pytest apps/tests/invariants/test_import_boundaries.py -v" "pytest path"
check clean "uv run pytest apps/tests/invariants/ -q" "pytest dir"
check clean "uv run pytest -k invariants" "pytest -k"
check clean "cat apps/tests/invariants/_helpers.py"                "cat read"
check clean "grep format_invariant apps/tests/invariants/_helpers.py" "grep read"
check clean "ls web-ui/invariants/"                                "ls"
check clean "diff <(git show HEAD:apps/tests/invariants/foo.py) apps/tests/invariants/foo.py" "diff"
check clean "cd apps/tests/invariants && pytest test_schema_managed_by_atlas.py" "cd then read"
check clean "echo 'foo' # remembers web-ui/invariants"             "comment mention only"
check clean "git log apps/tests/invariants/"                       "git log"
check clean "git diff --stat adddf30 -- apps/tests/invariants/"    "git diff"

echo ""
echo "=== Substrings that must NOT trigger (historical false-positives) ==="
check clean "uv run ruff check apps/"                              "ruff check (no path)"
check clean "uv run pytest -k 'compare or remove'"                 "pytest -k with cp/rm substrings"
check clean "grep 'remove' apps/shared/src/dirt_shared/services/foo.py" "remove substring"

echo ""
echo "=== Writes that MUST trigger ==="
check ask   "rm apps/tests/invariants/test_foo.py"                 "rm file"
check ask   "rm -rf apps/tests/invariants/"                        "rm -rf dir"
check ask   "mv /tmp/foo apps/tests/invariants/new_test.py"        "mv into protected"
check ask   "mv apps/tests/invariants/old.py /tmp/archive"         "mv out of protected"
check ask   "cp /tmp/new apps/tests/invariants/x.py"               "cp into protected"
check ask   "sed -i 's/a/b/' apps/tests/invariants/test_x.py"      "sed -i"
check ask   "sed -i.bak 's/a/b/' apps/tests/invariants/test_x.py"  "sed -i.bak"
check ask   "awk -i inplace '{print}' apps/tests/invariants/x.py"  "awk -i inplace"
check ask   "echo 'x' > apps/tests/invariants/new.py"              "echo redirect"
check ask   "echo 'x' >> apps/tests/invariants/new.py"             "echo append"
check ask   "cat <<EOF > web-ui/invariants/eslint.config.ts"       "heredoc redirect"
check ask   "tee web-ui/invariants/eslint.config.ts"               "tee target"
check ask   "tee -a .githooks/pre-commit"                          "tee -a target"
check ask   "mkdir -p apps/tests/invariants/new_dir"               "mkdir -p"
check ask   "chmod +x .githooks/pre-commit"                        "chmod"
check ask   "touch web-ui/src/api-client/generated/marker"         "touch generated"
check ask   "ln -sf /tmp/x apps/tests/invariants/link.py"          "ln -sf"

echo ""
echo "=== Compound commands ==="
check clean "sed -i 's/a/b/' foo.py; cat apps/tests/invariants/X.py" "sed on unprotected THEN read protected"
check ask   "cd /tmp && rm apps/tests/invariants/X.py"             "&& chain, rm"
check ask   "rm /tmp/foo; rm apps/tests/invariants/X.py"            "second cmd in sequence"

echo ""
echo "=== contract_status.json carve-out (agent-editable data file) ==="
check clean "sed -i 's/a/b/' apps/tests/invariants/contract_status.json" "sed -i on contract_status"
check clean "echo '{}' > apps/tests/invariants/contract_status.json" "echo redirect to contract_status"
check clean "cat new.json > apps/tests/invariants/contract_status.json" "cat redirect to contract_status"
check clean "tee apps/tests/invariants/contract_status.json"       "tee contract_status"
check clean "tee -a apps/tests/invariants/contract_status.json"    "tee -a contract_status"
check clean "rm apps/tests/invariants/contract_status.json"        "rm contract_status (still clean — agent-editable)"
check clean "mv /tmp/new.json apps/tests/invariants/contract_status.json" "mv into contract_status"
check clean "jq '.expected_missing' apps/tests/invariants/contract_status.json > /tmp/foo" "read via redirect; target unprotected"
check clean "sed -i 's/a/b/' apps/tests/invariants/contract_status.json && git add apps/tests/invariants/contract_status.json" "edit then git add — both segments"

echo ""
echo "=== contract_status.json mixed with OTHER protected file — still ask ==="
check ask   "sed -i 's/x/y/' apps/tests/invariants/test_foo.py apps/tests/invariants/contract_status.json" "sed -i test_* AND contract_status"
check ask   "mv apps/tests/invariants/contract_status.json apps/tests/invariants/test_evil.py" "mv rename contract_status → test_*"
check ask   "cat new.json > apps/tests/invariants/contract_status.json; rm apps/tests/invariants/test_foo.py" "contract_status redirect THEN rm test_*"
check ask   "echo x > web-ui/invariants/eslint.config.ts; sed -i 's/a/b/' apps/tests/invariants/contract_status.json" "web-ui/invariants mixed with contract_status"

echo ""
echo "=============================================="
echo "  $pass passed, $fail failed"
echo "=============================================="
if [ "$fail" -gt 0 ]; then
  exit 1
fi
exit 0
