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
import { invalidateBreedingLogbookReads } from "./breedingLogbookQueries";
import type {
  PlantJournalEvent,
  PlantRow,
  PlantSexKey,
  PlantStageKey,
  SeedLotSexTypeKey,
  SeedLotSource,
} from "./breedingLogbookTypes";

const hostedApi = createHostedApiClient();
const pendingCommandsQueryKey = ["breeding-logbook", "pending-commands"] as const;
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
type BreedingGerminatePlantsRequest =
  hostedComponents["schemas"]["BreedingGerminatePlantsRequest"];
type BreedingClonePlantsRequest =
  hostedComponents["schemas"]["BreedingClonePlantsRequest"];
type BreedingBulkSexRequest = hostedComponents["schemas"]["BreedingBulkSexRequest"];
type BreedingBulkMoveRequest = hostedComponents["schemas"]["BreedingBulkMoveRequest"];
type BreedingBulkCullRequest = hostedComponents["schemas"]["BreedingBulkCullRequest"];
type BreedingCreatePlantNoteRequest =
  hostedComponents["schemas"]["BreedingCreatePlantNoteRequest"];

type PendingOperation =
  | "add-seeds"
  | "germinate"
  | "clone"
  | "bulk-sex"
  | "bulk-move"
  | "bulk-cull"
  | "note";

export type BreedingLogbookPendingCommand = {
  commandId: string;
  command: HostedCommand;
  operation: PendingOperation;
  label: string;
  affectedPlantKeys: readonly string[];
  optimisticPlantPatches: readonly PendingPlantPatch[];
  pendingNote: {
    plantKey: string;
    body: string;
  } | null;
};

type PendingPlantPatch = {
  plantKey: string;
  sexKey?: PlantSexKey;
  stageKey?: PlantStageKey;
  locationKey?: string;
  locationLabel?: string;
  culledOn?: string | null;
  lastNote?: string;
};

export type PendingTimelineNote = {
  id: string;
  body: string;
  dateLabel: string;
  error: string | null;
  statusLabel: string;
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
  seedParentPlantKey: string | null;
  pollenParentPlantKey: string | null;
  seedCount: number | null;
  notes: string | null;
};

type GerminatePlantsMutationInput = {
  idempotencyKey: string;
  seedLotId: string;
  count: number;
  tentId: string;
  affectedLabel: string;
  germinatedAt: string;
};

type ClonePlantsMutationInput = {
  idempotencyKey: string;
  motherPlantKey: string;
  count: number;
  tentId: string;
  takenAt: string;
};

type BulkSexMutationInput = {
  idempotencyKey: string;
  plantKeys: readonly string[];
  sexKey: PlantSexKey;
};

type BulkMoveMutationInput = {
  idempotencyKey: string;
  plantKeys: readonly string[];
  tentId: string;
  locationLabel: string;
  locationStageKey: PlantStageKey;
};

type BulkCullMutationInput = {
  idempotencyKey: string;
  plantKeys: readonly string[];
  reason: string;
};

type LogNoteMutationInput = {
  idempotencyKey: string;
  plantKey: string;
  body: string;
};

export function createBreedingLogbookIdempotencyKey(operation: string): string {
  const random =
    typeof crypto === "undefined" || crypto.randomUUID === undefined
      ? Math.random().toString(36).slice(2)
      : crypto.randomUUID();
  return `breeding-logbook:${operation}:${Date.now()}:${random}`;
}

export function canSubmitBulkCull(reason: string): boolean {
  return reason.trim().length > 0;
}

export function readonlyPlantPrefixPreview(prefix: string): string {
  return `${prefix}-`;
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
    acquired_at: null,
    seed_parent_plant_key: input.seedParentPlantKey,
    pollen_parent_plant_key: input.pollenParentPlantKey,
    pollinated_at: null,
    pollen_parent_is_reversed: null,
    seed_count: input.seedCount,
    sex_type_key: input.sexTypeKey,
    notes: input.notes,
  };
}

