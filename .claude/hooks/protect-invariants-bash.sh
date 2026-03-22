#!/bin/bash
# PreToolUse hook: blocks Bash commands that modify tests/invariants/
# Prevents bypassing the Edit/Write hook via sed, echo, tee, python, etc.

INPUT=$(cat /dev/stdin)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE '(tests/invariants/|tests\/invariants\/)' && \
   echo "$COMMAND" | grep -qE '(sed|awk|echo|tee|cat.*>|python|mv|cp|rm|chmod)'; then
    echo "BLOCKED: Cannot use shell commands to modify tests/invariants/. These are human-owned invariant tests." >&2
    exit 2
fi
exit 0
