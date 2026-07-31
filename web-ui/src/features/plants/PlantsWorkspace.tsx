import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { platform } from "@/shared/platform";
import type { SeedLotSummary } from "@/shared/seedLots";
import { MarkdownDocument } from "@/ui/MarkdownDocument";
import { Sparkline } from "@/ui/Sparkline";
import {
  activePendingCommandsForPlant,
  applyPendingPlantCommands,
  type BulkCreateSexTestsMutationInput,
  type BulkResultSexTestsMutationInput,
  canSubmitBulkCull,
  commandErrorText,
  createPlantsIdempotencyKey,
  failedCommandsForPlant,
  hasActivePendingForAnyPlant,
  isPendingCommandProjected,
  type PendingTimelineNote,
  type PlantFactUpdate,
  type PlantsPendingCommand,
  pendingTimelineNotes,
  readonlyPlantPrefixPreview,
  removeProjectedPendingCommands,
  type SexTestResultSexKey,
  type UpdateSexTestMutationInput,
  useBulkCreateSexTestsMutation,
  useBulkCullMutation,
  useBulkMoveMutation,
  useBulkResultSexTestsMutation,
  useBulkSexMutation,
  useClonePlantsMutation,
  useGerminatePlantsMutation,
  useLogPlantNoteMutation,
  usePlantsPendingCommands,
  useUpdatePlantFactsMutation,
  useUpdateSexTestMutation,
} from "./plantsMutations";
import { invalidatePlantsReads, usePlantsQueries } from "./plantsQueries";
import type {
  BulkPanel,
  LocationOption,
  PlantDetail,
  PlantGroupBy,
  PlantJournalEvent,
  PlantListLayout,
  PlantMetricHistory,
  PlantRow,
  PlantSexKey,
  PlantSexTest,
  PlantStageKey,
  PlantsBootstrap,
} from "./plantsTypes";

type AddPlantMode = "germinate" | "clone";
type BulkDateField = Extract<
  PlantFactUpdate["field"],
  "germinated_at" | "taken_at" | "veg_started_at" | "flower_started_at"
>;
type DetailDateFactField = Extract<
  PlantFactUpdate["field"],
  | "germinated_at"
  | "taken_at"
  | "rooted_at"
  | "veg_started_at"
  | "flower_started_at"
  | "culled_at"
  | "harvested_at"
  | "selected_for_breeding_at"
>;
type DetailTextFactField = Extract<
  PlantFactUpdate["field"],
  "culled_reason" | "selected_for_breeding_reason"
>;
type DetailFactsDraft = {
  sexKey: PlantSexKey;
  germinatedAt: string;
  takenAt: string;
  rootedAt: string;
  vegStartedAt: string;
  flowerStartedAt: string;
  culledAt: string;
  culledReason: string;
  harvestedAt: string;
  selectedForBreedingAt: string;
  selectedForBreedingReason: string;
};
type DetailFactsDraftDateKey =
  | "germinatedAt"
  | "takenAt"
  | "rootedAt"
  | "vegStartedAt"
  | "flowerStartedAt"
  | "culledAt"
  | "harvestedAt"
  | "selectedForBreedingAt";
type DetailFactsDraftTextKey = "culledReason" | "selectedForBreedingReason";
type DetailFactUpdate = PlantFactUpdate;

type TableGroup = {
  key: string;
  label: string;
  stageKey: PlantStageKey;
  plants: readonly PlantRow[];
};

type PlantTableSortKey =
  | "plant"
  | "generation"
  | "parents"
  | "sex"
  | "days"
  | "germinated"
  | "veg"
  | "flower"
  | "sexTest"
  | "lastNote";
type PlantTableSortDirection = "asc" | "desc";
type PlantTableSortState = {
  key: PlantTableSortKey;
  direction: PlantTableSortDirection;
} | null;

type PlantVisibilityFilter = "active" | "all" | "culled" | "harvested";
type PlantLifecycleStatusFilter = "all" | "started" | "veg" | "flower";
type PlantSexTestStateFilter =
  | "all"
  | "untested"
  | "pending"
  | "resulted"
  | "inconclusive";
type PlantsSearchState = {
  groupBy?: PlantGroupBy;
  layout?: PlantListLayout;
  parent?: string;
  q?: string;
  sexTest?: PlantSexTestStateFilter;
  status?: PlantLifecycleStatusFilter;
  strain?: string;
  visibility?: PlantVisibilityFilter;
};
type SexTestConclusiveResult = SexTestResultSexKey;
type SexTestResultOption = SexTestConclusiveResult | "inconclusive";
type SexTestResultDraftValue = SexTestResultOption | "";
type CreateSexTestsInput = BulkCreateSexTestsMutationInput;
type UpdateSexTestInput = UpdateSexTestMutationInput;
type ResultSexTestsInput = BulkResultSexTestsMutationInput;
type SexTestMutationSubmit<TInput> = (input: TInput, onSuccess: () => void) => void;

const EMPTY_SELECTION = new Set<string>();
const FALLBACK_LOCATION: LocationOption = {
  sourceTentId: 1,
  displayName: "Veg tent",
  role: "veg",
};
const CULLED_LOCATION: LocationOption = {
  sourceTentId: 0,
  displayName: "Removed",
  role: "culled",
};
const DATETIME_LOCAL_LENGTH = 16;
const BULK_DATE_FIELDS = [
  "germinated_at",
  "taken_at",
  "veg_started_at",
  "flower_started_at",
] as const satisfies readonly BulkDateField[];
const BULK_DATE_FIELD_COPY = {
  germinated_at: {
    actionLabel: "germ",
    fieldLabel: "Germinated at",
    optionLabel: "Germinated",
  },
  taken_at: {
    actionLabel: "taken",
    fieldLabel: "Taken at",
    optionLabel: "Taken",
  },
  veg_started_at: {
    actionLabel: "veg",
    fieldLabel: "Veg started at",
    optionLabel: "Veg start",
  },
  flower_started_at: {
    actionLabel: "flower",
    fieldLabel: "Flower started at",
    optionLabel: "Flower start",
  },
} as const satisfies Record<
  BulkDateField,
  { actionLabel: string; fieldLabel: string; optionLabel: string }
>;
const BULK_DATE_FIELD_OPTIONS = BULK_DATE_FIELDS.map((value) => ({
  label: BULK_DATE_FIELD_COPY[value].optionLabel,
  value,
})) satisfies readonly { label: string; value: BulkDateField }[];
const EMPTY_DETAIL_FACTS_DRAFT: DetailFactsDraft = {
  sexKey: "unknown",
  germinatedAt: "",
  takenAt: "",
  rootedAt: "",
  vegStartedAt: "",
  flowerStartedAt: "",
  culledAt: "",
  culledReason: "",
  harvestedAt: "",
  selectedForBreedingAt: "",
  selectedForBreedingReason: "",
};
const COMMON_DETAIL_DATE_DRAFT_FIELDS = [
  "vegStartedAt",
  "flowerStartedAt",
  "culledAt",
  "harvestedAt",
  "selectedForBreedingAt",
] as const satisfies readonly DetailFactsDraftDateKey[];
const CLONE_DETAIL_DATE_DRAFT_FIELDS = [
  "takenAt",
  "rootedAt",
  ...COMMON_DETAIL_DATE_DRAFT_FIELDS,
] as const satisfies readonly DetailFactsDraftDateKey[];
const SEED_DETAIL_DATE_DRAFT_FIELDS = [
  "germinatedAt",
  ...COMMON_DETAIL_DATE_DRAFT_FIELDS,
] as const satisfies readonly DetailFactsDraftDateKey[];
const DETAIL_DATE_FACT_FIELD_BY_DRAFT_KEY = {
  germinatedAt: "germinated_at",
  takenAt: "taken_at",
  rootedAt: "rooted_at",
  vegStartedAt: "veg_started_at",
  flowerStartedAt: "flower_started_at",
  culledAt: "culled_at",
  harvestedAt: "harvested_at",
  selectedForBreedingAt: "selected_for_breeding_at",
} as const satisfies Record<DetailFactsDraftDateKey, DetailDateFactField>;
const DETAIL_TEXT_DRAFT_FIELDS = [
  "culledReason",
  "selectedForBreedingReason",
] as const satisfies readonly DetailFactsDraftTextKey[];
const DETAIL_TEXT_FACT_FIELD_BY_DRAFT_KEY = {
  culledReason: "culled_reason",
  selectedForBreedingReason: "selected_for_breeding_reason",
} as const satisfies Record<DetailFactsDraftTextKey, DetailTextFactField>;
const DETAIL_TEXT_OWNER_DATE_DRAFT_KEY = {
  culledReason: "culledAt",
  selectedForBreedingReason: "selectedForBreedingAt",
} as const satisfies Record<DetailFactsDraftTextKey, DetailFactsDraftDateKey>;
const PLANT_LIST_LAYOUT_VALUES = ["table", "board"] as const;
const PLANT_GROUP_BY_VALUES = ["stage", "parents"] as const;
const PLANT_LIFECYCLE_STATUS_VALUES = ["all", "started", "veg", "flower"] as const;
const PLANT_SEX_TEST_STATE_VALUES = [
  "all",
  "untested",
  "pending",
  "resulted",
  "inconclusive",
] as const;
const PLANT_VISIBILITY_VALUES = ["active", "all", "culled", "harvested"] as const;
const DEFAULT_PLANTS_SEARCH = {
  groupBy: "stage",
  layout: "table",
  parent: "all",
  q: "",
  sexTest: "all",
  status: "all",
  strain: "all",
  visibility: "active",
} as const satisfies Required<PlantsSearchState>;
const PLANT_FILTER_COLLATOR = new Intl.Collator("en", { sensitivity: "base" });
const PLANT_TABLE_SORT_COLLATOR = new Intl.Collator("en", {
  numeric: true,
  sensitivity: "base",
});
const DEFAULT_SEX_TEST_VENDOR = "Farmer Freeman";
const DEFAULT_SEX_TEST_ASSAY = "EZ-XY";
const PLANT_TABLE_GRID_CLASS =
  "grid grid-cols-[36px_150px_42px_168px_40px_64px_72px_72px_72px_92px_minmax(150px,1fr)]";
const PLANT_TABLE_SORT_COLUMNS = [
  { key: "plant", label: "Plant" },
  { key: "generation", label: "Gen" },
  { key: "parents", label: "Parents" },
  { key: "sex", label: "Sex" },
  { key: "days", label: "Days" },
  { key: "germinated", label: "Germ" },
  { key: "veg", label: "Veg" },
  { key: "flower", label: "Flwr" },
  { key: "sexTest", label: "Test" },
  { key: "lastNote", label: "Last note" },
] as const satisfies readonly { key: PlantTableSortKey; label: string }[];

type PlantsPageView = "plants" | "add-plants" | "detail";
type PlantsPageMode = "list" | "new-plant" | "detail";

export function validatePlantsSearch(
  search: Record<string, unknown>,
): PlantsSearchState {
  return {
    groupBy: parseSearchEnum(
      search.groupBy,
      PLANT_GROUP_BY_VALUES,
      DEFAULT_PLANTS_SEARCH.groupBy,
    ),
    layout: parseSearchEnum(
      search.layout,
      PLANT_LIST_LAYOUT_VALUES,
      DEFAULT_PLANTS_SEARCH.layout,
    ),
    parent: parseSearchString(search.parent, DEFAULT_PLANTS_SEARCH.parent),
    q: parseSearchString(search.q, DEFAULT_PLANTS_SEARCH.q),
    sexTest: parseSearchEnum(
      search.sexTest,
      PLANT_SEX_TEST_STATE_VALUES,
      DEFAULT_PLANTS_SEARCH.sexTest,
    ),
    status: parseSearchEnum(
      search.status,
      PLANT_LIFECYCLE_STATUS_VALUES,
      DEFAULT_PLANTS_SEARCH.status,
    ),
    strain: parseSearchString(search.strain, DEFAULT_PLANTS_SEARCH.strain),
    visibility: parseSearchEnum(
      search.visibility,
      PLANT_VISIBILITY_VALUES,
      DEFAULT_PLANTS_SEARCH.visibility,
    ),
  };
}

export function normalizePlantsSearch(
  search: PlantsSearchState,
): Required<PlantsSearchState> {
  return {
    groupBy: search.groupBy ?? DEFAULT_PLANTS_SEARCH.groupBy,
    layout: search.layout ?? DEFAULT_PLANTS_SEARCH.layout,
    parent: search.parent ?? DEFAULT_PLANTS_SEARCH.parent,
    q: search.q ?? DEFAULT_PLANTS_SEARCH.q,
    sexTest: search.sexTest ?? DEFAULT_PLANTS_SEARCH.sexTest,
    status: search.status ?? DEFAULT_PLANTS_SEARCH.status,
    strain: search.strain ?? DEFAULT_PLANTS_SEARCH.strain,
    visibility: search.visibility ?? DEFAULT_PLANTS_SEARCH.visibility,
  };
}

export function PlantsListPage({
  search,
}: {
  search: Required<PlantsSearchState>;
}): ReactNode {
  return <PlantsPage mode="list" search={search} />;
}

export function NewPlantPage({
  seedLots,
}: {
  seedLots: readonly SeedLotSummary[];
}): ReactNode {
  return <PlantsPage mode="new-plant" seedLots={seedLots} />;
}

export function PlantDetailPage({
  editMode = false,
  plantKey,
}: {
  editMode?: boolean;
  plantKey: string;
}): ReactNode {
  return <PlantsPage editMode={editMode} mode="detail" plantKey={plantKey} />;
}

function parseSearchEnum<TValue extends string>(
  value: unknown,
  values: readonly TValue[],
  fallback: TValue,
): TValue {
  return typeof value === "string" && values.includes(value as TValue)
    ? (value as TValue)
    : fallback;
}

