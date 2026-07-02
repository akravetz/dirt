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
  PlantSexTest,
  PlantSexTestResultSexKey,
  PlantStageKey,
} from "./plantsTypes";

const hostedApi = createHostedApiClient();
const pendingCommandsQueryKey = ["plants", "pending-commands"] as const;
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
type HostedPlantFactUpdate = hostedComponents["schemas"]["BreedingPlantFactUpdate"];
type BreedingBulkCullRequest = hostedComponents["schemas"]["BreedingBulkCullRequest"];
type BreedingCreatePlantNoteRequest =
  hostedComponents["schemas"]["BreedingCreatePlantNoteRequest"];
type BreedingBulkPlantNoteRequest =
  hostedComponents["schemas"]["BreedingBulkPlantNoteRequest"];
type BreedingBulkCreateSexTestsRequest =
  hostedComponents["schemas"]["BreedingBulkCreateSexTestsRequest"];
type BreedingUpdateSexTestRequest =
  hostedComponents["schemas"]["BreedingUpdateSexTestRequest"];
type BreedingBulkResultSexTestsRequest =
  hostedComponents["schemas"]["BreedingBulkResultSexTestsRequest"];

const PLANT_PATCH_FIELDS = [
  "sexKey",
  "currentTentId",
  "currentTentName",
  "gridPosition",
  "takenAt",
  "takenOn",
  "rootedAt",
  "rootedOn",
  "germinatedAt",
  "germinatedOn",
  "vegStartedAt",
  "vegStartedOn",
  "flowerStartedAt",
  "flowerStartedOn",
  "culledAt",
  "culledOn",
  "culledReason",
  "harvestedAt",
  "harvestedOn",
  "selectedForBreedingAt",
  "selectedForBreedingOn",
  "selectedForBreedingReason",
  "lastNote",
] as const satisfies readonly (keyof PlantRow)[];
const STAGE_FACT_PATCH_FIELDS = [
  "culledAt",
  "harvestedAt",
  "selectedForBreedingAt",
  "flowerStartedAt",
  "vegStartedAt",
] as const satisfies readonly (keyof PlantRow)[];

type PendingOperation =
  | "germinate"
  | "clone"
  | "bulk-sex"
  | "bulk-move"
  | "update-facts"
  | "bulk-cull"
  | "note"
  | "sex-test-bulk-create"
  | "sex-test-update"
  | "sex-test-bulk-result";

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

