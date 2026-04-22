#!/bin/bash
# PreToolUse hook (Bash): asks the user before Bash commands that
# WRITE to a protected path.
#
# Protected paths:
#   - apps/tests/invariants/           (Python architectural invariants)
#   - .githooks/                       (hand-written git hooks)
#   - web-ui/invariants/               (TypeScript architectural invariants)
#   - web-ui/src/api-client/generated/ (OpenAPI-generated client)
#
# Design
# ------
# The previous version matched "protected path mentioned ANYWHERE and
# any of (sed|awk|echo|tee|cat.*>|python|mv|cp|rm|chmod) anywhere" with
# no word boundaries and no directional check. That produced
# false-positives on `uv run pytest apps/tests/invariants/X.py` (cp
# substring in "capture", rm in "remove", etc.) and on any command
# that merely READ a protected file.
#
# This version flags commands that demonstrate WRITE INTENT targeting
# a protected path:
#
#   1. `sed -i` / `awk -i` (in-place edit flag)
#   2. Redirect operator (`>`, `>>`, `tee`, `tee -a`) whose target is
#      a protected path
#   3. A named mutating verb (rm, rmdir, chmod, chown, touch, mkdir,
#      install, ln) with a protected path as argument
#   4. `mv` or `cp` with a protected path anywhere after the verb
#      (conservative: both "path is source" and "path is target" count
#      as mutations within the same command segment)
#
# All patterns respect command separators — `.*` is replaced with
# `[^;&|]*` so the match cannot span into a following command. This
# stops `sed -i 's/x/y/' foo.py; cat apps/tests/invariants/X.py`
# from false-positiving.
#
# Emits `permissionDecision: ask` (not `deny`) so legitimate edits the
# user explicitly requested still go through after a one-click OK.
#
# Known limitations (acknowledged, not fixed here)
# ------------------------------------------------
# - Heredocs ending with a redirect still work. Tiny variations of
#   the above patterns (e.g. `>(tee ...)`) slip through.
# - Any indirection through a language runtime (`python -c "..."`,
#   `node -e "..."`) bypasses the regex entirely.
# - Upstream issue anthropics/claude-code#29709 notes that Bash can
#   always side-step Edit/Write hooks. Treat this hook as a speed-bump;
#   the real fence is pre-commit + git history + review. See
#   .pre-commit-config.yaml (id: invariants).

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# Whitelist: if every protected-path reference in the command resolves
# specifically to apps/tests/invariants/contract_status.json (the
# agent-editable data table per docs/plans/generator-prompts.md), skip
# the ask entirely. Any other protected-path reference in the same
# command — even alongside contract_status.json — falls through to the
# regular pattern checks below.
PROTECTED_TOKENS=$(echo "$COMMAND" | grep -oE '(apps/tests/invariants/[^ ,;&|"'"'"'`)>]+|\.githooks/[^ ,;&|"'"'"'`)>]+|web-ui/invariants/[^ ,;&|"'"'"'`)>]+|web-ui/src/api-client/generated/[^ ,;&|"'"'"'`)>]+)' || true)
if [ -n "$PROTECTED_TOKENS" ]; then
    NON_WHITELISTED=$(echo "$PROTECTED_TOKENS" | grep -vE '(^|/)apps/tests/invariants/contract_status\.json$' | head -1 || true)
    if [ -z "$NON_WHITELISTED" ]; then
        exit 0
    fi
fi

PATHS='(apps/tests/invariants|\.githooks|web-ui/invariants|web-ui/src/api-client/generated)'

# Word-start anchor for verbs (POSIX ERE has no \b). Matches
# start-of-string or one of: space, tab, `;`, `&`, `|`, `(`.
WB='(^|[[:space:];&|(])'

# Span that does NOT cross a command separator.
NOSEP='[^;&|]*'

PATTERNS=(
  # 1. in-place edit: sed/awk/gawk with a `-i` flag (possibly combined
  #    with other short flags: `-iE`, `-ibak`), followed by the
  #    protected path anywhere in the same command segment.
  "${WB}(sed|awk|gawk)[[:space:]]+-[a-zA-Z]*i[a-zA-Z.]*([[:space:]]|$)${NOSEP}${PATHS}"

  # 2. redirect to a protected path (`>`, `>>`, `tee`, `tee -a`).
  "(>>?|tee([[:space:]]+-a)?)[[:space:]]*['\"]?${PATHS}"

  # 3. named mutating verb where the protected path appears anywhere
  #    in the same command segment. Permissive on arguments between
  #    verb and path (handles `chmod +x PATH`, `ln -sf SRC PATH`,
  #    `install -m 0644 SRC PATH`, etc.). NOSEP guards against
  #    matching across `;`/`&&`/`||`/`|` into a following command.
  "${WB}(rm|rmdir|chmod|chown|touch|mkdir|install|ln)[[:space:]]${NOSEP}${PATHS}"

  # 4. mv/cp where the protected path appears anywhere in the same
  #    command segment after the verb.
  "${WB}(mv|cp)[[:space:]]${NOSEP}${PATHS}"
)

for p in "${PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$p"; then
    cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"This command appears to write to a protected path (apps/tests/invariants/, .githooks/, web-ui/invariants/, or web-ui/src/api-client/generated/). Approve only if you explicitly asked for this change."}}
JSON
    exit 0
  fi
done
exit 0
