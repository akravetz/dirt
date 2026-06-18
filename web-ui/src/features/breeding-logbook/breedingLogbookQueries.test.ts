import { describe, expect, it } from "vitest";
import type { hostedComponents } from "@/api-client";
import {
  applyPendingPlantCommands,
  type BreedingLogbookPendingCommand,
  buildBulkCullRequest,
  buildBulkMoveRequest,
  buildBulkSexRequest,
  buildClonePlantsRequest,
  buildCreateSeedLotRequest,
  buildGerminatePlantsRequest,
  buildLogNoteRequest,
  canSubmitBulkCull,
  isPendingCommandProjected,
  pendingTimelineNotes,
  readonlyPlantPrefixPreview,
} from "./breedingLogbookMutations";
import {
  mapBootstrap,
  mapPlantDetail,
  mapPlantList,
  mapSeedLotList,
} from "./breedingLogbookQueries";
import type { PlantRow } from "./breedingLogbookTypes";

type HostedBootstrap = hostedComponents["schemas"]["BreedingLogbookBootstrapResponse"];
type HostedPlantDetail =
  hostedComponents["schemas"]["BreedingLogbookPlantDetailResponse"];
type HostedPlantList = hostedComponents["schemas"]["BreedingLogbookPlantListResponse"];
type HostedSeedLotList =
  hostedComponents["schemas"]["BreedingLogbookSeedLotListResponse"];
type HostedMetricHistory = hostedComponents["schemas"]["PlantMetricHistoryResponse"];
type HostedCommand = hostedComponents["schemas"]["CommandResponse"];