type PlantPatchField = (typeof PLANT_PATCH_FIELDS)[number];
type PendingPlantPatch = {
  plantKey: PlantRow["key"];
  sexTestPatches?: readonly PendingSexTestPatch[];
} & {
  [TKey in PlantPatchField]?: PlantRow[TKey];
};
type PendingSexTestPatch = Partial<PlantSexTest> & {
  optimisticId?: string;
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

type PlantFactField = HostedPlantFactUpdate["field"];
type TextPlantFactField = Extract<
  PlantFactField,
  "culled_reason" | "selected_for_breeding_reason"
>;
type DatePlantFactField = Exclude<PlantFactField, "sex_key" | TextPlantFactField>;
type DateFactPatchTimestampField =
  | "germinatedAt"
  | "takenAt"
  | "rootedAt"
  | "vegStartedAt"
  | "flowerStartedAt"
  | "culledAt"
  | "harvestedAt"
  | "selectedForBreedingAt";
type DateFactPatchDateOnlyField =
  | "germinatedOn"
  | "takenOn"
  | "rootedOn"
  | "vegStartedOn"
  | "flowerStartedOn"
  | "culledOn"
  | "harvestedOn"
  | "selectedForBreedingOn";
type TextFactPatchField = "culledReason" | "selectedForBreedingReason";
type DatePlantFactUpdate = { field: DatePlantFactField; value: string | null };
type TextPlantFactUpdate = { field: TextPlantFactField; value: string | null };
export type PlantFactUpdate =
  | { field: "sex_key"; value: PlantSexKey }
  | DatePlantFactUpdate
  | TextPlantFactUpdate;

const DATE_FACT_PATCH_FIELDS = {
  germinated_at: {
    timestampField: "germinatedAt",
    dateOnlyField: "germinatedOn",
  },
  taken_at: {
    timestampField: "takenAt",
    dateOnlyField: "takenOn",
  },
  rooted_at: {
    timestampField: "rootedAt",
    dateOnlyField: "rootedOn",
  },
  veg_started_at: {
    timestampField: "vegStartedAt",
    dateOnlyField: "vegStartedOn",
  },
  flower_started_at: {
    timestampField: "flowerStartedAt",
    dateOnlyField: "flowerStartedOn",
  },
  culled_at: {
    timestampField: "culledAt",
    dateOnlyField: "culledOn",
  },
  harvested_at: {
    timestampField: "harvestedAt",
    dateOnlyField: "harvestedOn",
  },
  selected_for_breeding_at: {
    timestampField: "selectedForBreedingAt",
    dateOnlyField: "selectedForBreedingOn",
  },
} as const satisfies Record<
  DatePlantFactField,
  {
    timestampField: DateFactPatchTimestampField;
    dateOnlyField: DateFactPatchDateOnlyField;
  }
>;
const TEXT_FACT_PATCH_FIELDS = {
  culled_reason: "culledReason",
  selected_for_breeding_reason: "selectedForBreedingReason",
} as const satisfies Record<TextPlantFactField, TextFactPatchField>;

type UpdatePlantFactsMutationInput = {
  idempotencyKey: string;
  plantKeys: readonly string[];
  updates: readonly PlantFactUpdate[];
};

type BulkCullMutationInput = {
  idempotencyKey: string;
  plantKeys: readonly string[];
  reason: string;
  culledAt: string;
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

export type SexTestResultSexKey = PlantSexTestResultSexKey;

export type BulkCreateSexTestInput = {
  plantKey: string;
  vendorTestCode: string;
  notes: string | null;
};

export type BulkCreateSexTestsMutationInput = {
  idempotencyKey: string;
  vendorName: string;
  assayName: string | null;
  sampleCollectedAt: string;
  sampleSentAt: string | null;
  tests: readonly BulkCreateSexTestInput[];
};

export type UpdateSexTestMutationInput = {
  idempotencyKey: string;
  plantKey: string;
  sexTestId: string;
  sexTestSourceId: number;
  vendorName: string;
  assayName: string | null;
  vendorTestCode: string;
  sampleCollectedAt: string;
  sampleSentAt: string | null;
  resultReceivedAt: string | null;
  resultSexKey: SexTestResultSexKey | null;
  isInconclusive: boolean;
  notes: string | null;
};

export type BulkResultSexTestInput = {
  plantKey: string;
  sexTestSourceId: number;
  resultSexKey: SexTestResultSexKey | null;
  isInconclusive: boolean;
};

export type BulkResultSexTestsMutationInput = {
  idempotencyKey: string;
  resultReceivedAt: string;
  results: readonly BulkResultSexTestInput[];
};

export function createPlantsIdempotencyKey(operation: string): string {
  const random =
    typeof crypto === "undefined" || crypto.randomUUID === undefined
      ? Math.random().toString(36).slice(2)
      : crypto.randomUUID();
  return `plants:${operation}:${Date.now()}:${random}`;
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
    culled_at: input.culledAt,
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

export function buildBulkCreateSexTestsRequest(
  input: BulkCreateSexTestsMutationInput,
): BreedingBulkCreateSexTestsRequest {
  return {
    idempotency_key: input.idempotencyKey,
    vendor_name: input.vendorName.trim(),
    assay_name: trimNullableText(input.assayName),
    sample_collected_at: input.sampleCollectedAt,
    sample_sent_at: input.sampleSentAt,
    tests: input.tests.map((test) => ({
      plant_key: test.plantKey,
      vendor_test_code: test.vendorTestCode.trim(),
      notes: trimNullableText(test.notes),
    })),
  };
}

export function buildUpdateSexTestRequest(
  input: UpdateSexTestMutationInput,
): BreedingUpdateSexTestRequest {
  return {
    idempotency_key: input.idempotencyKey,
    sex_test_source_id: input.sexTestSourceId,
    vendor_name: input.vendorName.trim(),
    assay_name: trimNullableText(input.assayName),
    vendor_test_code: input.vendorTestCode.trim(),
    sample_collected_at: input.sampleCollectedAt,
    sample_sent_at: input.sampleSentAt,
    result_received_at: input.resultReceivedAt,
    result_sex_key: input.resultSexKey,
    is_inconclusive: input.isInconclusive,
    notes: trimNullableText(input.notes),
  };
}

export function buildBulkResultSexTestsRequest(
  input: BulkResultSexTestsMutationInput,
): BreedingBulkResultSexTestsRequest {
  return {
    idempotency_key: input.idempotencyKey,
    result_received_at: input.resultReceivedAt,
    results: input.results.map((result) => ({
      sex_test_source_id: result.sexTestSourceId,
      result_sex_key: result.resultSexKey,
      is_inconclusive: result.isInconclusive,
    })),
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
      queryKey: ["plants", "commands", pending.commandId],
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
        optimisticPlantPatches: plantFactUpdatesToPatches(input.plantKeys, [
          { field: "culled_at", value: input.culledAt },
          { field: "culled_reason", value: input.reason.trim() },
        ]),
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

export function useBulkCreateSexTestsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: bulkCreateSexTests,
    onSuccess: (command, input) => {
      const plantKeys = input.tests.map((test) => test.plantKey);
      addPendingCommand(queryClient, {
        command,
        operation: "sex-test-bulk-create",
        label: `Creating ${input.tests.length} sex tests`,
        affectedPlantKeys: plantKeys,
        optimisticPlantPatches: bulkCreateSexTestsToPatches(input),
        pendingNote: null,
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient, plantKeys);
      }
    },
  });
}

export function useUpdateSexTestMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateSexTest,
    onSuccess: (command, input) => {
      addPendingCommand(queryClient, {
        command,
        operation: "sex-test-update",
        label: `Updating sex test ${input.sexTestSourceId}`,
        affectedPlantKeys: [input.plantKey],
        optimisticPlantPatches: [updateSexTestToPatch(input)],
        pendingNote: null,
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient, [input.plantKey]);
      }
    },
  });
}

