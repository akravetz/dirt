"""Filesystem-backed wiki reader — tree, file, search, backlinks.

Backs ``GET /api/wiki/tree``, ``GET /api/wiki/file?path=...``, and
``GET /api/wiki/search?q=...``. All paths are normalized and rejected if
they escape the wiki root.

Design choices (per API.md §9 + data_model.md §4i/4j):

- Body is returned as raw markdown — the SPA renders via react-markdown.
  No server-side HTML rendering.
- Backlinks are computed on the fly with a grep pass + a small mtime-keyed
  cache; for a ~70-file tree it's <5 ms cold. Not worth a persistent index.
- Search is a linear substring scan over filename + title + body.
  FTS5 / tsvector can be added later if the corpus grows.
"""

from __future__ import annotations

# wiki/ lives at the repo root — sibling of var/. Resolve relative to
# this module rather than via the (singleton-retired) Settings global.
# Override via DIRT_WIKI_DIR env var.
#   wiki.py at apps/shared/src/dirt_shared/services/wiki.py
#   parents[0] services/, [1] dirt_shared/, [2] src/, [3] shared/, [4] apps/, [5] repo
import os
import re
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[5]
WIKI_DIR = Path(os.environ.get("DIRT_WIKI_DIR", _REPO_ROOT / "wiki"))


# A minimal YAML subset that the wiki frontmatter uses:
#   key: value
#   key: [item, item, "quoted item"]
# Anything more complex falls back to a string value.
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_KV_RE = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
_LIST_RE = re.compile(r"^\[(.*)\]$")


@dataclass(frozen=True)
class WikiFileRef:
    name: str
    path: str  # "wiki/plants/plant-a.md"
    title: str
    sticker_color: str | None = None


@dataclass(frozen=True)
class WikiFolder:
    name: str
    files: list[WikiFileRef]


@dataclass(frozen=True)
class WikiTree:
    """Faithful snapshot of ``wiki/``.

    ``folders`` is the real subdirectories. ``root_files`` is the *.md
    files that live at the wiki root (``overview.md``, ``index.md``,
    ``log.md``). No synthetic regrouping — the frontend decides how to
    render loose files vs foldered files.
    """

    root_files: list[WikiFileRef]
    folders: list[WikiFolder]


@dataclass(frozen=True)
class WikiFile:
    path: str
    title: str
    subtitle: str | None
    frontmatter: dict[str, object]
    body_markdown: str
    backlinks: list[WikiFileRef]


@dataclass(frozen=True)
class SearchResult:
    path: str
    title: str
    match_type: str  # "title" | "path" | "content"
    snippet: str | None = None


# ============================================================
# Path handling
# ============================================================


def _normalize_path(path: str) -> Path:
    """Accepts 'wiki/foo/bar.md' or 'foo/bar.md'; returns the absolute file path.

    Rejects anything that escapes ``WIKI_DIR`` (traversal) or points outside
    the wiki tree. Returns a Path that may or may not exist — caller checks.
    """
    p = path.removeprefix("wiki/").lstrip("/")
    if ".." in Path(p).parts:
        raise ValueError(f"path escapes wiki root: {path!r}")
    target = (WIKI_DIR / p).resolve()
    # Harden: resolve() collapses .. so even if we stripped it above, confirm
    # the resolved path still lives under WIKI_DIR.
    try:
        target.relative_to(WIKI_DIR.resolve())
    except ValueError as e:
        raise ValueError(f"path escapes wiki root: {path!r}") from e
    return target


def _wiki_rel(path: Path) -> str:
    """Inverse of ``_normalize_path``: absolute path → 'wiki/...' form."""
    rel = path.resolve().relative_to(WIKI_DIR.resolve())
    return f"wiki/{rel.as_posix()}"


# ============================================================
# Frontmatter + inline-markdown parsing
# ============================================================


def _parse_yaml_value(raw: str) -> object:
    """Best-effort minimal YAML: scalars + flow-style lists."""
    raw = raw.strip()
    if not raw:
        return ""
    m = _LIST_RE.match(raw)
    if m:
        inner = m.group(1).strip()
        if not inner:
            return []
        items = []
        for part in _split_flow_list(inner):
            part = part.strip().strip('"').strip("'")
            items.append(part)
        return items
    return raw.strip('"').strip("'")


