// Hosted live route (/live) — latest signed camera asset plus PTZ-only
// command intent through the Railway control plane. The local gateway is
// still the only process that executes camera moves.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { createHostedApiClient, type hostedComponents } from "@/api-client";

export const Route = createFileRoute("/live")({
  component: HostedLivePage,
});

const hostedApi = createHostedApiClient();
const HOSTED_TENT_ID = 1;
const HOSTED_DEVICE_ID = "obsbot-main" as const;
const HOSTED_CAPABILITY_ID = "ptz_move" as const;
const HOSTED_ASSETS_KEY = ["cloud.assets.latest", HOSTED_TENT_ID] as const;
type HostedCommandCreate = hostedComponents["schemas"]["CommandCreateRequest"];
type HostedCommandInput = Omit<HostedCommandCreate, "idempotency_key">;
type HostedCommandType = HostedCommandCreate["command_type"];
type HostedCommand = hostedComponents["schemas"]["CommandResponse"];
type HostedSyncStatus = hostedComponents["schemas"]["SyncStatusResponse"];
type HostedAsset = hostedComponents["schemas"]["AssetResponse"];
type CommandButtonState = {
  disabled: boolean;
  status: HostedSyncStatus["status"];
  statusClass: string;
};
type HostedCameraAssetState =
  | { state: "loading" }
  | { state: "empty" }
  | { state: "unavailable" }
  | { state: "ready"; asset: HostedAsset };
type CommandRowModel = {
  id: string;
  status: string;
  statusClass: string;
  typeLabel: string;
};

