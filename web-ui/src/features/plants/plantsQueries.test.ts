import { describe, expect, it } from "vitest";
import type { hostedComponents } from "@/api-client";
import {
  filterPlantsForSearch,
  normalizePlantsSearch,
  plantLifecycleStatus,
  validatePlantsSearch,
} from "./PlantsWorkspace";
import {
  applyPendingPlantCommands,
  buildBulkCullRequest,
  buildBulkLogNoteRequest,
  buildBulkMoveRequest,
  buildBulkSexRequest,
  buildClonePlantsRequest,
  buildGerminatePlantsRequest,
  buildLogNoteRequest,
  buildUpdatePlantFactsRequest,
  canSubmitBulkCull,
  isPendingCommandProjected,
  type PlantsPendingCommand,
  pendingTimelineNotes,
  readonlyPlantPrefixPreview,
} from "./plantsMutations";
import { mapBootstrap, mapPlantDetail, mapPlantList } from "./plantsQueries";
import type { PlantRow } from "./plantsTypes";

type HostedBootstrap = hostedComponents["schemas"]["BreedingLogbookBootstrapResponse"];
type HostedPlantDetail =
  hostedComponents["schemas"]["BreedingLogbookPlantDetailResponse"];
type HostedPlantList = hostedComponents["schemas"]["BreedingLogbookPlantListResponse"];
type HostedMetricHistory = hostedComponents["schemas"]["PlantMetricHistoryResponse"];
type HostedCommand = hostedComponents["schemas"]["CommandResponse"];

describe("plants hosted response mapping", () => {
  it("maps bootstrap lookups and nullable locations", () => {
    const bootstrap = {
      today: "2026-05-05",
      today_label: "05/05/26",
      plant_sexes: [{ key: "female", display_name: "Female", display_order: 30 }],
      seed_lot_sex_types: [
        { key: "regular", display_name: "Regular", display_order: 30 },
      ],
      stages: [{ key: "flower", display_name: "Flower", display_order: 30 }],
      locations: [
        {
          source_tent_id: 1,
          display_name: "Main flower",
          role: "flower",
          grid_position: null,
        },
      ],
    } satisfies HostedBootstrap;

    expect(mapBootstrap(bootstrap)).toMatchObject({
      today: "2026-05-05",
      todayLabel: "05/05/26",
      locations: [{ sourceTentId: 1, displayName: "Main flower", role: "flower" }],
    });
  });

  it("maps plant detail timeline and metric history responses", () => {
    const plant = {
      id: "1",
      key: "SBBS-R1-001",
      name: "Plant A",
      strain: "Sirius Black",
      generation: "R1",
      parents_label: "Plant B x Plant C",
      sex_key: "female",
      stage_key: "flower",
      stage_day: 12,
      is_clone: false,
      germinated_at: "2026-03-15T16:45:00.000Z",
      germinated_on: "2026-03-15",
      taken_at: null,
      taken_on: null,
      rooted_at: null,
      rooted_on: null,
      veg_started_at: "2026-04-01T16:45:00.000Z",
      veg_started_on: "2026-04-01",
      flower_started_at: "2026-05-01T16:45:00.000Z",
      flower_started_on: "2026-05-01",
      culled_on: null,
      current_tent_id: 1,
      current_tent_name: "Main flower",
      grid_position: null,
      seed_lot_label: "SBBS R1 #2",
      last_note: "Trichomes stacking",
      telemetry_summary: "1 plant stream",
    } satisfies HostedPlantList["plants"][number];
    const plants = {
      active_count: 1,
      culled_count: 0,
      group_by: "stage",
      plants: [plant],
    } satisfies HostedPlantList;
    const detail = {
      plant,
      lineage: {
        parents: "Plant B x Plant C",
        offspring: "Cross #43: SBBS R1 #3 (1 plant)",
      },
      metrics: [{ label: "Substrate Temp", value: "69.8°F", tone: "ok" }],
      events: [
        {
          id: "event-201",
          occurred_at: "2026-05-05T02:45:00Z",
          date_label: "May 5",
          tag: "sex",
          body: "Confirmed female",
          has_photo: false,
        },
      ],
      telemetry: [],
      wiki_content: null,
    } satisfies HostedPlantDetail;
    const history = {
      range: "24h",
      bucket: "1h",
      streams: [
        {
          metric: "substrate_temp_c",
          display_name: "Substrate Temp",
          display_unit: "°F",
          source_unit: "degC",
          value_precision: 1,
          accent: "temp",
          y_min: null,
          y_max: null,
          display_order: 10,
          device_id: "plant-a-node",
          capability_id: "substrate-temp",
          points: [
            {
              bucket: "1h",
              bucket_start_at: "2026-05-05T01:00:00Z",
              bucket_end_at: "2026-05-05T02:00:00Z",
              min: 68.1,
              avg: 69.8,
              max: 70.2,
              source_min: 20.1,
              source_avg: 21,
              source_max: 21.2,
              sample_count: 1,
              source_unit: "degC",
              display_unit: "°F",
            },
          ],
        },
      ],
    } satisfies HostedMetricHistory;

    expect(mapPlantList(plants).plants[0]).toMatchObject({
      currentTentName: "Main flower",
      strain: "Sirius Black",
    });
    expect(mapPlantDetail(detail, history)).toMatchObject({
      plant: { key: "SBBS-R1-001", lastNote: "Trichomes stacking" },
      lineage: { offspring: "Cross #43: SBBS R1 #3 (1 plant)" },
      events: [{ id: "event-201", tag: "sex", body: "Confirmed female" }],
      metricHistory: [
        {
          key: "temperature",
          value: "69.8",
          points: [69.8],
        },
      ],
    });
  });
});

