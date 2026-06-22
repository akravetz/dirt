import type { QueryClient } from "@tanstack/react-query";
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { createHostedApiClient, type hostedComponents } from "@/api-client";
import { platform } from "@/shared/platform";
import { invalidateSeedLotReads } from "./seedsQueries";
import type { SeedLotSexTypeKey, SeedLotSource } from "./seedsTypes";

const hostedApi = createHostedApiClient();
const pendingSeedCommandsQueryKey = [
  "breeding-logbook",
  "seed-lots",
  "pending-commands",
] as const;
const TERMINAL_COMMAND_STATUSES = new Set([
  "succeeded",
  "failed",
  "rejected",
  "expired",
]);
const PROJECTION_REFRESH_DELAYS_MS = [0, 2_500, 7_500, 15_000] as const;

type HostedCommand = hostedComponents["schemas"]["CommandResponse"];
type BreedingCreateSeedLotRequest =
  hostedComponents["schemas"]["BreedingCreateSeedLotRequest"];
type BreedingUpdateSeedLotInventoryRequest =
  hostedComponents["schemas"]["BreedingUpdateSeedLotInventoryRequest"];

type PendingSeedOperation = "add-seeds" | "update-seed-lot";

export type SeedsPendingCommand = {
  commandId: string;
  command: HostedCommand;
  operation: PendingSeedOperation;
  label: string;
  seedLotId: string | null;
};

export type AddSeedLotMutationInput = {
  idempotencyKey: string;
  source: SeedLotSource;
  generation: string;
  prefix: string;
  sexTypeKey: SeedLotSexTypeKey;
  strain: string | null;
  cultivar: string | null;
  sourceName: string | null;
  vendorName: string | null;
  acquiredAt: string | null;
  seedParentPlantKey: string | null;
  pollenParentPlantKey: string | null;
  seedCount: number | null;
  notes: string | null;
};

export type UpdateSeedLotInventoryInput = {
  idempotencyKey: string;
  seedLotId: string;
  sourceSeedLotId: number;
  label: string;
  sexTypeKey: SeedLotSexTypeKey;
  seedCount: number | null;
  notes: string | null;
  vendorName: string | null;
  acquiredAt: string | null;
};

export function createSeedsIdempotencyKey(operation: string): string {
  const random =
    typeof crypto === "undefined" || crypto.randomUUID === undefined
      ? Math.random().toString(36).slice(2)
      : crypto.randomUUID();
  return `breeding-logbook:${operation}:${Date.now()}:${random}`;
}

export function buildCreateSeedLotRequest(
  input: AddSeedLotMutationInput,
): BreedingCreateSeedLotRequest {
  return {
    idempotency_key: input.idempotencyKey,
    source: input.source,
    generation: input.generation,
    prefix: input.prefix,
    strain: input.strain,
    cultivar: input.cultivar,
    source_name: input.sourceName,
    vendor_name: input.vendorName,
    acquired_at: input.acquiredAt,
    seed_parent_plant_key: input.seedParentPlantKey,
    pollen_parent_plant_key: input.pollenParentPlantKey,
    pollinated_at: null,
    pollen_parent_is_reversed: null,
    seed_count: input.seedCount,
    sex_type_key: input.sexTypeKey,
    notes: input.notes,
  };
}

export function buildUpdateSeedLotInventoryRequest(
  input: UpdateSeedLotInventoryInput,
): BreedingUpdateSeedLotInventoryRequest {
  return {
    idempotency_key: input.idempotencyKey,
    seed_lot_source_id: input.sourceSeedLotId,
    sex_type_key: input.sexTypeKey,
    seed_count: input.seedCount,
    notes: input.notes,
    vendor_name: input.vendorName,
    acquired_at: input.acquiredAt,
  };
}

export function useSeedsPendingCommands(): readonly SeedsPendingCommand[] {
  const queryClient = useQueryClient();
  const pendingQuery = useQuery({
    queryKey: pendingSeedCommandsQueryKey,
    queryFn: () => getPendingSeedCommands(queryClient),
    initialData: [],
    staleTime: Infinity,
  });
  const pendingCommands = pendingQuery.data;
  const pollableCommands = useMemo(
    () =>
      pendingCommands.filter(
        (pending) => !isTerminalCommandStatus(pending.command.status),
      ),
    [pendingCommands],
  );
  const commandPollQueries = useQueries({
    queries: pollableCommands.map((pending) => ({
      queryKey: ["breeding-logbook", "commands", pending.commandId],
      queryFn: () => fetchCommand(pending.commandId),
      refetchInterval: 2_500,
      staleTime: 0,
    })),
  });

  useEffect(() => {
    for (const [index, query] of commandPollQueries.entries()) {
      const command = query.data;
      const pending = pollableCommands[index];
      if (command === undefined || pending === undefined) continue;
      if (pending.command === command) continue;
      const transitionedToSuccess =
        !isTerminalCommandStatus(pending.command.status) &&
        command.status === "succeeded";
      updatePendingSeedCommand(queryClient, pending.commandId, command);
      if (transitionedToSuccess) {
        scheduleSeedProjectionRefresh(
          queryClient,
          pending.seedLotId === null ? [] : [pending.seedLotId],
        );
      }
    }
  }, [commandPollQueries, pollableCommands, queryClient]);

  return pendingCommands;
}

