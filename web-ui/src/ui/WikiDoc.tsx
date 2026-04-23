// Main pane for the /wiki route — breadcrumb + frontmatter block +
// markdown body + backlinks.
//
// Body renders through react-markdown (already a dep via PlantDetail).
// Typography lives in the `.wiki-prose` utility in styles.css; we just
// wrap the rendered markdown in that class so headings/links/tables
// pick up the mock's type scale.
//
// boundaries lint forbids ui/ → api-client/, so the WikiFile /
// WikiBacklink types are local duck-types of
// contracts/webapp-v1.yaml #/components/schemas/{WikiFile,WikiBacklink}.
import ReactMarkdown from "react-markdown";

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
// the user sees in the sidebar.
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
  const lastIdx = crumbs.length - 1;

  return (
    <article
      aria-label="Wiki document"
      className="flex min-h-0 min-w-0 max-w-215 flex-1 flex-col overflow-y-auto bg-paper px-12 pb-20 pt-9"
    >
      <nav
        aria-label="Breadcrumb"
        className="mb-5 font-mono text-fs-11 uppercase tracking-cap-short text-ink-3"
      >
        {crumbs.map((crumb, idx) => (
          <span key={crumb.prefix}>
            {idx > 0 ? " / " : null}
            <span className={idx === lastIdx ? "font-semibold text-ink" : undefined}>
              {crumb.label}
            </span>
          </span>
        ))}
      </nav>

      <header>
        <h1 className="m-0 flex items-center gap-3 font-sans text-fs-32 font-semibold tracking-tighter text-ink">
          {doc.title}
        </h1>
        {doc.subtitle ? (
          <p className="mt-1.5 font-serif text-fs-16 italic text-ink-3">
            {doc.subtitle}
          </p>
        ) : null}
      </header>

      {matterEntries.length > 0 ? (
        <section
          aria-label="Frontmatter"
          data-testid="wiki-frontmatter"
          className="my-6 border-y border-rule-strong py-3 font-mono text-fs-11"
        >
          {matterEntries.map(([key, value]) => (
            <div
              key={key}
              data-testid="wiki-frontmatter-row"
              className="grid grid-cols-[100px_1fr] gap-x-3.5 gap-y-0 py-0.75"
            >
              <span className="text-fs-10 uppercase tracking-caps text-ink-3">
                {key}
              </span>
              <span className="text-ink">{formatFrontmatterValue(value)}</span>
            </div>
          ))}
        </section>
      ) : null}

      <section aria-label="Body" data-testid="wiki-body" className="wiki-prose">
        <ReactMarkdown>{doc.body_markdown}</ReactMarkdown>
      </section>

      {doc.backlinks.length > 0 ? (
        <section
          aria-label="Backlinks"
          className="mt-12 border-t border-rule-strong pt-3.5"
        >
          <h2 className="font-mono text-fs-10 uppercase tracking-cap-narrow text-ink-3">
            Backlinks
          </h2>
          <ul className="mt-2 list-none p-0">
            {doc.backlinks.map((bl) => (
              <li key={bl.path} className="py-1 font-sans text-fs-13 text-ink-2">
                {bl.title}{" "}
                <span className="font-mono text-fs-11 text-ink-3">{bl.path}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
