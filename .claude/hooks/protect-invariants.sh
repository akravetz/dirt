#!/bin/bash
# PreToolUse hook: blocks Edit/Write to tests/invariants/
# Invariant tests are human-owned and must not be modified by the agent.

INPUT=$(cat /dev/stdin)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE" == *"tests/invariants/"* ]]; then
    echo "BLOCKED: tests/invariants/ files are human-owned invariant tests. You MUST NOT modify these files. If an invariant test fails, fix your code to satisfy the test." >&2
    exit 2
fi
exit 0
