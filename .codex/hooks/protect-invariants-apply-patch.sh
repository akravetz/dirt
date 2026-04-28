#!/usr/bin/env bash
# Codex PreToolUse hook (apply_patch): denies patches targeting protected paths.
#
# Codex sends the raw patch in tool_input.command. We inspect patch headers rather
# than free text so comments or code strings mentioning a protected path do not
# block unrelated edits.

set -euo pipefail

INPUT=$(cat)
PATCH=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$PATCH" ] && exit 0

is_contract_status() {
  case "$1" in
    apps/tests/invariants/contract_status.json|*/apps/tests/invariants/contract_status.json)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_protected_path() {
  local path="$1"
  case "$path" in
    apps/tests/invariants|*/apps/tests/invariants|apps/tests/invariants/*|*/apps/tests/invariants/*|\
    .githooks|*/.githooks|.githooks/*|*/.githooks/*|\
    web-ui/invariants|*/web-ui/invariants|web-ui/invariants/*|*/web-ui/invariants/*|\
    web-ui/src/api-client/generated|*/web-ui/src/api-client/generated|web-ui/src/api-client/generated/*|*/web-ui/src/api-client/generated/*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

deny() {
  local path="$1"
  jq -n --arg path "$path" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "apply_patch targets protected path \($path). Stop and ask the user for an explicit migration or human-owned-file exception before proceeding."
    }
  }'
}

while IFS= read -r path; do
  path=${path%$'\r'}
  [ -z "$path" ] && continue
  if is_contract_status "$path"; then
    continue
  fi
  if is_protected_path "$path"; then
    deny "$path"
    exit 0
  fi
done < <(
  printf '%s\n' "$PATCH" |
    sed -nE 's/^\*\*\* (Add|Update|Delete) File:[[:space:]]*//p; s/^\*\*\* Move to:[[:space:]]*//p'
)

exit 0
