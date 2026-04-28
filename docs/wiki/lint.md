# Wiki Linting

Read before running `scripts/lint.py` or interpreting its output.

## Deterministic lint (run after every ingestion or daily update)

Run `uv run scripts/lint.py`. It performs 7 checks and exits non-zero if any fail:

1. **Index sync** — Parses `wiki/index.md` for markdown links; globs all `.md` files in `wiki/`. Flags files missing from the index and index entries pointing to nonexistent files.
2. **Backlink checker** — For each `wiki/daily/*.md`, checks whether plants mentioned in that entry are linked from the corresponding plant's Timeline section. Also verifies that all plant timeline links resolve to real daily files.
3. **Photo coverage** — Reads EXIF `DateTimeOriginal` (tag 36867) from all JPEGs in `var/raw/photos/`. Flags photo dates with no matching daily entry, and daily entries with no matching photo.
4. **Timeline continuity** — Parses dates from `wiki/daily/YYYY-MM-DD.md` filenames, sorts them, and reports any gaps between first and last entry.
5. **Overview staleness** — Compares the `updated` field in `wiki/overview.md` frontmatter against the most recent daily filename. Flags if overview is older.
6. **Frontmatter validation** — Every `.md` in `wiki/` (except `index.md` and `log.md`) must have YAML frontmatter with `title`, `type`, `created`, and `updated`. Flags missing or malformed frontmatter.
7. **File length** — Flags wiki files over 200 lines as a warning ("consider splitting") and over 400 lines as a failure ("should be split"). `index.md` and `log.md` are exempt (they grow naturally). Long files are a signal that a page is covering too many topics and should be broken into linked sub-pages.

Fix all reported issues before considering any update complete.

## LLM lint (weekly or on-demand)

The deterministic script cannot catch semantic issues. Periodically perform a deeper review using LLM reasoning:

- **Contradiction detection** — Read all plant pages and cross-reference claims (e.g., plant height, node count, health status) for inconsistencies across entries. Surface contradictions in `wiki/log.md` for user review; do not silently resolve them.
- **Concept gap finder** — Scan recent daily entries and flag domain terms (LST, VPD, flushing, trichomes, etc.) with no `wiki/concepts/` page.
- **Overview rewrite** — When `wiki/overview.md` is stale (flagged by lint check 5), synthesize a new overview by reading the most recent daily entries and plant pages.
