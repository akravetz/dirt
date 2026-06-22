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
import { invalidatePlantsReads } from "./plantsQueries";
import type {
  PlantJournalEvent,
  PlantRow,
  PlantSexKey,
  PlantStageKey,
} from "./plantsTypes";

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
type BreedingGerminatePlantsRequest =
  hostedComponents["schemas"]["BreedingGerminatePlantsRequest"];
type BreedingClonePlantsRequest =
  hostedComponents["schemas"]["BreedingClonePlantsRequest"];
type BreedingBulkSexRequest = hostedComponents["schemas"]["BreedingBulkSexRequest"];
type BreedingBulkMoveRequest = hostedComponents["schemas"]["BreedingBulkMoveRequest"];
type BreedingUpdatePlantFactsRequest =
  hostedComponents["schemas"]["BreedingUpdatePlantFactsRequest"];
type BreedingBulkCullRequest = hostedComponents["schemas"]["BreedingBulkCullRequest"];
type BreedingCreatePlantNoteRequest =
  hostedComponents["schemas"]["BreedingCreatePlantNoteRequest"];
type BreedingBulkPlantNoteRequest =
  hostedComponents["schemas"]["BreedingBulkPlantNoteRequest"];

type PendingOperation =
  | "germinate"
  | "clone"
  | "bulk-sex"
  | "bulk-move"
  | "update-facts"
  | "bulk-cull"
  | "note";

export type PlantsPendingCommand = {
  commandId: string;
  command: HostedCommand;
  operation: PendingOperation;
  label: string;
  affectedPlantKeys: readonly string[];
  optimisticPlantPatches: readonly PendingPlantPatch[];
  pendingNote: {
    plantKeys: readonly string[];
    body: string;
  } | null;
};

type PendingPlantPatch = {
  plantKey: string;
  sexKey?: PlantSexKey;
  stageKey?: PlantStageKey;
  currentTentId?: number;
  currentTentName?: string;
  gridPosition?: string | null;
  takenAt?: string | null;
  takenOn?: string | null;
  rootedAt?: string | null;
  rootedOn?: string | null;
  germinatedAt?: string | null;
  germinatedOn?: string | null;
  vegStartedAt?: string | null;
  vegStartedOn?: string | null;
  flowerStartedAt?: string | null;
  flowerStartedOn?: string | null;
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

type GerminatePlantsMutationInput = {
  idempotencyKey: string;
  seedLotId: string;
  count: number;
  sourceTentId: number;
  affectedLabel: string;
  germinatedAt: string;
};

type ClonePlantsMutationInput = {
  idempotencyKey: string;
  motherPlantKey: string;
  count: number;
  sourceTentId: number;
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
  sourceTentId: number;
  locationLabel: string;
};

type PlantFactUpdate =
  | { field: "sex_key"; value: PlantSexKey }
  | {
      field:
        | "germinated_at"
        | "taken_at"
        | "rooted_at"
        | "veg_started_at"
        | "flower_started_at";
      value: string | null;
    };

type UpdatePlantFactsMutationInput = {
  idempotencyKey: string;
  plantKeys: readonly string[];
  updates: readonly PlantFactUpdate[];
};

type BulkCullMutationInput = {
  idempotencyKey: string;
  plantKeys: readonly string[];
  reason: string;
};

type SingleLogNoteRequestInput = {
  idempotencyKey: string;
  plantKey: string;
  body: string;
};

type LogNoteMutationInput = {
  idempotencyKey: string;
  plantKeys: readonly string[];
  body: string;
};

export function createPlantsIdempotencyKey(operation: string): string {
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

export function buildGerminatePlantsRequest(
  input: GerminatePlantsMutationInput,
): BreedingGerminatePlantsRequest {
  return {
    idempotency_key: input.idempotencyKey,
    seed_lot_id: input.seedLotId,
    count: input.count,
    source_tent_id: input.sourceTentId,
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
    source_tent_id: input.sourceTentId,
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
    source_tent_id: input.sourceTentId,
    grid_position: null,
  };
}

export function buildUpdatePlantFactsRequest(
  input: UpdatePlantFactsMutationInput,
): BreedingUpdatePlantFactsRequest {
  return {
    idempotency_key: input.idempotencyKey,
    plant_keys: [...input.plantKeys],
    updates: input.updates.map((update) => ({
      field: update.field,
      value: update.value,
    })),
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
  input: SingleLogNoteRequestInput,
): BreedingCreatePlantNoteRequest {
  return {
    idempotency_key: input.idempotencyKey,
    body: input.body.trim(),
    observed_at: null,
  };
}

export function buildBulkLogNoteRequest(
  input: LogNoteMutationInput,
): BreedingBulkPlantNoteRequest {
  return {
    idempotency_key: input.idempotencyKey,
    plant_keys: [...input.plantKeys],
    body: input.body.trim(),
    observed_at: null,
  };
}

export function usePlantsPendingCommands(): readonly PlantsPendingCommand[] {
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
          currentTentId: input.sourceTentId,
          currentTentName: input.locationLabel,
          gridPosition: null,
        })),
        pendingNote: null,
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient, input.plantKeys);
      }
    },
  });
}