export function buildGerminatePlantsRequest(
  input: GerminatePlantsMutationInput,
): BreedingGerminatePlantsRequest {
  return {
    idempotency_key: input.idempotencyKey,
    seed_lot_id: input.seedLotId,
    count: input.count,
    tent_id: input.tentId,
    grid_position: null,
    germinated_at: input.germinatedAt,
  };
}

export function buildClonePlantsRequest(
  input: ClonePlantsMutationInput,
): BreedingClonePlantsRequest {
  return {
    idempotency_key: input.idempotencyKey,
    mother_plant_key: input.motherPlantKey,
    count: input.count,
    tent_id: input.tentId,
    grid_position: null,
    taken_at: input.takenAt,
  };
}

export function buildBulkSexRequest(
  input: BulkSexMutationInput,
): BreedingBulkSexRequest {
  return {
    idempotency_key: input.idempotencyKey,
    plant_keys: [...input.plantKeys],
    sex_key: input.sexKey,
  };
}

export function buildBulkMoveRequest(
  input: BulkMoveMutationInput,
): BreedingBulkMoveRequest {
  return {
    idempotency_key: input.idempotencyKey,
    plant_keys: [...input.plantKeys],
    tent_id: input.tentId,
    grid_position: null,
  };
}

export function buildBulkCullRequest(
  input: BulkCullMutationInput,
): BreedingBulkCullRequest {
  return {
    idempotency_key: input.idempotencyKey,
    plant_keys: [...input.plantKeys],
    reason: input.reason.trim(),
  };
}

export function buildLogNoteRequest(
  input: LogNoteMutationInput,
): BreedingCreatePlantNoteRequest {
  return {
    idempotency_key: input.idempotencyKey,
    body: input.body.trim(),
    observed_at: null,
  };
}

export function useBreedingLogbookPendingCommands(): readonly BreedingLogbookPendingCommand[] {
  const queryClient = useQueryClient();
  const pendingQuery = useQuery({
    queryKey: pendingCommandsQueryKey,
    queryFn: () => getPendingCommands(queryClient),
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
      updatePendingCommand(queryClient, pending.commandId, command);
      if (transitionedToSuccess) {
        scheduleProjectionRefresh(queryClient, pending.affectedPlantKeys);
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
      addPendingCommand(queryClient, {
        command,
        operation: "add-seeds",
        label: `Seed lot ${input.prefix} queued`,
        affectedPlantKeys: [],
        optimisticPlantPatches: [],
        pendingNote: null,
      });
      invalidateBreedingLogbookReads(queryClient);
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient);
      }
    },
  });
}

export function useGerminatePlantsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: germinatePlants,
    onSuccess: (command, input) => {
      addPendingCommand(queryClient, {
        command,
        operation: "germinate",
        label: `Germinating ${input.count} from ${input.affectedLabel}`,
        affectedPlantKeys: [],
        optimisticPlantPatches: [],
        pendingNote: null,
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient);
      }
    },
  });
}

export function useClonePlantsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: clonePlants,
    onSuccess: (command, input) => {
      addPendingCommand(queryClient, {
        command,
        operation: "clone",
        label: `Taking ${input.count} clones`,
        affectedPlantKeys: [input.motherPlantKey],
        optimisticPlantPatches: [],
        pendingNote: null,
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient, [input.motherPlantKey]);
      }
    },
  });
}

export function useBulkSexMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: bulkSexPlants,
    onSuccess: (command, input) => {
      addPendingCommand(queryClient, {
        command,
        operation: "bulk-sex",
        label: `Setting sex on ${input.plantKeys.length} plants`,
        affectedPlantKeys: input.plantKeys,
        optimisticPlantPatches: input.plantKeys.map((plantKey) => ({
          plantKey,
          sexKey: input.sexKey,
        })),
        pendingNote: null,
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient, input.plantKeys);
      }
    },
  });
}

