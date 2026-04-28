#!/usr/bin/env bash
# Codex PreToolUse hook (Bash): denies Bash commands that write to protected paths.
#
# Protected paths:
#   - apps/tests/invariants/** except apps/tests/invariants/contract_status.json
#   - .githooks/**
#   - web-ui/invariants/**
#   - web-ui/src/api-client/generated/**

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

PROTECTED_TOKENS=$(echo "$COMMAND" | grep -oE '(apps/tests/invariants/[^ ,;&|"'"'"'`)>]+|\.githooks/[^ ,;&|"'"'"'`)>]+|web-ui/invariants/[^ ,;&|"'"'"'`)>]+|web-ui/src/api-client/generated/[^ ,;&|"'"'"'`)>]+)' || true)
if [ -n "$PROTECTED_TOKENS" ]; then
    NON_WHITELISTED=$(echo "$PROTECTED_TOKENS" | grep -vE '(^|/)apps/tests/invariants/contract_status\.json$' | head -1 || true)
    if [ -z "$NON_WHITELISTED" ]; then
        exit 0
    fi
fi

PATHS='(apps/tests/invariants|\.githooks|web-ui/invariants|web-ui/src/api-client/generated)'
WB='(^|[[:space:];&|(])'
NOSEP='[^;&|]*'

PATTERNS=(
  "${WB}(sed|awk|gawk)[[:space:]]+-[a-zA-Z]*i[a-zA-Z.]*([[:space:]]|$)${NOSEP}${PATHS}"
  "(>>?|tee([[:space:]]+-a)?)[[:space:]]*['\"]?${PATHS}"
  "${WB}(rm|rmdir|chmod|chown|touch|mkdir|install|ln)[[:space:]]${NOSEP}${PATHS}"
  "${WB}(mv|cp)[[:space:]]${NOSEP}${PATHS}"
)

for p in "${PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$p"; then
    cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"This command appears to write to a protected path (apps/tests/invariants/** except contract_status.json, .githooks/**, web-ui/invariants/**, or web-ui/src/api-client/generated/**). Stop and ask the user for an explicit migration or human-owned-file exception before proceeding."}}
JSON
    exit 0
  fi
done

exit 0