export function useUpdatePlantFactsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updatePlantFacts,
    onSuccess: (command, input) => {
      addPendingCommand(queryClient, {
        command,
        operation: "update-facts",
        label: `Updating facts on ${input.plantKeys.length} plants`,
        affectedPlantKeys: input.plantKeys,
        optimisticPlantPatches: plantFactUpdatesToPatches(
          input.plantKeys,
          input.updates,
        ),
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
        label:
          input.plantKeys.length === 1
            ? "Logging note"
            : `Logging note on ${input.plantKeys.length} plants`,
        affectedPlantKeys: input.plantKeys,
        optimisticPlantPatches: input.plantKeys.map((plantKey) => ({
          plantKey,
          lastNote: input.body.trim(),
        })),
        pendingNote: {
          plantKeys: input.plantKeys,
          body: input.body.trim(),
        },
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient, input.plantKeys);
      }
    },
  });
}

export function activePendingCommandsForPlant(
  pendingCommands: readonly PlantsPendingCommand[],
  plantKey: string,
): readonly PlantsPendingCommand[] {
  return pendingCommands.filter(
    (pending) =>
      pending.affectedPlantKeys.includes(plantKey) &&
      !isTerminalCommandStatus(pending.command.status),
  );
}

export function failedCommandsForPlant(
  pendingCommands: readonly PlantsPendingCommand[],
  plantKey: string,
): readonly PlantsPendingCommand[] {
  return pendingCommands.filter(
    (pending) =>
      pending.affectedPlantKeys.includes(plantKey) &&
      isFailedCommandStatus(pending.command.status),
  );
}

export function hasActivePendingForAnyPlant(
  pendingCommands: readonly PlantsPendingCommand[],
  plantKeys: readonly string[],
): boolean {
  return plantKeys.some(
    (plantKey) => activePendingCommandsForPlant(pendingCommands, plantKey).length > 0,
  );
}

