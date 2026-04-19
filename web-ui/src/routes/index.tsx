import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: IndexPage,
});

function IndexPage() {
  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <h1 className="font-serif italic text-6xl text-ink">
          dirt<span className="text-accent-magenta">.</span>
        </h1>
        <p className="font-mono text-xs text-ink-3 uppercase tracking-[0.3em] mt-2">
          harness ready · wire me up
        </p>
      </div>
    </main>
  );
}
