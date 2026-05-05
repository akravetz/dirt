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
// Local state sources:
//   - /api/ptz/state via TanStack Query for the initial preset list +
//     active-preset / current-zoom values. Mutations invalidate the
//     cache so the UI reflects the new camera state after each move.
//
// Hosted mode submits PTZ-only command intent to the cloud control plane
// and renders command lifecycle from /api/commands. The local gateway is
// still the only process that executes camera moves.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { type components, createDirtApiClient, isHostedApiMode } from "@/api-client";
import {
  type CloudCommand,
  type CloudCommandCreate,
  type CloudCommandStatus,
  type CloudCommandType,
  type CloudSyncStatus,
  cloudGet,
  cloudPost,
} from "@/api-client/cloud";
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
const HOSTED_TENT_ID = "main";
const HOSTED_DEVICE_ID = "obsbot-main" as const;
const HOSTED_CAPABILITY_ID = "ptz_move" as const;

function LivePage() {
  return isHostedApiMode ? <HostedCloudLivePage /> : <LocalLivePage />;
}

function LocalLivePage() {
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

  const presets = stateQuery.data ? toPresetRows(stateQuery.data) : [];
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
            {stateQuery.isLoading ? (
              <PTZStatePanel message="Loading PTZ state…" />
            ) : stateQuery.error ? (
              <PTZStatePanel message="PTZ state unavailable" tone="error" />
            ) : (
              <>
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
              </>
            )}
          </aside>
        </div>
      </div>
    </main>
  );
}