export function useBulkResultSexTestsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: bulkResultSexTests,
    onSuccess: (command, input) => {
      const plantKeys = input.results.map((result) => result.plantKey);
      addPendingCommand(queryClient, {
        command,
        operation: "sex-test-bulk-result",
        label: `Recording ${input.results.length} sex test results`,
        affectedPlantKeys: plantKeys,
        optimisticPlantPatches: bulkResultSexTestsToPatches(input),
        pendingNote: null,
      });
      if (command.status === "succeeded") {
        scheduleProjectionRefresh(queryClient, plantKeys);
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

async function bulkCreateSexTests(
  input: BulkCreateSexTestsMutationInput,
): Promise<HostedCommand> {
  const { data } = await hostedApi.POST("/api/breeding-logbook/sex-tests:bulk-create", {
    body: buildBulkCreateSexTestsRequest(input),
  });
  return hostedData(data, "POST /api/breeding-logbook/sex-tests:bulk-create");
}

async function updateSexTest(
  input: UpdateSexTestMutationInput,
): Promise<HostedCommand> {
  const { data } = await hostedApi.POST(
    "/api/breeding-logbook/sex-tests/{sex_test_id}:update",
    {
      params: { path: { sex_test_id: input.sexTestId } },
      body: buildUpdateSexTestRequest(input),
    },
  );
  return hostedData(data, "POST /api/breeding-logbook/sex-tests/{sex_test_id}:update");
}

async function bulkResultSexTests(
  input: BulkResultSexTestsMutationInput,
): Promise<HostedCommand> {
  const { data } = await hostedApi.POST("/api/breeding-logbook/sex-tests:bulk-result", {
    body: buildBulkResultSexTestsRequest(input),
  });
  return hostedData(data, "POST /api/breeding-logbook/sex-tests:bulk-result");
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
      applyPlantFactUpdateToPatch(patch, update);
    }
    return patch;
  });
}

function bulkCreateSexTestsToPatches(
  input: BulkCreateSexTestsMutationInput,
): readonly PendingPlantPatch[] {
  const body = buildBulkCreateSexTestsRequest(input);
  return body.tests.map((test) => ({
    plantKey: test.plant_key,
    sexTestPatches: [
      {
        optimisticId: pendingSexTestId(body.idempotency_key, test.plant_key),
        vendorName: body.vendor_name,
        assayName: body.assay_name,
        vendorTestCode: test.vendor_test_code,
        sampleCollectedAt: body.sample_collected_at,
        sampleSentAt: body.sample_sent_at,
        resultReceivedAt: null,
        resultSexKey: null,
        isInconclusive: false,
        notes: test.notes ?? null,
      },
    ],
  }));
}