export function pendingTimelineNotes(
  events: readonly PlantJournalEvent[],
  pendingCommands: readonly PlantsPendingCommand[],
  plantKey: string,
): readonly PendingTimelineNote[] {
  return pendingCommands.flatMap((pending) => {
    if (!pending.pendingNote?.plantKeys.includes(plantKey)) return [];
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
  pendingCommands: readonly PlantsPendingCommand[],
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
  pending: PlantsPendingCommand,
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
  if (!pending.pendingNote.plantKeys.includes(detailPlantKey)) return true;
  return hasSyncedNote(events, pending.pendingNote.body);
}

export function commandErrorText(pendingCommand: PlantsPendingCommand): string | null {
  if (!isFailedCommandStatus(pendingCommand.command.status)) return null;
  return (
    pendingCommand.command.error ||
    `${pendingCommand.label} ${pendingCommand.command.status}`
  );
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

async function updatePlantFacts(
  input: UpdatePlantFactsMutationInput,
): Promise<HostedCommand> {
  const { data } = await hostedApi.POST("/api/breeding-logbook/plants:update-facts", {
    body: buildUpdatePlantFactsRequest(input),
  });
  return hostedData(data, "POST /api/breeding-logbook/plants:update-facts");
}

async function bulkCullPlants(input: BulkCullMutationInput): Promise<HostedCommand> {
  const { data } = await hostedApi.POST("/api/breeding-logbook/plants:bulk-cull", {
    body: buildBulkCullRequest(input),
  });
  return hostedData(data, "POST /api/breeding-logbook/plants:bulk-cull");
}

async function logPlantNote(input: LogNoteMutationInput): Promise<HostedCommand> {
  const { data } = await hostedApi.POST("/api/breeding-logbook/plants:bulk-note", {
    body: buildBulkLogNoteRequest(input),
  });
  return hostedData(data, "POST /api/breeding-logbook/plants:bulk-note");
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
  input: Omit<PlantsPendingCommand, "commandId">,
): void {
  queryClient.setQueryData<readonly PlantsPendingCommand[]>(
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
  queryClient.setQueryData<readonly PlantsPendingCommand[]>(
    pendingCommandsQueryKey,
    (current = []) =>
      current.map((pending) =>
        pending.commandId === commandId ? { ...pending, command } : pending,
      ),
  );
}

function getPendingCommands(queryClient: QueryClient): readonly PlantsPendingCommand[] {
  return queryClient.getQueryData(pendingCommandsQueryKey) ?? [];
}

function scheduleProjectionRefresh(
  queryClient: QueryClient,
  plantKeys: readonly string[] = [],
): void {
  for (const delayMs of PROJECTION_REFRESH_DELAYS_MS) {
    platform.setTimeout(() => {
      invalidatePlantsReads(queryClient, plantKeys);
    }, delayMs);
  }
}

function shouldApplyOptimisticCommand(pending: PlantsPendingCommand): boolean {
  return !isFailedCommandStatus(pending.command.status);
}

function plantFactUpdatesToPatches(
  plantKeys: readonly string[],
  updates: readonly PlantFactUpdate[],
): readonly PendingPlantPatch[] {
  return plantKeys.map((plantKey) => {
    const patch: PendingPlantPatch = { plantKey };
    for (const update of updates) {
      if (update.field === "sex_key") {
        patch.sexKey = update.value;
      } else if (update.field === "germinated_at") {
        patch.germinatedAt = update.value;
        patch.germinatedOn = dateOnlyFromFactValue(update.value);
      } else if (update.field === "taken_at") {
        patch.takenAt = update.value;
        patch.takenOn = dateOnlyFromFactValue(update.value);
      } else if (update.field === "rooted_at") {
        patch.rootedAt = update.value;
        patch.rootedOn = dateOnlyFromFactValue(update.value);
      } else if (update.field === "veg_started_at") {
        patch.vegStartedAt = update.value;
        patch.vegStartedOn = dateOnlyFromFactValue(update.value);
      } else if (update.field === "flower_started_at") {
        patch.flowerStartedAt = update.value;
        patch.flowerStartedOn = dateOnlyFromFactValue(update.value);
      }
    }
    return patch;
  });
}

function dateOnlyFromFactValue(value: string | null): string | null {
  return value === null ? null : value.slice(0, 10);
}

function applyPlantPatch(plant: PlantRow, patch: PendingPlantPatch): PlantRow {
  return {
    ...plant,
    sexKey: patch.sexKey ?? plant.sexKey,
    stageKey: patch.stageKey ?? plant.stageKey,
    currentTentId: patch.currentTentId ?? plant.currentTentId,
    currentTentName: patch.currentTentName ?? plant.currentTentName,
    gridPosition:
      patch.gridPosition !== undefined ? patch.gridPosition : plant.gridPosition,
    takenAt: patch.takenAt !== undefined ? patch.takenAt : plant.takenAt,
    takenOn: patch.takenOn !== undefined ? patch.takenOn : plant.takenOn,
    rootedAt: patch.rootedAt !== undefined ? patch.rootedAt : plant.rootedAt,
    rootedOn: patch.rootedOn !== undefined ? patch.rootedOn : plant.rootedOn,
    germinatedAt:
      patch.germinatedAt !== undefined ? patch.germinatedAt : plant.germinatedAt,
    germinatedOn:
      patch.germinatedOn !== undefined ? patch.germinatedOn : plant.germinatedOn,
    vegStartedAt:
      patch.vegStartedAt !== undefined ? patch.vegStartedAt : plant.vegStartedAt,
    vegStartedOn:
      patch.vegStartedOn !== undefined ? patch.vegStartedOn : plant.vegStartedOn,
    flowerStartedAt:
      patch.flowerStartedAt !== undefined
        ? patch.flowerStartedAt
        : plant.flowerStartedAt,
    flowerStartedOn:
      patch.flowerStartedOn !== undefined
        ? patch.flowerStartedOn
        : plant.flowerStartedOn,
    culledOn: patch.culledOn !== undefined ? patch.culledOn : plant.culledOn,
    lastNote: patch.lastNote ?? plant.lastNote,
  };
}

function isPlantPatchProjected(plant: PlantRow, patch: PendingPlantPatch): boolean {
  if (patch.sexKey !== undefined && plant.sexKey !== patch.sexKey) return false;
  if (patch.stageKey !== undefined && plant.stageKey !== patch.stageKey) return false;
  if (
    patch.currentTentId !== undefined &&
    plant.currentTentId !== patch.currentTentId
  ) {
    return false;
  }
  if (
    patch.currentTentName !== undefined &&
    plant.currentTentName !== patch.currentTentName
  ) {
    return false;
  }
  if (patch.gridPosition !== undefined && plant.gridPosition !== patch.gridPosition) {
    return false;
  }
  if (patch.takenAt !== undefined && plant.takenAt !== patch.takenAt) {
    return false;
  }
  if (patch.takenOn !== undefined && plant.takenOn !== patch.takenOn) {
    return false;
  }
  if (patch.rootedAt !== undefined && plant.rootedAt !== patch.rootedAt) {
    return false;
  }
  if (patch.rootedOn !== undefined && plant.rootedOn !== patch.rootedOn) {
    return false;
  }
  if (patch.germinatedAt !== undefined && plant.germinatedAt !== patch.germinatedAt) {
    return false;
  }
  if (patch.germinatedOn !== undefined && plant.germinatedOn !== patch.germinatedOn) {
    return false;
  }
  if (patch.vegStartedAt !== undefined && plant.vegStartedAt !== patch.vegStartedAt) {
    return false;
  }
  if (patch.vegStartedOn !== undefined && plant.vegStartedOn !== patch.vegStartedOn) {
    return false;
  }
  if (
    patch.flowerStartedAt !== undefined &&
    plant.flowerStartedAt !== patch.flowerStartedAt
  ) {
    return false;
  }
  if (
    patch.flowerStartedOn !== undefined &&
    plant.flowerStartedOn !== patch.flowerStartedOn
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