function HostedCloudLivePage() {
  const queryClient = useQueryClient();
  const syncQuery = useQuery({
    queryKey: ["cloud.sync.status"],
    queryFn: async () => cloudGet<CloudSyncStatus>("/api/sync/status"),
    refetchInterval: 10_000,
  });
  const commandsQuery = useQuery({
    queryKey: ["cloud.commands.recent"],
    queryFn: async () => cloudGet<CloudCommand[]>("/api/commands"),
    refetchInterval: 2_000,
  });
  const commandMutation = useMutation({
    mutationFn: async (command: Omit<CloudCommandCreate, "idempotency_key">) =>
      cloudPost<CloudCommand>("/api/commands", {
        ...command,
        idempotency_key: commandIdempotencyKey(command.command_type),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cloud.commands.recent"] });
      void queryClient.invalidateQueries({ queryKey: ["cloud.sync.status"] });
    },
  });

  const syncStatus = syncQuery.data?.status ?? "offline";
  const disabled = syncStatus !== "live" || commandMutation.isPending;
  const recentCommands = commandsQuery.data ?? [];
  const latestCommand = recentCommands[0] ?? null;

  const submit = (command_type: CloudCommandType, payload: Record<string, unknown>) => {
    commandMutation.mutate({
      tent_id: HOSTED_TENT_ID,
      device_id: HOSTED_DEVICE_ID,
      capability_id: HOSTED_CAPABILITY_ID,
      command_type,
      payload,
    });
  };

  return (
    <main className="flex-1 overflow-auto">
      <div className="mx-auto flex max-w-400 flex-col gap-6 px-8 pb-16 pt-7">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <h1 className="font-sans text-fs-24 font-semibold tracking-tight text-ink">
            Tent Camera
          </h1>
          <span
            className={`border px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps ${hostedStatusClass(syncStatus)}`}
          >
            Gateway {syncStatus}
          </span>
        </header>
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
          <div className="border border-rule-strong bg-paper-2 p-4">
            <div className="grid aspect-video place-items-center border border-rule bg-paper">
              <div className="grid grid-cols-3 gap-2">
                <span aria-hidden="true" />
                <button
                  type="button"
                  aria-label="Look up"
                  disabled={disabled}
                  onClick={() => submit("ptz_look", { x: 0, y: -0.25 })}
                  className={hostedControlButtonClass(disabled)}
                >
                  ^
                </button>
                <span aria-hidden="true" />
                <button
                  type="button"
                  aria-label="Look left"
                  disabled={disabled}
                  onClick={() => submit("ptz_look", { x: -0.25, y: 0 })}
                  className={hostedControlButtonClass(disabled)}
                >
                  &lt;
                </button>
                <span aria-hidden="true" />
                <button
                  type="button"
                  aria-label="Look right"
                  disabled={disabled}
                  onClick={() => submit("ptz_look", { x: 0.25, y: 0 })}
                  className={hostedControlButtonClass(disabled)}
                >
                  &gt;
                </button>
                <span aria-hidden="true" />
                <button
                  type="button"
                  aria-label="Look down"
                  disabled={disabled}
                  onClick={() => submit("ptz_look", { x: 0, y: 0.25 })}
                  className={hostedControlButtonClass(disabled)}
                >
                  v
                </button>
                <span aria-hidden="true" />
              </div>
            </div>
          </div>
          <aside className="flex flex-col gap-4">
            <section className="border border-rule-strong bg-paper-2 p-4">
              <h2 className="mb-3 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                Presets
              </h2>
              <div className="grid grid-cols-2 gap-2">
                {HOSTED_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    disabled={disabled}
                    onClick={() => submit("ptz_preset", { preset_id: preset.id })}
                    className={hostedTextButtonClass(disabled)}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </section>
            <section className="border border-rule-strong bg-paper-2 p-4">
              <h2 className="mb-3 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                Zoom
              </h2>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => submit("ptz_zoom", { delta: -0.1 })}
                  className={hostedTextButtonClass(disabled)}
                >
                  -
                </button>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => submit("ptz_zoom", { delta: 0.1 })}
                  className={hostedTextButtonClass(disabled)}
                >
                  +
                </button>
              </div>
            </section>
            <section className="border border-rule-strong bg-paper-2 p-4">
              <h2 className="mb-3 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                Commands
              </h2>
              {commandsQuery.isLoading ? (
                <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                  Loading
                </p>
              ) : latestCommand === null ? (
                <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                  None
                </p>
              ) : (
                <ol className="flex flex-col gap-2">
                  {recentCommands.slice(0, 5).map((command) => (
                    <li
                      key={command.command_id}
                      className="flex items-center justify-between gap-3 border border-rule bg-paper px-3 py-2"
                    >
                      <span className="font-sans text-fs-12 text-ink">
                        {formatCommandType(command.command_type)}
                      </span>
                      <span
                        className={`font-mono text-fs-10 uppercase tracking-caps ${commandStatusClass(command.status)}`}
                      >
                        {command.status}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
              {commandMutation.error ? (
                <p className="mt-3 font-mono text-fs-10 uppercase tracking-caps text-accent-magenta">
                  Command failed
                </p>
              ) : null}
            </section>
          </aside>
        </section>
      </div>
    </main>
  );
}

function PTZStatePanel({
  message,
  tone = "muted",
}: {
  message: string;
  tone?: "muted" | "error";
}) {
  const toneClass = tone === "error" ? "text-accent-magenta" : "text-ink-3";
  return (
    <section
      aria-label="PTZ state"
      className="border border-rule-strong bg-paper-2 p-4"
    >
      <p className={`font-mono text-fs-10 uppercase tracking-caps ${toneClass}`}>
        {message}
      </p>
    </section>
  );
}

// Adapt PTZState.presets (full contract shape) to the narrower shape
// PresetList consumes. Until /api/ptz/state returns, the right rail
// shows a loading/error panel instead of invented preset rows.

const DISPLAY_LABELS: Record<string, string> = {
  overview: "Overview",
  plant_a: "Plant A",
  plant_b: "Plant B",
  plant_c: "Plant C",
  plant_d: "Plant D",
};

const HOSTED_PRESETS = [
  { id: "overview", label: "Overview" },
  { id: "plant_a", label: "Plant A" },
  { id: "plant_b", label: "Plant B" },
  { id: "plant_c", label: "Plant C" },
  { id: "plant_d", label: "Plant D" },
] as const;

function toPresetRows(state: PTZState): readonly PresetRow[] {
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

function commandIdempotencyKey(commandType: CloudCommandType): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `hosted-live:${commandType}:${random}`;
}

function hostedControlButtonClass(disabled: boolean): string {
  return [
    "grid h-12 w-12 place-items-center border font-mono text-fs-14",
    disabled
      ? "cursor-not-allowed border-rule text-ink-3"
      : "border-ink bg-paper text-ink hover:bg-paper-3",
  ].join(" ");
}

function hostedTextButtonClass(disabled: boolean): string {
  return [
    "border px-3 py-2 text-left font-sans text-fs-12",
    disabled
      ? "cursor-not-allowed border-rule text-ink-3"
      : "border-ink bg-paper text-ink hover:bg-paper-3",
  ].join(" ");
}

function hostedStatusClass(status: CloudSyncStatus["status"]): string {
  if (status === "live") return "border-status-ok text-status-ok";
  if (status === "stale") return "border-status-warn text-status-warn";
  return "border-accent-magenta text-accent-magenta";
}

function commandStatusClass(status: CloudCommandStatus): string {
  if (status === "succeeded") return "text-status-ok";
  if (status === "failed" || status === "rejected" || status === "expired") {
    return "text-accent-magenta";
  }
  return "text-status-warn";
}

function formatCommandType(commandType: CloudCommandType): string {
  if (commandType === "ptz_preset") return "Preset";
  if (commandType === "ptz_look") return "Look";
  return "Zoom";
}
