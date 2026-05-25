---
name: ui-refinement
description: Iterative browser-first workflow for refining an existing product UI without rebuilding it from scratch. Use when the user asks to revamp, refine, redesign, polish, improve first impression, improve hierarchy/density/spacing/affordances, or work through a screen such as a dashboard, detail page, form, navigation, or responsive view using screenshots and human review loops.
---

# UI Refinement

Use this skill to refine existing UI in small, reviewable loops. Act like a design engineer working inside the current product system, not a generator creating a new app.

## Core Rule

Preserve the existing product, data model, and component conventions unless the user explicitly asks for a structural redesign. Prefer focused diffs, screenshots, and human review over broad rewrites.

## Required Setup

1. Read the repo's command docs before running anything.
2. Check `git status --short` and keep unrelated dirty files out of the pass.
3. Start or reuse the local dev server.
4. Use the required browser automation tool for the repo.
5. Capture the current screen at desktop and mobile widths before making UI changes. Capture both first-viewport screenshots and full-page screenshots when the surface naturally scrolls.
6. Read `references/refactoring-ui-review.md` before the first audit in a session.

For this Dirt repo, that usually means:

```bash
make dev-status
make dev-up
```

Then open the Web URL with `agent-browser` and log in with the documented local credentials.

## Workflow

### 1. Scope One Surface

Convert broad requests into one reviewable surface:

- dashboard first impression
- tent detail page
- command panel
- device list
- schedule editor
- empty/loading/error state
- mobile version of a specific view

If the user names a surface, use it. If they say "the UI", pick the most user-visible screen and state that choice.

### 2. Audit Before Editing

Inspect the live UI and produce a concise audit organized by:

- **Hierarchy**: what should draw the eye first, what competes, what is too quiet.
- **Density**: whether the screen is sparse, cramped, or missing scan structure.
- **Spacing**: inconsistent gaps, ambiguous grouping, padding that fights the content.
- **Typography**: type scale, weight, line length, label/value treatment.
- **Affordances**: unclear click targets, weak controls, disabled/loading/error states.
- **Content Fit**: whether labels, values, timestamps, and long words survive real data.
- **Responsive Behavior**: desktop/mobile layout, wrapping, occlusion, tap targets.

Include 2-5 proposed changes, ordered by impact. Ask for direction before broad visual changes unless the user already approved implementation.

When auditing a dashboard or repeated-item surface, explicitly check representative item counts:

- **0 items**: empty state preserves layout and does not look broken.
- **1 item**: grid/list treatments do not leave dead-fill lanes or awkward empty tracks.
- **Many items**: wrapping, borders, row rhythm, and scroll behavior still scan cleanly.

When auditing mobile, explicitly check the first viewport for horizontal overflow, clipped nav tabs, clipped action buttons, and controls that require sideways scrolling without a clear affordance.

### 3. Implement One Pass

After direction is clear:

1. Read the relevant frontend files and nearby components.
2. Reuse existing components, Tailwind tokens, icons, routes, and data hooks.
3. Make the smallest coherent pass that improves the selected surface.
4. Avoid new design languages, decorative gradients, nested cards, or marketing-style sections unless the existing app already uses them.
5. Keep local copy purposeful and task-oriented; do not add explanatory in-app text about how the UI works.

### 4. Verify Visually

After edits:

1. Let hot reload update the page, or restart only if the stack requires it.
2. Capture desktop and mobile screenshots for both the current viewport and full page when the surface scrolls.
3. Check text fit, overlap, empty/loading/error states touched by the change, low-count repeated-item states, and mobile nav/action clipping.
4. Check browser console and page errors. Treat normal dev-server messages such as Vite connection/hot-update logs and React DevTools suggestions as noise; investigate warnings, uncaught errors, failed module loads, and API/network failures.
5. Run focused type/lint/test commands appropriate to touched files. If a test command exits successfully because no tests matched, report that explicitly as "no test files found" rather than implying behavioral coverage.

### 5. Report for Human Review

Return:

- the URL to review
- what changed
- screenshot paths or a concise visual description if screenshots are unavailable
- validation run
- unrelated dirty files noticed before the pass, if any
- open tradeoffs or specific questions

Use review-friendly language: "keep/revert/tighten" candidates, not a defensive explanation of every choice.

## Feedback Loop

Treat user feedback as visual direction. Typical requests:

- "keep this part"
- "make it denser"
- "this feels too loud"
- "this should be more operational"
- "revert that section"
- "try the same hierarchy on mobile"

Apply feedback in another small pass, re-screenshot, and report again.

## Reference

Read `references/refactoring-ui-review.md` for the detailed review checklist and Refactoring UI-inspired principles.