describe("breeding logbook hosted response mapping", () => {
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
          key: "main",
          display_name: "Main flower",
          stage_key: "flower",
          tent_id: "main",
          grid_position: null,
        },
      ],
    } satisfies HostedBootstrap;

    expect(mapBootstrap(bootstrap)).toMatchObject({
      today: "2026-05-05",
      todayLabel: "05/05/26",
      locations: [{ key: "main", displayName: "Main flower", stageKey: "flower" }],
    });
  });

  it("maps plant, seed lot, detail timeline, and metric history responses", () => {
    const plant = {
      id: "1",
      key: "SBBS-R1-001",
      name: "Plant A",
      generation: "R1",
      parents_label: "Plant B x Plant C",
      sex_key: "female",
      stage_key: "flower",
      stage_day: 12,
      germinated_on: "2026-03-15",
      veg_started_on: "2026-04-01",
      flower_started_on: "2026-05-01",
      culled_on: null,
      location_key: "main",
      location_label: "main",
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
    const seedLots = {
      seed_lots: [
        {
          id: "2",
          label: "SBBS R1 #2",
          prefix: "SBBS",
          generation: "R1",
          source: "cross",
          source_label: "in-house cross",
          parents_label: "Plant B x Plant C",
          sex_type_key: "regular",
          seed_count: null,
        },
      ],
    } satisfies HostedSeedLotList;
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

    expect(mapPlantList(plants).plants[0]?.locationLabel).toBe("main");
    expect(mapSeedLotList(seedLots).seedLots[0]?.parentsLabel).toBe(
      "Plant B x Plant C",
    );
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

describe("breeding logbook mutation request mapping", () => {
  it("builds snake_case write request bodies from screen-shaped inputs", () => {
    expect(
      buildCreateSeedLotRequest({
        idempotencyKey: "seed-click",
        source: "cross",
        generation: "F2",
        prefix: "MF",
        sexTypeKey: "regular",
        strain: null,
        cultivar: null,
        sourceName: null,
        vendorName: null,
        seedParentPlantKey: "MOM-001",
        pollenParentPlantKey: "DAD-001",
        seedCount: null,
        notes: null,
      }),
    ).toEqual({
      idempotency_key: "seed-click",
      source: "cross",
      generation: "F2",
      prefix: "MF",
      strain: null,
      cultivar: null,
      source_name: null,
      vendor_name: null,
      acquired_at: null,
      seed_parent_plant_key: "MOM-001",
      pollen_parent_plant_key: "DAD-001",
      pollinated_at: null,
      pollen_parent_is_reversed: null,
      seed_count: null,
      sex_type_key: "regular",
      notes: null,
    });

    expect(
      buildGerminatePlantsRequest({
        idempotencyKey: "germ-click",
        seedLotId: "42",
        count: 6,
        tentId: "veg",
        affectedLabel: "MF F2",
      }),
    ).toEqual({
      idempotency_key: "germ-click",
      seed_lot_id: "42",
      count: 6,
      tent_id: "veg",
      grid_position: null,
      germinated_at: null,
    });

    expect(
      buildClonePlantsRequest({
        idempotencyKey: "clone-click",
        motherPlantKey: "MF-001",
        count: 2,
        tentId: "clone",
      }),
    ).toEqual({
      idempotency_key: "clone-click",
      mother_plant_key: "MF-001",
      count: 2,
      tent_id: "clone",
      grid_position: null,
      taken_at: null,
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
        tentId: "flower",
        locationLabel: "Flower",
        locationStageKey: "flower",
      }),
    ).toEqual({
      idempotency_key: "move-click",
      plant_keys: ["MF-001"],
      tent_id: "flower",
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
  });

  it("keeps add-plants prefix read-only and out of germinate/clone requests", () => {
    expect(readonlyPlantPrefixPreview("MF")).toBe("MF-");
    expect(
      Object.keys(
        buildGerminatePlantsRequest({
          idempotencyKey: "germ-click",
          seedLotId: "42",
          count: 6,
          tentId: "veg",
          affectedLabel: "MF F2",
        }),
      ),
    ).not.toContain("plant_keys");
    expect(
      Object.keys(
        buildClonePlantsRequest({
          idempotencyKey: "clone-click",
          motherPlantKey: "MF-001",
          count: 2,
          tentId: "clone",
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

describe("breeding logbook pending UX helpers", () => {
  it("optimistically applies plant patches until the read projection catches up", () => {
    const plant = makePlantRow({
      key: "MF-001",
      sexKey: "unknown",
      stageKey: "veg",
      locationKey: "veg",
      locationLabel: "Veg",
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
          stageKey: "flower",
          locationKey: "flower",
          locationLabel: "Flower",
        },
      ],
    });

    expect(applyPendingPlantCommands([plant], [pendingSex, pendingMove])).toEqual([
      {
        ...plant,
        sexKey: "female",
        stageKey: "flower",
        locationKey: "flower",
        locationLabel: "Flower",
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
  });

  it("hides plants from active views immediately after a cull command is accepted", () => {
    const plant = makePlantRow({
      key: "MF-002",
      stageKey: "flower",
      locationKey: "flower",
      locationLabel: "Flower",
    });
    const pendingCull = makePendingCommand({
      command: makeCommand({ status: "succeeded" }),
      optimisticPlantPatches: [
        {
          plantKey: "MF-002",
          stageKey: "culled",
          locationKey: "removed",
          locationLabel: "Removed",
        },
      ],
    });

    const [projected] = applyPendingPlantCommands([plant], [pendingCull]);

    expect(projected?.stageKey).toBe("culled");
    expect(projected?.locationLabel).toBe("Removed");
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
  optimisticPlantPatches?: BreedingLogbookPendingCommand["optimisticPlantPatches"];
}): BreedingLogbookPendingCommand {
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
            plantKey: "MF-001",
            body,
          },
  };
}

function makePlantRow(overrides: Partial<PlantRow>): PlantRow {
  return {
    id: "1",
    key: "MF-001",
    name: "MF-001",
    generation: "F2",
    parentsLabel: "Mother x Father",
    sexKey: "unknown",
    stageKey: "veg",
    stageDay: 14,
    germinatedOn: "2026-06-01",
    vegStartedOn: "2026-06-10",
    flowerStartedOn: null,
    culledOn: null,
    locationKey: "veg",
    locationLabel: "Veg",
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
    capability_id: null,
    claimed_at: null,
    claimed_by: null,
    command_id: "command-1",
    command_type: "breeding_plant_note_create",
    device_id: null,
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
    tent_id: "breeding-logbook",
  };
}
