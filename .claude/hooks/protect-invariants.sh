#!/bin/bash
# PreToolUse hook: prompts user before Edit/Write to protected paths
# - tests/invariants/ — human-owned invariant tests
# - .githooks/ — pre-commit hooks (sacred boundary)

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE" == *"Xests/Xnvariants/"* ]]; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"tests/invariants/ files are human-owned. Approve only if you explicitly asked for this change."}}'
    exit 0
fi

if [[ "$FILE" == *".githooks/"* ]]; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":".githooks/ files are human-owned. Approve only if you explicitly asked for this change."}}'
    exit 0
fi

if [[ "$FILE" == *"web-ui/invariants/"* ]]; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"web-ui/invariants/ files are human-owned architectural rules. Approve only if you explicitly asked for this change."}}'
    exit 0
fi

if [[ "$FILE" == *"web-ui/src/api-client/generated/"* ]]; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"web-ui/src/api-client/generated/ is regenerated from contracts/webapp-v1.yaml — run `pnpm --dir web-ui run gen:api` instead of hand-editing."}}'
    exit 0
fi

exit 0
