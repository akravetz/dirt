import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/wiki")({
  component: WikiPage,
});

function WikiPage() {
  return (
    <main className="p-6">
      <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
        Wiki · placeholder
      </p>
    </main>
  );
}
