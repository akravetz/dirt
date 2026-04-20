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

exit 0