def _split_flow_list(inner: str) -> list[str]:
    """Split a flow-style list's inner content on commas, respecting quotes."""
    items: list[str] = []
    depth = 0
    in_quote: str | None = None
    buf: list[str] = []
    for ch in inner:
        if in_quote:
            if ch == in_quote:
                in_quote = None
            buf.append(ch)
        elif ch in ("'", '"'):
            in_quote = ch
            buf.append(ch)
        elif ch == "[":
            depth += 1
            buf.append(ch)
        elif ch == "]":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        items.append("".join(buf))
    return items


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Return ``(frontmatter_dict, body_without_frontmatter)``.

    If the text has no frontmatter, returns ``({}, text)`` unchanged.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict[str, object] = {}
    for line in m.group(1).splitlines():
        kv = _KV_RE.match(line)
        if kv:
            fm[kv.group(1)] = _parse_yaml_value(kv.group(2))
    return fm, text[m.end() :]


def _extract_title(frontmatter: dict[str, object], body: str, fallback: str) -> str:
    """Prefer frontmatter['title']; then the first H1 in the body; else fallback."""
    fm_title = frontmatter.get("title")
    if isinstance(fm_title, str) and fm_title.strip():
        return fm_title.strip()
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _extract_subtitle(body: str) -> str | None:
    """First non-empty *italic* line after the H1 — the plant-a.md convention."""
    after_h1 = False
    for line in body.splitlines():
        if line.startswith("# "):
            after_h1 = True
            continue
        if after_h1:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("*") and stripped.endswith("*"):
                return stripped.strip("*").strip()
            return None  # non-italic content means no subtitle
    return None


# ============================================================
# Tree walk
# ============================================================

_IGNORED_NAMES = {"CLAUDE.md"}


def _sticker_color_for(code: str) -> str:
    # Fallback used only for building tree file refs before we hit the DB;
    # matches the seed values in the Atlas init migration.
    return {"a": "yellow", "b": "orange", "c": "pink", "d": "blue"}.get(code, "")


