#!/usr/bin/env bash
# Codex PreToolUse hook (Bash): denies Bash commands that write to protected paths.
#
# Protected paths:
#   - apps/tests/invariants/**
#   - .githooks/**
#   - web-ui/invariants/**
#   - web-ui/src/api-client/generated/**

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

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
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"This command appears to write to a protected path (apps/tests/invariants/**, .githooks/**, web-ui/invariants/**, or web-ui/src/api-client/generated/**). Stop and ask the user for an explicit migration or human-owned-file exception before proceeding."}}
JSON
    exit 0
  fi
done

exit 0
