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
import { STICKER_BG, type StickerColor } from "@/ui/plant-types";

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
}: {
  node: WikiTreeFileNode;
  active: boolean;
  onSelect: (path: string, title: string) => void;
}) {
  const sticker = node.sticker_color
    ? STICKER_BG[node.sticker_color as StickerColor]
    : null;
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
        className={
          active
            ? "flex w-full items-center gap-2 border-l-2 border-accent-magenta bg-rule/30 px-3 py-1.5 text-left text-ink"
            : "flex w-full items-center gap-2 border-l-2 border-transparent px-3 py-1.5 text-left text-ink-2 hover:bg-rule/30 hover:text-ink"
        }
      >
        {sticker ? (
          <span
            className={`inline-block h-2 w-2 rounded-full ${sticker}`}
            aria-hidden
          />
        ) : (
          <span className="inline-block h-2 w-2" aria-hidden />
        )}
        <span className="truncate">{node.title}</span>
      </button>
    </li>
  );
}

export function WikiSidebar({ tree, activePath, onSelect }: WikiSidebarProps) {
  return (
    <nav
      aria-label="Wiki tree"
      className="flex w-64 shrink-0 flex-col gap-4 border-r border-rule bg-paper py-4 text-sm"
    >
      {tree.map((node) => {
        if (node.type === "file") {
          return (
            <ul key={node.path} className="list-none">
              <FileRow
                node={node}
                active={activePath === node.path}
                onSelect={onSelect}
              />
            </ul>
          );
        }
        return (
          <section
            key={node.name}
            aria-label={node.name}
            className="flex flex-col gap-1"
          >
            <h3 className="px-3 font-mono text-xs uppercase tracking-caps text-ink-3">
              {node.name}
            </h3>
            <ul className="flex list-none flex-col">
              {node.children.map((child) => (
                <FileRow
                  key={child.path}
                  node={child}
                  active={activePath === child.path}
                  onSelect={onSelect}
                />
              ))}
            </ul>
          </section>
        );
      })}
    </nav>
  );
}
