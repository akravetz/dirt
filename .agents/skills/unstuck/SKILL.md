---
name: unstuck
description: Structured debugging protocol when stuck in a loop. Invoke when you've tried 3+ variations of the same approach without progress.
disable-model-invocation: false
---

# /unstuck — Break the Loop

Invoke this when you (or the user) notice you're looping: trying variations of the same fix, tweaking config repeatedly, or guessing without evidence.

## Phase 1: STOP

1. **Acknowledge the loop.** State plainly: "I'm stuck."
2. **Log failed approaches.** List what you tried and why each failed. Be specific — not "tried changing config" but "switched asyncio_mode to strict, got error X."
3. **Check for hedging.** Scan your recent reasoning for: "should work", "I believe", "probably", "seems to". These mean you're guessing, not debugging. Replace with "I don't know — I need evidence."

**Gate:** Do not proceed to Phase 2 until the failed approaches log is written.

## Phase 2: THINK

Do NOT write any code or make any changes in this phase.

1. **Isolate.** Use bash to binary-search the problem to the smallest reproducing case. Cut the problem space in half each time. Example: all tests → one test dir → one file → one test → one fixture.
2. **Hypothesize.** Write 3 hypotheses for the root cause. They must be:
   - **Distinct** — different root causes, not variations of one idea
   - **Testable** — each has a specific experiment that confirms or refutes it
   - **Ranked** — ordered by likelihood with reasoning
3. **Gather evidence.** For each hypothesis:
   - Search the internet for known issues
   - Read upstream source code (don't guess what a library does — read it)
   - Run targeted bash experiments
4. **Present findings to the user.** Share your hypotheses, evidence, and recommendation before implementing.

**Gate:** Do not proceed to Phase 3 until you have evidence pointing to a specific root cause.

## Phase 3: ACT

1. **Implement** the fix for the hypothesis with the strongest evidence.
2. **Verify** with a binary pass/fail — run the test, check the output.
3. **If it fails**, add this attempt to the failed approaches log and return to Phase 2. Do not try a variation of the same fix.

## Circuit Breaker

After **3 failed fix attempts**, STOP completely. Tell the user:
- What you've tried (the full log)
- What you've ruled out
- What you think the problem might be but can't solve

Let the user decide the next step.

## Failure Modes to Self-Detect

- **Fix Loop**: Applying the same category of fix repeatedly (e.g., tweaking asyncio config 5 different ways). If your fixes share a theme, you're in a loop.
- **Confidence Mirage**: Saying "this should work" without running it. Run it.
- **Config Whack-a-Mole**: Changing settings without understanding what they do. Read the source first.
- **Skipping Isolation**: Jumping to hypotheses without narrowing the problem. Isolate first, always.
