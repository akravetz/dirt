// Live route (/live) — tent camera feed + PTZ controls.
//
// Left column: <CameraFeed> auto-refreshes /api/feed/live.jpg every
// ~10s via cache-bust query param; clicking fires POST /api/ptz/look
// with normalized [-1, 1] coordinates.
//
// Right rail: <PresetList> (overview + plant_a..d) fires
// POST /api/ptz/preset/{id}; <ZoomSlider> (1–4×) fires
// POST /api/ptz/zoom on release.
//
// State sources:
//   - /api/ptz/state via TanStack Query for the initial preset list +
//     active-preset / current-zoom values. Mutations invalidate the
//     cache so the UI reflects the new camera state after each move.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { type components, createDirtApiClient } from "@/api-client";
import { CameraFeed } from "@/ui/CameraFeed";
import { PresetList, type PresetRow } from "@/ui/PresetList";
import type { StickerColor } from "@/ui/plant-types";
import { ZoomSlider } from "@/ui/ZoomSlider";

type PTZState = components["schemas"]["PTZState"];
type ContractStickerColor = components["schemas"]["PlantStickerColor"];

export const Route = createFileRoute("/live")({
  component: LivePage,
});

const api = createDirtApiClient();
const PTZ_STATE_KEY = ["ptz.state"] as const;

function LivePage() {
  const queryClient = useQueryClient();

  const stateQuery = useQuery({
    queryKey: PTZ_STATE_KEY,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/ptz/state");
      if (error) throw error;
      return data;
    },
  });

  // Local zoom mirrors the slider position so dragging feels live even
  // before the server round-trips. Seeded from /api/ptz/state.zoom, then
  // re-seeded whenever a successful mutation updates the cached state.
  const [localZoom, setLocalZoom] = useState<number>(1);
  useEffect(() => {
    if (stateQuery.data) {
      setLocalZoom(stateQuery.data.zoom);
    }
  }, [stateQuery.data]);

  const lookMutation = useMutation({
    mutationFn: async (body: { x: number; y: number }) => {
      const { data, error } = await api.POST("/api/ptz/look", { body });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PTZ_STATE_KEY });
    },
  });

  const presetMutation = useMutation({
    mutationFn: async (id: string) => {
      const { data, error } = await api.POST("/api/ptz/preset/{id}", {
        params: { path: { id } },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PTZ_STATE_KEY });
    },
  });

  const zoomMutation = useMutation({
    mutationFn: async (zoom: number) => {
      const { data, error } = await api.POST("/api/ptz/zoom", {
        body: { zoom },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PTZ_STATE_KEY });
    },
  });

  const presets = toPresetRows(stateQuery.data);
  const activePreset = stateQuery.data?.preset ?? null;

  return (
    <main className="flex-1 overflow-auto">
      <div className="mx-auto flex max-w-400 flex-col gap-6 px-8 pb-16 pt-7">
        <header>
          <h1 className="font-sans text-fs-24 font-semibold tracking-tight text-ink">
            Tent Camera
          </h1>
        </header>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
          <CameraFeed
            onLook={(x, y) => {
              lookMutation.mutate({ x, y });
            }}
          />
          <aside className="flex flex-col gap-4">
            <PresetList
              presets={presets}
              activeId={activePreset}
              onSelect={(id) => {
                presetMutation.mutate(id);
              }}
            />
            <ZoomSlider
              value={localZoom}
              onChange={setLocalZoom}
              onCommit={(next) => {
                zoomMutation.mutate(next);
              }}
            />
          </aside>
        </div>
      </div>
    </main>
  );
}

// Adapt PTZState.presets (full contract shape) to the narrower shape
// PresetList consumes. Defaults to the mockup's five-preset set when
// /api/ptz/state is still loading so the right rail has stable layout
// while the query resolves.
const FALLBACK_PRESETS: readonly PresetRow[] = [
  { id: "overview", label: "Overview", stickerColor: null },
  { id: "plant_a", label: "Plant A", stickerColor: "yellow" },
  { id: "plant_b", label: "Plant B", stickerColor: "orange" },
  { id: "plant_c", label: "Plant C", stickerColor: "pink" },
  { id: "plant_d", label: "Plant D", stickerColor: "blue" },
] as const;

const DISPLAY_LABELS: Record<string, string> = {
  overview: "Overview",
  plant_a: "Plant A",
  plant_b: "Plant B",
  plant_c: "Plant C",
  plant_d: "Plant D",
};

function toPresetRows(state: PTZState | undefined): readonly PresetRow[] {
  if (!state) return FALLBACK_PRESETS;
  return state.presets.map((preset) => ({
    id: preset.id,
    label: DISPLAY_LABELS[preset.id] ?? preset.label,
    stickerColor: normalizeStickerColor(preset.sticker_color),
  }));
}

// Contract and ui/plant-types both enumerate the same four sticker
// colors; this narrows the contract's nullable/optional field down to
// the ui/ type so PresetList can use the shared STICKER_BG lookup.
function normalizeStickerColor(
  input: ContractStickerColor | null | undefined,
): StickerColor | null {
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
