import type { ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownDocumentProps {
  bodyMarkdown: string;
}

const markdownComponents = {
  h1: ({ children }) => (
    <h1 className="mb-3 mt-0 font-sans text-fs-20 font-semibold leading-tight text-ink">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-5 border-b border-rule pb-1 font-sans text-fs-16 font-semibold leading-tight text-ink">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-4 font-sans text-fs-13 font-semibold uppercase tracking-cap-med text-ink-2">
      {children}
    </h3>
  ),
  p: ({ children }) => <p className="my-3 leading-ui text-ink-2">{children}</p>,
  a: ({ children, href }) => (
    <a
      className="text-accent-magenta underline decoration-accent-magenta/45 underline-offset-3 hover:decoration-accent-magenta"
      href={href}
      rel={href?.startsWith("http") ? "noreferrer" : undefined}
      target={href?.startsWith("http") ? "_blank" : undefined}
    >
      {children}
    </a>
  ),
  ul: ({ children }) => (
    <ul className="my-3 list-disc space-y-1 pl-5 text-ink-2">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-3 list-decimal space-y-1 pl-5 text-ink-2">{children}</ol>
  ),
  li: ({ children }) => <li className="pl-1 leading-ui">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="my-4 border-l-2 border-accent-purple pl-4 text-ink-2">
      {children}
    </blockquote>
  ),
  code: ({ children, className }) => (
    <code
      className={
        className ??
        "border border-rule bg-paper px-1 py-0.5 font-mono text-fs-10 text-ink"
      }
    >
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-4 overflow-x-auto border border-rule bg-paper p-3 font-mono text-fs-10 leading-ui text-ink">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto">
      <table className="w-full border-collapse text-left font-sans text-fs-11 text-ink-2">
        {children}
      </table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-rule bg-paper px-2 py-1 font-semibold text-ink">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-rule px-2 py-1 align-top">{children}</td>
  ),
  hr: () => <hr className="my-5 border-rule" />,
} satisfies Components;

export function MarkdownDocument({ bodyMarkdown }: MarkdownDocumentProps): ReactNode {
  return (
    <div className="break-words font-sans text-fs-13 text-ink-2">
      <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>
        {bodyMarkdown}
      </ReactMarkdown>
    </div>
  );
}