export function useBulkMoveMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: bulkMovePlants,
    onSuccess: (command, input) => {
      addPendingCommand(queryClient, {
        command,
        operation: "bulk-move",
        label: `Moving ${input.plantKeys.length} plants to ${input.locationLabel}`,
        affectedPlantKeys: input.plantKeys,
        optimisticPlantPatches: input.plantKeys.map((plantKey) => ({
          plantKey,
          locationKey: input.tentId,
          locationLabel: input.locationLabel,
          stageKey: input.locationStageKey,
        })),
        pendingNote: null,
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient, input.plantKeys);
      }
    },
  });
}

export function useBulkCullMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: bulkCullPlants,
    onSuccess: (command, input) => {
      addPendingCommand(queryClient, {
        command,
        operation: "bulk-cull",
        label: `Culling ${input.plantKeys.length} plants`,
        affectedPlantKeys: input.plantKeys,
        optimisticPlantPatches: input.plantKeys.map((plantKey) => ({
          plantKey,
          locationKey: "removed",
          locationLabel: "Removed",
          stageKey: "culled",
        })),
        pendingNote: null,
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient, input.plantKeys);
      }
    },
  });
}

export function useLogPlantNoteMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logPlantNote,
    onSuccess: (command, input) => {
      addPendingCommand(queryClient, {
        command,
        operation: "note",
        label: "Logging note",
        affectedPlantKeys: [input.plantKey],
        optimisticPlantPatches: [
          {
            plantKey: input.plantKey,
            lastNote: input.body.trim(),
          },
        ],
        pendingNote: {
          plantKey: input.plantKey,
          body: input.body.trim(),
        },
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient, [input.plantKey]);
      }
    },
  });
}

export function activePendingCommandsForPlant(
  pendingCommands: readonly BreedingLogbookPendingCommand[],
  plantKey: string,
): readonly BreedingLogbookPendingCommand[] {
  return pendingCommands.filter(
    (pending) =>
      pending.affectedPlantKeys.includes(plantKey) &&
      !isTerminalCommandStatus(pending.command.status),
  );
}

export function failedCommandsForPlant(
  pendingCommands: readonly BreedingLogbookPendingCommand[],
  plantKey: string,
): readonly BreedingLogbookPendingCommand[] {
  return pendingCommands.filter(
    (pending) =>
      pending.affectedPlantKeys.includes(plantKey) &&
      isFailedCommandStatus(pending.command.status),
  );
}

export function hasActivePendingForAnyPlant(
  pendingCommands: readonly BreedingLogbookPendingCommand[],
  plantKeys: readonly string[],
): boolean {
  return plantKeys.some(
    (plantKey) => activePendingCommandsForPlant(pendingCommands, plantKey).length > 0,
  );
}

export function pendingTimelineNotes(
  events: readonly PlantJournalEvent[],
  pendingCommands: readonly BreedingLogbookPendingCommand[],
  plantKey: string,
): readonly PendingTimelineNote[] {
  return pendingCommands.flatMap((pending) => {
    if (pending.pendingNote?.plantKey !== plantKey) return [];
    if (hasSyncedNote(events, pending.pendingNote.body)) return [];
    return [
      {
        id: `pending-${pending.commandId}`,
        body: pending.pendingNote.body,
        dateLabel: "Pending",
        error: isFailedCommandStatus(pending.command.status)
          ? pending.command.error || `${pending.command.status} command`
          : null,
        statusLabel:
          pending.command.status === "succeeded"
            ? "Syncing"
            : isFailedCommandStatus(pending.command.status)
              ? "Failed"
              : "Queued",
      },
    ];
  });
}

