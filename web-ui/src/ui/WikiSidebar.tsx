// Sidebar tree for the /wiki route.
//
// Pure presentational: receives a WikiTreeResponse["tree"] and renders
// one <button> per file (leaf) and one <section> per folder (one nesting
// level is enough — the backend's tree is flat folders, no sub-folders).
// Plant files show their sticker dot using the shared STICKER_BG lookup
// so the sidebar colour matches the dashboard plants-strip.
//
// boundaries lint forbids ui/ → api-client/ (even for `import type`), so
// the tree types below are structural duck-types of
// contracts/webapp-v1.yaml #/components/schemas/{WikiTreeNode,
// WikiTreeFile,WikiTreeFolder,PlantStickerColor}. Consumer typecheck on
// the route catches drift.
import { useState } from "react";

import { readExpandedWikiFolders, writeExpandedWikiFolders } from "@/shared/storage";
import { STICKER_BG, type StickerColor } from "@/ui/plant-types";

const FILE_ROW_ACTIVE =
  "flex w-full items-center gap-1.5 whitespace-nowrap border-l-2 border-accent-magenta bg-paper py-1 pr-3 text-left font-sans text-fs-12 font-semibold leading-prose-tight text-ink";
const FILE_ROW_IDLE =
  "flex w-full items-center gap-1.5 whitespace-nowrap border-l-2 border-transparent py-1 pr-3 text-left font-sans text-fs-12 leading-prose-tight text-ink-2 hover:bg-paper-3 hover:text-ink";

export interface WikiTreeFileNode {
  type: "file";
  name: string;
  path: string;
  title: string;
  sticker_color?: StickerColor | null;
}
export interface WikiTreeFolderNode {
  type: "folder";
  name: string;
  children: WikiTreeFileNode[];
}
export type WikiTreeNode = WikiTreeFileNode | WikiTreeFolderNode;

interface WikiSidebarProps {
  tree: readonly WikiTreeNode[];
  activePath: string | null;
  onSelect: (path: string, title: string) => void;
}

function FileRow({
  node,
  active,
  onSelect,
  indented,
}: {
  node: WikiTreeFileNode;
  active: boolean;
  onSelect: (path: string, title: string) => void;
  indented: boolean;
}) {
  const sticker = node.sticker_color
    ? STICKER_BG[node.sticker_color as StickerColor]
    : null;
  const pad = indented ? (active ? " pl-8" : " pl-8.5") : active ? " pl-5" : " pl-5.5";
  return (
    <li>
      <button
        type="button"
        data-testid="wiki-sidebar-file"
        data-path={node.path}
        aria-current={active ? "page" : undefined}
        onClick={() => {
          onSelect(node.path, node.title);
        }}
        className={(active ? FILE_ROW_ACTIVE : FILE_ROW_IDLE) + pad}
      >
        {sticker ? (
          <span
            className={`inline-block h-2 w-2 shrink-0 border border-ink ${sticker}`}
            aria-hidden
          />
        ) : (
          <span className="inline-block h-2 w-2 shrink-0" aria-hidden />
        )}
        <span className="min-w-0 flex-1 truncate">{node.title}</span>
      </button>
    </li>
  );
}

export function WikiSidebar({ tree, activePath, onSelect }: WikiSidebarProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() =>
    readExpandedWikiFolders(),
  );

  const toggle = (name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      writeExpandedWikiFolders(next);
      return next;
    });
  };

  return (
    <nav
      aria-label="Wiki tree"
      className="flex w-70 shrink-0 flex-col gap-0.5 overflow-y-auto border-r border-rule-strong bg-paper-2 px-3.5 pb-10 pt-5"
    >
      {tree.map((node) => {
        if (node.type === "file") {
          return (
            <ul key={node.path} className="list-none">
              <FileRow
                node={node}
                active={activePath === node.path}
                onSelect={onSelect}
                indented={false}
              />
            </ul>
          );
        }
        const count = node.children.length;
        const isOpen = expanded.has(node.name);
        return (
          <section
            key={node.name}
            aria-label={node.name}
            className="mb-1.5 flex flex-col"
          >
            <h3 className="m-0 p-0">
              <button
                type="button"
                data-testid="wiki-sidebar-folder"
                data-name={node.name}
                aria-expanded={isOpen}
                onClick={() => {
                  toggle(node.name);
                }}
                className="flex w-full items-center gap-1.5 px-2 py-1.25 text-left font-sans text-fs-11 font-semibold uppercase tracking-caps text-ink-3 hover:text-ink"
              >
                <span
                  aria-hidden
                  className="inline-block w-2 shrink-0 font-mono text-fs-10 leading-none text-ink-3"
                >
                  {isOpen ? "▾" : "▸"}
                </span>
                <span>{node.name}</span>
                <span className="ml-auto border border-rule px-1 text-fs-10 font-normal normal-case tracking-normal text-ink-3">
                  {count}
                </span>
              </button>
            </h3>
            <ul hidden={!isOpen} className="m-0 flex list-none flex-col p-0">
              {node.children.map((child) => (
                <FileRow
                  key={child.path}
                  node={child}
                  active={activePath === child.path}
                  onSelect={onSelect}
                  indented
                />
              ))}
            </ul>
          </section>
        );
      })}
    </nav>
  );
}
