#!/bin/bash
# PreToolUse hook: blocks Bash commands that modify protected paths
# Prevents bypassing the Edit/Write hook via sed, echo, tee, python, etc.
# Protected: tests/invariants/, .githooks/

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

PROTECTED_PATHS='(tests/invariants/|tests\/invariants\/|\.githooks/|\.githooks\/)'

if echo "$COMMAND" | grep -qE "$PROTECTED_PATHS" && \
   echo "$COMMAND" | grep -qE '(sed|awk|echo|tee|cat.*>|python|mv|cp|rm|chmod)'; then
    echo "BLOCKED: Cannot use shell commands to modify protected paths (tests/invariants/, .githooks/). These are human-owned." >&2
    exit 2
fi
exit 0