describe("plants list filters", () => {
  it("filters by query, parent, strain, and lifecycle status", () => {
    const plants = [
      makePlantRow({
        key: "MF-001",
        name: "MF-001",
        parentsLabel: "Mother x Father",
        strain: "Maruf Black",
      }),
      makePlantRow({
        id: "2",
        key: "SB-001",
        name: "SB-001",
        parentsLabel: "Sirius Black x BS01",
        strain: "Sirius Black",
        vegStartedAt: null,
        vegStartedOn: null,
      }),
      makePlantRow({
        id: "3",
        isClone: true,
        key: "CL-001",
        name: "CL-001",
        parentsLabel: "Mother x Father",
        strain: "Maruf Black",
        germinatedAt: null,
        germinatedOn: null,
        takenAt: "2026-06-02T16:45:00.000Z",
        takenOn: "2026-06-02",
        vegStartedAt: null,
        vegStartedOn: null,
      }),
      makePlantRow({
        id: "4",
        key: "FL-001",
        name: "FL-001",
        parentsLabel: "Mother x Father",
        strain: "Maruf Black",
        flowerStartedAt: "2026-06-20T16:45:00.000Z",
        flowerStartedOn: "2026-06-20",
      }),
    ];

    expect(
      filterPlantsForSearch(
        plants,
        normalizePlantsSearch(
          validatePlantsSearch({
            parent: "Mother x Father",
            q: "mf",
            status: "veg",
            strain: "Maruf Black",
          }),
        ),
      ).map((plant) => plant.key),
    ).toEqual(["MF-001"]);
    expect(
      filterPlantsForSearch(
        plants,
        normalizePlantsSearch(validatePlantsSearch({ status: "started" })),
      ).map((plant) => plant.key),
    ).toEqual(["SB-001", "CL-001"]);
    const floweringPlant = plants.find((plant) => plant.key === "FL-001");
    expect(floweringPlant).toBeDefined();
    if (floweringPlant === undefined) return;
    expect(plantLifecycleStatus(floweringPlant)).toBe("flower");
  });
});

