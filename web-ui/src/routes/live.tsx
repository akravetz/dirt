import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/live")({
  component: LivePage,
});

function LivePage() {
  return (
    <main className="p-6">
      <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
        Live feed · placeholder
      </p>
    </main>
  );
}