def get_tree() -> WikiTree:
    """Walk ``wiki/``; each subdirectory becomes a folder, root ``*.md``
    files land in ``root_files``. Hidden dirs + ``CLAUDE.md`` skipped."""
    if not WIKI_DIR.exists():
        return WikiTree(root_files=[], folders=[])

    folders: list[WikiFolder] = []
    for child in sorted(WIKI_DIR.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            files = _folder_files(child)
            if files:
                folders.append(WikiFolder(name=child.name, files=files))

    root_files = [
        _file_ref(p)
        for p in sorted(WIKI_DIR.glob("*.md"))
        if p.name not in _IGNORED_NAMES and not p.name.startswith(".")
    ]
    return WikiTree(root_files=root_files, folders=folders)


def _folder_files(folder: Path) -> list[WikiFileRef]:
    out: list[WikiFileRef] = []
    for p in sorted(folder.glob("*.md")):
        if p.name in _IGNORED_NAMES or p.name.startswith("."):
            continue
        out.append(_file_ref(p))
    return out


def _file_ref(path: Path) -> WikiFileRef:
    sticker: str | None = None
    if path.parent.name == "plants":
        stem = path.stem  # 'plant-a'
        if stem.startswith("plant-") and len(stem) == 7:
            sticker = _sticker_color_for(stem[-1])
    # Avoid a full re-parse for the tree; just read the frontmatter block.
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    fm, body = _parse_frontmatter(text)
    title = _extract_title(fm, body, fallback=path.stem)
    return WikiFileRef(
        name=path.name,
        path=_wiki_rel(path),
        title=title,
        sticker_color=sticker,
    )


# ============================================================
# File read + backlinks
# ============================================================

# mtime-keyed backlinks cache. Key = mtime-rollup across all wiki files;
# when ANY file's mtime changes, we recompute. Simple + correct for our scale.
_backlinks_cache: dict[str, list[WikiFileRef]] = {}
_backlinks_mtime: float | None = None


def _wiki_mtime_rollup() -> float:
    """Max mtime across all ``wiki/**/*.md``. Cheap stat-only walk."""
    if not WIKI_DIR.exists():
        return 0.0
    mx = 0.0
    for p in WIKI_DIR.rglob("*.md"):
        try:
            mx = max(mx, p.stat().st_mtime)
        except OSError:
            continue
    return mx


def _invalidate_backlinks_if_stale() -> None:
    global _backlinks_mtime, _backlinks_cache
    rollup = _wiki_mtime_rollup()
    if _backlinks_mtime != rollup:
        _backlinks_cache = {}
        _backlinks_mtime = rollup


def _backlinks_for(target_path: str) -> list[WikiFileRef]:
    """Files that link or reference ``target_path`` (the 'wiki/...' form).

    Matches two patterns:
    - markdown link ``](./foo.md)`` or ``](../daily/2026-04-18.md)``
    - frontmatter ``related: [..., wiki/foo/bar.md, ...]``
    Results are cached under the mtime rollup.
    """
    _invalidate_backlinks_if_stale()
    if target_path in _backlinks_cache:
        return _backlinks_cache[target_path]

    target_basename = Path(target_path).name
    target_rel = target_path.removeprefix("wiki/")

    refs: list[WikiFileRef] = []
    for p in sorted(WIKI_DIR.rglob("*.md")):
        if p.name in _IGNORED_NAMES:
            continue
        this_rel = _wiki_rel(p)
        if this_rel == target_path:
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            continue
        # Relative link hit: either the basename alone or the full
        # 'wiki/...' path anywhere in a markdown link.
        if (
            f"]({target_basename})" in content
            or f"]({target_rel})" in content
            or f"](wiki/{target_rel})" in content
            or f"../{target_rel}" in content
        ):
            refs.append(_file_ref(p))
            continue
        # Frontmatter related[] reference.
        fm, _body = _parse_frontmatter(content)
        related = fm.get("related") or []
        if isinstance(related, list):
            for r in related:
                r = str(r).strip()
                if r in (target_path, f"wiki/{target_rel}", target_rel):
                    refs.append(_file_ref(p))
                    break
                # Frontmatter sometimes drops the .md suffix.
                if (
                    r + ".md" == target_path
                    or r + ".md" == f"wiki/{target_rel}"
                    or r + ".md" == target_rel
                ):
                    refs.append(_file_ref(p))
                    break

    _backlinks_cache[target_path] = refs
    return refs


def get_file(path: str) -> WikiFile | None:
    """Read a wiki markdown file + compute its backlinks.

    ``path`` accepts either 'wiki/...' or unprefixed form. Raises
    ``ValueError`` on traversal; returns ``None`` if the file doesn't exist.
    """
    abs_path = _normalize_path(path)
    if not abs_path.exists() or not abs_path.is_file():
        return None
    rel = _wiki_rel(abs_path)
    text = abs_path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    title = _extract_title(fm, body, fallback=abs_path.stem)
    subtitle = _extract_subtitle(body)
    backlinks = _backlinks_for(rel)
    return WikiFile(
        path=rel,
        title=title,
        subtitle=subtitle,
        frontmatter=fm,
        body_markdown=body,
        backlinks=backlinks,
    )


# ============================================================
# Search
# ============================================================


def search(q: str, limit: int = 12) -> list[SearchResult]:
    """Linear substring search over filename + title + body.

    Matches in decreasing order of signal: title > path > content (title
    matches bubble to the top). Content snippets are clipped to ~80 chars
    around the hit.
    """
    if not q.strip():
        return []
    needle = q.lower()

    title_hits: list[SearchResult] = []
    path_hits: list[SearchResult] = []
    content_hits: list[SearchResult] = []

    for p in sorted(WIKI_DIR.rglob("*.md")):
        if p.name in _IGNORED_NAMES:
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, body = _parse_frontmatter(content)
        rel = _wiki_rel(p)
        title = _extract_title(fm, body, fallback=p.stem)

        if needle in title.lower():
            title_hits.append(SearchResult(path=rel, title=title, match_type="title"))
            continue
        if needle in rel.lower() or needle in p.name.lower():
            path_hits.append(SearchResult(path=rel, title=title, match_type="path"))
            continue
        idx = body.lower().find(needle)
        if idx >= 0:
            start = max(0, idx - 30)
            end = min(len(body), idx + len(q) + 50)
            snippet = body[start:end].replace("\n", " ").strip()
            content_hits.append(
                SearchResult(
                    path=rel,
                    title=title,
                    match_type="content",
                    snippet=snippet,
                )
            )

    return (title_hits + path_hits + content_hits)[:limit]