function updateSexTestToPatch(input: UpdateSexTestMutationInput): PendingPlantPatch {
  const body = buildUpdateSexTestRequest(input);
  const patch: PendingPlantPatch = {
    plantKey: input.plantKey,
    sexTestPatches: [
      {
        id: input.sexTestId,
        sourceSexTestId: body.sex_test_source_id,
        vendorName: body.vendor_name,
        assayName: body.assay_name,
        vendorTestCode: body.vendor_test_code,
        sampleCollectedAt: body.sample_collected_at,
        sampleSentAt: body.sample_sent_at,
        resultReceivedAt: body.result_received_at,
        resultSexKey: body.result_sex_key,
        isInconclusive: body.is_inconclusive,
        notes: body.notes,
      },
    ],
  };
  const sexKey = conclusiveSexKeyFromResult(
    body.result_received_at,
    body.result_sex_key,
    body.is_inconclusive,
  );
  if (sexKey !== undefined) {
    patch.sexKey = sexKey;
  }
  return patch;
}

function bulkResultSexTestsToPatches(
  input: BulkResultSexTestsMutationInput,
): readonly PendingPlantPatch[] {
  const body = buildBulkResultSexTestsRequest(input);
  return input.results.map((result) => {
    const patch: PendingPlantPatch = {
      plantKey: result.plantKey,
      sexTestPatches: [
        {
          sourceSexTestId: result.sexTestSourceId,
          resultReceivedAt: body.result_received_at,
          resultSexKey: result.resultSexKey,
          isInconclusive: result.isInconclusive,
        },
      ],
    };
    const sexKey = conclusiveSexKeyFromResult(
      body.result_received_at,
      result.resultSexKey,
      result.isInconclusive,
    );
    if (sexKey !== undefined) {
      patch.sexKey = sexKey;
    }
    return patch;
  });
}

function applyPlantFactUpdateToPatch(
  patch: PendingPlantPatch,
  update: PlantFactUpdate,
): void {
  if (update.field === "sex_key") {
    assignPatchValue(patch, "sexKey", update.value);
    return;
  }
  if (isDatePlantFactField(update.field)) {
    const fields = DATE_FACT_PATCH_FIELDS[update.field];
    assignPatchValue(patch, fields.timestampField, update.value);
    assignPatchValue(patch, fields.dateOnlyField, dateOnlyFromFactValue(update.value));
    return;
  }
  assignPatchValue(patch, TEXT_FACT_PATCH_FIELDS[update.field], update.value);
}

function assignPatchValue<TKey extends PlantPatchField>(
  patch: PendingPlantPatch,
  field: TKey,
  value: PlantRow[TKey],
): void {
  Object.assign(patch, { [field]: value });
}

function isDatePlantFactField(field: PlantFactField): field is DatePlantFactField {
  return field in DATE_FACT_PATCH_FIELDS;
}

function dateOnlyFromFactValue(value: string | null): string | null {
  return value === null ? null : value.slice(0, 10);
}

function applyPlantPatch(plant: PlantRow, patch: PendingPlantPatch): PlantRow {
  const next = {
    ...plant,
    ...definedPlantPatchValues(patch),
    sexTests:
      patch.sexTestPatches === undefined
        ? plant.sexTests
        : applySexTestPatches(plant, patch.sexTestPatches),
  };
  if (patchAffectsStage(patch)) {
    next.stageKey = plantStageKeyFromFacts(next);
  }
  return next;
}

function definedPlantPatchValues(
  patch: PendingPlantPatch,
): Partial<Pick<PlantRow, PlantPatchField>> {
  const values: Partial<Pick<PlantRow, PlantPatchField>> = {};
  for (const field of PLANT_PATCH_FIELDS) {
    const value = patch[field];
    if (value !== undefined) {
      Object.assign(values, { [field]: value });
    }
  }
  return values;
}

function patchAffectsStage(patch: PendingPlantPatch): boolean {
  return STAGE_FACT_PATCH_FIELDS.some((field) => patch[field] !== undefined);
}

function plantStageKeyFromFacts(plant: PlantRow): PlantStageKey {
  if (plant.culledAt !== null) return "culled";
  if (plant.harvestedAt !== null) return "harvested";
  if (plant.selectedForBreedingAt !== null) return "breeding";
  if (plant.flowerStartedAt !== null) return "flower";
  if (plant.vegStartedAt !== null) return "veg";
  return "germinating";
}