export function useAddSeedLotMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createSeedLot,
    onSuccess: (command, input) => {
      addPendingSeedCommand(queryClient, {
        command,
        operation: "add-seeds",
        label: `Seed lot ${input.prefix} queued`,
        seedLotId: null,
      });
      invalidateSeedLotReads(queryClient);
      if (command.status === "succeeded") {
        scheduleSeedProjectionRefresh(queryClient);
      }
    },
  });
}

export function useUpdateSeedLotInventoryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateSeedLotInventory,
    onSuccess: (command, input) => {
      addPendingSeedCommand(queryClient, {
        command,
        operation: "update-seed-lot",
        label: `Seed lot ${input.label} update queued`,
        seedLotId: input.seedLotId,
      });
      invalidateSeedLotReads(queryClient, [input.seedLotId]);
      if (command.status === "succeeded") {
        scheduleSeedProjectionRefresh(queryClient, [input.seedLotId]);
      }
    },
  });
}

export function commandErrorText(command: SeedsPendingCommand): string | null {
  if (!isFailedCommandStatus(command.command.status)) return null;
  return command.command.error || `${command.label} ${command.command.status}`;
}

export function seedCommandStatusLabel(command: SeedsPendingCommand): string {
  const error = commandErrorText(command);
  if (error !== null) return error;
  if (command.command.status === "succeeded") return "succeeded / refreshing reads";
  return command.command.status;
}

async function createSeedLot(input: AddSeedLotMutationInput): Promise<HostedCommand> {
  const { data } = await hostedApi.POST("/api/breeding-logbook/seed-lots", {
    body: buildCreateSeedLotRequest(input),
  });
  return hostedData(data, "POST /api/breeding-logbook/seed-lots");
}

async function updateSeedLotInventory(
  input: UpdateSeedLotInventoryInput,
): Promise<HostedCommand> {
  const { data } = await hostedApi.POST(
    "/api/breeding-logbook/seed-lots/{seed_lot_id}:update",
    {
      params: { path: { seed_lot_id: input.seedLotId } },
      body: buildUpdateSeedLotInventoryRequest(input),
    },
  );
  return hostedData(data, "POST /api/breeding-logbook/seed-lots/{seed_lot_id}:update");
}

async function fetchCommand(commandId: string): Promise<HostedCommand> {
  const { data } = await hostedApi.GET("/api/commands/{command_id}", {
    params: { path: { command_id: commandId } },
  });
  return hostedData(data, "GET /api/commands/{command_id}");
}

function hostedData<T>(data: T | undefined, path: string): T {
  if (data === undefined) {
    throw new Error(`${path} returned no data`);
  }
  return data;
}

function addPendingSeedCommand(
  queryClient: QueryClient,
  input: Omit<SeedsPendingCommand, "commandId">,
): void {
  queryClient.setQueryData<readonly SeedsPendingCommand[]>(
    pendingSeedCommandsQueryKey,
    (current = []) => {
      const next = {
        ...input,
        commandId: input.command.command_id,
      };
      return [
        next,
        ...current.filter((pending) => pending.commandId !== next.commandId),
      ];
    },
  );
}

function updatePendingSeedCommand(
  queryClient: QueryClient,
  commandId: string,
  command: HostedCommand,
): void {
  queryClient.setQueryData<readonly SeedsPendingCommand[]>(
    pendingSeedCommandsQueryKey,
    (current = []) =>
      current.map((pending) =>
        pending.commandId === commandId ? { ...pending, command } : pending,
      ),
  );
}

function getPendingSeedCommands(
  queryClient: QueryClient,
): readonly SeedsPendingCommand[] {
  return queryClient.getQueryData(pendingSeedCommandsQueryKey) ?? [];
}

function scheduleSeedProjectionRefresh(
  queryClient: QueryClient,
  seedLotIds: readonly string[] = [],
): void {
  for (const delayMs of PROJECTION_REFRESH_DELAYS_MS) {
    platform.setTimeout(() => {
      invalidateSeedLotReads(queryClient, seedLotIds);
    }, delayMs);
  }
}

function isTerminalCommandStatus(status: string): boolean {
  return TERMINAL_COMMAND_STATUSES.has(status);
}

function isFailedCommandStatus(status: string): boolean {
  return status === "failed" || status === "rejected" || status === "expired";
}