export function applyPendingPlantCommands(
  plants: readonly PlantRow[],
  pendingCommands: readonly BreedingLogbookPendingCommand[],
): readonly PlantRow[] {
  const patchesByPlantKey = new Map<string, PendingPlantPatch[]>();
  for (const pending of pendingCommands) {
    if (!shouldApplyOptimisticCommand(pending)) continue;
    for (const patch of pending.optimisticPlantPatches) {
      const current = patchesByPlantKey.get(patch.plantKey) ?? [];
      patchesByPlantKey.set(patch.plantKey, [...current, patch]);
    }
  }
  if (patchesByPlantKey.size === 0) return plants;

  return plants.map((plant) => {
    const patches = patchesByPlantKey.get(plant.key);
    if (patches === undefined) return plant;
    return patches.reduce(applyPlantPatch, plant);
  });
}

export function isPendingCommandProjected(
  pending: BreedingLogbookPendingCommand,
  plants: readonly PlantRow[],
  events: readonly PlantJournalEvent[],
  detailPlantKey: string,
): boolean {
  const patchesProjected = pending.optimisticPlantPatches.every((patch) => {
    const plant = plants.find((candidate) => candidate.key === patch.plantKey);
    return plant !== undefined && isPlantPatchProjected(plant, patch);
  });
  if (!patchesProjected) return false;
  if (pending.pendingNote === null) return true;
  if (pending.pendingNote.plantKey !== detailPlantKey) return true;
  return hasSyncedNote(events, pending.pendingNote.body);
}

export function commandErrorText(
  pendingCommand: BreedingLogbookPendingCommand,
): string | null {
  if (!isFailedCommandStatus(pendingCommand.command.status)) return null;
  return (
    pendingCommand.command.error ||
    `${pendingCommand.label} ${pendingCommand.command.status}`
  );
}

async function createSeedLot(input: AddSeedLotMutationInput): Promise<HostedCommand> {
  const { data } = await hostedApi.POST("/api/breeding-logbook/seed-lots", {
    body: buildCreateSeedLotRequest(input),
  });
  return hostedData(data, "POST /api/breeding-logbook/seed-lots");
}

async function germinatePlants(
  input: GerminatePlantsMutationInput,
): Promise<HostedCommand> {
  const body = buildGerminatePlantsRequest(input);
  const { data } = await hostedApi.POST("/api/breeding-logbook/plants:germinate", {
    body: bodyWithoutRequiredNullGridPosition(body),
    bodySerializer: () => JSON.stringify(body),
  });
  return hostedData(data, "POST /api/breeding-logbook/plants:germinate");
}

async function clonePlants(input: ClonePlantsMutationInput): Promise<HostedCommand> {
  const body = buildClonePlantsRequest(input);
  const { data } = await hostedApi.POST("/api/breeding-logbook/plants:clone", {
    body: bodyWithoutRequiredNullGridPosition(body),
    bodySerializer: () => JSON.stringify(body),
  });
  return hostedData(data, "POST /api/breeding-logbook/plants:clone");
}

async function bulkSexPlants(input: BulkSexMutationInput): Promise<HostedCommand> {
  const { data } = await hostedApi.POST("/api/breeding-logbook/plants:bulk-sex", {
    body: buildBulkSexRequest(input),
  });
  return hostedData(data, "POST /api/breeding-logbook/plants:bulk-sex");
}

async function bulkMovePlants(input: BulkMoveMutationInput): Promise<HostedCommand> {
  const body = buildBulkMoveRequest(input);
  const { data } = await hostedApi.POST("/api/breeding-logbook/plants:bulk-move", {
    body: bodyWithoutRequiredNullGridPosition(body),
    bodySerializer: () => JSON.stringify(body),
  });
  return hostedData(data, "POST /api/breeding-logbook/plants:bulk-move");
}

async function bulkCullPlants(input: BulkCullMutationInput): Promise<HostedCommand> {
  const { data } = await hostedApi.POST("/api/breeding-logbook/plants:bulk-cull", {
    body: buildBulkCullRequest(input),
  });
  return hostedData(data, "POST /api/breeding-logbook/plants:bulk-cull");
}