function isPlantPatchProjected(plant: PlantRow, patch: PendingPlantPatch): boolean {
  if (patch.lastNote !== undefined && plant.lastNote.trim() !== patch.lastNote.trim()) {
    return false;
  }
  for (const field of PLANT_PATCH_FIELDS) {
    if (field === "lastNote") continue;
    if (!isPatchFieldProjected(plant, patch, field)) return false;
  }
  return areSexTestPatchesProjected(plant, patch.sexTestPatches ?? []);
}

function isPatchFieldProjected<TKey extends PlantPatchField>(
  plant: PlantRow,
  patch: PendingPlantPatch,
  field: TKey,
): boolean {
  const expected = patch[field];
  return expected === undefined || Object.is(plant[field], expected);
}

function applySexTestPatches(
  plant: PlantRow,
  patches: readonly PendingSexTestPatch[],
): readonly PlantSexTest[] {
  return patches.reduce(
    (sexTests, patch) => applySexTestPatch(plant, sexTests, patch),
    plant.sexTests,
  );
}

function applySexTestPatch(
  plant: PlantRow,
  sexTests: readonly PlantSexTest[],
  patch: PendingSexTestPatch,
): readonly PlantSexTest[] {
  const index = findSexTestPatchIndex(sexTests, patch);
  if (index === -1) {
    const sexTest = plantSexTestFromPatch(plant, patch);
    return sexTest === null ? sexTests : [sexTest, ...sexTests];
  }
  return sexTests.map((sexTest, sexTestIndex) =>
    sexTestIndex === index ? mergeSexTestPatch(sexTest, patch) : sexTest,
  );
}

function plantSexTestFromPatch(
  plant: PlantRow,
  patch: PendingSexTestPatch,
): PlantSexTest | null {
  if (
    patch.vendorName === undefined ||
    patch.vendorTestCode === undefined ||
    patch.sampleCollectedAt === undefined
  ) {
    return null;
  }
  return {
    id:
      patch.id ??
      patch.optimisticId ??
      pendingSexTestId("sex-test", `${patch.vendorName}:${patch.vendorTestCode}`),
    sourceSexTestId: patch.sourceSexTestId ?? pendingSourceSexTestId(patch),
    sourcePlantId: patch.sourcePlantId ?? sourcePlantIdFromPlant(plant),
    vendorName: patch.vendorName,
    assayName: patch.assayName ?? null,
    vendorTestCode: patch.vendorTestCode,
    sampleCollectedAt: patch.sampleCollectedAt,
    sampleSentAt: patch.sampleSentAt ?? null,
    resultReceivedAt: patch.resultReceivedAt ?? null,
    resultSexKey: patch.resultSexKey ?? null,
    isInconclusive: patch.isInconclusive ?? false,
    notes: patch.notes ?? null,
  };
}

function mergeSexTestPatch(
  sexTest: PlantSexTest,
  patch: PendingSexTestPatch,
): PlantSexTest {
  return {
    id: patch.id ?? sexTest.id,
    sourceSexTestId: patch.sourceSexTestId ?? sexTest.sourceSexTestId,
    sourcePlantId: patch.sourcePlantId ?? sexTest.sourcePlantId,
    vendorName: patch.vendorName ?? sexTest.vendorName,
    assayName: patch.assayName === undefined ? sexTest.assayName : patch.assayName,
    vendorTestCode: patch.vendorTestCode ?? sexTest.vendorTestCode,
    sampleCollectedAt: patch.sampleCollectedAt ?? sexTest.sampleCollectedAt,
    sampleSentAt:
      patch.sampleSentAt === undefined ? sexTest.sampleSentAt : patch.sampleSentAt,
    resultReceivedAt:
      patch.resultReceivedAt === undefined
        ? sexTest.resultReceivedAt
        : patch.resultReceivedAt,
    resultSexKey:
      patch.resultSexKey === undefined ? sexTest.resultSexKey : patch.resultSexKey,
    isInconclusive: patch.isInconclusive ?? sexTest.isInconclusive,
    notes: patch.notes === undefined ? sexTest.notes : patch.notes,
  };
}

