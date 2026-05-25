// Hosted wiki route (/wiki).
//
// TODO(hosted-wiki): decide the real hosted wiki ownership and contract.
// If we keep this surface, define hosted /api/wiki/tree, /api/wiki/file,
// and /api/wiki/search contracts first. This route intentionally makes no
// network calls until we choose whether to sync wiki content, serve it from
// the control-plane API, or remove the browser wiki surface.
import { createFileRoute } from "@tanstack/react-router";

type WikiSearch = {
  path?: string;
};

export const Route = createFileRoute("/wiki")({
  component: WikiPage,
  validateSearch: (search: Record<string, unknown>): WikiSearch => {
    const raw = search.path;
    return typeof raw === "string" && raw.length > 0 ? { path: raw } : {};
  },
});

function WikiPage() {
  return (
    <main className="flex min-h-0 min-w-0 flex-1 items-center justify-center p-8">
      <section aria-label="Wiki unavailable" className="max-w-xl">
        <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
          Wiki unavailable
        </p>
      </section>
    </main>
  );
}
