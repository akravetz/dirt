// Main pane for the /wiki route — breadcrumb + frontmatter block +
// markdown body + backlinks.
//
// Markdown rendering is intentionally minimal: we preserve the raw
// markdown body in a `<pre>` with whitespace preserved (the plan's user
// story says "renders raw markdown with frontmatter block + breadcrumb"
// — no compiled-HTML step required). This avoids pulling in a markdown-
// renderer dependency; the contract's body_markdown field is what the
// user sees. Upgrading to react-markdown later is a drop-in swap behind
// this component's boundary.
//
// boundaries lint forbids ui/ → api-client/, so the WikiFile /
// WikiBacklink types are local duck-types of
// contracts/webapp-v1.yaml #/components/schemas/{WikiFile,WikiBacklink}.

export interface WikiBacklink {
  path: string;
  title: string;
}
export interface WikiFileDoc {
  path: string;
  title: string;
  subtitle?: string | null;
  frontmatter: Record<string, unknown>;
  body_markdown: string;
  backlinks: WikiBacklink[];
}

interface WikiDocProps {
  doc: WikiFileDoc;
}

// Stringify a frontmatter value for the matter table. Primitives render
// as-is; arrays join with ", "; objects fall back to JSON so nothing in
// the block is ever blank.
function formatFrontmatterValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map(formatFrontmatterValue).join(", ");
  return JSON.stringify(value);
}

// Derive "plants / plant-a.md" crumbs from a "wiki/plants/plant-a.md"
// path. Strip the leading "wiki/" segment so the trail matches what
// the user sees in the sidebar. Each crumb carries the cumulative path
// up to and including that segment so React has a stable key even when
// two segments share a name (e.g. "index.md" appearing under multiple
// folders in a future layout).
function breadcrumbSegments(path: string): Array<{ label: string; prefix: string }> {
  const stripped = path.startsWith("wiki/") ? path.slice("wiki/".length) : path;
  const parts = stripped.split("/").filter((s) => s.length > 0);
  const out: Array<{ label: string; prefix: string }> = [];
  for (let i = 0; i < parts.length; i += 1) {
    out.push({ label: parts[i] as string, prefix: parts.slice(0, i + 1).join("/") });
  }
  return out;
}

export function WikiDoc({ doc }: WikiDocProps) {
  const crumbs = breadcrumbSegments(doc.path);
  const matterEntries = Object.entries(doc.frontmatter);

  return (
    <article
      aria-label="Wiki document"
      className="flex min-w-0 flex-1 flex-col gap-6 px-8 py-6"
    >
      <nav
        aria-label="Breadcrumb"
        className="font-mono text-xs uppercase tracking-caps text-ink-3"
      >
        {crumbs.map((crumb, idx) => (
          <span key={crumb.prefix}>
            {idx > 0 ? " / " : null}
            <span>{crumb.label}</span>
          </span>
        ))}
      </nav>

      <header className="flex flex-col gap-1">
        <h1 className="font-serif text-3xl italic text-ink">{doc.title}</h1>
        {doc.subtitle ? <p className="text-ink-2 italic">{doc.subtitle}</p> : null}
      </header>

      {matterEntries.length > 0 ? (
        <section aria-label="Frontmatter" data-testid="wiki-frontmatter">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 border border-rule bg-rule/20 p-4 font-mono text-xs">
            {matterEntries.map(([key, value]) => (
              <div key={key} className="contents" data-testid="wiki-frontmatter-row">
                <dt className="uppercase tracking-caps text-ink-3">{key}</dt>
                <dd className="text-ink">{formatFrontmatterValue(value)}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      <section aria-label="Body">
        <pre
          data-testid="wiki-body"
          className="whitespace-pre-wrap font-mono text-sm leading-relaxed text-ink"
        >
          {doc.body_markdown}
        </pre>
      </section>

      {doc.backlinks.length > 0 ? (
        <section aria-label="Backlinks" className="border-t border-rule pt-4">
          <h2 className="font-mono text-xs uppercase tracking-caps text-ink-3">
            Backlinks
          </h2>
          <ul className="mt-2 list-none">
            {doc.backlinks.map((bl) => (
              <li key={bl.path} className="py-1 text-sm text-ink-2">
                {bl.title}{" "}
                <span className="font-mono text-xs text-ink-3">{bl.path}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
