# Refactoring UI Review Checklist

Use this checklist when auditing or refining an existing UI. It is based on public Refactoring UI material and common summaries of Adam Wathan and Steve Schoger's guidance. Primary public source: https://refactoringui.com/

## Source Notes

The public Refactoring UI table of contents emphasizes:

- start with a feature, not a layout
- detail comes later
- do not design too much
- hierarchy is everything
- de-emphasize to emphasize
- labels are a last resort
- separate visual hierarchy from document hierarchy
- balance weight and contrast
- establish spacing and sizing systems
- avoid ambiguous spacing
- establish a type scale
- not every link needs a color

Useful public summaries also emphasize designing in grayscale first, using spacing/contrast/typography before color, using a small number of font weights, and making supporting content quieter instead of making primary content louder.

## Audit Order

### 0. Collaboration Gate

For broad refinement prompts, the first deliverable is an audit and proposal, not code. The user should see the reasoning before implementation starts.

The proposal should make each change easy to approve, reject, or modify:

- name the UI problem
- explain why it matters for the screen's job
- describe the intended visual effect
- call out tradeoffs or risk

Only move from proposal to code after the user approves a direction or asks for implementation.

### 1. User Job and First Impression

Start with the task, not layout decoration.

- What is the screen for?
- What should the user understand in the first 3 seconds?
- What action or status matters most?
- Is the most important data visually dominant?
- Is anything decorative competing with operational information?

For Dirt-style operational screens, prefer dense, scannable, calm interfaces over landing-page composition.

### 2. Hierarchy

Not all elements are equal. Fix competing emphasis before changing colors.

Look for:

- too many elements with the same size/weight/color
- section titles louder than the actual values
- labels louder than values
- secondary timestamps or metadata competing with primary state
- controls with equal visual weight despite different risk or importance

Change levers:

- increase or reduce font weight
- use darker text for primary, softer text for secondary
- group related content with spacing before adding borders
- de-emphasize surrounding elements when the primary thing cannot get louder
- remove redundant labels when the value is self-explanatory

### 3. Density and Scan Structure

Do not equate "premium" with sparse if the product is operational. Choose density based on repeated use.

Look for:

- hero-scale text inside dashboards or tool surfaces
- excessive card padding hiding useful data below the fold
- flat lists that should be grouped or summarized
- tables/cards with no clear scan axis
- repeated labels that slow scanning
- repeated-item grids that only look good with a full row of items

Change levers:

- make key metrics compact but more structured
- create clear rows, columns, and groups
- use consistent label/value patterns
- reserve large type for genuinely primary state
- show related controls near the data they affect
- test 0/1/many item counts before committing a grid treatment; avoid `gap-px` or background-rule grids that create dead-fill lanes in one-item states

### 4. Spacing and Grouping

Spacing should reveal relationships. Ambiguous spacing makes users guess what belongs together.

Look for:

- equal space between unrelated and related items
- inconsistent card padding
- headers too close to previous sections
- icons, labels, and values with mismatched gaps
- layouts that rely on borders when proximity would work better

Change levers:

- use the existing spacing scale
- make within-group gaps smaller than between-group gaps
- align edges across repeated cards or rows
- remove one-off margins
- use fewer container types

### 5. Typography

Use type as a system, not as isolated local tweaks.

Look for:

- too many font sizes or weights
- tiny text used to de-emphasize important content
- light font weights at small sizes
- centered text in operational panels
- long line lengths in prose or cramped value labels
- document heading order driving visual size instead of screen hierarchy

Change levers:

- use 2-3 font sizes per compact surface
- use 2 font weights for most UI work
- make secondary text softer, not unreadably small
- align baselines and left edges
- keep labels short and values readable

### 6. Color and Contrast

Use color late. If the UI only works because of color, the hierarchy is weak.

Look for:

- too many accent colors
- gray text on colored backgrounds with poor contrast
- status colors that are too saturated for routine states
- links/buttons colored when placement or weight would suffice
- charts and badges dominating the screen
- light/dark mode drift where borders, status colors, chart lines, muted text, or selected states lose contrast or change hierarchy

Change levers:

- first test whether grayscale hierarchy works
- reserve saturated colors for action, alert, or selected state
- use contrast for focus, not decoration
- choose status colors with enough text contrast
- keep recurring statuses visually consistent
- review light and dark screenshots side by side before judging a color or contrast change

### 7. Affordances and States

The user should know what can be clicked and what will happen.

Look for:

- icon-only controls without clear hover/title behavior
- buttons styled like labels, labels styled like buttons
- weak disabled/loading/error states
- destructive and routine actions with equal treatment
- controls far from the affected data

Change levers:

- use familiar icons with tooltips
- distinguish primary, secondary, quiet, and destructive actions
- place actions near their object
- keep tap targets stable across viewport sizes
- ensure loading/error states preserve layout dimensions

### 8. Responsive Reality

Screens must survive real data and narrower widths.

Look for:

- metric labels wrapping into values
- long device names or timestamps breaking cards
- controls moving unpredictably on hover/loading
- mobile views that preserve desktop density without structure
- text overlap or clipped buttons
- first-viewport horizontal overflow, clipped nav tabs, clipped toolbar actions, or hidden overflow that makes primary controls unavailable

Change levers:

- use stable grid tracks, min/max widths, and wrapping rules
- test representative long strings
- preserve primary hierarchy on mobile
- collapse secondary details before primary values
- avoid viewport-scaled font sizes
- capture both first-viewport and full-page screenshots, in light and dark theme, so the visible landing impression and below-the-fold scroll content are reviewed separately

## Implementation Bias

- Prefer one coherent surface pass over scattered tweaks.
- Reuse current components and token patterns.
- Avoid adding cards inside cards.
- Avoid decorative blobs, gradients, or stock-like imagery in operational tools.
- Do not add visible help text that explains the UI unless the product genuinely needs user instruction.
- Keep changes easy to revert if the direction fails.