function areSexTestPatchesProjected(
  plant: PlantRow,
  patches: readonly PendingSexTestPatch[],
): boolean {
  return patches.every((patch) => {
    const sexTest = findMatchingSexTest(plant.sexTests, patch);
    return sexTest !== undefined && isSexTestPatchProjected(sexTest, patch);
  });
}

function isSexTestPatchProjected(
  sexTest: PlantSexTest,
  patch: PendingSexTestPatch,
): boolean {
  if (patch.sourceSexTestId === undefined) {
    return (
      sexTestPatchMatchesCreatedIdentity(sexTest, patch) &&
      allSexTestPatchValuesProjected(sexTest, patch)
    );
  }
  return allSexTestPatchValuesProjected(sexTest, patch);
}

function allSexTestPatchValuesProjected(
  sexTest: PlantSexTest,
  patch: PendingSexTestPatch,
): boolean {
  return SEX_TEST_PATCH_FIELDS.every((field) =>
    sexTestPatchValueProjected(sexTest, patch, field),
  );
}

const SEX_TEST_PATCH_FIELDS = [
  "vendorName",
  "assayName",
  "vendorTestCode",
  "sampleCollectedAt",
  "sampleSentAt",
  "resultReceivedAt",
  "resultSexKey",
  "isInconclusive",
  "notes",
] as const satisfies readonly (keyof PlantSexTest)[];

function sexTestPatchMatchesCreatedIdentity(
  sexTest: PlantSexTest,
  patch: PendingSexTestPatch,
): boolean {
  return (
    sexTestPatchValueProjected(sexTest, patch, "vendorName") &&
    sexTestPatchValueProjected(sexTest, patch, "vendorTestCode")
  );
}

function sexTestPatchValueProjected<TKey extends keyof PlantSexTest>(
  sexTest: PlantSexTest,
  patch: PendingSexTestPatch,
  field: TKey,
): boolean {
  const expected = patch[field];
  return expected === undefined || Object.is(sexTest[field], expected);
}

function findSexTestPatchIndex(
  sexTests: readonly PlantSexTest[],
  patch: PendingSexTestPatch,
): number {
  return sexTests.findIndex((sexTest) => sexTestsMatchPatch(sexTest, patch));
}

function findMatchingSexTest(
  sexTests: readonly PlantSexTest[],
  patch: PendingSexTestPatch,
): PlantSexTest | undefined {
  return sexTests.find((sexTest) => sexTestsMatchPatch(sexTest, patch));
}

function sexTestsMatchPatch(
  sexTest: PlantSexTest,
  patch: PendingSexTestPatch,
): boolean {
  if (patch.sourceSexTestId !== undefined) {
    return sexTest.sourceSexTestId === patch.sourceSexTestId;
  }
  if (patch.vendorName === undefined || patch.vendorTestCode === undefined) {
    return false;
  }
  return (
    normalizedSexTestIdentity(sexTest.vendorName) ===
      normalizedSexTestIdentity(patch.vendorName) &&
    normalizedSexTestIdentity(sexTest.vendorTestCode) ===
      normalizedSexTestIdentity(patch.vendorTestCode)
  );
}

function normalizedSexTestIdentity(value: string): string {
  return value.trim();
}

function pendingSexTestId(idempotencyKey: string, plantKey: string): string {
  return `pending:${idempotencyKey}:${plantKey}`;
}

function pendingSourceSexTestId(patch: PendingSexTestPatch): number {
  const identity = `${patch.vendorName ?? ""}:${patch.vendorTestCode ?? ""}`;
  let hash = 0;
  for (const character of identity) {
    hash = (hash * 31 + character.charCodeAt(0)) | 0;
  }
  return hash === 0 ? -1 : -Math.abs(hash);
}

function sourcePlantIdFromPlant(plant: PlantRow): number {
  const value = Number.parseInt(plant.id, 10);
  return Number.isNaN(value) ? 0 : value;
}

function conclusiveSexKeyFromResult(
  resultReceivedAt: string | null,
  resultSexKey: SexTestResultSexKey | null,
  isInconclusive: boolean,
): SexTestResultSexKey | undefined {
  if (resultReceivedAt === null || resultSexKey === null || isInconclusive) {
    return undefined;
  }
  return resultSexKey;
}

function trimNullableText(value: string | null): string | null {
  if (value === null) return null;
  const trimmed = value.trim();
  return trimmed.length === 0 ? null : trimmed;
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
