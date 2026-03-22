#!/bin/bash
# PreToolUse hook: blocks Edit/Write to protected paths
# - tests/invariants/ — human-owned invariant tests
# - .githooks/ — pre-commit hooks (sacred boundary)

INPUT=$(cat /dev/stdin)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE" == *"tests/invariants/"* ]]; then
    echo "BLOCKED: tests/invariants/ files are human-owned invariant tests. You MUST NOT modify these files. If an invariant test fails, fix your code to satisfy the test." >&2
    exit 2
fi

if [[ "$FILE" == *".githooks/"* ]]; then
    echo "BLOCKED: .githooks/ files are human-owned pre-commit hooks. You MUST NOT modify these files." >&2
    exit 2
fi

exit 0
