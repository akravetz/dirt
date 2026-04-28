# Wiki Query Filing Workflow

Read after answering a user question or providing advice — to decide whether the response should be persisted into the wiki rather than lost in chat history.

## Filing-worthy responses

- Diagnoses or assessments (e.g., "Plant C's light green color is likely nitrogen deficiency because…")
- Comparisons or analyses
- Decision rationales (why we chose X over Y)
- New concepts explained for the first time
- Synthesized insights from multiple sources

## NOT filing-worthy

- Simple factual answers ("water at 6pm")
- Confirmations or acknowledgments
- Routine status updates already captured in daily entries

## Filing destinations

- Diagnosis/observation about a plant → append to the relevant daily entry + update the plant page's current state
- New growing concept explained → create a `wiki/concepts/` page
- New technical concept relevant to the grow → create a `wiki/concepts/` page
- Hardware deployed or reconfigured → create/update a `wiki/hardware/` page
- Decision made with rationale (grow or infrastructure) → create a `wiki/decisions/` page
- Comparison or deep analysis → file in `var/outputs/` and link from relevant wiki pages

## After filing

1. Update `wiki/index.md` if a new page was created
2. Update `wiki/log.md` with a `## [DATE] query-filed | Title` entry
3. Add backlinks from related pages
4. Run the deterministic lint (`uv run scripts/lint.py`) — see [`../lint.md`](../lint.md)