describe("plants mutation request mapping", () => {
  it("builds snake_case write request bodies from screen-shaped inputs", () => {
    expect(
      buildGerminatePlantsRequest({
        idempotencyKey: "germ-click",
        seedLotId: "42",
        count: 6,
        sourceTentId: 1,
        affectedLabel: "MF F2",
        germinatedAt: "2026-06-17T15:30:00.000Z",
      }),
    ).toEqual({
      idempotency_key: "germ-click",
      seed_lot_id: "42",
      count: 6,
      source_tent_id: 1,
      grid_position: null,
      germinated_at: "2026-06-17T15:30:00.000Z",
    });

    expect(
      buildClonePlantsRequest({
        idempotencyKey: "clone-click",
        motherPlantKey: "MF-001",
        count: 2,
        sourceTentId: 3,
        takenAt: "2026-06-17T16:45:00.000Z",
      }),
    ).toEqual({
      idempotency_key: "clone-click",
      mother_plant_key: "MF-001",
      count: 2,
      source_tent_id: 3,
      grid_position: null,
      taken_at: "2026-06-17T16:45:00.000Z",
    });

    expect(
      buildBulkSexRequest({
        idempotencyKey: "sex-click",
        plantKeys: ["MF-001", "MF-002"],
        sexKey: "female",
      }),
    ).toEqual({
      idempotency_key: "sex-click",
      plant_keys: ["MF-001", "MF-002"],
      sex_key: "female",
    });
    expect(
      buildBulkMoveRequest({
        idempotencyKey: "move-click",
        plantKeys: ["MF-001"],
        sourceTentId: 2,
        locationLabel: "Flower",
      }),
    ).toEqual({
      idempotency_key: "move-click",
      plant_keys: ["MF-001"],
      source_tent_id: 2,
      grid_position: null,
    });
    expect(
      buildBulkCullRequest({
        idempotencyKey: "cull-click",
        plantKeys: ["MF-002"],
        reason: "  selected male  ",
      }),
    ).toEqual({
      idempotency_key: "cull-click",
      plant_keys: ["MF-002"],
      reason: "selected male",
    });
    expect(
      buildLogNoteRequest({
        idempotencyKey: "note-click",
        plantKey: "MF-001",
        body: "  stem rub changed  ",
      }),
    ).toEqual({
      idempotency_key: "note-click",
      body: "stem rub changed",
      observed_at: null,
    });
    expect(
      buildUpdatePlantFactsRequest({
        idempotencyKey: "facts-click",
        plantKeys: ["MF-001", "MF-002"],
        updates: [
          { field: "sex_key", value: "female" },
          { field: "germinated_at", value: "2026-06-15T16:45:00.000Z" },
          { field: "taken_at", value: "2026-06-14T16:45:00.000Z" },
          { field: "rooted_at", value: "2026-06-16T16:45:00.000Z" },
          { field: "veg_started_at", value: "2026-06-17T16:45:00.000Z" },
          { field: "flower_started_at", value: null },
        ],
      }),
    ).toEqual({
      idempotency_key: "facts-click",
      plant_keys: ["MF-001", "MF-002"],
      updates: [
        { field: "sex_key", value: "female" },
        { field: "germinated_at", value: "2026-06-15T16:45:00.000Z" },
        { field: "taken_at", value: "2026-06-14T16:45:00.000Z" },
        { field: "rooted_at", value: "2026-06-16T16:45:00.000Z" },
        { field: "veg_started_at", value: "2026-06-17T16:45:00.000Z" },
        { field: "flower_started_at", value: null },
      ],
    });
    expect(
      buildBulkLogNoteRequest({
        idempotencyKey: "bulk-note-click",
        plantKeys: ["MF-001", "MF-002"],
        body: "  canopy improved  ",
      }),
    ).toEqual({
      idempotency_key: "bulk-note-click",
      plant_keys: ["MF-001", "MF-002"],
      body: "canopy improved",
      observed_at: null,
    });
  });

  it("keeps add-plants prefix read-only and out of germinate/clone requests", () => {
    expect(readonlyPlantPrefixPreview("MF")).toBe("MF-");
    expect(
      Object.keys(
        buildGerminatePlantsRequest({
          idempotencyKey: "germ-click",
          seedLotId: "42",
          count: 6,
          sourceTentId: 1,
          affectedLabel: "MF F2",
          germinatedAt: "2026-06-17T15:30:00.000Z",
        }),
      ),
    ).not.toContain("plant_keys");
    expect(
      Object.keys(
        buildClonePlantsRequest({
          idempotencyKey: "clone-click",
          motherPlantKey: "MF-001",
          count: 2,
          sourceTentId: 3,
          takenAt: "2026-06-17T16:45:00.000Z",
        }),
      ),
    ).not.toContain("clone_keys");
  });

  it("requires a nonblank cull reason before submit", () => {
    expect(canSubmitBulkCull("")).toBe(false);
    expect(canSubmitBulkCull("   ")).toBe(false);
    expect(canSubmitBulkCull("selected male")).toBe(true);
  });
});