async function logPlantNote(input: LogNoteMutationInput): Promise<HostedCommand> {
  const { data } = await hostedApi.POST(
    "/api/breeding-logbook/plants/{plant_key}/notes",
    {
      params: { path: { plant_key: input.plantKey } },
      body: buildLogNoteRequest(input),
    },
  );
  return hostedData(data, "POST /api/breeding-logbook/plants/{plant_key}/notes");
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

function bodyWithoutRequiredNullGridPosition<TBody extends { grid_position: null }>(
  body: TBody,
): Omit<TBody, "grid_position"> {
  // openapi-fetch's writable-body helper strips null-only fields, so serialize
  // the exact generated-schema body while satisfying its call-site type.
  const { grid_position: _gridPosition, ...clientBody } = body;
  return clientBody;
}

function addPendingCommand(
  queryClient: QueryClient,
  input: Omit<BreedingLogbookPendingCommand, "commandId">,
): void {
  queryClient.setQueryData<readonly BreedingLogbookPendingCommand[]>(
    pendingCommandsQueryKey,
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

function updatePendingCommand(
  queryClient: QueryClient,
  commandId: string,
  command: HostedCommand,
): void {
  queryClient.setQueryData<readonly BreedingLogbookPendingCommand[]>(
    pendingCommandsQueryKey,
    (current = []) =>
      current.map((pending) =>
        pending.commandId === commandId ? { ...pending, command } : pending,
      ),
  );
}

function getPendingCommands(
  queryClient: QueryClient,
): readonly BreedingLogbookPendingCommand[] {
  return queryClient.getQueryData(pendingCommandsQueryKey) ?? [];
}

function scheduleProjectionRefresh(
  queryClient: QueryClient,
  plantKeys: readonly string[] = [],
): void {
  for (const delayMs of PROJECTION_REFRESH_DELAYS_MS) {
    platform.setTimeout(() => {
      invalidateBreedingLogbookReads(queryClient, plantKeys);
    }, delayMs);
  }
}

function shouldApplyOptimisticCommand(pending: BreedingLogbookPendingCommand): boolean {
  return !isFailedCommandStatus(pending.command.status);
}

function applyPlantPatch(plant: PlantRow, patch: PendingPlantPatch): PlantRow {
  return {
    ...plant,
    sexKey: patch.sexKey ?? plant.sexKey,
    stageKey: patch.stageKey ?? plant.stageKey,
    locationKey: patch.locationKey ?? plant.locationKey,
    locationLabel: patch.locationLabel ?? plant.locationLabel,
    culledOn: patch.culledOn !== undefined ? patch.culledOn : plant.culledOn,
    lastNote: patch.lastNote ?? plant.lastNote,
  };
}

function isPlantPatchProjected(plant: PlantRow, patch: PendingPlantPatch): boolean {
  if (patch.sexKey !== undefined && plant.sexKey !== patch.sexKey) return false;
  if (patch.stageKey !== undefined && plant.stageKey !== patch.stageKey) return false;
  if (patch.locationKey !== undefined && plant.locationKey !== patch.locationKey) {
    return false;
  }
  if (
    patch.locationLabel !== undefined &&
    plant.locationLabel !== patch.locationLabel
  ) {
    return false;
  }
  if (patch.culledOn !== undefined && plant.culledOn !== patch.culledOn) {
    return false;
  }
  if (patch.lastNote !== undefined && plant.lastNote.trim() !== patch.lastNote.trim()) {
    return false;
  }
  return true;
}

function isTerminalCommandStatus(status: string): boolean {
  return TERMINAL_COMMAND_STATUSES.has(status);
}

function isFailedCommandStatus(status: string): boolean {
  return status === "failed" || status === "rejected" || status === "expired";
}

function hasSyncedNote(events: readonly PlantJournalEvent[], body: string): boolean {
  const normalizedBody = body.trim();
  return events.some(
    (event) => event.tag === "note" && event.body.trim() === normalizedBody,
  );
}