function HostedLivePage() {
  const queryClient = useQueryClient();
  const [assetRefreshCommandId, setAssetRefreshCommandId] = useState<string | null>(
    null,
  );
  const syncQuery = useQuery({
    queryKey: ["cloud.sync.status"],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/sync/status");
      return hostedData(data, "GET /api/sync/status");
    },
    refetchInterval: 10_000,
  });
  const commandsQuery = useQuery({
    queryKey: ["cloud.commands.recent"],
    queryFn: async () => {
      const { data } = await hostedApi.GET("/api/commands");
      return hostedData(data, "GET /api/commands");
    },
    refetchInterval: 2_000,
  });
  const assetsQuery = useQuery({
    queryKey: HOSTED_ASSETS_KEY,
    queryFn: async () => {
      const { data } = await hostedApi.GET(
        "/api/tents/{source_tent_id}/assets/latest",
        {
          params: { path: { source_tent_id: HOSTED_TENT_ID } },
        },
      );
      return hostedData(data, "GET /api/tents/{source_tent_id}/assets/latest");
    },
    refetchInterval: 10_000,
    retry: false,
  });
  const commandMutation = useMutation({
    mutationFn: async (command: HostedCommandInput) => {
      const { data } = await hostedApi.POST("/api/commands", {
        body: {
          ...command,
          idempotency_key: commandIdempotencyKey(command.command_type),
        },
      });
      return hostedData(data, "POST /api/commands");
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cloud.commands.recent"] });
      void queryClient.invalidateQueries({ queryKey: ["cloud.sync.status"] });
      void queryClient.invalidateQueries({ queryKey: HOSTED_ASSETS_KEY });
    },
  });

  const buttonState = toCommandButtonState(syncQuery.data, commandMutation.isPending);
  const recentCommands = commandsQuery.data ?? [];
  const commandRows = toCommandRows(recentCommands.slice(0, 5));
  const latestSucceededCommandId =
    recentCommands.find((command) => command.status === "succeeded")?.command_id ??
    null;
  const cameraAsset = toHostedCameraAssetState(
    assetsQuery.data?.[0] ?? null,
    assetsQuery.isLoading,
    Boolean(assetsQuery.error),
  );

  useEffect(() => {
    if (
      latestSucceededCommandId !== null &&
      latestSucceededCommandId !== assetRefreshCommandId
    ) {
      setAssetRefreshCommandId(latestSucceededCommandId);
      void queryClient.invalidateQueries({ queryKey: HOSTED_ASSETS_KEY });
    }
  }, [assetRefreshCommandId, latestSucceededCommandId, queryClient]);

  const submit = (
    command_type: HostedCommandType,
    payload: Record<string, unknown>,
  ) => {
    commandMutation.mutate({
      source_tent_id: HOSTED_TENT_ID,
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
            className={`border px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps ${buttonState.statusClass}`}
          >
            Gateway {buttonState.status}
          </span>
        </header>
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
          <HostedCameraFeed
            asset={cameraAsset}
            disabled={buttonState.disabled}
            onLook={(x, y) => submit("ptz_look", { x, y })}
          />
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
                    disabled={buttonState.disabled}
                    onClick={() => submit("ptz_preset", { preset_id: preset.id })}
                    className={hostedTextButtonClass(buttonState.disabled)}
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
                  disabled={buttonState.disabled}
                  onClick={() => submit("ptz_zoom", { delta: -0.1 })}
                  className={hostedTextButtonClass(buttonState.disabled)}
                >
                  -
                </button>
                <button
                  type="button"
                  disabled={buttonState.disabled}
                  onClick={() => submit("ptz_zoom", { delta: 0.1 })}
                  className={hostedTextButtonClass(buttonState.disabled)}
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
              ) : commandRows.length === 0 ? (
                <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
                  None
                </p>
              ) : (
                <ol className="flex flex-col gap-2">
                  {commandRows.map((command) => (
                    <li
                      key={command.id}
                      className="flex items-center justify-between gap-3 border border-rule bg-paper px-3 py-2"
                    >
                      <span className="font-sans text-fs-12 text-ink">
                        {command.typeLabel}
                      </span>
                      <span
                        className={`font-mono text-fs-10 uppercase tracking-caps ${command.statusClass}`}
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

function HostedCameraFeed({
  asset,
  disabled,
  onLook,
}: {
  asset: HostedCameraAssetState;
  disabled: boolean;
  onLook: (x: number, y: number) => void;
}) {
  const clickClass = disabled ? "cursor-not-allowed" : "cursor-crosshair";
  return (
    <figure
      aria-label="Live camera feed"
      className="flex flex-col gap-0 border border-ink bg-ink p-0 ring-1 ring-accent-purple ring-inset"
    >
      {asset.state === "ready" ? (
        <button
          type="button"
          aria-label="Live camera feed"
          disabled={disabled}
          onClick={(event) => {
            const rect = event.currentTarget.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return;
            const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            const y = ((event.clientY - rect.top) / rect.height) * 2 - 1;
            onLook(clamp11(x), clamp11(y));
          }}
          className={`relative block aspect-video w-full p-0 ${clickClass}`}
        >
          <img
            alt=""
            src={asset.asset.signed_url}
            className="absolute inset-0 block h-full w-full select-none object-contain"
            draggable={false}
          />
        </button>
      ) : (
        <div className="grid aspect-video place-items-center bg-paper">
          <p
            className={`font-mono text-fs-10 uppercase tracking-caps ${
              asset.state === "unavailable" ? "text-accent-magenta" : "text-ink-3"
            }`}
          >
            {hostedAssetMessage(asset.state)}
          </p>
        </div>
      )}
      {asset.state === "ready" ? (
        <figcaption className="border-t border-rule-strong bg-paper-2 px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          Captured {formatTimestamp(asset.asset.captured_at)}
        </figcaption>
      ) : null}
    </figure>
  );
}

const HOSTED_PRESETS = [
  { id: "overview", label: "Overview" },
  { id: "plant_a", label: "Plant A" },
  { id: "plant_b", label: "Plant B" },
  { id: "plant_c", label: "Plant C" },
  { id: "plant_d", label: "Plant D" },
] as const;

function hostedData<T>(data: T | undefined, label: string): T {
  if (data === undefined) {
    throw new Error(`${label} returned no data`);
  }
  return data;
}

function commandIdempotencyKey(commandType: HostedCommandType): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `hosted-live:${commandType}:${random}`;
}

function hostedTextButtonClass(disabled: boolean): string {
  return [
    "border px-3 py-2 text-left font-sans text-fs-12",
    disabled
      ? "cursor-not-allowed border-rule text-ink-3"
      : "border-ink bg-paper text-ink hover:bg-paper-3",
  ].join(" ");
}

function toCommandButtonState(
  sync: HostedSyncStatus | undefined,
  isSubmitting: boolean,
): CommandButtonState {
  const status = sync?.status ?? "offline";
  return {
    disabled: status !== "live" || isSubmitting,
    status,
    statusClass: toHostedStatusClass(status),
  };
}

function toCommandRows(commands: readonly HostedCommand[]): readonly CommandRowModel[] {
  return commands.map((command) => ({
    id: command.command_id,
    status: command.status,
    statusClass: toCommandStatusClass(command.status),
    typeLabel: toCommandTypeLabel(command.command_type),
  }));
}

function toHostedCameraAssetState(
  asset: HostedAsset | null,
  loading: boolean,
  unavailable: boolean,
): HostedCameraAssetState {
  if (unavailable) return { state: "unavailable" };
  if (loading) return { state: "loading" };
  if (asset === null) return { state: "empty" };
  return { state: "ready", asset };
}

function hostedAssetMessage(state: HostedCameraAssetState["state"]): string {
  if (state === "unavailable") return "Signed asset URL unavailable";
  if (state === "loading") return "Loading camera image";
  return "No synced camera image";
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function clamp11(n: number): number {
  if (n < -1) return -1;
  if (n > 1) return 1;
  return n;
}

function toHostedStatusClass(status: HostedSyncStatus["status"]): string {
  if (status === "live") return "border-status-ok text-status-ok";
  if (status === "stale") return "border-status-warn text-status-warn";
  return "border-accent-magenta text-accent-magenta";
}

function toCommandStatusClass(status: string): string {
  if (status === "succeeded") return "text-status-ok";
  if (status === "failed" || status === "rejected" || status === "expired") {
    return "text-accent-magenta";
  }
  return "text-status-warn";
}

function toCommandTypeLabel(commandType: string): string {
  if (commandType === "ptz_preset") return "Preset";
  if (commandType === "ptz_look") return "Look";
  return "Zoom";
}
