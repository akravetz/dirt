import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: IndexPage,
});

function IndexPage() {
  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
        Dashboard · placeholder
      </p>
    </main>
  );
}