describe("plants pending UX helpers", () => {
  it("optimistically applies plant patches until the read projection catches up", () => {
    const plant = makePlantRow({
      key: "MF-001",
      sexKey: "unknown",
      stageKey: "veg",
      currentTentId: 1,
      currentTentName: "Veg",
      gridPosition: null,
      lastNote: "",
    });
    const pendingSex = makePendingCommand({
      command: makeCommand({ status: "succeeded" }),
      optimisticPlantPatches: [{ plantKey: "MF-001", sexKey: "female" }],
    });
    const pendingMove = makePendingCommand({
      command: makeCommand({ status: "queued" }),
      optimisticPlantPatches: [
        {
          plantKey: "MF-001",
          currentTentId: 2,
          currentTentName: "Flower",
          gridPosition: null,
        },
      ],
    });
    const pendingFacts = makePendingCommand({
      command: makeCommand({ status: "queued" }),
      optimisticPlantPatches: [
        {
          plantKey: "MF-001",
          takenAt: "2026-06-14T16:45:00.000Z",
          takenOn: "2026-06-14",
          rootedAt: "2026-06-16T16:45:00.000Z",
          rootedOn: "2026-06-16",
          germinatedAt: "2026-06-15T16:45:00.000Z",
          germinatedOn: "2026-06-15",
          vegStartedAt: "2026-06-17T16:45:00.000Z",
          vegStartedOn: "2026-06-17",
          flowerStartedAt: "2026-06-18T16:45:00.000Z",
          flowerStartedOn: "2026-06-18",
        },
      ],
    });

    expect(
      applyPendingPlantCommands([plant], [pendingSex, pendingMove, pendingFacts]),
    ).toEqual([
      {
        ...plant,
        sexKey: "female",
        currentTentId: 2,
        currentTentName: "Flower",
        gridPosition: null,
        takenAt: "2026-06-14T16:45:00.000Z",
        takenOn: "2026-06-14",
        rootedAt: "2026-06-16T16:45:00.000Z",
        rootedOn: "2026-06-16",
        germinatedAt: "2026-06-15T16:45:00.000Z",
        germinatedOn: "2026-06-15",
        vegStartedAt: "2026-06-17T16:45:00.000Z",
        vegStartedOn: "2026-06-17",
        flowerStartedAt: "2026-06-18T16:45:00.000Z",
        flowerStartedOn: "2026-06-18",
      },
    ]);
    expect(
      isPendingCommandProjected(
        pendingSex,
        [{ ...plant, sexKey: "female" }],
        [],
        "MF-001",
      ),
    ).toBe(true);
    expect(isPendingCommandProjected(pendingMove, [plant], [], "MF-001")).toBe(false);
    expect(
      isPendingCommandProjected(
        pendingFacts,
        [
          {
            ...plant,
            takenAt: "2026-06-14T16:45:00.000Z",
            takenOn: "2026-06-14",
            rootedAt: "2026-06-16T16:45:00.000Z",
            rootedOn: "2026-06-16",
            germinatedAt: "2026-06-15T16:45:00.000Z",
            germinatedOn: "2026-06-15",
            vegStartedAt: "2026-06-17T16:45:00.000Z",
            vegStartedOn: "2026-06-17",
            flowerStartedAt: "2026-06-18T16:45:00.000Z",
            flowerStartedOn: "2026-06-18",
          },
        ],
        [],
        "MF-001",
      ),
    ).toBe(true);
  });

  it("hides plants from active views immediately after a cull command is accepted", () => {
    const plant = makePlantRow({
      key: "MF-002",
      stageKey: "flower",
      currentTentId: 2,
      currentTentName: "Flower",
      gridPosition: null,
    });
    const pendingCull = makePendingCommand({
      command: makeCommand({ status: "succeeded" }),
      optimisticPlantPatches: [
        {
          plantKey: "MF-002",
          stageKey: "culled",
        },
      ],
    });

    const [projected] = applyPendingPlantCommands([plant], [pendingCull]);

    expect(projected?.stageKey).toBe("culled");
    expect(projected?.currentTentName).toBe("Flower");
    expect(projected ? projected.stageKey !== "culled" : false).toBe(false);
  });

  it("shows pending notes distinctly until projection syncs them", () => {
    const pending = makePendingCommand({
      body: "Stem rub shifted.",
      command: makeCommand({ status: "queued" }),
    });

    expect(pendingTimelineNotes([], [pending], "MF-001")).toEqual([
      {
        id: "pending-command-1",
        body: "Stem rub shifted.",
        dateLabel: "Pending",
        error: null,
        statusLabel: "Queued",
      },
    ]);
    expect(
      pendingTimelineNotes(
        [
          {
            id: "note-1",
            dateLabel: "Jun 18",
            tag: "note",
            body: "Stem rub shifted.",
            hasPhoto: false,
          },
        ],
        [pending],
        "MF-001",
      ),
    ).toEqual([]);
    expect(
      isPendingCommandProjected(
        pending,
        [makePlantRow({ key: "MF-001", lastNote: "Stem rub shifted." })],
        [
          {
            id: "note-1",
            dateLabel: "Jun 18",
            tag: "note",
            body: "Stem rub shifted.",
            hasPhoto: false,
          },
        ],
        "MF-001",
      ),
    ).toBe(true);
  });

  it("shows bulk pending notes on each affected plant", () => {
    const pending = makePendingCommand({
      body: "Canopy improved.",
      command: makeCommand({ status: "queued" }),
      optimisticPlantPatches: [
        { plantKey: "MF-001", lastNote: "Canopy improved." },
        { plantKey: "MF-002", lastNote: "Canopy improved." },
      ],
    });

    expect(pendingTimelineNotes([], [pending], "MF-001")).toHaveLength(1);
    expect(pendingTimelineNotes([], [pending], "MF-002")).toHaveLength(1);
    expect(pendingTimelineNotes([], [pending], "MF-003")).toEqual([]);
    expect(
      isPendingCommandProjected(
        pending,
        [
          makePlantRow({ key: "MF-001", lastNote: "Canopy improved." }),
          makePlantRow({ key: "MF-002", lastNote: "Canopy improved." }),
        ],
        [],
        "MF-003",
      ),
    ).toBe(true);
    expect(
      isPendingCommandProjected(
        pending,
        [
          makePlantRow({ key: "MF-001", lastNote: "Canopy improved." }),
          makePlantRow({ key: "MF-002", lastNote: "Canopy improved." }),
        ],
        [],
        "MF-001",
      ),
    ).toBe(false);
  });

  it("keeps failed command errors visible without changing synced facts", () => {
    const failed = makePendingCommand({
      body: "Stem rub shifted.",
      command: makeCommand({
        status: "failed",
        error: "local plant not found",
      }),
    });

    expect(pendingTimelineNotes([], [failed], "MF-001")).toEqual([
      {
        id: "pending-command-1",
        body: "Stem rub shifted.",
        dateLabel: "Pending",
        error: "local plant not found",
        statusLabel: "Failed",
      },
    ]);
  });
});

