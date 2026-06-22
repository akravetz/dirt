import { describe, expect, it } from "vitest";
import type { hostedComponents } from "@/api-client";
import {
  filterSeedLots,
  normalizeSeedsSearch,
  validateSeedsSearch,
} from "./SeedsWorkspace";
import {
  buildCreateSeedLotRequest,
  buildUpdateSeedLotInventoryRequest,
} from "./seedsMutations";
import {
  mapSeedLotDetail,
  mapSeedLotList,
  mapSeedParentPlants,
  mapSeedsBootstrap,
} from "./seedsQueries";

type HostedBootstrap = hostedComponents["schemas"]["BreedingLogbookBootstrapResponse"];
type HostedPlantList = hostedComponents["schemas"]["BreedingLogbookPlantListResponse"];
type HostedSeedLotDetail =
  hostedComponents["schemas"]["BreedingLogbookSeedLotDetailResponse"];
type HostedSeedLotList =
  hostedComponents["schemas"]["BreedingLogbookSeedLotListResponse"];

describe("seeds hosted response mapping", () => {
  it("maps bootstrap, seed-lot list, parent plants, and detail responses", () => {
    const bootstrap = {
      today: "2026-06-18",
      today_label: "06/18/26",
      plant_sexes: [{ key: "female", display_name: "Female", display_order: 30 }],
      seed_lot_sex_types: [
        { key: "regular", display_name: "Regular", display_order: 30 },
      ],
      stages: [{ key: "flower", display_name: "Flower", display_order: 30 }],
      locations: [],
    } satisfies HostedBootstrap;
    const seedLots = {
      seed_lots: [
        {
          id: "lot-sbbs-r1",
          label: "SBBS R1 #2",
          prefix: "SBBS",
          strain: "Sirius Black x BS01",
          cultivar: "R1",
          generation: "R1",
          source: "cross",
          source_label: "in-house cross",
          parents_label: "Plant B x Plant C",
          sex_type_key: "regular",
          seed_count: null,
        },
      ],
    } satisfies HostedSeedLotList;
    const plants = {
      active_count: 1,
      culled_count: 0,
      group_by: "stage",
      plants: [
        {
          id: "1",
          key: "SBBS-R1-001",
          name: "Plant A",
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
        },
      ],
    } satisfies HostedPlantList;
    const detail = {
      acquired_at: null,
      created_plant_count: 4,
      cross: {
        notes: "Selected lowers.",
        parents_label: "Plant B x Plant C",
        pollen_parent_is_reversed: null,
        pollen_parent_key: "SBBS-R1-003",
        pollen_parent_label: "Plant C",
        pollen_parent_name: "Plant C",
        pollen_parent_source_plant_id: 3,
        pollinated_at: "2026-05-03T19:00:00Z",
        seed_parent_key: "SBBS-R1-002",
        seed_parent_label: "Plant B",
        seed_parent_name: "Plant B",
        seed_parent_source_plant_id: 2,
        source_cross_event_id: 43,
      },
      cultivar: "R1",
      generation: "R1",
      id: "lot-sbbs-r1",
      is_purchased: false,
      label: "SBBS R1 #2",
      line: {
        cultivar: "R1",
        description: "Selected resin line.",
        generation: "R1",
        prefix: "SBBS",
        source_line_id: 12,
        source_name: null,
        strain: "Sirius Black x BS01",
      },
      notes: "Keep cool.",
      parents_label: "Plant B x Plant C",
      prefix: "SBBS",
      produced_by_cross_event_source_id: 43,
      seed_count: 28,
      sex_type_key: "regular",
      source: "cross",
      source_label: "in-house cross",
      source_line_id: 12,
      source_seed_lot_id: 2,
      strain: "Sirius Black x BS01",
      vendor_name: null,
    } satisfies HostedSeedLotDetail;

    expect(mapSeedsBootstrap(bootstrap).seedLotSexTypes[0]).toMatchObject({
      key: "regular",
      displayName: "Regular",
    });
    expect(mapSeedLotList(seedLots).seedLots[0]).toMatchObject({
      prefix: "SBBS",
      parentsLabel: "Plant B x Plant C",
      sexTypeKey: "regular",
    });
    expect(mapSeedParentPlants(plants)[0]).toMatchObject({
      key: "SBBS-R1-001",
      sexKey: "female",
      stageKey: "flower",
    });
    expect(mapSeedLotDetail(detail)).toMatchObject({
      sourceSeedLotId: 2,
      createdPlantCount: 4,
      line: { sourceLineId: 12, description: "Selected resin line." },
      cross: { sourceCrossEventId: 43, seedParentLabel: "Plant B" },
    });
  });
});

describe("seeds mutation request mapping", () => {
  it("builds create and inventory update requests from screen-shaped inputs", () => {
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
        acquiredAt: null,
        seedParentPlantKey: "MOM-001",
        pollenParentPlantKey: "DAD-001",
        seedCount: 24,
        notes: "cool storage",
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
      seed_count: 24,
      sex_type_key: "regular",
      notes: "cool storage",
    });
    expect(
      buildUpdateSeedLotInventoryRequest({
        idempotencyKey: "seed-update-click",
        seedLotId: "lot-sbbs-r1",
        sourceSeedLotId: 2,
        label: "SBBS / Sirius Black x BS01",
        sexTypeKey: "feminized",
        seedCount: null,
        notes: "recount later",
        vendorName: "Archive",
        acquiredAt: "2026-06-18T16:00:00.000Z",
      }),
    ).toEqual({
      idempotency_key: "seed-update-click",
      seed_lot_source_id: 2,
      sex_type_key: "feminized",
      seed_count: null,
      notes: "recount later",
      vendor_name: "Archive",
      acquired_at: "2026-06-18T16:00:00.000Z",
    });
  });
});

describe("seeds URL search helpers", () => {
  it("filters inventory by source, sex type, and text search", () => {
    const seedLots = mapSeedLotList({
      seed_lots: [
        {
          id: "lot-cross",
          label: "MF F2",
          prefix: "MF",
          strain: "Mother x Father",
          cultivar: "F2",
          generation: "F2",
          source: "cross",
          source_label: "in-house cross",
          parents_label: "Mother x Father",
          sex_type_key: "regular",
          seed_count: 18,
        },
        {
          id: "lot-purchased",
          label: "Maruf Black",
          prefix: "MB",
          strain: "Maruf Black",
          cultivar: "F1",
          generation: "F1",
          source: "purchased",
          source_label: "Archive",
          parents_label: "Maruf Black (purchased)",
          sex_type_key: "feminized",
          seed_count: 6,
        },
      ],
    } satisfies HostedSeedLotList).seedLots;

    expect(
      filterSeedLots(seedLots, {
        q: "maruf",
        source: "all",
        sex: "all",
      }),
    ).toHaveLength(1);
    expect(
      filterSeedLots(seedLots, {
        q: "",
        source: "cross",
        sex: "regular",
      }),
    ).toHaveLength(1);
    expect(
      normalizeSeedsSearch(
        validateSeedsSearch({ source: "other", sex: "feminized", q: 42 }),
      ),
    ).toEqual({ q: "", source: "all", sex: "feminized" });
  });
});
