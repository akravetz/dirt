// Wiki route (/wiki) — sidebar tree + markdown pane + Cmd+K palette.
//
// URL model: ?path=plants/plant-a.md (typed via validateSearch). Opens a
// page directly from its path — shareable link, refreshable. Missing
// or blank path → show the tree only (no document pane).
//
// Data: /api/wiki/tree fetched once per mount via TanStack Query;
// /api/wiki/file fetched per selected path, keyed on the path string
// so navigating between pages hits the cache on return. Search fires
// GET /api/wiki/search against a debounced trimmed non-empty query —
// empty/whitespace queries short-circuit to the recent-files list kept
// in shared/storage.ts (TS-09 single localStorage owner).
//
// Cmd+K: window-scoped keydown listener toggles the palette. The listener
// is a DOM/event-lifecycle useEffect (not data-fetching), so TS-06 does
// not flag it.
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";

import { type components, createDirtApiClient } from "@/api-client";
import {
  pushRecentWikiFile,
  type RecentWikiFile,
  readRecentWikiFiles,
} from "@/shared/storage";
import { CmdKPalette, type PaletteSearchResult } from "@/ui/CmdKPalette";
import { WikiDoc, type WikiFileDoc } from "@/ui/WikiDoc";
import { WikiSidebar, type WikiTreeNode } from "@/ui/WikiSidebar";

type WikiFileResponse = components["schemas"]["WikiFile"];
type WikiTreeResponseSchema = components["schemas"]["WikiTreeResponse"];
type WikiSearchResponse = components["schemas"]["WikiSearchResponse"];

interface WikiSearch {
  path?: string;
}

export const Route = createFileRoute("/wiki")({
  component: WikiPage,
  // Accept `?path=…`; any other shape drops the key entirely so the URL
  // stays clean on bare /wiki visits (instead of `?path=null`).
  validateSearch: (search: Record<string, unknown>): WikiSearch => {
    const raw = search.path;
    return typeof raw === "string" && raw.length > 0 ? { path: raw } : {};
  },
});

const api = createDirtApiClient();

// Debounce ms for the search query — tuned so each keystroke does NOT
// fire a network request while the user is typing a word, but results
// feel live once they pause. Matches the common command-palette feel.
const SEARCH_DEBOUNCE_MS = 150;

// Narrow the contract's WikiTreeNode union to the ui/ component's
// structural shape. Duck-type compatibility is load-bearing here: the
// runtime shape is identical; we only need TypeScript to accept the
// assignment across the boundaries layer.
function toSidebarTree(tree: WikiTreeResponseSchema["tree"]): WikiTreeNode[] {
  return tree.map((node): WikiTreeNode => {
    if (node.type === "folder") {
      return {
        type: "folder",
        name: node.name,
        children: node.children
          .filter((c): c is Extract<typeof c, { type: "file" }> => c.type === "file")
          .map((c) => ({
            type: "file",
            name: c.name,
            path: c.path,
            title: c.title,
            sticker_color: narrowSticker(c.sticker_color),
          })),
      };
    }
    return {
      type: "file",
      name: node.name,
      path: node.path,
      title: node.title,
      sticker_color: narrowSticker(node.sticker_color),
    };
  });
}

type SidebarSticker = "yellow" | "orange" | "pink" | "blue" | null;
function narrowSticker(
  input: components["schemas"]["PlantStickerColor"] | null | undefined,
): SidebarSticker {
  if (
    input === "yellow" ||
    input === "orange" ||
    input === "pink" ||
    input === "blue"
  ) {
    return input;
  }
  return null;
}

function toWikiDoc(payload: WikiFileResponse): WikiFileDoc {
  return {
    path: payload.path,
    title: payload.title,
    subtitle: payload.subtitle ?? null,
    frontmatter: payload.frontmatter,
    body_markdown: payload.body_markdown,
    backlinks: payload.backlinks.map((b) => ({ path: b.path, title: b.title })),
  };
}

function WikiPage() {
  const navigate = useNavigate({ from: Route.fullPath });
  const { path: rawPath } = Route.useSearch();
  const selectedPath = rawPath ?? null;

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [recents, setRecents] = useState<RecentWikiFile[]>(() => readRecentWikiFiles());

  // Debounce the palette query for the search endpoint. The empty/
  // whitespace branch below short-circuits to recents, so this debounce
  // only runs while the user is actively typing.
  useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedQuery(paletteQuery);
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      clearTimeout(handle);
    };
  }, [paletteQuery]);

  // Global Cmd+K / Ctrl+K toggle. One event listener owned by the route
  // component; removed on unmount. Not data-fetching, so TS-06 is fine.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      } else if (e.key === "Escape") {
        setPaletteOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const treeQuery = useQuery({
    queryKey: ["wiki.tree"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/wiki/tree");
      if (error) throw error;
      return data;
    },
  });

  const fileQuery = useQuery({
    queryKey: ["wiki.file", selectedPath] as const,
    queryFn: async () => {
      if (selectedPath === null) throw new Error("no path selected");
      const { data, error } = await api.GET("/api/wiki/file", {
        params: { query: { path: selectedPath } },
      });
      if (error) throw error;
      return data;
    },
    enabled: selectedPath !== null,
  });

  // Search query — `enabled` gate guarantees we never fire a GET with
  // an empty/whitespace `q`. The e2e asserts this via network tracking.
  const trimmedQuery = debouncedQuery.trim();
  const searchEnabled = paletteOpen && trimmedQuery.length > 0;
  const searchQuery = useQuery({
    queryKey: ["wiki.search", trimmedQuery] as const,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/wiki/search", {
        params: { query: { q: trimmedQuery } },
      });
      if (error) throw error;
      return data;
    },
    enabled: searchEnabled,
  });

  const tree = useMemo(
    () => (treeQuery.data ? toSidebarTree(treeQuery.data.tree) : []),
    [treeQuery.data],
  );
  const doc = fileQuery.data ? toWikiDoc(fileQuery.data) : null;
  const results: PaletteSearchResult[] = searchData(searchQuery.data);

  const openPath = (path: string, title: string) => {
    setRecents(pushRecentWikiFile({ path, title }));
    setPaletteOpen(false);
    setPaletteQuery("");
    void navigate({ search: { path } });
  };

  return (
    <main className="flex min-h-0 min-w-0 flex-1">
      <WikiSidebar
        tree={tree}
        activePath={selectedPath}
        onSelect={(path, title) => {
          openPath(path, title);
        }}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {doc ? (
          <WikiDoc doc={doc} />
        ) : (
          <section
            aria-label="Wiki empty state"
            className="flex flex-1 items-center justify-center p-8"
          >
            <p className="font-mono text-xs uppercase tracking-caps text-ink-3">
              {treeQuery.isLoading
                ? "Loading wiki…"
                : "Pick a page from the sidebar or press ⌘K to search."}
            </p>
          </section>
        )}
      </div>
      <CmdKPalette
        open={paletteOpen}
        query={paletteQuery}
        onQueryChange={setPaletteQuery}
        onClose={() => {
          setPaletteOpen(false);
        }}
        onSelect={openPath}
        results={results}
        recents={recents}
      />
    </main>
  );
}

function searchData(data: WikiSearchResponse | undefined): PaletteSearchResult[] {
  if (!data) return [];
  return data.results.map((r) => ({
    path: r.path,
    title: r.title,
    match_type: r.match_type,
    snippet: r.snippet ?? null,
  }));
}