function makePendingCommand({
  body,
  command,
  optimisticPlantPatches = body === undefined
    ? []
    : [{ plantKey: "MF-001", lastNote: body }],
}: {
  body?: string;
  command: HostedCommand;
  optimisticPlantPatches?: PlantsPendingCommand["optimisticPlantPatches"];
}): PlantsPendingCommand {
  return {
    commandId: command.command_id,
    command,
    operation: "note",
    label: "Logging note",
    affectedPlantKeys:
      optimisticPlantPatches.length > 0
        ? optimisticPlantPatches.map((patch) => patch.plantKey)
        : ["MF-001"],
    optimisticPlantPatches,
    pendingNote:
      body === undefined
        ? null
        : {
            plantKeys:
              optimisticPlantPatches.length > 0
                ? optimisticPlantPatches.map((patch) => patch.plantKey)
                : ["MF-001"],
            body,
          },
  };
}

function makePlantRow(overrides: Partial<PlantRow>): PlantRow {
  return {
    id: "1",
    key: "MF-001",
    name: "MF-001",
    strain: "Maruf Black",
    generation: "F2",
    parentsLabel: "Mother x Father",
    sexKey: "unknown",
    stageKey: "veg",
    stageDay: 14,
    isClone: false,
    takenAt: null,
    takenOn: null,
    rootedAt: null,
    rootedOn: null,
    germinatedAt: "2026-06-01T16:45:00.000Z",
    germinatedOn: "2026-06-01",
    vegStartedAt: "2026-06-10T16:45:00.000Z",
    vegStartedOn: "2026-06-10",
    flowerStartedAt: null,
    flowerStartedOn: null,
    culledOn: null,
    currentTentId: 1,
    currentTentName: "Veg",
    gridPosition: null,
    seedLotLabel: "MF F2",
    lastNote: "",
    telemetrySummary: "",
    ...overrides,
  };
}

function makeCommand({
  error = null,
  status,
}: {
  error?: string | null;
  status: string;
}): HostedCommand {
  return {
    claimed_at: null,
    claimed_by: null,
    command_id: "command-1",
    command_type: "breeding_plant_note_create",
    error,
    expires_at: "2026-06-18T12:00:00Z",
    finished_at: null,
    idempotency_key: "note-click",
    payload: {},
    queued_at: "2026-06-18T11:00:00Z",
    result: null,
    site_id: "main",
    started_at: null,
    status,
    target: null,
  };
}
