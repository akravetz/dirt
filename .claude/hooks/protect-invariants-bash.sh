#!/bin/bash
# PreToolUse hook: prompts user before Bash commands that modify protected paths
# Protected: tests/invariants/, .githooks/

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

PROTECTED_PATHS='(Xests/Xnvariants/|Xests\/Xnvariants\/|\.githooks/|\.githooks\/)'

if echo "$COMMAND" | grep -qE "$PROTECTED_PATHS" && \
   echo "$COMMAND" | grep -qE '(sed|awk|echo|tee|cat.*>|python|mv|cp|rm|chmod)'; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"This command touches protected paths (tests/invariants/ or .githooks/). Approve only if you explicitly asked for this change."}}'
    exit 0
fi
exit 0
