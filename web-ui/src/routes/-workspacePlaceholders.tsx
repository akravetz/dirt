import { Link, useRouterState } from "@tanstack/react-router";
import type { ReactNode } from "react";

type WorkspaceAction = {
  label: string;
  link: ReactNode;
};

type WorkspacePlaceholderProps = {
  actions?: readonly WorkspaceAction[];
  facts?: readonly { label: string; value: string }[];
  kicker: string;
  title: string;
};

export function useIsLeafRoute(routeId: string): boolean {
  return useRouterState({
    select: (state) => state.matches.at(-1)?.routeId === routeId,
  });
}

export function WorkspacePlaceholder({
  actions = [],
  facts = [],
  kicker,
  title,
}: WorkspacePlaceholderProps): ReactNode {
  return (
    <main className="flex-1 overflow-auto">
      <div className="mx-auto flex max-w-220 flex-col gap-5 px-5 py-6 sm:px-8">
        <header className="border-b border-rule-strong pb-4">
          <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            {kicker}
          </p>
          <h1 className="mt-1 font-sans text-fs-24 font-semibold tracking-tight text-ink">
            {title}
          </h1>
        </header>

        {facts.length === 0 ? null : (
          <section className="grid grid-cols-1 gap-px border border-rule-strong bg-rule sm:grid-cols-2">
            {facts.map((fact) => (
              <div key={fact.label} className="min-w-0 bg-paper-2 p-4">
                <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                  {fact.label}
                </p>
                <p className="mt-1 break-words font-sans text-fs-13 text-ink">
                  {fact.value}
                </p>
              </div>
            ))}
          </section>
        )}

        {actions.length === 0 ? null : (
          <nav aria-label={`${title} actions`} className="flex flex-wrap gap-2">
            {actions.map((action) => (
              <span key={action.label}>{action.link}</span>
            ))}
          </nav>
        )}
      </div>
    </main>
  );
}

export function WorkspaceLink({
  children,
  to,
}: {
  children: ReactNode;
  to: "/plants" | "/plants/new" | "/seeds" | "/seeds/new" | "/tents";
}): ReactNode {
  return (
    <Link
      to={to}
      className="inline-flex border border-rule px-3 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 hover:border-rule-strong hover:text-ink"
    >
      {children}
    </Link>
  );
}