function parseSearchString(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

function pageViewFromMode(mode: PlantsPageMode): PlantsPageView {
  if (mode === "new-plant") return "add-plants";
  if (mode === "detail") return "detail";
  return "plants";
}

function filterPlantsByVisibility(
  plants: readonly PlantRow[],
  visibility: PlantVisibilityFilter,
): readonly PlantRow[] {
  if (visibility === "all") return plants;
  if (visibility === "culled") {
    return plants.filter((plant) => plant.stageKey === "culled");
  }
  if (visibility === "harvested") {
    return plants.filter((plant) => plant.stageKey === "harvested");
  }
  return plants.filter(isActivePlant);
}

function isActivePlant(plant: PlantRow): boolean {
  return plant.stageKey !== "culled" && plant.stageKey !== "harvested";
}

export function filterPlantsForSearch(
  plants: readonly PlantRow[],
  search: Required<PlantsSearchState>,
): readonly PlantRow[] {
  const query = normalizeSearchText(search.q);
  return plants.filter((plant) => {
    if (search.parent !== "all" && plant.parentsLabel !== search.parent) return false;
    if (search.strain !== "all" && plant.strain !== search.strain) return false;
    if (search.status !== "all" && plantLifecycleStatus(plant) !== search.status) {
      return false;
    }
    if (search.sexTest !== "all" && plantSexTestState(plant) !== search.sexTest) {
      return false;
    }
    if (query.length === 0) return true;
    return normalizeSearchText(plantSearchText(plant)).includes(query);
  });
}

export function plantLifecycleStatus(
  plant: PlantRow,
): Exclude<PlantLifecycleStatusFilter, "all"> | "unstarted" {
  if (plant.flowerStartedAt !== null) return "flower";
  if (plant.vegStartedAt !== null) return "veg";
  if (plant.germinatedAt !== null || plant.takenAt !== null) return "started";
  return "unstarted";
}

function plantSexTestState(plant: PlantRow): Exclude<PlantSexTestStateFilter, "all"> {
  const sexTest = latestSexTest(plant);
  if (sexTest === undefined) return "untested";
  return sexTestState(sexTest);
}

function PlantsPage({
  editMode = false,
  mode,
  plantKey = "",
  seedLots = [],
  search = DEFAULT_PLANTS_SEARCH,
}: {
  editMode?: boolean;
  mode: PlantsPageMode;
  plantKey?: string;
  seedLots?: readonly SeedLotSummary[];
  search?: Required<PlantsSearchState>;
}): ReactNode {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [view, setView] = useState<PlantsPageView>(() => pageViewFromMode(mode));
  const [selectedPlantIds, setSelectedPlantIds] =
    useState<ReadonlySet<string>>(EMPTY_SELECTION);
  const [bulkPanel, setBulkPanel] = useState<BulkPanel>(null);
  const [bulkSex, setBulkSex] = useState<PlantSexKey>("female");
  const [bulkDateField, setBulkDateField] = useState<BulkDateField>("veg_started_at");
  const [bulkDateValue, setBulkDateValue] = useState(datetimeLocalNow);
  const [bulkCullReason, setBulkCullReason] = useState("");
  const [bulkCullAt, setBulkCullAt] = useState(datetimeLocalNow);
  const [moveLocationKey, setMoveLocationKey] = useState(1);
  const [addPlantMode, setAddPlantMode] = useState<AddPlantMode>("germinate");
  const [selectedSeedLotId, setSelectedSeedLotId] = useState("lot-maruf-black");
  const [germinateCount, setGerminateCount] = useState(10);
  const [germinateLocationKey, setGerminateLocationKey] = useState(1);
  const [germinatedAt, setGerminatedAt] = useState(datetimeLocalNow);
  const [cloneMotherId, setCloneMotherId] = useState("plant-a");
  const [cloneCount, setCloneCount] = useState(4);
  const [cloneLocationKey, setCloneLocationKey] = useState(1);
  const [cloneTakenAt, setCloneTakenAt] = useState(datetimeLocalNow);
  const [detailPlantKey, setDetailPlantKey] = useState(plantKey);
  const [detailFactsEditing, setDetailFactsEditing] = useState(false);
  const [detailFactsDraft, setDetailFactsDraft] = useState<DetailFactsDraft>(
    EMPTY_DETAIL_FACTS_DRAFT,
  );
  const [detailFactsDraftPlantKey, setDetailFactsDraftPlantKey] = useState<
    string | null
  >(null);
  const [bulkNotePlantKeys, setBulkNotePlantKeys] = useState<readonly string[] | null>(
    null,
  );
  const [noteText, setNoteText] = useState("");
  const [draggingPlantId, setDraggingPlantId] = useState<string | null>(null);
  const [tableSort, setTableSort] = useState<PlantTableSortState>(null);

  useEffect(() => {
    setView(pageViewFromMode(mode));
    setDetailPlantKey(plantKey);
    setDetailFactsEditing(editMode);
    if (!editMode) setDetailFactsDraftPlantKey(null);
    setBulkNotePlantKeys(null);
  }, [editMode, mode, plantKey]);

  const logbook = usePlantsQueries(detailPlantKey);
  const pendingCommands = usePlantsPendingCommands();
  const germinateMutation = useGerminatePlantsMutation();
  const cloneMutation = useClonePlantsMutation();
  const bulkSexMutation = useBulkSexMutation();
  const bulkMoveMutation = useBulkMoveMutation();
  const updatePlantFactsMutation = useUpdatePlantFactsMutation();
  const bulkCullMutation = useBulkCullMutation();
  const logNoteMutation = useLogPlantNoteMutation();
  const bulkCreateSexTestsMutation = useBulkCreateSexTestsMutation();
  const updateSexTestMutation = useUpdateSexTestMutation();
  const bulkResultSexTestsMutation = useBulkResultSexTestsMutation();
  const serverPlants = logbook.plants.plants;
  const plants = useMemo(
    () => applyPendingPlantCommands(serverPlants, pendingCommands),
    [serverPlants, pendingCommands],
  );
  const activeCount = plants.filter(isActivePlant).length;
  const culledCount = plants.filter((plant) => plant.stageKey === "culled").length;
  const harvestedCount = plants.filter(
    (plant) => plant.stageKey === "harvested",
  ).length;
  const archivedCount = culledCount + harvestedCount;
  const visiblePlants = filterPlantsByVisibility(plants, search.visibility);
  const filteredPlants = filterPlantsForSearch(visiblePlants, search);
  const selectedPlants = plants.filter((plant) => selectedPlantIds.has(plant.id));
  const selectedPlantKeys = selectedPlants.map((plant) => plant.key);
  const selectedPlantsHavePendingCommand = hasActivePendingForAnyPlant(
    pendingCommands,
    selectedPlantKeys,
  );
  const detailPlant =
    plants.find(
      (plant) => plant.key === (detailPlantKey || logbook.detail.plant.key),
    ) ?? logbook.detail.plant;
  const detail = { ...logbook.detail, plant: detailPlant };
  useLayoutEffect(() => {
    if (!detailFactsEditing) return;
    if (detailFactsDraftPlantKey === detail.plant.key) return;
    setDetailFactsDraft(detailFactsDraftFromPlant(detail.plant));
    setDetailFactsDraftPlantKey(detail.plant.key);
  }, [detail.plant, detailFactsDraftPlantKey, detailFactsEditing]);
  const noteTargetPlantKeys = bulkNotePlantKeys ?? [detail.plant.key];
  const loggingBulkNote = bulkNotePlantKeys !== null;
  const succeededCommandProjectionState = useMemo(() => {
    const projectedCommandIds: string[] = [];
    const unprojectedCommands: PlantsPendingCommand[] = [];
    for (const pending of pendingCommands) {
      if (pending.command.status !== "succeeded") continue;
      if (
        isPendingCommandProjected(
          pending,
          serverPlants,
          logbook.detail.events,
          logbook.detail.plant.key,
        )
      ) {
        projectedCommandIds.push(pending.commandId);
      } else {
        unprojectedCommands.push(pending);
      }
    }
    return { projectedCommandIds, unprojectedCommands };
  }, [pendingCommands, serverPlants, logbook.detail.events, logbook.detail.plant.key]);
  const { projectedCommandIds, unprojectedCommands: unprojectedSucceededCommands } =
    succeededCommandProjectionState;

  useEffect(() => {
    if (projectedCommandIds.length === 0) return;
    removeProjectedPendingCommands(queryClient, projectedCommandIds);
  }, [projectedCommandIds, queryClient]);

  useEffect(() => {
    if (unprojectedSucceededCommands.length === 0) return;
    let timeoutId: number | null = null;
    const refreshUntilProjected = () => {
      invalidatePlantsReads(
        queryClient,
        unprojectedSucceededCommands.flatMap((pending) => pending.affectedPlantKeys),
      );
      timeoutId = platform.setTimeout(refreshUntilProjected, 5_000);
    };

    refreshUntilProjected();

    return () => {
      if (timeoutId !== null) {
        platform.clearTimeout(timeoutId);
      }
    };
  }, [queryClient, unprojectedSucceededCommands]);

  const clearSelection = () => {
    setSelectedPlantIds(new Set());
    setBulkPanel(null);
  };
  const selectedLocation =
    logbook.bootstrap.locations.find(
      (location) => location.sourceTentId === moveLocationKey,
    ) ??
    logbook.bootstrap.locations[0] ??
    FALLBACK_LOCATION;
  const maxEventDateTime = datetimeLocalNow();
  const detailPlantHasPendingCommand =
    activePendingCommandsForPlant(pendingCommands, detail.plant.key).length > 0;
  const sexTestMutationPending =
    bulkCreateSexTestsMutation.isPending ||
    updateSexTestMutation.isPending ||
    bulkResultSexTestsMutation.isPending;
  const sexTestMutationError = mutationErrorText(
    bulkCreateSexTestsMutation.error ??
      updateSexTestMutation.error ??
      bulkResultSexTestsMutation.error,
  );

  return (
    <main className="flex-1 overflow-auto bg-paper text-ink">
      <div className="mx-auto flex max-w-330 flex-col gap-4 px-4 pb-14 pt-4 sm:px-6">
        {view === "plants" ? (
          <PlantsSurface
            activeCount={activeCount}
            archivedCount={archivedCount}
            bootstrap={logbook.bootstrap}
            bulkCullAt={bulkCullAt}
            bulkDateField={bulkDateField}
            bulkDateValue={bulkDateValue}
            bulkPanel={bulkPanel}
            bulkSex={bulkSex}
            culledCount={culledCount}
            draggingPlantId={draggingPlantId}
            groupBy={search.groupBy}
            harvestedCount={harvestedCount}
            layout={search.layout}
            maxEventDateTime={maxEventDateTime}
            moveLocationKey={moveLocationKey}
            filterSourcePlants={visiblePlants}
            plants={filteredPlants}
            search={search}
            sexTestCreatePending={bulkCreateSexTestsMutation.isPending}
            sexTestResultPending={bulkResultSexTestsMutation.isPending}
            tableSort={tableSort}
            selectedLocation={selectedLocation}
            selectedPlantIds={selectedPlantIds}
            selectedPlants={selectedPlants}
            visibility={search.visibility}
            pendingCommands={pendingCommands}
            bulkCullReason={bulkCullReason}
            mutationError={mutationErrorText(
              bulkSexMutation.error ??
                bulkMoveMutation.error ??
                updatePlantFactsMutation.error ??
                bulkCullMutation.error ??
                bulkCreateSexTestsMutation.error ??
                updateSexTestMutation.error ??
                bulkResultSexTestsMutation.error,
            )}
            destructiveActionsDisabled={selectedPlantsHavePendingCommand}
            onAddPlants={() => {
              void navigate({ to: "/plants/new" });
            }}
            onAddSeeds={() => {
              void navigate({ to: "/seeds/new" });
            }}
            onApplyCull={() => {
              if (
                selectedPlantKeys.length === 0 ||
                selectedPlantsHavePendingCommand ||
                !canSubmitBulkCull(bulkCullReason) ||
                !canSubmitEventDateTime(bulkCullAt, maxEventDateTime)
              ) {
                return;
              }
              const bulkCullAtUtc = datetimeLocalToUtcIso(bulkCullAt);
              if (bulkCullAtUtc === null) return;
              bulkCullMutation.mutate(
                {
                  idempotencyKey: createPlantsIdempotencyKey("bulk-cull"),
                  plantKeys: selectedPlantKeys,
                  reason: bulkCullReason,
                  culledAt: bulkCullAtUtc,
                },
                {
                  onSuccess: () => {
                    setBulkCullReason("");
                    setBulkCullAt(datetimeLocalNow());
                    clearSelection();
                  },
                },
              );
            }}
            onApplyMove={() => {
              if (selectedPlantKeys.length === 0 || selectedPlantsHavePendingCommand) {
                return;
              }
              bulkMoveMutation.mutate(
                {
                  idempotencyKey: createPlantsIdempotencyKey("bulk-move"),
                  plantKeys: selectedPlantKeys,
                  sourceTentId: selectedLocation.sourceTentId,
                  locationLabel: selectedLocation.displayName,
                },
                {
                  onSuccess: clearSelection,
                },
              );
            }}
            onApplyBulkDate={() => {
              if (
                selectedPlantKeys.length === 0 ||
                selectedPlantsHavePendingCommand ||
                !canSubmitEventDateTime(bulkDateValue, maxEventDateTime)
              ) {
                return;
              }
              const bulkDateUtc = datetimeLocalToUtcIso(bulkDateValue);
              if (bulkDateUtc === null) return;
              updatePlantFactsMutation.mutate(
                {
                  idempotencyKey: createPlantsIdempotencyKey("bulk-update-facts"),
                  plantKeys: selectedPlantKeys,
                  updates: [{ field: bulkDateField, value: bulkDateUtc }],
                },
                {
                  onSuccess: clearSelection,
                },
              );
            }}
            onClearBulkDate={() => {
              if (selectedPlantKeys.length === 0 || selectedPlantsHavePendingCommand) {
                return;
              }
              updatePlantFactsMutation.mutate(
                {
                  idempotencyKey: createPlantsIdempotencyKey("bulk-clear-facts"),
                  plantKeys: selectedPlantKeys,
                  updates: [{ field: bulkDateField, value: null }],
                },
                {
                  onSuccess: clearSelection,
                },
              );
            }}
            onApplySex={() => {
              if (selectedPlantKeys.length === 0 || selectedPlantsHavePendingCommand) {
                return;
              }
              bulkSexMutation.mutate(
                {
                  idempotencyKey: createPlantsIdempotencyKey("bulk-sex"),
                  plantKeys: selectedPlantKeys,
                  sexKey: bulkSex,
                },
                {
                  onSuccess: clearSelection,
                },
              );
            }}
            onCreateSexTests={(input, onSuccess) => {
              bulkCreateSexTestsMutation.mutate(input, {
                onSuccess: () => {
                  onSuccess();
                  clearSelection();
                },
              });
            }}
            onResultSexTests={(input, onSuccess) => {
              bulkResultSexTestsMutation.mutate(input, { onSuccess });
            }}
            onBulkDateFieldChange={setBulkDateField}
            onBulkDateValueChange={setBulkDateValue}
            onBulkPanelChange={setBulkPanel}
            onBulkSexChange={setBulkSex}
            onBulkCullReasonChange={setBulkCullReason}
            onBulkCullAtChange={setBulkCullAt}
            onClearSelection={clearSelection}
            onDragEnd={() => {
              setDraggingPlantId(null);
            }}
            onDragStart={setDraggingPlantId}
            onDropPlant={(location) => {
              if (draggingPlantId === null) return;
              const moveIds = selectedPlantIds.has(draggingPlantId)
                ? selectedPlantIds
                : new Set([draggingPlantId]);
              const movePlantKeys = plants
                .filter((plant) => moveIds.has(plant.id))
                .map((plant) => plant.key);
              if (
                movePlantKeys.length === 0 ||
                hasActivePendingForAnyPlant(pendingCommands, movePlantKeys)
              ) {
                setDraggingPlantId(null);
                return;
              }
              bulkMoveMutation.mutate(
                {
                  idempotencyKey: createPlantsIdempotencyKey("board-move"),
                  plantKeys: movePlantKeys,
                  sourceTentId: location.sourceTentId,
                  locationLabel: location.displayName,
                },
                {
                  onSuccess: () => {
                    clearSelection();
                    setDraggingPlantId(null);
                  },
                },
              );
            }}
            onGroupByChange={(groupBy) => {
              void navigate({
                to: "/plants",
                search: (previous) => ({ ...previous, groupBy }),
                replace: true,
              });
            }}
            onLayoutChange={(layout) => {
              void navigate({
                to: "/plants",
                search: (previous) => ({ ...previous, layout }),
                replace: true,
              });
            }}
            onParentFilterChange={(parent) => {
              void navigate({
                to: "/plants",
                search: (previous) => ({ ...previous, parent }),
                replace: true,
              });
            }}
            onQueryChange={(q) => {
              void navigate({
                to: "/plants",
                search: (previous) => ({ ...previous, q }),
                replace: true,
              });
            }}
            onResetFilters={() => {
              void navigate({
                to: "/plants",
                search: (previous) => ({
                  ...previous,
                  parent: DEFAULT_PLANTS_SEARCH.parent,
                  q: DEFAULT_PLANTS_SEARCH.q,
                  sexTest: DEFAULT_PLANTS_SEARCH.sexTest,
                  status: DEFAULT_PLANTS_SEARCH.status,
                  strain: DEFAULT_PLANTS_SEARCH.strain,
                }),
                replace: true,
              });
            }}
            onStatusFilterChange={(status) => {
              void navigate({
                to: "/plants",
                search: (previous) => ({ ...previous, status }),
                replace: true,
              });
            }}
            onSexTestFilterChange={(sexTest) => {
              void navigate({
                to: "/plants",
                search: (previous) => ({ ...previous, sexTest }),
                replace: true,
              });
            }}
            onStrainFilterChange={(strain) => {
              void navigate({
                to: "/plants",
                search: (previous) => ({ ...previous, strain }),
                replace: true,
              });
            }}
            onTableSortChange={setTableSort}
            onMoveLocationChange={setMoveLocationKey}
            onOpenBulkNote={() => {
              const firstSelected = selectedPlants[0];
              if (!firstSelected) return;
              void navigate({
                to: "/plants/$plantKey",
                params: { plantKey: firstSelected.key },
              });
            }}
            onOpenDetail={(nextPlantKey) => {
              void navigate({
                to: "/plants/$plantKey",
                params: { plantKey: nextPlantKey },
              });
            }}
            onSelectedPlantIdsChange={setSelectedPlantIds}
            onVisibilityChange={(visibility) => {
              void navigate({
                to: "/plants",
                search: (previous) => ({ ...previous, visibility }),
                replace: true,
              });
            }}
          />
        ) : view === "add-plants" ? (
          <AddPlantsSurface
            cloneCount={cloneCount}
            cloneLocationKey={cloneLocationKey}
            cloneMotherId={cloneMotherId}
            cloneTakenAt={cloneTakenAt}
            germinateCount={germinateCount}
            germinatedAt={germinatedAt}
            germinateLocationKey={germinateLocationKey}
            maxEventDateTime={maxEventDateTime}
            mode={addPlantMode}
            plants={plants}
            seedLots={seedLots}
            selectedSeedLotId={selectedSeedLotId}
            bootstrap={logbook.bootstrap}
            pendingCommands={pendingCommands}
            mutationError={mutationErrorText(
              germinateMutation.error ?? cloneMutation.error,
            )}
            mutationPending={germinateMutation.isPending || cloneMutation.isPending}
            onAddSeeds={() => {
              void navigate({ to: "/seeds/new" });
            }}
            onBack={() => {
              void navigate({ to: "/plants" });
            }}
            onCloneCountChange={setCloneCount}
            onCloneLocationChange={setCloneLocationKey}
            onCloneMotherChange={setCloneMotherId}
            onCloneTakenAtChange={setCloneTakenAt}
            onGerminateCountChange={setGerminateCount}
            onGerminatedAtChange={setGerminatedAt}
            onGerminateLocationChange={setGerminateLocationKey}
            onModeChange={setAddPlantMode}
            onSeedLotChange={setSelectedSeedLotId}
            onSow={(seedLot, location) => {
              const germinatedAtUtc = datetimeLocalToUtcIso(germinatedAt);
              if (germinatedAtUtc === null) return;
              germinateMutation.mutate(
                {
                  idempotencyKey: createPlantsIdempotencyKey("germinate"),
                  seedLotId: seedLot.id,
                  count: germinateCount,
                  sourceTentId: location.sourceTentId,
                  affectedLabel: seedLot.label,
                  germinatedAt: germinatedAtUtc,
                },
                {
                  onSuccess: () => {
                    clearSelection();
                    void navigate({ to: "/plants" });
                  },
                },
              );
            }}
            onTakeClones={(mother, location) => {
              const cloneTakenAtUtc = datetimeLocalToUtcIso(cloneTakenAt);
              if (cloneTakenAtUtc === null) return;
              cloneMutation.mutate(
                {
                  idempotencyKey: createPlantsIdempotencyKey("clone"),
                  motherPlantKey: mother.key,
                  count: cloneCount,
                  sourceTentId: location.sourceTentId,
                  takenAt: cloneTakenAtUtc,
                },
                {
                  onSuccess: () => {
                    clearSelection();
                    void navigate({ to: "/plants" });
                  },
                },
              );
            }}
          />
        ) : (
          <PlantJournalDetail
            detail={detail}
            factActionsDisabled={
              detailPlantHasPendingCommand || updatePlantFactsMutation.isPending
            }
            factsDraft={detailFactsDraft}
            factsEditing={detailFactsEditing}
            factsMutationError={mutationErrorText(updatePlantFactsMutation.error)}
            factsMutationPending={updatePlantFactsMutation.isPending}
            maxEventDateTime={maxEventDateTime}
            noteTargetCount={noteTargetPlantKeys.length}
            noteText={noteText}
            mutationError={mutationErrorText(logNoteMutation.error)}
            mutationPending={logNoteMutation.isPending}
            pendingNotes={pendingTimelineNotes(
              detail.events,
              pendingCommands,
              detail.plant.key,
            )}
            pendingCommands={pendingCommands}
            sexTestActionsDisabled={detailPlantHasPendingCommand}
            sexTestMutationError={sexTestMutationError}
            sexTestMutationPending={sexTestMutationPending}
            onBack={() => {
              setBulkNotePlantKeys(null);
              setDetailFactsEditing(false);
              setDetailFactsDraftPlantKey(null);
              void navigate({ to: "/plants" });
            }}
            onCancelFactsEdit={() => {
              if (editMode) {
                void navigate({
                  to: "/plants/$plantKey",
                  params: { plantKey: detail.plant.key },
                });
                return;
              }
              setDetailFactsEditing(false);
              setDetailFactsDraftPlantKey(null);
            }}
            onFactsDraftChange={setDetailFactsDraft}
            onStartFactsEdit={() => {
              setDetailFactsDraft(detailFactsDraftFromPlant(detail.plant));
              setDetailFactsDraftPlantKey(detail.plant.key);
              void navigate({
                to: "/plants/$plantKey/edit",
                params: { plantKey: detail.plant.key },
              });
            }}
            onLogNote={() => {
              const body = noteText.trim();
              if (body.length === 0 || noteTargetPlantKeys.length === 0) return;
              logNoteMutation.mutate(
                {
                  idempotencyKey: createPlantsIdempotencyKey("plant-note"),
                  plantKeys: noteTargetPlantKeys,
                  body,
                },
                {
                  onSuccess: () => {
                    setNoteText("");
                    if (loggingBulkNote) {
                      setBulkNotePlantKeys(null);
                      clearSelection();
                    }
                  },
                },
              );
            }}
            onCreateSexTests={(input, onSuccess) => {
              bulkCreateSexTestsMutation.mutate(input, { onSuccess });
            }}
            onResultSexTests={(input, onSuccess) => {
              bulkResultSexTestsMutation.mutate(input, { onSuccess });
            }}
            onNoteTextChange={setNoteText}
            onSaveFacts={() => {
              if (
                !canSaveDetailFactsDraft(
                  detail.plant,
                  detailFactsDraft,
                  maxEventDateTime,
                )
              ) {
                return;
              }
              const updates = detailFactUpdates(detail.plant, detailFactsDraft);
              if (updates.length === 0) {
                if (editMode) {
                  void navigate({
                    to: "/plants/$plantKey",
                    params: { plantKey: detail.plant.key },
                  });
                } else {
                  setDetailFactsEditing(false);
                  setDetailFactsDraftPlantKey(null);
                }
                return;
              }
              updatePlantFactsMutation.mutate(
                {
                  idempotencyKey: createPlantsIdempotencyKey("plant-update-facts"),
                  plantKeys: [detail.plant.key],
                  updates,
                },
                {
                  onSuccess: () => {
                    setDetailFactsEditing(false);
                    setDetailFactsDraftPlantKey(null);
                    if (editMode) {
                      void navigate({
                        to: "/plants/$plantKey",
                        params: { plantKey: detail.plant.key },
                      });
                    }
                  },
                },
              );
            }}
            onUpdateSexTest={(input, onSuccess) => {
              updateSexTestMutation.mutate(input, { onSuccess });
            }}
          />
        )}
      </div>
    </main>
  );
}

export function StatusScreen({
  message,
  tone = "neutral",
}: {
  message: string;
  tone?: "neutral" | "danger";
}): ReactNode {
  return (
    <main className="flex-1 overflow-auto bg-paper p-6">
      <p
        className={
          tone === "danger"
            ? "font-mono text-fs-10 uppercase tracking-caps text-accent-magenta"
            : "font-mono text-fs-10 uppercase tracking-caps text-ink-3"
        }
      >
        {message}
      </p>
    </main>
  );
}

function PlantsSurface({
  activeCount,
  archivedCount,
  bootstrap,
  bulkCullAt,
  bulkCullReason,
  bulkDateField,
  bulkDateValue,
  bulkPanel,
  bulkSex,
  culledCount,
  destructiveActionsDisabled,
  draggingPlantId,
  filterSourcePlants,
  groupBy,
  harvestedCount,
  layout,
  maxEventDateTime,
  mutationError,
  moveLocationKey,
  onAddPlants,
  onAddSeeds,
  onApplyBulkDate,
  onApplyCull,
  onApplyMove,
  onApplySex,
  onCreateSexTests,
  onBulkDateFieldChange,
  onBulkDateValueChange,
  onBulkPanelChange,
  onBulkCullAtChange,
  onBulkCullReasonChange,
  onBulkSexChange,
  onClearBulkDate,
  onClearSelection,
  onDragEnd,
  onDragStart,
  onDropPlant,
  onGroupByChange,
  onLayoutChange,
  onMoveLocationChange,
  onOpenBulkNote,
  onOpenDetail,
  onParentFilterChange,
  onQueryChange,
  onResultSexTests,
  onResetFilters,
  onSelectedPlantIdsChange,
  onSexTestFilterChange,
  onStatusFilterChange,
  onStrainFilterChange,
  onTableSortChange,
  onVisibilityChange,
  plants,
  pendingCommands,
  search,
  sexTestCreatePending,
  sexTestResultPending,
  tableSort,
  selectedLocation,
  selectedPlantIds,
  selectedPlants,
  visibility,
}: {
  activeCount: number;
  archivedCount: number;
  bootstrap: PlantsBootstrap;
  bulkCullAt: string;
  bulkCullReason: string;
  bulkDateField: BulkDateField;
  bulkDateValue: string;
  bulkPanel: BulkPanel;
  bulkSex: PlantSexKey;
  culledCount: number;
  destructiveActionsDisabled: boolean;
  draggingPlantId: string | null;
  filterSourcePlants: readonly PlantRow[];
  groupBy: PlantGroupBy;
  harvestedCount: number;
  layout: PlantListLayout;
  maxEventDateTime: string;
  mutationError: string | null;
  moveLocationKey: number;
  plants: readonly PlantRow[];
  pendingCommands: readonly PlantsPendingCommand[];
  search: Required<PlantsSearchState>;
  sexTestCreatePending: boolean;
  sexTestResultPending: boolean;
  tableSort: PlantTableSortState;
  selectedLocation: LocationOption;
  selectedPlantIds: ReadonlySet<string>;
  selectedPlants: readonly PlantRow[];
  visibility: PlantVisibilityFilter;
  onAddPlants: () => void;
  onAddSeeds: () => void;
  onApplyBulkDate: () => void;
  onApplyCull: () => void;
  onApplyMove: () => void;
  onApplySex: () => void;
  onCreateSexTests: SexTestMutationSubmit<CreateSexTestsInput>;
  onBulkDateFieldChange: (field: BulkDateField) => void;
  onBulkDateValueChange: (value: string) => void;
  onBulkPanelChange: (panel: BulkPanel) => void;
  onBulkCullAtChange: (value: string) => void;
  onBulkCullReasonChange: (reason: string) => void;
  onBulkSexChange: (sex: PlantSexKey) => void;
  onClearBulkDate: () => void;
  onClearSelection: () => void;
  onDragEnd: () => void;
  onDragStart: (plantId: string) => void;
  onDropPlant: (location: LocationOption) => void;
  onGroupByChange: (groupBy: PlantGroupBy) => void;
  onLayoutChange: (layout: PlantListLayout) => void;
  onMoveLocationChange: (sourceTentId: number) => void;
  onOpenBulkNote: () => void;
  onOpenDetail: (plantId: string) => void;
  onParentFilterChange: (parent: string) => void;
  onQueryChange: (query: string) => void;
  onResultSexTests: SexTestMutationSubmit<ResultSexTestsInput>;
  onResetFilters: () => void;
  onSelectedPlantIdsChange: (plantIds: ReadonlySet<string>) => void;
  onSexTestFilterChange: (sexTest: PlantSexTestStateFilter) => void;
  onStatusFilterChange: (status: PlantLifecycleStatusFilter) => void;
  onStrainFilterChange: (strain: string) => void;
  onTableSortChange: (sort: PlantTableSortState) => void;
  onVisibilityChange: (visibility: PlantVisibilityFilter) => void;
}): ReactNode {
  const selectedCount = selectedPlantIds.size;
  const allVisibleSelected =
    plants.length > 0 && plants.every((plant) => selectedPlantIds.has(plant.id));
  const someVisibleSelected = plants.some((plant) => selectedPlantIds.has(plant.id));
  const listFooter =
    visibility === "active"
      ? `${plants.length} shown / ${activeCount} active / grouped by ${groupBy} / ${archivedCount} archived hidden`
      : `${plants.length} shown / grouped by ${groupBy} / ${activeCount} active / ${culledCount} culled / ${harvestedCount} harvested`;

  const togglePlant = (plantId: string) => {
    const next = new Set(selectedPlantIds);
    if (next.has(plantId)) {
      next.delete(plantId);
    } else {
      next.add(plantId);
    }
    onSelectedPlantIdsChange(next);
  };

  const toggleAllVisible = () => {
    if (allVisibleSelected) {
      onSelectedPlantIdsChange(new Set());
      return;
    }
    onSelectedPlantIdsChange(new Set(plants.map((plant) => plant.id)));
  };

  return (
    <>
      <section className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="font-sans text-fs-22 font-semibold text-ink">Plants</h2>
          <p className="mt-1 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            {activeCount} active / {archivedCount} archived
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={onAddSeeds}>
            + Add seeds
          </Button>
          <Button variant="primary" onClick={onAddPlants}>
            + Add plants
          </Button>
        </div>
      </section>
      <PlantChrome
        archivedCount={archivedCount}
        culledCount={culledCount}
        filterSourcePlants={filterSourcePlants}
        groupBy={groupBy}
        harvestedCount={harvestedCount}
        layout={layout}
        search={search}
        visibility={visibility}
        onGroupByChange={onGroupByChange}
        onLayoutChange={onLayoutChange}
        onParentFilterChange={onParentFilterChange}
        onQueryChange={onQueryChange}
        onResetFilters={onResetFilters}
        onSexTestFilterChange={onSexTestFilterChange}
        onStatusFilterChange={onStatusFilterChange}
        onStrainFilterChange={onStrainFilterChange}
        onVisibilityChange={onVisibilityChange}
      />
      {selectedCount > 0 ? (
        <BulkActionToolbar
          bulkCullAt={bulkCullAt}
          bulkCullReason={bulkCullReason}
          bulkDateField={bulkDateField}
          bulkDateValue={bulkDateValue}
          bulkPanel={bulkPanel}
          bulkSex={bulkSex}
          destructiveActionsDisabled={destructiveActionsDisabled}
          locations={bootstrap.locations}
          maxEventDateTime={maxEventDateTime}
          moveLocationKey={moveLocationKey}
          mutationPending={sexTestCreatePending}
          pendingCommands={pendingCommands}
          selectedCount={selectedCount}
          selectedPlants={selectedPlants}
          selectedLocation={selectedLocation}
          onApplyBulkDate={onApplyBulkDate}
          onApplyCull={onApplyCull}
          onApplyMove={onApplyMove}
          onApplySex={onApplySex}
          onCreateSexTests={onCreateSexTests}
          onBulkDateFieldChange={onBulkDateFieldChange}
          onBulkDateValueChange={onBulkDateValueChange}
          onBulkPanelChange={onBulkPanelChange}
          onBulkCullAtChange={onBulkCullAtChange}
          onBulkCullReasonChange={onBulkCullReasonChange}
          onBulkSexChange={onBulkSexChange}
          onClearBulkDate={onClearBulkDate}
          onClear={onClearSelection}
          onMoveLocationChange={onMoveLocationChange}
          onOpenNote={onOpenBulkNote}
        />
      ) : null}
      <PendingCommandSummary commands={pendingCommands} mutationError={mutationError} />
      <PendingSexTestResultsPanel
        maxEventDateTime={maxEventDateTime}
        mutationPending={sexTestResultPending}
        pendingCommands={pendingCommands}
        plants={plants}
        onResultSexTests={onResultSexTests}
      />
      {layout === "table" ? (
        <PlantTable
          allChecked={allVisibleSelected}
          bootstrap={bootstrap}
          groupBy={groupBy}
          plants={plants}
          pendingCommands={pendingCommands}
          selectedPlantIds={selectedPlantIds}
          someChecked={someVisibleSelected}
          sortState={tableSort}
          onOpenDetail={onOpenDetail}
          onSortChange={onTableSortChange}
          onToggleAll={toggleAllVisible}
          onTogglePlant={togglePlant}
        />
      ) : (
        <PlantBoard
          bootstrap={bootstrap}
          draggingPlantId={draggingPlantId}
          plants={plants}
          pendingCommands={pendingCommands}
          selectedPlantIds={selectedPlantIds}
          includeArchived={visibility !== "active"}
          onDragEnd={onDragEnd}
          onDragStart={onDragStart}
          onDropPlant={onDropPlant}
          onOpenDetail={onOpenDetail}
          onTogglePlant={togglePlant}
        />
      )}
      <p className="font-mono text-fs-9 uppercase tracking-caps text-ink-3">
        {listFooter}
        {selectedPlants.length > 0
          ? ` / ${selectedPlants.length} selected for command actions`
          : ""}
      </p>
    </>
  );
}

function PlantChrome({
  archivedCount,
  culledCount,
  filterSourcePlants,
  groupBy,
  harvestedCount,
  layout,
  onGroupByChange,
  onLayoutChange,
  onParentFilterChange,
  onQueryChange,
  onResetFilters,
  onSexTestFilterChange,
  onStatusFilterChange,
  onStrainFilterChange,
  onVisibilityChange,
  search,
  visibility,
}: {
  archivedCount: number;
  culledCount: number;
  filterSourcePlants: readonly PlantRow[];
  groupBy: PlantGroupBy;
  harvestedCount: number;
  layout: PlantListLayout;
  search: Required<PlantsSearchState>;
  onGroupByChange: (groupBy: PlantGroupBy) => void;
  onLayoutChange: (layout: PlantListLayout) => void;
  onParentFilterChange: (parent: string) => void;
  onQueryChange: (query: string) => void;
  onResetFilters: () => void;
  onSexTestFilterChange: (sexTest: PlantSexTestStateFilter) => void;
  onStatusFilterChange: (status: PlantLifecycleStatusFilter) => void;
  onStrainFilterChange: (strain: string) => void;
  onVisibilityChange: (visibility: PlantVisibilityFilter) => void;
  visibility: PlantVisibilityFilter;
}): ReactNode {
  const parentOptions = plantExactFilterOptions(
    filterSourcePlants,
    "parentsLabel",
    search.parent,
  );
  const strainOptions = plantExactFilterOptions(
    filterSourcePlants,
    "strain",
    search.strain,
  );
  const hasListFilters =
    search.q !== DEFAULT_PLANTS_SEARCH.q ||
    search.parent !== DEFAULT_PLANTS_SEARCH.parent ||
    search.sexTest !== DEFAULT_PLANTS_SEARCH.sexTest ||
    search.status !== DEFAULT_PLANTS_SEARCH.status ||
    search.strain !== DEFAULT_PLANTS_SEARCH.strain;

  return (
    <section className="grid gap-3 border border-rule bg-paper-2 px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          label="Group"
          options={[
            { label: "Stage", value: "stage" },
            { label: "Parents", value: "parents" },
          ]}
          value={groupBy}
          onChange={onGroupByChange}
        />
        <Segmented
          label="Visibility"
          options={[
            { label: "Active", value: "active" },
            { label: `All (${archivedCount})`, value: "all" },
            { label: `Culled (${culledCount})`, value: "culled" },
            { label: `Harvested (${harvestedCount})`, value: "harvested" },
          ]}
          value={visibility}
          onChange={onVisibilityChange}
        />
        <Segmented
          label="Status"
          options={[
            { label: "All", value: "all" },
            { label: "Started", value: "started" },
            { label: "Veg", value: "veg" },
            { label: "Flower", value: "flower" },
          ]}
          value={search.status}
          onChange={onStatusFilterChange}
        />
        <Segmented
          label="Sex test"
          options={[
            { label: "All", value: "all" },
            { label: "Untested", value: "untested" },
            { label: "Pending", value: "pending" },
            { label: "Resulted", value: "resulted" },
            { label: "Inconclusive", value: "inconclusive" },
          ]}
          value={search.sexTest}
          onChange={onSexTestFilterChange}
        />
        <Segmented
          label="Layout"
          options={[
            { label: "▤ Table", value: "table" },
            { label: "▥ Board", value: "board" },
          ]}
          value={layout}
          onChange={onLayoutChange}
        />
      </div>
      <div className="grid gap-2 md:grid-cols-[minmax(190px,1fr)_minmax(170px,0.7fr)_minmax(170px,0.7fr)_auto] md:items-end">
        <TextField
          label="Search"
          placeholder="name, key, code, note"
          value={search.q}
          onChange={onQueryChange}
        />
        <SelectField
          label="Parent"
          options={parentOptions}
          value={search.parent}
          onChange={onParentFilterChange}
        />
        <SelectField
          label="Strain"
          options={strainOptions}
          value={search.strain}
          onChange={onStrainFilterChange}
        />
        <button
          type="button"
          disabled={!hasListFilters}
          onClick={onResetFilters}
          className="h-9 border border-rule bg-paper px-2.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink disabled:cursor-not-allowed disabled:text-ink-3"
        >
          Clear
        </button>
      </div>
    </section>
  );
}

function BulkActionToolbar({
  bulkCullAt,
  bulkCullReason,
  bulkDateField,
  bulkDateValue,
  bulkPanel,
  bulkSex,
  destructiveActionsDisabled,
  locations,
  maxEventDateTime,
  moveLocationKey,
  mutationPending,
  onApplyBulkDate,
  onApplyCull,
  onApplyMove,
  onApplySex,
  onCreateSexTests,
  onBulkDateFieldChange,
  onBulkDateValueChange,
  onBulkPanelChange,
  onBulkCullAtChange,
  onBulkCullReasonChange,
  onBulkSexChange,
  onClearBulkDate,
  onClear,
  onMoveLocationChange,
  onOpenNote,
  pendingCommands,
  selectedCount,
  selectedLocation,
  selectedPlants,
}: {
  bulkCullAt: string;
  bulkCullReason: string;
  bulkDateField: BulkDateField;
  bulkDateValue: string;
  bulkPanel: BulkPanel;
  bulkSex: PlantSexKey;
  destructiveActionsDisabled: boolean;
  locations: readonly LocationOption[];
  maxEventDateTime: string;
  moveLocationKey: number;
  mutationPending: boolean;
  pendingCommands: readonly PlantsPendingCommand[];
  selectedCount: number;
  selectedLocation: LocationOption;
  selectedPlants: readonly PlantRow[];
  onApplyBulkDate: () => void;
  onApplyCull: () => void;
  onApplyMove: () => void;
  onApplySex: () => void;
  onCreateSexTests: SexTestMutationSubmit<CreateSexTestsInput>;
  onBulkDateFieldChange: (field: BulkDateField) => void;
  onBulkDateValueChange: (value: string) => void;
  onBulkPanelChange: (panel: BulkPanel) => void;
  onBulkCullAtChange: (value: string) => void;
  onBulkCullReasonChange: (reason: string) => void;
  onBulkSexChange: (sex: PlantSexKey) => void;
  onClearBulkDate: () => void;
  onClear: () => void;
  onMoveLocationChange: (sourceTentId: number) => void;
  onOpenNote: () => void;
}): ReactNode {
  return (
    <section className="border border-ink bg-paper-2">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink">
          {selectedCount} selected
        </p>
        <span aria-hidden="true" className="mx-1 h-5 w-px bg-rule-strong" />
        <ToolbarButton
          active={bulkPanel === "sex"}
          label="Set sex"
          onClick={() => {
            onBulkPanelChange(bulkPanel === "sex" ? null : "sex");
          }}
        >
          sex
        </ToolbarButton>
        <ToolbarButton
          active={bulkPanel === "sex-test"}
          label="Sample sex tests"
          onClick={() => {
            onBulkPanelChange(bulkPanel === "sex-test" ? null : "sex-test");
          }}
        >
          test
        </ToolbarButton>
        <ToolbarButton
          active={bulkPanel === "dates"}
          label="Set dates"
          onClick={() => {
            onBulkPanelChange(bulkPanel === "dates" ? null : "dates");
          }}
        >
          dates
        </ToolbarButton>
        <ToolbarButton
          active={bulkPanel === "move"}
          label="Move tent"
          onClick={() => {
            onBulkPanelChange(bulkPanel === "move" ? null : "move");
          }}
        >
          move
        </ToolbarButton>
        <ToolbarButton label="Add note" onClick={onOpenNote}>
          note
        </ToolbarButton>
        <ToolbarButton
          active={bulkPanel === "cull"}
          label="Cull"
          tone="danger"
          onClick={() => {
            onBulkPanelChange(bulkPanel === "cull" ? null : "cull");
          }}
        >
          cut
        </ToolbarButton>
        <button
          type="button"
          onClick={onClear}
          className="ml-auto border border-rule px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink"
        >
          clear x
        </button>
      </div>
      {bulkPanel === "sex" ? (
        <div className="flex flex-wrap items-center gap-3 border-t border-rule bg-paper px-3 py-3">
          <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            Set sex on {selectedCount} →
          </p>
          <Segmented
            label="Sex"
            options={[
              { label: "♂ Male", value: "male" },
              { label: "♀ Female", value: "female" },
              { label: "Unknown", value: "unknown" },
            ]}
            value={bulkSex}
            onChange={onBulkSexChange}
          />
          <Button
            variant="primary"
            disabled={destructiveActionsDisabled}
            onClick={onApplySex}
          >
            Apply
          </Button>
          {destructiveActionsDisabled ? <PendingBlockMessage /> : null}
        </div>
      ) : null}
      {bulkPanel === "sex-test" ? (
        <SexTestSamplingPanel
          maxEventDateTime={maxEventDateTime}
          mutationPending={mutationPending}
          pendingCommands={pendingCommands}
          plants={selectedPlants}
          submitLabel={`Create ${selectedCount} tests`}
          onCreateSexTests={onCreateSexTests}
        />
      ) : null}
      {bulkPanel === "dates" ? (
        <div className="flex flex-wrap items-end gap-3 border-t border-rule bg-paper px-3 py-3">
          <Segmented
            label="Date"
            options={BULK_DATE_FIELD_OPTIONS}
            value={bulkDateField}
            onChange={onBulkDateFieldChange}
          />
          <DateTimeField
            label={bulkDateFieldLabel(bulkDateField)}
            max={maxEventDateTime}
            value={bulkDateValue}
            onChange={onBulkDateValueChange}
          />
          <Button
            variant="primary"
            disabled={
              destructiveActionsDisabled ||
              !canSubmitEventDateTime(bulkDateValue, maxEventDateTime)
            }
            onClick={onApplyBulkDate}
          >
            Set {bulkDateFieldShortLabel(bulkDateField)} on {selectedCount}
          </Button>
          <Button
            variant="secondary"
            disabled={destructiveActionsDisabled}
            onClick={onClearBulkDate}
          >
            Clear date
          </Button>
          {destructiveActionsDisabled ? <PendingBlockMessage /> : null}
        </div>
      ) : null}
      {bulkPanel === "move" ? (
        <div className="flex flex-wrap items-center gap-3 border-t border-rule bg-paper px-3 py-3">
          <SelectField
            label="Move to"
            value={moveLocationKey}
            options={locations.map((location) => ({
              label: location.displayName,
              value: location.sourceTentId,
            }))}
            onChange={onMoveLocationChange}
          />
          <Button
            variant="primary"
            disabled={destructiveActionsDisabled}
            onClick={onApplyMove}
          >
            Move {selectedCount} →
          </Button>
          <p className="font-mono text-fs-9 uppercase tracking-caps text-ink-3">
            queues a move command to {selectedLocation.displayName}
          </p>
          {destructiveActionsDisabled ? <PendingBlockMessage /> : null}
        </div>
      ) : null}
      {bulkPanel === "cull" ? (
        <div className="flex flex-wrap items-center gap-3 border-t border-rule bg-paper px-3 py-3">
          <DateTimeField
            label="Culled at"
            max={maxEventDateTime}
            value={bulkCullAt}
            onChange={onBulkCullAtChange}
          />
          <TextField
            label="Reason"
            value={bulkCullReason}
            placeholder="selected male"
            onChange={onBulkCullReasonChange}
          />
          <Button
            variant="danger"
            disabled={
              destructiveActionsDisabled ||
              !canSubmitBulkCull(bulkCullReason) ||
              !canSubmitEventDateTime(bulkCullAt, maxEventDateTime)
            }
            onClick={onApplyCull}
          >
            x Confirm cull
          </Button>
          {destructiveActionsDisabled ? <PendingBlockMessage /> : null}
        </div>
      ) : null}
    </section>
  );
}

type SexTestSampleRowDraft = {
  vendorTestCode: string;
  notes: string;
};

const EMPTY_SEX_TEST_SAMPLE_ROW: SexTestSampleRowDraft = {
  vendorTestCode: "",
  notes: "",
};
const SEX_TEST_RESULT_OPTIONS = [
  { label: "Female", value: "female" },
  { label: "Male", value: "male" },
  { label: "Inconclusive", value: "inconclusive" },
] satisfies readonly { label: string; value: SexTestResultDraftValue }[];

function SexTestSamplingPanel({
  maxEventDateTime,
  mutationPending,
  onCreateSexTests,
  pendingCommands,
  plants,
  submitLabel,
}: {
  maxEventDateTime: string;
  mutationPending: boolean;
  pendingCommands: readonly PlantsPendingCommand[];
  plants: readonly PlantRow[];
  submitLabel: string;
  onCreateSexTests: SexTestMutationSubmit<CreateSexTestsInput>;
}): ReactNode {
  const [vendorName, setVendorName] = useState(DEFAULT_SEX_TEST_VENDOR);
  const [assayName, setAssayName] = useState(DEFAULT_SEX_TEST_ASSAY);
  const [sampleCollectedAt, setSampleCollectedAt] = useState(datetimeLocalNow);
  const [sampleSentAt, setSampleSentAt] = useState("");
  const [rowDrafts, setRowDrafts] = useState<Record<string, SexTestSampleRowDraft>>({});
  const rows = plants.map((plant) => ({
    plant,
    draft: rowDrafts[plant.key] ?? EMPTY_SEX_TEST_SAMPLE_ROW,
  }));
  const duplicateCodes = duplicateSexTestCodes(
    rows.map((row) => row.draft.vendorTestCode),
  );
  const hasPendingAffectedPlant = plants.some(
    (plant) => activePendingCommandsForPlant(pendingCommands, plant.key).length > 0,
  );
  const sampleCollectedValid = canSubmitEventDateTime(
    sampleCollectedAt,
    maxEventDateTime,
  );
  const sampleSentValid =
    sampleSentAt.length === 0 ||
    (canSubmitEventDateTime(sampleSentAt, maxEventDateTime) &&
      sampleSentAt >= sampleCollectedAt);
  const allRowsHaveCodes = rows.every(
    (row) => row.draft.vendorTestCode.trim().length > 0,
  );
  const canSubmit =
    plants.length > 0 &&
    vendorName.trim().length > 0 &&
    sampleCollectedValid &&
    sampleSentValid &&
    allRowsHaveCodes &&
    duplicateCodes.size === 0 &&
    !hasPendingAffectedPlant &&
    !mutationPending;

  const updateRow = (plantKey: string, patch: Partial<SexTestSampleRowDraft>) => {
    setRowDrafts((current) => ({
      ...current,
      [plantKey]: {
        ...(current[plantKey] ?? EMPTY_SEX_TEST_SAMPLE_ROW),
        ...patch,
      },
    }));
  };
  const resetDraft = () => {
    setVendorName(DEFAULT_SEX_TEST_VENDOR);
    setAssayName(DEFAULT_SEX_TEST_ASSAY);
    setSampleCollectedAt(datetimeLocalNow());
    setSampleSentAt("");
    setRowDrafts({});
  };

  return (
    <div className="grid gap-3 border-t border-rule bg-paper px-3 py-3">
      <div className="grid gap-2 md:grid-cols-[minmax(150px,0.8fr)_minmax(120px,0.55fr)_minmax(170px,0.8fr)_minmax(170px,0.8fr)]">
        <TextField
          label="Vendor"
          placeholder={DEFAULT_SEX_TEST_VENDOR}
          value={vendorName}
          onChange={setVendorName}
        />
        <TextField
          label="Assay"
          placeholder={DEFAULT_SEX_TEST_ASSAY}
          value={assayName}
          onChange={setAssayName}
        />
        <DateTimeField
          label="Collected"
          max={maxEventDateTime}
          value={sampleCollectedAt}
          onChange={setSampleCollectedAt}
        />
        <DateTimeField
          label="Sent"
          max={maxEventDateTime}
          required={false}
          value={sampleSentAt}
          onChange={setSampleSentAt}
        />
      </div>
      <div className="overflow-x-auto border border-rule-strong bg-paper">
        <div className="min-w-130 md:min-w-0">
          <div className="grid grid-cols-[150px_minmax(150px,0.8fr)_minmax(180px,1fr)] gap-2 border-b border-rule bg-paper-2 px-3 py-2 font-mono text-fs-9 uppercase tracking-caps text-ink-3">
            <span>Plant</span>
            <span>Vendor code</span>
            <span>Notes</span>
          </div>
          {rows.map(({ plant, draft }) => {
            const normalizedCode = normalizedSexTestCode(draft.vendorTestCode);
            const duplicate =
              normalizedCode.length > 0 && duplicateCodes.has(normalizedCode);
            return (
              <div
                key={plant.key}
                className="grid grid-cols-[150px_minmax(150px,0.8fr)_minmax(180px,1fr)] items-center gap-2 border-b border-rule px-3 py-2 last:border-b-0"
              >
                <div className="min-w-0">
                  <p className="truncate font-sans text-fs-12 font-semibold text-ink">
                    {plant.name}
                  </p>
                  <p className="truncate font-mono text-fs-9 uppercase tracking-caps text-ink-3">
                    {plant.key} / {formatPlantLocation(plant)}
                  </p>
                </div>
                <input
                  value={draft.vendorTestCode}
                  placeholder="FF-XY-001"
                  onChange={(event) => {
                    updateRow(plant.key, { vendorTestCode: event.target.value });
                  }}
                  className={
                    duplicate
                      ? "h-9 border border-status-err bg-paper px-2 font-sans text-fs-12 text-ink placeholder:text-ink-3"
                      : "h-9 border border-rule bg-paper px-2 font-sans text-fs-12 text-ink placeholder:text-ink-3"
                  }
                />
                <input
                  value={draft.notes}
                  placeholder="leaf punch"
                  onChange={(event) => {
                    updateRow(plant.key, { notes: event.target.value });
                  }}
                  className="h-9 border border-rule bg-paper px-2 font-sans text-fs-12 text-ink placeholder:text-ink-3"
                />
              </div>
            );
          })}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        {duplicateCodes.size > 0 ? <InlineError text="Duplicate test code" /> : null}
        {!sampleSentValid ? <InlineError text="Sent time is invalid" /> : null}
        {hasPendingAffectedPlant ? <PendingBlockMessage /> : null}
        <Button
          variant="primary"
          disabled={!canSubmit}
          onClick={() => {
            const sampleCollectedAtUtc = datetimeLocalToUtcIso(sampleCollectedAt);
            const sampleSentAtUtc =
              sampleSentAt.length === 0 ? null : datetimeLocalToUtcIso(sampleSentAt);
            if (sampleCollectedAtUtc === null) return;
            if (sampleSentAt.length > 0 && sampleSentAtUtc === null) return;
            onCreateSexTests(
              {
                idempotencyKey: createPlantsIdempotencyKey("sex-tests-bulk-create"),
                vendorName,
                assayName,
                sampleCollectedAt: sampleCollectedAtUtc,
                sampleSentAt: sampleSentAtUtc,
                tests: rows.map(({ plant, draft }) => ({
                  plantKey: plant.key,
                  vendorTestCode: draft.vendorTestCode,
                  notes: draft.notes,
                })),
              },
              resetDraft,
            );
          }}
        >
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}

function PendingSexTestResultsPanel({
  maxEventDateTime,
  mutationPending,
  onResultSexTests,
  pendingCommands,
  plants,
}: {
  maxEventDateTime: string;
  mutationPending: boolean;
  pendingCommands: readonly PlantsPendingCommand[];
  plants: readonly PlantRow[];
  onResultSexTests: SexTestMutationSubmit<ResultSexTestsInput>;
}): ReactNode {
  const rows = pendingSexTestRows(plants);
  const [resultReceivedAt, setResultReceivedAt] = useState(datetimeLocalNow);
  const [resultDrafts, setResultDrafts] = useState<
    Record<number, SexTestResultDraftValue>
  >({});
  if (rows.length === 0) return null;

  const selectedRows = rows.filter(({ sexTest }) =>
    hasSexTestResultDraft(resultDrafts[sexTest.sourceSexTestId]),
  );
  const selectedRowsWithRealIds = selectedRows.filter(({ sexTest }) =>
    hasProjectedSexTestIdentity(sexTest),
  );
  const selectedRowsHavePendingCommands = selectedRowsWithRealIds.some(
    ({ plant }) => activePendingCommandsForPlant(pendingCommands, plant.key).length > 0,
  );
  const resultReceivedAtValid = canSubmitEventDateTime(
    resultReceivedAt,
    maxEventDateTime,
  );
  const canSubmit =
    selectedRows.length > 0 &&
    selectedRows.length === selectedRowsWithRealIds.length &&
    resultReceivedAtValid &&
    !selectedRowsHavePendingCommands &&
    !mutationPending;

  return (
    <section className="grid gap-3 border border-rule-strong bg-paper-2 px-3 py-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="font-mono text-fs-10 uppercase tracking-caps text-ink">
            Pending sex-test results
          </h3>
          <p className="mt-1 font-mono text-fs-9 uppercase tracking-caps text-ink-3">
            {rows.length} pending / batch results
          </p>
        </div>
        <DateTimeField
          label="Received"
          max={maxEventDateTime}
          value={resultReceivedAt}
          onChange={setResultReceivedAt}
        />
      </div>
      <div className="grid gap-px bg-rule">
        {rows.map(({ plant, sexTest }) => {
          const sourceId = sexTest.sourceSexTestId;
          const resultValue = resultDrafts[sourceId] ?? "";
          const syncing = !hasProjectedSexTestIdentity(sexTest);
          return (
            <div
              key={`${plant.key}:${sexTest.id}`}
              className="grid gap-2 bg-paper px-3 py-2 md:grid-cols-[minmax(150px,0.8fr)_minmax(110px,0.45fr)_minmax(260px,1fr)] md:items-center"
            >
              <div className="min-w-0">
                <p className="truncate font-sans text-fs-12 font-semibold text-ink">
                  {plant.name}
                </p>
                <p className="truncate font-mono text-fs-9 uppercase tracking-caps text-ink-3">
                  {plant.key} / {formatPlantLocation(plant)}
                </p>
              </div>
              <span className="truncate font-mono text-fs-10 uppercase tracking-caps text-ink">
                {sexTest.vendorTestCode}
              </span>
              <div className="flex flex-wrap items-center gap-2">
                <Segmented
                  disabled={syncing}
                  label="Result"
                  options={SEX_TEST_RESULT_OPTIONS}
                  value={resultValue}
                  onChange={(value) => {
                    setResultDrafts((current) => ({
                      ...current,
                      [sourceId]: value,
                    }));
                  }}
                />
                {syncing ? (
                  <span className="font-mono text-fs-9 uppercase tracking-caps text-status-warn">
                    syncing
                  </span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        {!resultReceivedAtValid ? <InlineError text="Received time required" /> : null}
        {selectedRowsHavePendingCommands ? <PendingBlockMessage /> : null}
        <Button
          variant="primary"
          disabled={!canSubmit}
          onClick={() => {
            const resultReceivedAtUtc = datetimeLocalToUtcIso(resultReceivedAt);
            if (resultReceivedAtUtc === null) return;
            onResultSexTests(
              {
                idempotencyKey: createPlantsIdempotencyKey("sex-tests-bulk-result"),
                resultReceivedAt: resultReceivedAtUtc,
                results: selectedRowsWithRealIds.flatMap(({ plant, sexTest }) => {
                  const result = resultDrafts[sexTest.sourceSexTestId];
                  if (!hasSexTestResultDraft(result)) return [];
                  return [
                    {
                      plantKey: plant.key,
                      sexTestSourceId: sexTest.sourceSexTestId,
                      ...resultInputFromOption(result),
                    },
                  ];
                }),
              },
              () => {
                setResultDrafts({});
                setResultReceivedAt(datetimeLocalNow());
              },
            );
          }}
        >
          Record {selectedRows.length} result
          {selectedRows.length === 1 ? "" : "s"}
        </Button>
      </div>
    </section>
  );
}

function PendingBlockMessage(): ReactNode {
  return (
    <p className="font-mono text-fs-9 uppercase tracking-caps text-status-warn">
      affected plant command pending
    </p>
  );
}

function PendingCommandSummary({
  commands,
  mutationError,
}: {
  commands: readonly PlantsPendingCommand[];
  mutationError: string | null;
}): ReactNode {
  const visibleCommands = commands.filter((command) => {
    const error = commandErrorText(command);
    return error !== null || command.command.status !== "succeeded";
  });
  if (visibleCommands.length === 0 && mutationError === null) return null;
  return (
    <section className="border border-status-warn bg-paper-2 px-3 py-2.5">
      <div className="grid gap-1">
        {mutationError ? <InlineError text={mutationError} /> : null}
        {visibleCommands.map((command) => {
          const error = commandErrorText(command);
          return (
            <p
              key={command.commandId}
              className={
                error
                  ? "font-mono text-fs-10 uppercase tracking-caps text-status-err"
                  : "font-mono text-fs-10 uppercase tracking-caps text-status-warn"
              }
            >
              {command.label} / {error ?? command.command.status}
            </p>
          );
        })}
      </div>
    </section>
  );
}

function PendingPlantMarker({
  pendingCommands,
  plantKey,
}: {
  pendingCommands: readonly PlantsPendingCommand[];
  plantKey: string;
}): ReactNode {
  const activeCommands = activePendingCommandsForPlant(pendingCommands, plantKey);
  const failedCommands = failedCommandsForPlant(pendingCommands, plantKey);
  if (failedCommands.length > 0) {
    return (
      <span className="shrink-0 border border-status-err px-1.5 py-0.5 font-mono text-fs-9 uppercase tracking-caps text-status-err">
        failed
      </span>
    );
  }
  if (activeCommands.length === 0) return null;
  return (
    <span className="shrink-0 border border-status-warn px-1.5 py-0.5 font-mono text-fs-9 uppercase tracking-caps text-status-warn">
      pending
    </span>
  );
}

function PlantInlineError({
  pendingCommands,
  plantKey,
}: {
  pendingCommands: readonly PlantsPendingCommand[];
  plantKey: string;
}): ReactNode {
  const failedCommand = failedCommandsForPlant(pendingCommands, plantKey)[0];
  const error = failedCommand ? commandErrorText(failedCommand) : null;
  if (error === null) return null;
  return <span className="mr-2 text-status-err">{error}</span>;
}

function InlineError({ text }: { text: string }): ReactNode {
  return (
    <p className="font-mono text-fs-10 uppercase tracking-caps text-status-err">
      {text}
    </p>
  );
}

function mutationErrorText(error: Error | null): string | null {
  if (error === null) return null;
  return error.message;
}

function ToolbarButton({
  active = false,
  children,
  label,
  onClick,
  tone = "neutral",
}: {
  active?: boolean;
  children: ReactNode;
  label: string;
  onClick: () => void;
  tone?: "neutral" | "danger";
}): ReactNode {
  const className =
    tone === "danger"
      ? "h-8.5 min-w-8.5 border border-status-err px-2 font-mono text-fs-9 uppercase tracking-caps text-status-err transition hover:bg-paper"
      : active
        ? "h-8.5 min-w-8.5 border border-ink bg-paper px-2 font-mono text-fs-9 uppercase tracking-caps text-ink"
        : "h-8.5 min-w-8.5 border border-rule bg-paper px-2 font-mono text-fs-9 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink";
  return (
    <button type="button" aria-label={label} onClick={onClick} className={className}>
      {children}
    </button>
  );
}

function PlantTable({
  allChecked,
  bootstrap,
  groupBy,
  onOpenDetail,
  onSortChange,
  onToggleAll,
  onTogglePlant,
  pendingCommands,
  plants,
  selectedPlantIds,
  someChecked,
  sortState,
}: {
  allChecked: boolean;
  bootstrap: PlantsBootstrap;
  groupBy: PlantGroupBy;
  pendingCommands: readonly PlantsPendingCommand[];
  plants: readonly PlantRow[];
  selectedPlantIds: ReadonlySet<string>;
  someChecked: boolean;
  sortState: PlantTableSortState;
  onOpenDetail: (plantId: string) => void;
  onSortChange: (sort: PlantTableSortState) => void;
  onToggleAll: () => void;
  onTogglePlant: (plantId: string) => void;
}): ReactNode {
  const sortedPlants = useMemo(
    () => sortPlantsForTable(plants, sortState),
    [plants, sortState],
  );
  const groups = useMemo(
    () => groupPlants(sortedPlants, bootstrap, groupBy),
    [sortedPlants, bootstrap, groupBy],
  );

  return (
    <section className="overflow-x-auto border border-rule-strong bg-paper">
      <div className="min-w-230">
        <div
          className={`${PLANT_TABLE_GRID_CLASS} gap-2 border-b border-rule-strong bg-paper-2 px-3 py-2`}
        >
          <Checkbox
            checked={allChecked}
            indeterminate={someChecked && !allChecked}
            label="Select all visible plants"
            onChange={onToggleAll}
          />
          {PLANT_TABLE_SORT_COLUMNS.map((column) => (
            <PlantTableSortHeader
              key={column.key}
              columnKey={column.key}
              label={column.label}
              sortState={sortState}
              onSortChange={onSortChange}
            />
          ))}
        </div>
        {groups.map((group) => (
          <div key={group.key}>
            <div className="flex items-center gap-2 border-b border-rule bg-paper-3 px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-ink">
              <span aria-hidden="true">▾</span>
              <StageSquare stageKey={group.stageKey} />
              <span>{group.label}</span>
              <span className="text-ink-3">{group.plants.length}</span>
            </div>
            {group.plants.map((plant) => (
              <PlantTableRow
                key={plant.id}
                plant={plant}
                pendingCommands={pendingCommands}
                selected={selectedPlantIds.has(plant.id)}
                onOpenDetail={onOpenDetail}
                onTogglePlant={onTogglePlant}
              />
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function PlantTableRow({
  onOpenDetail,
  onTogglePlant,
  pendingCommands,
  plant,
  selected,
}: {
  plant: PlantRow;
  pendingCommands: readonly PlantsPendingCommand[];
  selected: boolean;
  onOpenDetail: (plantId: string) => void;
  onTogglePlant: (plantId: string) => void;
}): ReactNode {
  return (
    <div
      className={
        selected
          ? `${PLANT_TABLE_GRID_CLASS} items-center gap-2 border-b border-rule bg-accent-magenta/8 px-3 py-2.5 font-sans text-fs-11 last:border-b-0`
          : `${PLANT_TABLE_GRID_CLASS} items-center gap-2 border-b border-rule px-3 py-2.5 font-sans text-fs-11 last:border-b-0 hover:bg-paper-2`
      }
    >
      <Checkbox
        checked={selected}
        label={`Select ${plant.name}`}
        onChange={() => {
          onTogglePlant(plant.id);
        }}
      />
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-1.5">
          <button
            type="button"
            onClick={() => {
              onOpenDetail(plant.key);
            }}
            className="max-w-full truncate font-semibold text-ink underline-offset-2 hover:underline"
          >
            {plant.name}
          </button>
          <PendingPlantMarker pendingCommands={pendingCommands} plantKey={plant.key} />
        </div>
        <p className="mt-0.5 truncate font-mono text-fs-9 uppercase tracking-caps text-ink-3">
          {plant.key} / {formatPlantLocation(plant)}
        </p>
      </div>
      <span className="font-mono text-fs-10 text-ink">{plant.generation}</span>
      <span className="truncate font-mono text-fs-10 text-ink-3">
        {plant.parentsLabel}
      </span>
      <span className={`font-mono text-fs-14 ${sexTextClass(plant.sexKey)}`}>
        {sexGlyph(plant.sexKey)}
      </span>
      <span
        className={
          plant.culledOn
            ? "font-mono text-fs-10 text-status-err"
            : "font-mono text-fs-10 text-ink"
        }
      >
        {plant.culledOn ? shortDate(plant.culledOn) : `d${plant.stageDay}`}
      </span>
      <DateCell value={plant.germinatedOn} />
      <DateCell value={plant.vegStartedOn} />
      <DateCell value={plant.flowerStartedOn} />
      <SexTestInline plant={plant} />
      <span className="truncate text-ink-3">
        <PlantInlineError pendingCommands={pendingCommands} plantKey={plant.key} />
        {plant.lastNote}
      </span>
    </div>
  );
}

function PlantTableSortHeader({
  columnKey,
  label,
  onSortChange,
  sortState,
}: {
  columnKey: PlantTableSortKey;
  label: string;
  sortState: PlantTableSortState;
  onSortChange: (sort: PlantTableSortState) => void;
}): ReactNode {
  const activeDirection = sortState?.key === columnKey ? sortState.direction : null;
  const nextAction =
    activeDirection === "asc"
      ? "descending"
      : activeDirection === "desc"
        ? "original order"
        : "ascending";
  const indicator =
    activeDirection === "asc" ? "↑" : activeDirection === "desc" ? "↓" : "-";

  return (
    <button
      type="button"
      aria-label={`Sort ${label} ${nextAction}`}
      aria-pressed={activeDirection !== null}
      onClick={() => {
        onSortChange(nextPlantTableSortState(sortState, columnKey));
      }}
      className={
        activeDirection === null
          ? "flex h-5 min-w-0 items-center gap-1 text-left font-mono text-fs-9 uppercase tracking-caps text-ink-3 transition hover:text-ink"
          : "flex h-5 min-w-0 items-center gap-1 text-left font-mono text-fs-9 uppercase tracking-caps text-ink transition hover:text-accent-magenta"
      }
    >
      <span className="truncate">{label}</span>
      <span
        aria-hidden="true"
        className={
          activeDirection === null
            ? "ml-auto w-3 text-right text-transparent"
            : "ml-auto w-3 text-right text-accent-magenta"
        }
      >
        {indicator}
      </span>
    </button>
  );
}

function PlantBoard({
  bootstrap,
  draggingPlantId,
  onDragEnd,
  onDragStart,
  onDropPlant,
  onOpenDetail,
  onTogglePlant,
  pendingCommands,
  plants,
  selectedPlantIds,
  includeArchived,
}: {
  bootstrap: PlantsBootstrap;
  draggingPlantId: string | null;
  includeArchived: boolean;
  plants: readonly PlantRow[];
  selectedPlantIds: ReadonlySet<string>;
  onDragEnd: () => void;
  onDragStart: (plantId: string) => void;
  onDropPlant: (location: LocationOption) => void;
  onOpenDetail: (plantId: string) => void;
  onTogglePlant: (plantId: string) => void;
  pendingCommands: readonly PlantsPendingCommand[];
}): ReactNode {
  const dropLocations = bootstrap.locations.filter((location) =>
    includeArchived
      ? locationDropStageKey(location) !== null
      : canDropIntoLocation(location),
  );
  const boardStages = bootstrap.stages.filter((stage) =>
    includeArchived ? true : stage.key !== "culled" && stage.key !== "harvested",
  );
  const columns = boardStages.map((stage) => {
    const location =
      stage.key === "culled"
        ? CULLED_LOCATION
        : dropLocations.find((candidate) =>
            canUseLocationForStage(candidate, stage.key),
          );
    return {
      location,
      stage,
      plants: plants.filter((plant) => plant.stageKey === stage.key),
    };
  });
  const boardGridClass =
    columns.length === 6
      ? "grid min-w-[1020px] grid-cols-6 gap-px border border-rule-strong bg-rule"
      : "grid min-w-[850px] grid-cols-5 gap-px border border-rule-strong bg-rule";

  return (
    <section className="overflow-x-auto">
      <div className={boardGridClass}>
        {columns.map((column) => (
          <div
            key={column.stage.key}
            className={
              draggingPlantId === null
                ? "min-w-0 bg-paper"
                : "min-w-0 bg-paper outline outline-1 outline-accent-magenta"
            }
          >
            <header className="flex items-center gap-2 border-b border-rule bg-paper-2 px-3 py-2">
              <StageSquare stageKey={column.stage.key} />
              <h3 className="font-mono text-fs-10 uppercase tracking-caps text-ink">
                {column.stage.displayName}
              </h3>
              <span className="ml-auto font-mono text-fs-10 text-ink-3">
                {column.plants.length}
              </span>
            </header>
            <ul
              aria-label={`${column.stage.displayName} drop column`}
              className="flex min-h-72 flex-col gap-2 p-2.5"
              onDragOver={(event) => {
                event.preventDefault();
              }}
              onDrop={(event) => {
                event.preventDefault();
                if (
                  column.location === undefined ||
                  !canDropIntoLocation(column.location)
                ) {
                  return;
                }
                onDropPlant(column.location);
              }}
            >
              {column.plants.slice(0, 4).map((plant) => (
                <PlantBoardChip
                  key={plant.id}
                  plant={plant}
                  selected={selectedPlantIds.has(plant.id)}
                  onDragEnd={onDragEnd}
                  onDragStart={onDragStart}
                  onOpenDetail={onOpenDetail}
                  pendingCommands={pendingCommands}
                  onTogglePlant={onTogglePlant}
                />
              ))}
              {column.plants.length > 4 ? (
                <li className="font-mono text-fs-9 uppercase tracking-caps text-ink-3">
                  +{column.plants.length - 4} more
                </li>
              ) : column.plants.length === 0 ? (
                <li className="font-mono text-fs-9 uppercase tracking-caps text-ink-3">
                  —
                </li>
              ) : null}
            </ul>
          </div>
        ))}
      </div>
      <p className="mt-2 font-mono text-fs-9 uppercase tracking-caps text-ink-3">
        drag a chip, or a selected set, across a column boundary to queue a move command
      </p>
    </section>
  );
}

function PlantBoardChip({
  onDragEnd,
  onDragStart,
  onOpenDetail,
  onTogglePlant,
  pendingCommands,
  plant,
  selected,
}: {
  plant: PlantRow;
  selected: boolean;
  onDragEnd: () => void;
  onDragStart: (plantId: string) => void;
  onOpenDetail: (plantId: string) => void;
  onTogglePlant: (plantId: string) => void;
  pendingCommands: readonly PlantsPendingCommand[];
}): ReactNode {
  return (
    <li
      draggable
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", plant.id);
        onDragStart(plant.id);
      }}
      onDragEnd={onDragEnd}
      className={
        selected
          ? "cursor-grab border border-accent-magenta bg-accent-magenta/8 px-2.5 py-2 transition active:cursor-grabbing"
          : "cursor-grab border border-rule bg-paper-2 px-2.5 py-2 transition hover:border-rule-strong active:cursor-grabbing"
      }
    >
      <div className="flex min-w-0 items-start gap-2">
        <Checkbox
          checked={selected}
          label={`Select ${plant.name}`}
          onChange={() => {
            onTogglePlant(plant.id);
          }}
        />
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={() => {
              onOpenDetail(plant.key);
            }}
            className="max-w-full truncate font-sans text-fs-12 font-semibold text-ink underline-offset-2 hover:underline"
          >
            {plant.name}
          </button>
          <PendingPlantMarker pendingCommands={pendingCommands} plantKey={plant.key} />
          <p className="mt-1 truncate font-mono text-fs-9 uppercase tracking-caps text-ink-3">
            {plant.generation} /{" "}
            {plant.culledOn
              ? `culled ${shortDate(plant.culledOn)}`
              : `d${plant.stageDay}`}
          </p>
          <div className="mt-1">
            <SexTestInline compact plant={plant} />
          </div>
        </div>
        <span className={`font-mono text-fs-13 ${sexTextClass(plant.sexKey)}`}>
          {sexGlyph(plant.sexKey)}
        </span>
      </div>
    </li>
  );
}

function AddPlantsSurface({
  bootstrap,
  cloneCount,
  cloneLocationKey,
  cloneMotherId,
  cloneTakenAt,
  germinateCount,
  germinatedAt,
  germinateLocationKey,
  maxEventDateTime,
  mode,
  mutationError,
  mutationPending,
  onAddSeeds,
  onBack,
  onCloneCountChange,
  onCloneLocationChange,
  onCloneMotherChange,
  onCloneTakenAtChange,
  onGerminateCountChange,
  onGerminatedAtChange,
  onGerminateLocationChange,
  onModeChange,
  onSeedLotChange,
  onSow,
  onTakeClones,
  pendingCommands,
  plants,
  seedLots,
  selectedSeedLotId,
}: {
  bootstrap: PlantsBootstrap;
  cloneCount: number;
  cloneLocationKey: number;
  cloneMotherId: string;
  cloneTakenAt: string;
  germinateCount: number;
  germinatedAt: string;
  germinateLocationKey: number;
  maxEventDateTime: string;
  mode: AddPlantMode;
  mutationError: string | null;
  mutationPending: boolean;
  plants: readonly PlantRow[];
  seedLots: readonly SeedLotSummary[];
  selectedSeedLotId: string;
  pendingCommands: readonly PlantsPendingCommand[];
  onAddSeeds: () => void;
  onBack: () => void;
  onCloneCountChange: (count: number) => void;
  onCloneLocationChange: (sourceTentId: number) => void;
  onCloneMotherChange: (plantId: string) => void;
  onCloneTakenAtChange: (value: string) => void;
  onGerminateCountChange: (count: number) => void;
  onGerminatedAtChange: (value: string) => void;
  onGerminateLocationChange: (sourceTentId: number) => void;
  onModeChange: (mode: AddPlantMode) => void;
  onSeedLotChange: (seedLotId: string) => void;
  onSow: (seedLot: SeedLotSummary, location: LocationOption) => void;
  onTakeClones: (mother: PlantRow, location: LocationOption) => void;
}): ReactNode {
  const selectedSeedLot =
    seedLots.find((lot) => lot.id === selectedSeedLotId) ?? seedLots[0];
  const germLocations = bootstrap.locations;
  const germLocation =
    germLocations.find((location) => location.sourceTentId === germinateLocationKey) ??
    germLocations[0] ??
    bootstrap.locations[0] ??
    FALLBACK_LOCATION;
  const cloneLocations = bootstrap.locations;
  const cloneLocation =
    cloneLocations.find((location) => location.sourceTentId === cloneLocationKey) ??
    cloneLocations[0] ??
    bootstrap.locations[0] ??
    FALLBACK_LOCATION;
  const cloneMothers = plants.filter(
    (plant) => isActivePlant(plant) && plant.stageKey !== "germinating",
  );
  const mother =
    cloneMothers.find((plant) => plant.id === cloneMotherId) ?? cloneMothers[0];
  const clonePrefix = clonePrefixFor(mother?.name ?? "mother");

  return (
    <>
      <SurfaceHeader
        description="Queue germination or clone commands; local Dirt assigns plant keys."
        title="Add plants"
        onBack={onBack}
      />
      <div className="flex">
        <Segmented
          label="Mode"
          options={[
            { label: "⌗ Germinate", value: "germinate" },
            { label: "✂ Clone", value: "clone" },
          ]}
          value={mode}
          onChange={onModeChange}
        />
      </div>
      <PendingCommandSummary
        commands={pendingCommands.filter(
          (command) =>
            command.operation === "germinate" || command.operation === "clone",
        )}
        mutationError={mutationError}
      />
      <section className="grid gap-px border border-rule-strong bg-rule md:grid-cols-[minmax(360px,1fr)_minmax(280px,360px)]">
        <div className="bg-paper-2 p-5">
          {mode === "germinate" ? (
            <div className="grid gap-4">
              <div className="flex items-end gap-2">
                <SelectField
                  label="Seed lot"
                  value={selectedSeedLot?.id ?? ""}
                  options={seedLots.map((lot) => ({ label: lot.label, value: lot.id }))}
                  onChange={onSeedLotChange}
                />
                <Button variant="secondary" onClick={onAddSeeds}>
                  + Add seeds
                </Button>
              </div>
              <NumberStepper
                label="Count"
                max={96}
                min={1}
                value={germinateCount}
                onChange={onGerminateCountChange}
              />
              <DateTimeField
                label="Germinated at"
                max={maxEventDateTime}
                value={germinatedAt}
                onChange={onGerminatedAtChange}
              />
              <SelectField
                label="Into tent"
                value={germLocation.sourceTentId}
                options={germLocations.map((location) => ({
                  label: location.displayName,
                  value: location.sourceTentId,
                }))}
                onChange={onGerminateLocationChange}
              />
              <ReadOnlyFact
                label="Label prefix"
                value={
                  selectedSeedLot
                    ? readonlyPlantPrefixPreview(selectedSeedLot.prefix)
                    : readonlyPlantPrefixPreview("NEW")
                }
              />
            </div>
          ) : (
            <div className="grid gap-4">
              <SelectField
                label="Mother plant"
                value={mother?.id ?? ""}
                options={cloneMothers.map((plant) => ({
                  label: `${plant.name} ${sexGlyph(plant.sexKey)}`,
                  value: plant.id,
                }))}
                onChange={onCloneMotherChange}
              />
              <NumberStepper
                label="Count"
                max={48}
                min={1}
                value={cloneCount}
                onChange={onCloneCountChange}
              />
              <DateTimeField
                label="Taken at"
                max={maxEventDateTime}
                value={cloneTakenAt}
                onChange={onCloneTakenAtChange}
              />
              <SelectField
                label="Into tent"
                value={cloneLocation.sourceTentId}
                options={cloneLocations.map((location) => ({
                  label: location.displayName,
                  value: location.sourceTentId,
                }))}
                onChange={onCloneLocationChange}
              />
              <ReadOnlyFact
                label="Label prefix"
                value={readonlyPlantPrefixPreview(clonePrefix)}
              />
            </div>
          )}
        </div>
        <div className="bg-paper p-4">
          <h3 className="font-sans text-fs-13 font-semibold text-ink">Preview</h3>
          <ReadOnlyPrefixPreview
            count={mode === "germinate" ? germinateCount : cloneCount}
            prefix={
              mode === "germinate"
                ? readonlyPlantPrefixPreview(selectedSeedLot?.prefix ?? "NEW")
                : readonlyPlantPrefixPreview(clonePrefix)
            }
          />
          <p className="mt-4 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            {mode === "germinate"
              ? `${selectedSeedLot?.parentsLabel ?? "No seed lot"} / gen ${selectedSeedLot?.generation ?? "?"} / ${germLocation.displayName}`
              : `clone of ${mother?.name ?? "mother"} / gen ${mother?.generation ?? "?"} / sex ${mother ? sexLabel(mother.sexKey) : "unknown"}`}
          </p>
          <div className="mt-5 flex justify-end">
            {mode === "germinate" ? (
              <Button
                variant="primary"
                disabled={
                  !selectedSeedLot ||
                  mutationPending ||
                  !canSubmitEventDateTime(germinatedAt, maxEventDateTime)
                }
                onClick={() => {
                  if (selectedSeedLot) onSow(selectedSeedLot, germLocation);
                }}
              >
                Sow {germinateCount} plants →
              </Button>
            ) : (
              <Button
                variant="primary"
                disabled={
                  !mother ||
                  mutationPending ||
                  !canSubmitEventDateTime(cloneTakenAt, maxEventDateTime)
                }
                onClick={() => {
                  if (mother) onTakeClones(mother, cloneLocation);
                }}
              >
                Take {cloneCount} clones →
              </Button>
            )}
          </div>
        </div>
      </section>
    </>
  );
}

function PlantJournalDetail({
  detail,
  factActionsDisabled,
  factsDraft,
  factsEditing,
  factsMutationError,
  factsMutationPending,
  maxEventDateTime,
  mutationError,
  mutationPending,
  noteTargetCount,
  noteText,
  onBack,
  onCancelFactsEdit,
  onCreateSexTests,
  onFactsDraftChange,
  onLogNote,
  onNoteTextChange,
  onResultSexTests,
  onSaveFacts,
  onStartFactsEdit,
  onUpdateSexTest,
  pendingCommands,
  pendingNotes,
  sexTestActionsDisabled,
  sexTestMutationError,
  sexTestMutationPending,
}: {
  detail: PlantDetail;
  factActionsDisabled: boolean;
  factsDraft: DetailFactsDraft;
  factsEditing: boolean;
  factsMutationError: string | null;
  factsMutationPending: boolean;
  maxEventDateTime: string;
  mutationError: string | null;
  mutationPending: boolean;
  noteTargetCount: number;
  noteText: string;
  onBack: () => void;
  onCancelFactsEdit: () => void;
  onCreateSexTests: SexTestMutationSubmit<CreateSexTestsInput>;
  onFactsDraftChange: (draft: DetailFactsDraft) => void;
  onLogNote: () => void;
  onNoteTextChange: (text: string) => void;
  onResultSexTests: SexTestMutationSubmit<ResultSexTestsInput>;
  onSaveFacts: () => void;
  onStartFactsEdit: () => void;
  onUpdateSexTest: SexTestMutationSubmit<UpdateSexTestInput>;
  pendingCommands: readonly PlantsPendingCommand[];
  pendingNotes: readonly PendingTimelineNote[];
  sexTestActionsDisabled: boolean;
  sexTestMutationError: string | null;
  sexTestMutationPending: boolean;
}): ReactNode {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const sexTestWorkPanelRef = useRef<HTMLDivElement | null>(null);
  const [sexTestActionState, setSexTestActionState] = useState<{
    action: SexTestHistoryAction;
    plantKey: string;
  }>({ action: null, plantKey: detail.plant.key });
  const sexTestAction =
    sexTestActionState.plantKey === detail.plant.key ? sexTestActionState.action : null;
  const setSexTestAction = (nextAction: SexTestHistoryAction) => {
    setSexTestActionState({ action: nextAction, plantKey: detail.plant.key });
  };
  useEffect(() => {
    if (sexTestAction === null) return;
    sexTestWorkPanelRef.current?.scrollIntoView({ block: "start" });
  }, [sexTestAction]);

  return (
    <>
      <section className="flex flex-wrap items-center gap-2 border-b border-rule-strong pb-4">
        <button
          type="button"
          onClick={onBack}
          className="border border-rule px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink"
        >
          Back to plants
        </button>
        <StageSquare stageKey={detail.plant.stageKey} />
        <h2 className="font-sans text-fs-22 font-semibold text-ink">
          {detail.plant.name}
        </h2>
        <Pill>{detail.plant.generation}</Pill>
        <Pill>{sexLabel(detail.plant.sexKey)}</Pill>
        <Pill>{stageLabel(detail.plant)}</Pill>
      </section>
      <section className="grid gap-px border border-rule-strong bg-rule md:grid-cols-[248px_minmax(0,1fr)_256px]">
        <aside className="bg-paper-2 p-4">
          <div className="grid grid-cols-2 gap-px bg-rule">
            <Fact label="Generation" value={detail.plant.generation} />
            <Fact label="Sex" value={sexLabel(detail.plant.sexKey)} />
            <Fact
              label={detail.plant.isClone ? "Taken" : "Germinated"}
              value={shortDateOrDash(
                detail.plant.isClone ? detail.plant.takenOn : detail.plant.germinatedOn,
              )}
            />
            {detail.plant.isClone ? (
              <Fact label="Rooted" value={shortDateOrDash(detail.plant.rootedOn)} />
            ) : null}
            <Fact label="Vegged" value={shortDateOrDash(detail.plant.vegStartedOn)} />
            <Fact
              label="Flowered"
              value={shortDateOrDash(detail.plant.flowerStartedOn)}
            />
            <Fact label="Culled" value={shortDateOrDash(detail.plant.culledOn)} />
            <Fact label="Harvested" value={shortDateOrDash(detail.plant.harvestedOn)} />
            <Fact
              label="Selected"
              value={shortDateOrDash(detail.plant.selectedForBreedingOn)}
            />
            <Fact label="Location" value={formatPlantLocation(detail.plant)} />
          </div>
          <PlantFactsEditor
            disabled={factActionsDisabled}
            draft={factsDraft}
            editing={factsEditing}
            maxEventDateTime={maxEventDateTime}
            mutationError={factsMutationError}
            mutationPending={factsMutationPending}
            plant={detail.plant}
            onCancel={onCancelFactsEdit}
            onDraftChange={onFactsDraftChange}
            onEdit={onStartFactsEdit}
            onSave={onSaveFacts}
          />
          <PlantSexTestHistory
            action={sexTestAction}
            disabled={sexTestActionsDisabled}
            mutationError={sexTestMutationError}
            mutationPending={sexTestMutationPending}
            plant={detail.plant}
            onActionChange={setSexTestAction}
          />
          <div className="mt-4 border border-rule bg-paper p-3">
            <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              Lineage
            </p>
            <p className="mt-2 text-fs-12 leading-ui text-ink-2">
              ↑ {detail.lineage.parents}
            </p>
            <p className="mt-2 font-sans text-fs-13 font-semibold text-ink">
              {detail.plant.name}
            </p>
            <p className="mt-2 text-fs-12 leading-ui text-ink-2">
              ↓ {detail.lineage.offspring}
            </p>
          </div>
        </aside>
        <section className="bg-paper p-4">
          {sexTestAction ? (
            <div ref={sexTestWorkPanelRef}>
              <SexTestWorkPanel
                action={sexTestAction}
                disabled={sexTestActionsDisabled}
                maxEventDateTime={maxEventDateTime}
                mutationError={sexTestMutationError}
                mutationPending={sexTestMutationPending}
                pendingCommands={pendingCommands}
                plant={detail.plant}
                onCancel={() => {
                  setSexTestAction(null);
                }}
                onCreateSexTests={onCreateSexTests}
                onResultSexTests={onResultSexTests}
                onUpdateSexTest={onUpdateSexTest}
              />
            </div>
          ) : null}
          <div
            className={
              sexTestAction
                ? "mt-4 border border-rule bg-paper-2 p-3"
                : "border border-rule bg-paper-2 p-3"
            }
          >
            <textarea
              value={noteText}
              onChange={(event) => {
                onNoteTextChange(event.target.value);
              }}
              placeholder="Log an observation - leaves curling, vigour, pheno notes..."
              className="min-h-20 w-full resize-y border border-rule bg-paper p-3 font-sans text-fs-12 text-ink placeholder:text-ink-3"
            />
            <div className="mt-2 flex flex-wrap justify-end gap-2">
              {mutationError ? <InlineError text={mutationError} /> : null}
              <Button variant="secondary" disabled>
                + Attach photo
              </Button>
              <Button
                variant="primary"
                disabled={noteText.trim().length === 0 || mutationPending}
                onClick={onLogNote}
              >
                {noteTargetCount === 1
                  ? "Log note"
                  : `Log note on ${noteTargetCount} plants`}
              </Button>
            </div>
          </div>
          <ol className="mt-4 grid gap-3">
            {pendingNotes.map((note) => (
              <PendingTimelineEvent key={note.id} note={note} />
            ))}
            {detail.events.map((event) => (
              <TimelineEvent key={event.id} event={event} />
            ))}
          </ol>
        </section>
        <aside className="bg-paper-2 p-4">
          <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            Environment
          </p>
          <h3 className="mt-1 font-sans text-fs-14 font-semibold text-ink">
            {formatPlantLocation(detail.plant)}
          </h3>
          <p className="mt-1 font-mono text-fs-9 uppercase tracking-caps text-ink-3">
            {detail.telemetry.length} telemetry stream
            {detail.telemetry.length === 1 ? "" : "s"}
          </p>
          <div className="mt-4 border border-rule bg-paper p-3">
            <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              Substrate moisture
            </p>
            <p className="mt-1 font-mono text-fs-22 text-status-warn">
              {detail.metricHistory.find((metric) => metric.key === "moisture")
                ?.value ?? "0"}
              %
            </p>
            <div className="mt-2 h-2 border border-rule bg-paper-3">
              <div className="h-full w-2/5 bg-status-warn" />
            </div>
          </div>
          <div className="mt-3 grid gap-px bg-rule">
            {detail.metricHistory
              .filter((metric) => metric.key !== "moisture")
              .map((metric) => (
                <SparklineCard
                  key={metric.key}
                  hoverIndex={hoverIndex}
                  metric={metric}
                  onHoverIndex={setHoverIndex}
                />
              ))}
          </div>
          <button
            type="button"
            className="mt-4 w-full border border-dashed border-rule-strong px-3 py-3 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:text-ink"
          >
            Attach RS485 probe
          </button>
        </aside>
      </section>
      {detail.wikiContent === null ? (
        <section className="border border-rule-strong bg-paper-2 p-4">
          <h2 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
            Wiki
          </h2>
          <p className="mt-3 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            No projected wiki content for this plant.
          </p>
        </section>
      ) : (
        <section className="border border-rule-strong bg-paper-2 p-4">
          <header className="mb-4 flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-3">
            <h2 className="font-sans text-fs-16 font-semibold text-ink">
              {detail.wikiContent.title}
            </h2>
            <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              {formatDateTime(detail.wikiContent.sourceUpdatedAt)}
            </span>
          </header>
          <MarkdownDocument bodyMarkdown={detail.wikiContent.bodyMarkdown} />
        </section>
      )}
    </>
  );
}

function PlantFactsEditor({
  disabled,
  draft,
  editing,
  maxEventDateTime,
  mutationError,
  mutationPending,
  onCancel,
  onDraftChange,
  onEdit,
  onSave,
  plant,
}: {
  disabled: boolean;
  draft: DetailFactsDraft;
  editing: boolean;
  maxEventDateTime: string;
  mutationError: string | null;
  mutationPending: boolean;
  plant: PlantRow;
  onCancel: () => void;
  onDraftChange: (draft: DetailFactsDraft) => void;
  onEdit: () => void;
  onSave: () => void;
}): ReactNode {
  const saveDisabled =
    disabled || !canSaveDetailFactsDraft(plant, draft, maxEventDateTime);
  const updateDraft = (patch: Partial<DetailFactsDraft>) => {
    onDraftChange({ ...draft, ...patch });
  };

  return (
    <div className="mt-4 border border-rule bg-paper p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          Plant facts
        </p>
        {mutationPending ? (
          <p className="font-mono text-fs-9 uppercase tracking-caps text-status-warn">
            queueing
          </p>
        ) : editing ? null : (
          <button
            type="button"
            disabled={disabled}
            onClick={onEdit}
            className="border border-rule px-2 py-1 font-mono text-fs-9 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink disabled:cursor-not-allowed disabled:text-ink-3"
          >
            Edit
          </button>
        )}
      </div>
      {editing ? (
        <div className="mt-3 grid gap-3 border-t border-rule pt-3">
          <SelectField
            label="Sex"
            options={[
              { label: "Unsexed", value: "unknown" },
              { label: "Male", value: "male" },
              { label: "Female", value: "female" },
              { label: "Herm", value: "herm" },
              { label: "Reversed", value: "reversed" },
            ]}
            value={draft.sexKey}
            onChange={(sexKey) => {
              updateDraft({ sexKey });
            }}
          />
          <div className="grid gap-2">
            {plant.isClone ? (
              <>
                <FactDateEditRow
                  label="Taken"
                  max={maxEventDateTime}
                  value={draft.takenAt}
                  onChange={(takenAt) => {
                    updateDraft({ takenAt });
                  }}
                />
                <FactDateEditRow
                  label="Rooted"
                  max={maxEventDateTime}
                  value={draft.rootedAt}
                  onChange={(rootedAt) => {
                    updateDraft({ rootedAt });
                  }}
                />
              </>
            ) : (
              <FactDateEditRow
                label="Germ"
                max={maxEventDateTime}
                value={draft.germinatedAt}
                onChange={(germinatedAt) => {
                  updateDraft({ germinatedAt });
                }}
              />
            )}
            <FactDateEditRow
              label="Veg"
              max={maxEventDateTime}
              value={draft.vegStartedAt}
              onChange={(vegStartedAt) => {
                updateDraft({ vegStartedAt });
              }}
            />
            <FactDateEditRow
              label="Flower"
              max={maxEventDateTime}
              value={draft.flowerStartedAt}
              onChange={(flowerStartedAt) => {
                updateDraft({ flowerStartedAt });
              }}
            />
            <FactDateEditRow
              label="Cull"
              max={maxEventDateTime}
              value={draft.culledAt}
              onChange={(culledAt) => {
                updateDraft({ culledAt });
              }}
            />
            <TextField
              label="Cull reason"
              value={draft.culledReason}
              placeholder="selected male"
              onChange={(culledReason) => {
                updateDraft({ culledReason });
              }}
            />
            <FactDateEditRow
              label="Harvest"
              max={maxEventDateTime}
              value={draft.harvestedAt}
              onChange={(harvestedAt) => {
                updateDraft({ harvestedAt });
              }}
            />
            <FactDateEditRow
              label="Selected"
              max={maxEventDateTime}
              value={draft.selectedForBreedingAt}
              onChange={(selectedForBreedingAt) => {
                updateDraft({ selectedForBreedingAt });
              }}
            />
            <TextField
              label="Selection reason"
              value={draft.selectedForBreedingReason}
              placeholder="keeper candidate"
              onChange={(selectedForBreedingReason) => {
                updateDraft({ selectedForBreedingReason });
              }}
            />
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-rule pt-3">
            {mutationError ? <InlineError text={mutationError} /> : null}
            <Button variant="secondary" disabled={disabled} onClick={onCancel}>
              Cancel
            </Button>
            <Button variant="primary" disabled={saveDisabled} onClick={onSave}>
              Save changes
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-2 grid gap-px bg-rule">
          <FactReadRow label="Sex" value={sexLabel(plant.sexKey)} />
          {plant.isClone ? (
            <>
              <FactReadRow label="Taken" value={shortDateOrDash(plant.takenOn)} />
              <FactReadRow label="Rooted" value={shortDateOrDash(plant.rootedOn)} />
            </>
          ) : (
            <FactReadRow label="Germ" value={shortDateOrDash(plant.germinatedOn)} />
          )}
          <FactReadRow label="Veg" value={shortDateOrDash(plant.vegStartedOn)} />
          <FactReadRow label="Flower" value={shortDateOrDash(plant.flowerStartedOn)} />
          <FactReadRow label="Cull" value={shortDateOrDash(plant.culledOn)} />
          <FactReadRow label="Cull why" value={plant.culledReason?.trim() || "-"} />
          <FactReadRow label="Harvest" value={shortDateOrDash(plant.harvestedOn)} />
          <FactReadRow
            label="Selected"
            value={shortDateOrDash(plant.selectedForBreedingOn)}
          />
          <FactReadRow
            label="Select why"
            value={plant.selectedForBreedingReason?.trim() || "-"}
          />
        </div>
      )}
      {disabled && !mutationPending ? <PendingBlockMessage /> : null}
    </div>
  );
}

type SexTestHistoryAction =
  | { kind: "add" }
  | { kind: "edit"; sexTest: PlantSexTest }
  | { kind: "result"; sexTest: PlantSexTest }
  | null;
type ActiveSexTestHistoryAction = Exclude<SexTestHistoryAction, null>;
type SexTestEditDraft = {
  vendorName: string;
  assayName: string;
  vendorTestCode: string;
  sampleCollectedAt: string;
  sampleSentAt: string;
  notes: string;
};

function PlantSexTestHistory({
  action,
  disabled,
  mutationError,
  mutationPending,
  onActionChange,
  plant,
}: {
  action: SexTestHistoryAction;
  disabled: boolean;
  mutationError: string | null;
  mutationPending: boolean;
  plant: PlantRow;
  onActionChange: (action: SexTestHistoryAction) => void;
}): ReactNode {
  const addActive = action?.kind === "add";

  return (
    <div className="mt-4 border border-rule bg-paper p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          Sex tests
        </p>
        <button
          type="button"
          disabled={disabled || mutationPending}
          onClick={() => {
            onActionChange(addActive ? null : { kind: "add" });
          }}
          className={
            addActive
              ? "border border-rule-strong bg-paper-2 px-2 py-1 font-mono text-fs-9 uppercase tracking-caps text-ink transition disabled:cursor-not-allowed disabled:text-ink-3"
              : "border border-rule px-2 py-1 font-mono text-fs-9 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink disabled:cursor-not-allowed disabled:text-ink-3"
          }
        >
          Add
        </button>
      </div>
      {mutationError ? (
        <div className="mt-2">
          <InlineError text={mutationError} />
        </div>
      ) : null}
      <div className="mt-3 grid gap-px bg-rule">
        {plant.sexTests.length === 0 ? (
          <div className="bg-paper-2 px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            Untested
          </div>
        ) : (
          plant.sexTests.map((sexTest) => {
            const pending = sexTestState(sexTest) === "pending";
            const syncing = pending && !hasProjectedSexTestIdentity(sexTest);
            return (
              <div key={sexTest.id} className="bg-paper-2 px-3 py-2">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="truncate font-mono text-fs-10 uppercase tracking-caps text-ink">
                    {sexTest.vendorTestCode}
                  </span>
                  <span
                    className={`border px-1.5 py-0.5 font-mono text-fs-9 uppercase tracking-caps ${sexTestStatusClass(sexTest)}`}
                  >
                    {sexTestStatusLabel(sexTest)}
                  </span>
                </div>
                <p className="mt-1 truncate font-mono text-fs-9 uppercase tracking-caps text-ink-3">
                  {sexTest.vendorName} / {sexTest.assayName ?? "assay n/a"} / sample{" "}
                  {formatDateTime(sexTest.sampleCollectedAt)}
                </p>
                <p className="mt-1 truncate font-mono text-fs-9 uppercase tracking-caps text-ink-3">
                  sent{" "}
                  {sexTest.sampleSentAt ? formatDateTime(sexTest.sampleSentAt) : "-"} /
                  received{" "}
                  {sexTest.resultReceivedAt
                    ? formatDateTime(sexTest.resultReceivedAt)
                    : "-"}
                </p>
                {sexTest.notes ? (
                  <p className="mt-1 truncate text-fs-11 text-ink-2">{sexTest.notes}</p>
                ) : null}
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={
                      disabled ||
                      mutationPending ||
                      !hasProjectedSexTestIdentity(sexTest)
                    }
                    onClick={() => {
                      onActionChange({ kind: "edit", sexTest });
                    }}
                    className="border border-rule bg-paper px-2 py-1 font-mono text-fs-9 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink disabled:cursor-not-allowed disabled:text-ink-3"
                  >
                    Edit
                  </button>
                  {pending ? (
                    <button
                      type="button"
                      disabled={disabled || mutationPending || syncing}
                      onClick={() => {
                        onActionChange({ kind: "result", sexTest });
                      }}
                      className="border border-rule bg-paper px-2 py-1 font-mono text-fs-9 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink disabled:cursor-not-allowed disabled:text-ink-3"
                    >
                      {syncing ? "Syncing" : "Result"}
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
      {disabled && !mutationPending ? <PendingBlockMessage /> : null}
    </div>
  );
}

function SexTestWorkPanel({
  action,
  disabled,
  maxEventDateTime,
  mutationError,
  mutationPending,
  onCancel,
  onCreateSexTests,
  onResultSexTests,
  onUpdateSexTest,
  pendingCommands,
  plant,
}: {
  action: ActiveSexTestHistoryAction;
  disabled: boolean;
  maxEventDateTime: string;
  mutationError: string | null;
  mutationPending: boolean;
  pendingCommands: readonly PlantsPendingCommand[];
  plant: PlantRow;
  onCancel: () => void;
  onCreateSexTests: SexTestMutationSubmit<CreateSexTestsInput>;
  onResultSexTests: SexTestMutationSubmit<ResultSexTestsInput>;
  onUpdateSexTest: SexTestMutationSubmit<UpdateSexTestInput>;
}): ReactNode {
  const title =
    action.kind === "add"
      ? "Add sex test"
      : action.kind === "edit"
        ? "Edit sex test"
        : "Record sex-test result";

  return (
    <section className="border border-rule bg-paper-2">
      <header className="flex flex-wrap items-start justify-between gap-2 px-3 py-3">
        <div className="min-w-0">
          <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            Sex test
          </p>
          <h3 className="mt-1 font-sans text-fs-16 font-semibold text-ink">{title}</h3>
          <p className="mt-1 truncate font-mono text-fs-9 uppercase tracking-caps text-ink-3">
            {plant.name} / {plant.key}
          </p>
        </div>
        {action.kind === "add" ? (
          <Button variant="secondary" disabled={mutationPending} onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </header>
      {mutationError ? (
        <div className="px-3 pb-3">
          <InlineError text={mutationError} />
        </div>
      ) : null}
      {action.kind === "add" ? (
        <SexTestSamplingPanel
          maxEventDateTime={maxEventDateTime}
          mutationPending={mutationPending}
          pendingCommands={pendingCommands}
          plants={[plant]}
          submitLabel="Create test"
          onCreateSexTests={(input, onSuccess) => {
            onCreateSexTests(input, () => {
              onSuccess();
              onCancel();
            });
          }}
        />
      ) : null}
      {action.kind === "edit" ? (
        <div className="bg-paper px-3 pb-3">
          <SexTestEditForm
            disabled={disabled || mutationPending}
            maxEventDateTime={maxEventDateTime}
            plant={plant}
            sexTest={action.sexTest}
            onCancel={onCancel}
            onUpdateSexTest={(input, onSuccess) => {
              onUpdateSexTest(input, () => {
                onSuccess();
                onCancel();
              });
            }}
          />
        </div>
      ) : null}
      {action.kind === "result" ? (
        <div className="bg-paper px-3 pb-3">
          <SexTestResultForm
            disabled={
              disabled ||
              mutationPending ||
              !hasProjectedSexTestIdentity(action.sexTest)
            }
            maxEventDateTime={maxEventDateTime}
            plant={plant}
            sexTest={action.sexTest}
            onCancel={onCancel}
            onResultSexTests={(input, onSuccess) => {
              onResultSexTests(input, () => {
                onSuccess();
                onCancel();
              });
            }}
          />
        </div>
      ) : null}
    </section>
  );
}

function SexTestEditForm({
  disabled,
  maxEventDateTime,
  onCancel,
  onUpdateSexTest,
  plant,
  sexTest,
}: {
  disabled: boolean;
  maxEventDateTime: string;
  plant: PlantRow;
  sexTest: PlantSexTest;
  onCancel: () => void;
  onUpdateSexTest: SexTestMutationSubmit<UpdateSexTestInput>;
}): ReactNode {
  const [draft, setDraft] = useState(() => sexTestEditDraftFromTest(sexTest));

  useEffect(() => {
    setDraft(sexTestEditDraftFromTest(sexTest));
  }, [sexTest]);

  const sampleCollectedValid = canSubmitEventDateTime(
    draft.sampleCollectedAt,
    maxEventDateTime,
  );
  const sampleSentValid =
    draft.sampleSentAt.length === 0 ||
    (canSubmitEventDateTime(draft.sampleSentAt, maxEventDateTime) &&
      draft.sampleSentAt >= draft.sampleCollectedAt);
  const canSave =
    !disabled &&
    draft.vendorName.trim().length > 0 &&
    draft.vendorTestCode.trim().length > 0 &&
    sampleCollectedValid &&
    sampleSentValid &&
    sexTestEditDraftChanged(sexTest, draft);

  const updateDraft = (patch: Partial<SexTestEditDraft>) => {
    setDraft((current) => ({ ...current, ...patch }));
  };

  return (
    <div className="mt-3 grid gap-3 border-t border-rule pt-3">
      <TextField
        label="Vendor"
        placeholder={DEFAULT_SEX_TEST_VENDOR}
        value={draft.vendorName}
        onChange={(vendorName) => {
          updateDraft({ vendorName });
        }}
      />
      <TextField
        label="Assay"
        placeholder={DEFAULT_SEX_TEST_ASSAY}
        value={draft.assayName}
        onChange={(assayName) => {
          updateDraft({ assayName });
        }}
      />
      <TextField
        label="Vendor code"
        placeholder="FF-XY-001"
        value={draft.vendorTestCode}
        onChange={(vendorTestCode) => {
          updateDraft({ vendorTestCode });
        }}
      />
      <FactDateEditRow
        label="Collected"
        max={maxEventDateTime}
        value={draft.sampleCollectedAt}
        onChange={(sampleCollectedAt) => {
          updateDraft({ sampleCollectedAt });
        }}
      />
      <FactDateEditRow
        label="Sent"
        max={maxEventDateTime}
        value={draft.sampleSentAt}
        onChange={(sampleSentAt) => {
          updateDraft({ sampleSentAt });
        }}
      />
      <TextField
        label="Notes"
        placeholder="leaf punch"
        value={draft.notes}
        onChange={(notes) => {
          updateDraft({ notes });
        }}
      />
      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-rule pt-3">
        {!sampleSentValid ? <InlineError text="Sent time is invalid" /> : null}
        <Button variant="secondary" disabled={disabled} onClick={onCancel}>
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={!canSave}
          onClick={() => {
            const sampleCollectedAtUtc = datetimeLocalToUtcIso(draft.sampleCollectedAt);
            const sampleSentAtUtc =
              draft.sampleSentAt.length === 0
                ? null
                : datetimeLocalToUtcIso(draft.sampleSentAt);
            if (sampleCollectedAtUtc === null) return;
            if (draft.sampleSentAt.length > 0 && sampleSentAtUtc === null) return;
            onUpdateSexTest(
              {
                idempotencyKey: createPlantsIdempotencyKey("sex-test-update"),
                plantKey: plant.key,
                sexTestId: sexTest.id,
                sexTestSourceId: sexTest.sourceSexTestId,
                vendorName: draft.vendorName,
                assayName: draft.assayName,
                vendorTestCode: draft.vendorTestCode,
                sampleCollectedAt: sampleCollectedAtUtc,
                sampleSentAt: sampleSentAtUtc,
                resultReceivedAt: sexTest.resultReceivedAt,
                resultSexKey: conclusiveSexTestResultKey(sexTest.resultSexKey),
                isInconclusive: sexTest.isInconclusive,
                notes: draft.notes,
              },
              () => {},
            );
          }}
        >
          Save test
        </Button>
      </div>
    </div>
  );
}

function SexTestResultForm({
  disabled,
  maxEventDateTime,
  onCancel,
  onResultSexTests,
  plant,
  sexTest,
}: {
  disabled: boolean;
  maxEventDateTime: string;
  plant: PlantRow;
  sexTest: PlantSexTest;
  onCancel: () => void;
  onResultSexTests: SexTestMutationSubmit<ResultSexTestsInput>;
}): ReactNode {
  const [resultReceivedAt, setResultReceivedAt] = useState(datetimeLocalNow);
  const [result, setResult] = useState<SexTestResultDraftValue>("");
  const canSave =
    !disabled &&
    result !== "" &&
    canSubmitEventDateTime(resultReceivedAt, maxEventDateTime);

  return (
    <div className="mt-3 grid gap-3 border-t border-rule pt-3">
      <DateTimeField
        label="Received"
        max={maxEventDateTime}
        value={resultReceivedAt}
        onChange={setResultReceivedAt}
      />
      <Segmented
        disabled={disabled}
        label="Result"
        options={SEX_TEST_RESULT_OPTIONS}
        value={result}
        onChange={setResult}
      />
      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-rule pt-3">
        <Button variant="secondary" disabled={disabled} onClick={onCancel}>
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={!canSave}
          onClick={() => {
            const resultReceivedAtUtc = datetimeLocalToUtcIso(resultReceivedAt);
            if (result === "" || resultReceivedAtUtc === null) return;
            onResultSexTests(
              {
                idempotencyKey: createPlantsIdempotencyKey("sex-tests-bulk-result"),
                resultReceivedAt: resultReceivedAtUtc,
                results: [
                  {
                    plantKey: plant.key,
                    sexTestSourceId: sexTest.sourceSexTestId,
                    ...resultInputFromOption(result),
                  },
                ],
              },
              () => {},
            );
          }}
        >
          Save result
        </Button>
      </div>
    </div>
  );
}

function FactReadRow({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div className="grid min-h-9 grid-cols-[72px_minmax(0,1fr)] items-center gap-2 bg-paper-2 px-3 py-2">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <span className="truncate text-right font-sans text-fs-12 font-semibold text-ink">
        {value}
      </span>
    </div>
  );
}

function FactDateEditRow({
  label,
  max,
  onChange,
  value,
}: {
  label: string;
  max: string;
  onChange: (value: string) => void;
  value: string;
}): ReactNode {
  const invalid = value.length > 0 && !canSubmitEventDateTime(value, max);
  return (
    <div className="grid gap-1">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          {label}
        </span>
        <button
          type="button"
          disabled={value.length === 0}
          onClick={() => {
            onChange("");
          }}
          className="font-mono text-fs-9 uppercase tracking-caps text-ink-3 transition hover:text-ink disabled:text-ink-3"
        >
          Clear
        </button>
      </div>
      <input
        type="datetime-local"
        max={max}
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className={
          invalid
            ? "h-9 w-full border border-status-err bg-paper px-2 font-sans text-fs-12 text-ink"
            : "h-9 w-full border border-rule bg-paper px-2 font-sans text-fs-12 text-ink"
        }
      />
    </div>
  );
}

function PendingTimelineEvent({ note }: { note: PendingTimelineNote }): ReactNode {
  return (
    <li className="grid grid-cols-[78px_1fr] gap-3">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-status-warn">
        {note.dateLabel}
      </span>
      <div className="border-b border-dashed border-status-warn pb-3">
        <p className="flex items-center gap-2 font-mono text-fs-10 uppercase tracking-caps text-status-warn">
          <EventSquare tag="note" />
          note / {note.statusLabel}
        </p>
        <p className="mt-1 text-fs-12 leading-ui text-ink">{note.body}</p>
        {note.error ? <InlineError text={note.error} /> : null}
      </div>
    </li>
  );
}

function TimelineEvent({ event }: { event: PlantJournalEvent }): ReactNode {
  return (
    <li className="grid grid-cols-[78px_1fr] gap-3">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {event.dateLabel}
      </span>
      <div className="border-b border-rule pb-3">
        <p className="flex items-center gap-2 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          <EventSquare tag={event.tag} />
          {event.tag}
        </p>
        <p className="mt-1 text-fs-12 leading-ui text-ink">{event.body}</p>
        {event.hasPhoto ? (
          <div className="mt-2 flex aspect-video items-end border border-rule bg-paper-3 p-2">
            <span className="font-mono text-fs-9 uppercase tracking-caps text-ink-3">
              photo placeholder
            </span>
          </div>
        ) : null}
      </div>
    </li>
  );
}

function SparklineCard({
  hoverIndex,
  metric,
  onHoverIndex,
}: {
  hoverIndex: number | null;
  metric: PlantMetricHistory;
  onHoverIndex: (index: number | null) => void;
}): ReactNode {
  const points = metric.points.map((value, index) => ({
    ts: `mock-${index}`,
    value,
  }));
  return (
    <Sparkline
      name={metric.label}
      points={points}
      unit={metric.unit}
      accent={metricAccent(metric.key)}
      valuePrecision={metric.key === "ec" || metric.key === "ph" ? 2 : 1}
      hoverIndex={hoverIndex}
      onHoverIndex={onHoverIndex}
      summary={
        <p className="font-mono text-fs-12 text-ink">
          {metric.value}
          {metric.unit}
        </p>
      }
    />
  );
}

function SurfaceHeader({
  description,
  onBack,
  title,
}: {
  description: string;
  onBack: () => void;
  title: string;
}): ReactNode {
  return (
    <section className="flex flex-col gap-3 border-b border-rule-strong pb-4">
      <button
        type="button"
        onClick={onBack}
        className="w-fit border border-rule px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink"
      >
        Back to plants
      </button>
      <div>
        <h2 className="font-sans text-fs-22 font-semibold text-ink">{title}</h2>
        <p className="mt-1 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          {description}
        </p>
      </div>
    </section>
  );
}

function Segmented<TValue extends string>({
  disabled = false,
  label,
  onChange,
  options,
  value,
}: {
  disabled?: boolean;
  label: string;
  onChange: (value: TValue) => void;
  options: readonly { label: string; value: TValue }[];
  value: TValue;
}): ReactNode {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <div className="flex max-w-full flex-wrap gap-px bg-rule">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            onClick={() => {
              onChange(option.value);
            }}
            className={
              option.value === value
                ? "bg-paper-2 px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink disabled:cursor-not-allowed disabled:text-ink-3"
                : "bg-paper px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:text-ink disabled:cursor-not-allowed disabled:text-ink-3"
            }
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Button({
  children,
  disabled = false,
  onClick,
  variant,
}: {
  children: ReactNode;
  disabled?: boolean;
  onClick?: () => void;
  variant: "primary" | "secondary" | "danger";
}): ReactNode {
  const className =
    variant === "primary"
      ? "border border-ink bg-ink px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-paper transition hover:border-accent-magenta disabled:cursor-not-allowed disabled:border-rule-strong disabled:bg-paper-3 disabled:text-ink-3"
      : variant === "danger"
        ? "border border-status-err bg-paper px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-status-err transition hover:bg-paper-2 disabled:cursor-not-allowed disabled:text-ink-3"
        : "border border-rule-strong bg-paper px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-ink transition hover:border-ink-2 disabled:cursor-not-allowed disabled:text-ink-3";
  return (
    <button type="button" disabled={disabled} onClick={onClick} className={className}>
      {children}
    </button>
  );
}

function SelectField<TValue extends string | number>({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: TValue) => void;
  options: readonly { label: string; value: TValue }[];
  value: TValue;
}): ReactNode {
  return (
    <label className="grid min-w-42 flex-1 gap-1">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <select
        value={String(value)}
        onChange={(event) => {
          const selected = options.find(
            (option) => String(option.value) === event.target.value,
          );
          if (selected !== undefined) onChange(selected.value);
        }}
        className="h-9 border border-rule bg-paper px-3 font-sans text-fs-12 text-ink"
      >
        {options.map((option) => (
          <option key={option.value} value={String(option.value)}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function TextField({
  label,
  onChange,
  placeholder,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  placeholder: string;
  value: string;
}): ReactNode {
  return (
    <label className="grid gap-1">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="h-9 border border-rule bg-paper px-3 font-sans text-fs-12 text-ink placeholder:text-ink-3"
      />
    </label>
  );
}

function DateTimeField({
  label,
  max,
  onChange,
  required = true,
  value,
}: {
  label: string;
  max: string;
  onChange: (value: string) => void;
  required?: boolean;
  value: string;
}): ReactNode {
  return (
    <label className="grid gap-1">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <input
        type="datetime-local"
        required={required}
        max={max}
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="h-9 border border-rule bg-paper px-3 font-sans text-fs-12 text-ink"
      />
    </label>
  );
}

function NumberStepper({
  label,
  max,
  min,
  onChange,
  value,
}: {
  label: string;
  max: number;
  min: number;
  onChange: (value: number) => void;
  value: number;
}): ReactNode {
  return (
    <div className="grid gap-1">
      <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">{label}</p>
      <div className="flex w-fit items-center border border-rule bg-paper">
        <button
          type="button"
          onClick={() => {
            onChange(Math.max(min, value - 1));
          }}
          className="grid h-9 w-9 place-items-center border-r border-rule font-mono text-fs-14 text-ink"
        >
          -
        </button>
        <span className="grid h-9 min-w-14 place-items-center font-mono text-fs-16 text-ink">
          {value}
        </span>
        <button
          type="button"
          onClick={() => {
            onChange(Math.min(max, value + 1));
          }}
          className="grid h-9 w-9 place-items-center border-l border-rule font-mono text-fs-14 text-ink"
        >
          +
        </button>
      </div>
    </div>
  );
}

function Checkbox({
  checked,
  indeterminate = false,
  label,
  onChange,
}: {
  checked: boolean;
  indeterminate?: boolean;
  label: string;
  onChange: () => void;
}): ReactNode {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return (
    <input
      ref={ref}
      aria-label={label}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      className="h-4 w-4 appearance-none border border-rule-strong bg-paper checked:bg-accent-magenta indeterminate:bg-ink-3"
    />
  );
}

function ReadOnlyFact({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div className="grid gap-1">
      <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">{label}</p>
      <span className="border border-rule bg-paper px-3 py-2 font-mono text-fs-12 uppercase tracking-caps text-ink">
        {value}
      </span>
    </div>
  );
}

function ReadOnlyPrefixPreview({
  count,
  prefix,
}: {
  count: number;
  prefix: string;
}): ReactNode {
  return (
    <div className="mt-3 border border-rule bg-paper-2 px-3 py-2.5">
      <p className="font-mono text-fs-10 uppercase tracking-caps text-ink">
        {count} local plant labels will use prefix {prefix}
      </p>
      <p className="mt-1 font-mono text-fs-9 uppercase tracking-caps text-ink-3">
        suffixes and durable plant keys are assigned by the local gateway
      </p>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div className="min-w-0 bg-paper px-3 py-2.5">
      <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">{label}</p>
      <p className="mt-1 truncate font-mono text-fs-10 uppercase tracking-caps text-ink">
        {value}
      </p>
    </div>
  );
}

function DateCell({ value }: { value: string | null }): ReactNode {
  return (
    <span className="font-mono text-fs-10 text-ink-2">
      {value ? shortDate(value) : "-"}
    </span>
  );
}

function SexTestInline({
  compact = false,
  plant,
}: {
  compact?: boolean;
  plant: PlantRow;
}): ReactNode {
  const sexTest = latestSexTest(plant);
  if (sexTest === undefined) {
    return (
      <span className="font-mono text-fs-9 uppercase tracking-caps text-ink-3">-</span>
    );
  }
  return (
    <span
      title={`${sexTest.vendorTestCode} / ${sexTestStatusLabel(sexTest)}`}
      className={
        compact
          ? "inline-flex max-w-full items-center gap-1 font-mono text-fs-9 uppercase tracking-caps"
          : "inline-flex max-w-full flex-col font-mono text-fs-9 uppercase tracking-caps"
      }
    >
      <span className="max-w-full truncate text-ink">{sexTest.vendorTestCode}</span>
      <span className={sexTestStatusTextClass(sexTest)}>
        {sexTestStatusLabel(sexTest)}
      </span>
    </span>
  );
}

function StageSquare({ stageKey }: { stageKey: PlantStageKey }): ReactNode {
  return (
    <span aria-hidden="true" className={`h-2 w-2 ${stageSquareClass(stageKey)}`} />
  );
}

function EventSquare({ tag }: { tag: PlantJournalEvent["tag"] }): ReactNode {
  const className =
    tag === "cross"
      ? "bg-accent-purple"
      : tag === "stage"
        ? "bg-sensor-vpd"
        : tag === "sex"
          ? "bg-ink-2"
          : tag === "germ"
            ? "bg-leaf"
            : "bg-ink-3";

  return <span aria-hidden="true" className={`h-1.75 w-1.75 ${className}`} />;
}

function Pill({ children }: { children: ReactNode }): ReactNode {
  return (
    <span className="border border-rule-strong bg-paper-2 px-2 py-1 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
      {children}
    </span>
  );
}

function stageSquareClass(stageKey: PlantStageKey): string {
  if (stageKey === "germinating") return "bg-leaf";
  if (stageKey === "veg") return "bg-sensor-vpd";
  if (stageKey === "flower") return "bg-ink";
  if (stageKey === "breeding") return "bg-accent-purple";
  if (stageKey === "harvested") return "bg-sensor-reservoir";
  return "bg-status-err";
}

function sexGlyph(sexKey: PlantSexKey): string {
  if (sexKey === "male") return "♂";
  if (sexKey === "female") return "♀";
  if (sexKey === "herm") return "⚥";
  if (sexKey === "reversed") return "R";
  return "?";
}

function sexLabel(sexKey: PlantSexKey): string {
  if (sexKey === "male") return "Male";
  if (sexKey === "female") return "Female";
  if (sexKey === "herm") return "Herm";
  if (sexKey === "reversed") return "Reversed";
  return "Unsexed";
}

function sexTextClass(sexKey: PlantSexKey): string {
  if (sexKey === "male") return "text-sensor-humidity";
  if (sexKey === "female") return "text-accent-magenta";
  if (sexKey === "herm") return "text-status-warn";
  if (sexKey === "reversed") return "text-accent-purple";
  return "text-ink-3";
}

function metricAccent(
  key: PlantMetricHistory["key"],
): "temp" | "vpd" | "moisture" | "reservoir" {
  if (key === "temperature") return "temp";
  if (key === "ec") return "reservoir";
  if (key === "ph") return "vpd";
  return "moisture";
}

function shortDate(value: string): string {
  return value.slice(5);
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "unknown";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function shortDateOrDash(value: string | null): string {
  return value === null ? "-" : shortDate(value);
}

function detailFactsDraftFromPlant(plant: PlantRow): DetailFactsDraft {
  return {
    sexKey: plant.sexKey,
    germinatedAt: datetimeLocalFromOptionalFact(plant.germinatedAt, plant.germinatedOn),
    takenAt: datetimeLocalFromOptionalFact(plant.takenAt, plant.takenOn),
    rootedAt: datetimeLocalFromOptionalFact(plant.rootedAt, plant.rootedOn),
    vegStartedAt: datetimeLocalFromOptionalFact(plant.vegStartedAt, plant.vegStartedOn),
    flowerStartedAt: datetimeLocalFromOptionalFact(
      plant.flowerStartedAt,
      plant.flowerStartedOn,
    ),
    culledAt: datetimeLocalFromOptionalFact(plant.culledAt, plant.culledOn),
    culledReason: plant.culledReason ?? "",
    harvestedAt: datetimeLocalFromOptionalFact(plant.harvestedAt, plant.harvestedOn),
    selectedForBreedingAt: datetimeLocalFromOptionalFact(
      plant.selectedForBreedingAt,
      plant.selectedForBreedingOn,
    ),
    selectedForBreedingReason: plant.selectedForBreedingReason ?? "",
  };
}

function canSaveDetailFactsDraft(
  plant: PlantRow,
  draft: DetailFactsDraft,
  maxEventDateTime: string,
): boolean {
  return (
    detailFactsDraftDatesValid(plant, draft, maxEventDateTime) &&
    detailFactUpdates(plant, draft).length > 0
  );
}

function detailFactsDraftDatesValid(
  plant: PlantRow,
  draft: DetailFactsDraft,
  maxEventDateTime: string,
): boolean {
  return detailFactDateDraftFields(plant).every((field) => {
    const value = draft[field];
    return value.length === 0 || canSubmitEventDateTime(value, maxEventDateTime);
  });
}

function detailFactUpdates(
  plant: PlantRow,
  draft: DetailFactsDraft,
): DetailFactUpdate[] {
  const current = detailFactsDraftFromPlant(plant);
  const updates: DetailFactUpdate[] = [];
  if (draft.sexKey !== current.sexKey) {
    updates.push({ field: "sex_key", value: draft.sexKey });
  }
  for (const field of detailFactDateDraftFields(plant)) {
    if (draft[field] === current[field]) continue;
    const value = dateFactValueFromDraft(draft[field]);
    if (value !== undefined) {
      updates.push({ field: detailDateFieldFromDraftKey(field), value });
    }
  }
  for (const field of detailFactTextDraftFields()) {
    const currentValue = normalizedDetailTextDraftValue(current, field);
    const draftValue = normalizedDetailTextDraftValue(draft, field);
    if (draftValue === currentValue) continue;
    updates.push({ field: detailTextFieldFromDraftKey(field), value: draftValue });
  }
  return updates;
}

function detailFactDateDraftFields(
  plant: PlantRow,
): readonly DetailFactsDraftDateKey[] {
  return plant.isClone ? CLONE_DETAIL_DATE_DRAFT_FIELDS : SEED_DETAIL_DATE_DRAFT_FIELDS;
}

function detailDateFieldFromDraftKey(
  field: DetailFactsDraftDateKey,
): DetailDateFactField {
  return DETAIL_DATE_FACT_FIELD_BY_DRAFT_KEY[field];
}

function detailFactTextDraftFields(): readonly DetailFactsDraftTextKey[] {
  return DETAIL_TEXT_DRAFT_FIELDS;
}

function detailTextFieldFromDraftKey(
  field: DetailFactsDraftTextKey,
): DetailTextFactField {
  return DETAIL_TEXT_FACT_FIELD_BY_DRAFT_KEY[field];
}

function normalizedDetailTextDraftValue(
  draft: DetailFactsDraft,
  field: DetailFactsDraftTextKey,
): string | null {
  const ownerDate = draft[DETAIL_TEXT_OWNER_DATE_DRAFT_KEY[field]];
  if (ownerDate.length === 0) return null;
  const value = draft[field].trim();
  return value.length === 0 ? null : value;
}

function dateFactValueFromDraft(value: string): string | null | undefined {
  if (value.length === 0) return null;
  return datetimeLocalToUtcIso(value) ?? undefined;
}

function datetimeLocalNow(): string {
  return dateToDatetimeLocal(new Date());
}

function datetimeLocalFromDateOnly(value: string | null): string {
  return value === null ? datetimeLocalNow() : `${value}T12:00`;
}

function datetimeLocalFromIsoOrDateOnly(
  timestamp: string | null,
  dateOnly: string | null,
): string {
  if (timestamp === null) return datetimeLocalFromDateOnly(dateOnly);
  const parsed = new Date(timestamp);
  return Number.isNaN(parsed.getTime())
    ? datetimeLocalFromDateOnly(dateOnly)
    : dateToDatetimeLocal(parsed);
}

function datetimeLocalFromOptionalFact(
  timestamp: string | null,
  dateOnly: string | null,
): string {
  if (timestamp === null && dateOnly === null) return "";
  return datetimeLocalFromIsoOrDateOnly(timestamp, dateOnly);
}

function datetimeLocalFromRequiredIso(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? datetimeLocalNow()
    : dateToDatetimeLocal(parsed);
}

function datetimeLocalFromOptionalIso(value: string | null): string {
  if (value === null) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : dateToDatetimeLocal(parsed);
}

function dateToDatetimeLocal(value: Date): string {
  const offsetMs = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offsetMs)
    .toISOString()
    .slice(0, DATETIME_LOCAL_LENGTH);
}

function datetimeLocalToUtcIso(value: string): string | null {
  if (!isValidDatetimeLocal(value)) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString();
}

function canSubmitEventDateTime(value: string, max: string): boolean {
  return isValidDatetimeLocal(value) && value <= max;
}

function isValidDatetimeLocal(value: string): boolean {
  return value.length === DATETIME_LOCAL_LENGTH;
}

function stageLabel(plant: PlantRow): string {
  if (plant.stageKey === "culled")
    return `Culled ${plant.culledOn ? shortDate(plant.culledOn) : ""}`;
  return `${plant.stageKey} / d${plant.stageDay}`;
}

function bulkDateFieldLabel(field: BulkDateField): string {
  return BULK_DATE_FIELD_COPY[field].fieldLabel;
}

function bulkDateFieldShortLabel(field: BulkDateField): string {
  return BULK_DATE_FIELD_COPY[field].actionLabel;
}

function formatPlantLocation(plant: PlantRow): string {
  return plant.gridPosition === null
    ? plant.currentTentName
    : `${plant.currentTentName} / ${plant.gridPosition}`;
}

function locationDropStageKey(location: LocationOption): PlantStageKey | null {
  switch (location.role) {
    case "clone":
      return "germinating";
    case "veg":
      return "veg";
    case "flower":
      return "flower";
    case "breeding":
      return "breeding";
    case "culled":
      return "culled";
    default:
      return null;
  }
}

function canUseLocationForStage(
  location: LocationOption,
  stageKey: PlantStageKey,
): boolean {
  return locationDropStageKey(location) === stageKey;
}

function canDropIntoLocation(location: LocationOption): boolean {
  const dropStageKey = locationDropStageKey(location);
  return dropStageKey !== null && dropStageKey !== "culled";
}

function groupPlants(
  plants: readonly PlantRow[],
  bootstrap: PlantsBootstrap,
  groupBy: PlantGroupBy,
): readonly TableGroup[] {
  if (groupBy === "parents") {
    const parentLabels = [...new Set(plants.map((plant) => plant.parentsLabel))];
    return parentLabels.map((parentsLabel) => {
      const groupedPlants = plants.filter(
        (plant) => plant.parentsLabel === parentsLabel,
      );
      return {
        key: parentsLabel,
        label: parentsLabel,
        stageKey: groupedPlants[0]?.stageKey ?? "veg",
        plants: groupedPlants,
      };
    });
  }

  return bootstrap.stages
    .map((stage) => ({
      key: stage.key,
      label: stage.displayName,
      stageKey: stage.key,
      plants: plants.filter((plant) => plant.stageKey === stage.key),
    }))
    .filter((group) => group.plants.length > 0);
}

export function nextPlantTableSortState(
  current: PlantTableSortState,
  key: PlantTableSortKey,
): PlantTableSortState {
  if (current?.key !== key) return { key, direction: "asc" };
  if (current.direction === "asc") return { key, direction: "desc" };
  return null;
}

export function sortPlantsForTable(
  plants: readonly PlantRow[],
  sortState: PlantTableSortState,
): readonly PlantRow[] {
  if (sortState === null) return plants;
  return plants
    .map((plant, index) => ({ index, plant }))
    .toSorted((left, right) => {
      const comparison = comparePlantsForTable(
        left.plant,
        right.plant,
        sortState.key,
        sortState.direction,
      );
      if (comparison !== 0) return comparison;
      return left.index - right.index;
    })
    .map(({ plant }) => plant);
}

function comparePlantsForTable(
  left: PlantRow,
  right: PlantRow,
  key: PlantTableSortKey,
  direction: PlantTableSortDirection,
): number {
  switch (key) {
    case "plant":
      return applySortDirection(
        compareText(left.name, right.name) || compareText(left.key, right.key),
        direction,
      );
    case "generation":
      return applySortDirection(
        compareText(left.generation, right.generation),
        direction,
      );
    case "parents":
      return applySortDirection(
        compareText(left.parentsLabel, right.parentsLabel),
        direction,
      );
    case "sex":
      return applySortDirection(compareText(left.sexKey, right.sexKey), direction);
    case "days":
      return applySortDirection(left.stageDay - right.stageDay, direction);
    case "germinated":
      return compareNullableText(left.germinatedOn, right.germinatedOn, direction);
    case "veg":
      return compareNullableText(left.vegStartedOn, right.vegStartedOn, direction);
    case "flower":
      return compareNullableText(
        left.flowerStartedOn,
        right.flowerStartedOn,
        direction,
      );
    case "sexTest":
      return applySortDirection(
        compareText(plantSexTestSortText(left), plantSexTestSortText(right)),
        direction,
      );
    case "lastNote":
      return applySortDirection(compareText(left.lastNote, right.lastNote), direction);
  }
}

function applySortDirection(
  comparison: number,
  direction: PlantTableSortDirection,
): number {
  return direction === "asc" ? comparison : -comparison;
}

function compareText(left: string, right: string): number {
  return PLANT_TABLE_SORT_COLLATOR.compare(left.trim(), right.trim());
}

function compareNullableText(
  left: string | null,
  right: string | null,
  direction: PlantTableSortDirection,
): number {
  if (left === null && right === null) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  return applySortDirection(compareText(left, right), direction);
}

function plantSexTestSortText(plant: PlantRow): string {
  const sexTest = latestSexTest(plant);
  if (sexTest === undefined) return "";
  return `${sexTestStatusLabel(sexTest)} ${sexTest.vendorTestCode}`;
}

function plantExactFilterOptions(
  plants: readonly PlantRow[],
  field: "parentsLabel" | "strain",
  selectedValue: string,
): readonly { label: string; value: string }[] {
  const values = uniqueSortedValues(plants.map((plant) => plant[field]));
  if (selectedValue !== "all" && !values.includes(selectedValue)) {
    values.push(selectedValue);
    values.sort(PLANT_FILTER_COLLATOR.compare);
  }
  return [
    { label: field === "parentsLabel" ? "All parents" : "All strains", value: "all" },
    ...values.map((value) => ({ label: value, value })),
  ];
}

function uniqueSortedValues(values: readonly string[]): string[] {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))].sort(
    PLANT_FILTER_COLLATOR.compare,
  );
}

function latestSexTest(plant: PlantRow): PlantSexTest | undefined {
  return plant.sexTests[0];
}

function sexTestState(sexTest: PlantSexTest): Exclude<PlantSexTestStateFilter, "all"> {
  if (sexTest.resultReceivedAt === null) return "pending";
  if (sexTest.isInconclusive) return "inconclusive";
  return "resulted";
}

function sexTestStatusLabel(sexTest: PlantSexTest): string {
  if (sexTest.resultSexKey === "female") return "female";
  if (sexTest.resultSexKey === "male") return "male";
  if (sexTest.isInconclusive) return "inconclusive";
  if (sexTest.resultReceivedAt !== null) return "resulted";
  return "pending";
}

function sexTestStatusTextClass(sexTest: PlantSexTest): string {
  const state = sexTestState(sexTest);
  if (state === "pending") return "text-status-warn";
  if (state === "inconclusive") return "text-accent-purple";
  return sexTest.resultSexKey === "female"
    ? "text-accent-magenta"
    : "text-sensor-humidity";
}

function sexTestStatusClass(sexTest: PlantSexTest): string {
  const state = sexTestState(sexTest);
  if (state === "pending") return "border-status-warn text-status-warn";
  if (state === "inconclusive") return "border-accent-purple text-accent-purple";
  return sexTest.resultSexKey === "female"
    ? "border-accent-magenta text-accent-magenta"
    : "border-sensor-humidity text-sensor-humidity";
}

function duplicateSexTestCodes(codes: readonly string[]): ReadonlySet<string> {
  const seen = new Set<string>();
  const duplicates = new Set<string>();
  for (const code of codes) {
    const normalized = normalizedSexTestCode(code);
    if (normalized.length === 0) continue;
    if (seen.has(normalized)) {
      duplicates.add(normalized);
    } else {
      seen.add(normalized);
    }
  }
  return duplicates;
}

function normalizedSexTestCode(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function pendingSexTestRows(
  plants: readonly PlantRow[],
): readonly { plant: PlantRow; sexTest: PlantSexTest }[] {
  return plants.flatMap((plant) =>
    plant.sexTests
      .filter((sexTest) => sexTestState(sexTest) === "pending")
      .map((sexTest) => ({ plant, sexTest })),
  );
}

function hasProjectedSexTestIdentity(sexTest: PlantSexTest): boolean {
  return sexTest.sourceSexTestId > 0 && !sexTest.id.startsWith("pending:");
}

function resultInputFromOption(result: SexTestResultOption): {
  resultSexKey: SexTestConclusiveResult | null;
  isInconclusive: boolean;
} {
  if (result === "inconclusive") {
    return { resultSexKey: null, isInconclusive: true };
  }
  return { resultSexKey: result, isInconclusive: false };
}

function hasSexTestResultDraft(
  value: SexTestResultDraftValue | undefined,
): value is SexTestResultOption {
  return value === "female" || value === "male" || value === "inconclusive";
}

function sexTestEditDraftFromTest(sexTest: PlantSexTest): SexTestEditDraft {
  return {
    vendorName: sexTest.vendorName,
    assayName: sexTest.assayName ?? "",
    vendorTestCode: sexTest.vendorTestCode,
    sampleCollectedAt: datetimeLocalFromRequiredIso(sexTest.sampleCollectedAt),
    sampleSentAt: datetimeLocalFromOptionalIso(sexTest.sampleSentAt),
    notes: sexTest.notes ?? "",
  };
}

function sexTestEditDraftChanged(
  sexTest: PlantSexTest,
  draft: SexTestEditDraft,
): boolean {
  const current = sexTestEditDraftFromTest(sexTest);
  return (
    draft.vendorName !== current.vendorName ||
    draft.assayName !== current.assayName ||
    draft.vendorTestCode !== current.vendorTestCode ||
    draft.sampleCollectedAt !== current.sampleCollectedAt ||
    draft.sampleSentAt !== current.sampleSentAt ||
    draft.notes !== current.notes
  );
}

function conclusiveSexTestResultKey(
  sexKey: PlantSexKey | null,
): SexTestConclusiveResult | null {
  return sexKey === "female" || sexKey === "male" ? sexKey : null;
}

function plantSearchText(plant: PlantRow): string {
  return [
    plant.key,
    plant.name,
    plant.strain,
    plant.generation,
    plant.parentsLabel,
    plant.seedLotLabel,
    plant.currentTentName,
    plant.lastNote,
    ...plant.sexTests.flatMap((sexTest) => [
      sexTest.vendorName,
      sexTest.assayName ?? "",
      sexTest.vendorTestCode,
      sexTestStatusLabel(sexTest),
    ]),
  ].join(" ");
}

function normalizeSearchText(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function clonePrefixFor(name: string): string {
  const tail = name.trim().split(/\s+/).at(-1) ?? "M";
  return `C${tail.replace(/[^A-Za-z0-9]/g, "")}`.toUpperCase();
}
