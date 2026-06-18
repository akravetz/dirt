import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { storage } from "@/shared/storage";
import { Sparkline } from "@/ui/Sparkline";
import {
  applyMockAddSeedLot,
  applyMockBulkCull,
  applyMockBulkMove,
  applyMockBulkSex,
  applyMockLogNote,
  applyMockSowPlants,
  applyMockTakeClones,
  useBreedingLogbookQueries,
} from "./breedingLogbookQueries";
import type {
  BreedingLogbookBootstrap,
  BreedingLogbookView,
  BulkPanel,
  LocationOption,
  PlantDetail,
  PlantGroupBy,
  PlantJournalEvent,
  PlantListLayout,
  PlantMetricHistory,
  PlantRow,
  PlantSexKey,
  PlantStageKey,
  SeedLotSource,
  SeedLotSummary,
} from "./breedingLogbookTypes";

const THEME_STORAGE_KEY = "dirt.theme";
type Theme = "light" | "dark";
type AddPlantMode = "germinate" | "clone";

type AddSeedLotDraft = {
  source: SeedLotSource;
  motherId: string;
  fatherId: string;
  generation: string;
  prefix: string;
  strain: string;
  breeder: string;
};

type TableGroup = {
  key: string;
  label: string;
  stageKey: PlantStageKey;
  plants: readonly PlantRow[];
};

const VIEW_TABS = [
  { value: "plants", label: "Plants" },
  { value: "add-seeds", label: "Add seeds" },
  { value: "add-plants", label: "Add plants" },
] as const satisfies readonly {
  value: Exclude<BreedingLogbookView, "detail">;
  label: string;
}[];

const GENERATION_OPTIONS = ["F1", "F2", "F3", "F4", "S1", "BX1"] as const;
const EMPTY_SELECTION = new Set<string>();
const FALLBACK_LOCATION: LocationOption = {
  key: "veg",
  displayName: "Veg tent",
  stageKey: "veg",
};
const CULLED_LOCATION: LocationOption = {
  key: "removed",
  displayName: "Removed",
  stageKey: "culled",
};
const initialSeedLotDraft: AddSeedLotDraft = {
  source: "cross",
  motherId: "plant-d",
  fatherId: "r2",
  generation: "F2",
  prefix: "",
  strain: "",
  breeder: "",
};

function readStoredTheme(): Theme {
  const raw = storage.get(THEME_STORAGE_KEY);
  return raw === "dark" ? "dark" : "light";
}

export function BreedingLogbookPage(): ReactNode {
  const queryClient = useQueryClient();
  const [view, setView] = useState<BreedingLogbookView>("plants");
  const [layout, setLayout] = useState<PlantListLayout>("table");
  const [groupBy, setGroupBy] = useState<PlantGroupBy>("stage");
  const [showCulled, setShowCulled] = useState(false);
  const [selectedPlantIds, setSelectedPlantIds] =
    useState<ReadonlySet<string>>(EMPTY_SELECTION);
  const [bulkPanel, setBulkPanel] = useState<BulkPanel>(null);
  const [bulkSex, setBulkSex] = useState<PlantSexKey>("female");
  const [moveLocationKey, setMoveLocationKey] = useState("veg");
  const [seedLotDraft, setSeedLotDraft] =
    useState<AddSeedLotDraft>(initialSeedLotDraft);
  const [addPlantMode, setAddPlantMode] = useState<AddPlantMode>("germinate");
  const [selectedSeedLotId, setSelectedSeedLotId] = useState("lot-maruf-black");
  const [germinateCount, setGerminateCount] = useState(10);
  const [germinateLocationKey, setGerminateLocationKey] = useState("clone");
  const [cloneMotherId, setCloneMotherId] = useState("plant-a");
  const [cloneCount, setCloneCount] = useState(4);
  const [cloneLocationKey, setCloneLocationKey] = useState("veg");
  const [detailPlantId, setDetailPlantId] = useState("plant-a");
  const [noteText, setNoteText] = useState("");
  const [draggingPlantId, setDraggingPlantId] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(readStoredTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    storage.set(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const logbook = useBreedingLogbookQueries(detailPlantId);
  const plants = logbook.plants.plants;
  const seedLots = logbook.seedLots.seedLots;
  const visiblePlants = plants.filter(
    (plant) => showCulled || plant.stageKey !== "culled",
  );
  const selectedPlants = plants.filter((plant) => selectedPlantIds.has(plant.id));
  const detailPlant =
    plants.find((plant) => plant.id === detailPlantId) ?? logbook.detail.plant;
  const detail = { ...logbook.detail, plant: detailPlant };

  const openDetail = (plantId: string) => {
    setDetailPlantId(plantId);
    setView("detail");
  };
  const clearSelection = () => {
    setSelectedPlantIds(new Set());
    setBulkPanel(null);
  };
  const selectedLocation =
    logbook.bootstrap.locations.find((location) => location.key === moveLocationKey) ??
    logbook.bootstrap.locations[0] ??
    FALLBACK_LOCATION;

  return (
    <main className="flex-1 overflow-auto bg-paper text-ink">
      <BreedingLogbookTopBar
        todayLabel={logbook.bootstrap.todayLabel}
        theme={theme}
        view={view}
        onThemeChange={setTheme}
        onViewChange={(nextView) => {
          setView(nextView);
        }}
      />
      <div className="mx-auto flex max-w-330 flex-col gap-4 px-4 pb-14 pt-4 sm:px-6">
        {view === "plants" ? (
          <PlantsSurface
            activeCount={logbook.plants.activeCount}
            bootstrap={logbook.bootstrap}
            bulkPanel={bulkPanel}
            bulkSex={bulkSex}
            culledCount={logbook.plants.culledCount}
            draggingPlantId={draggingPlantId}
            groupBy={groupBy}
            layout={layout}
            moveLocationKey={moveLocationKey}
            plants={visiblePlants}
            selectedLocation={selectedLocation}
            selectedPlantIds={selectedPlantIds}
            selectedPlants={selectedPlants}
            showCulled={showCulled}
            onAddPlants={() => {
              setView("add-plants");
            }}
            onAddSeeds={() => {
              setView("add-seeds");
            }}
            onApplyCull={() => {
              applyMockBulkCull(queryClient, selectedPlantIds);
              clearSelection();
            }}
            onApplyMove={() => {
              applyMockBulkMove(queryClient, selectedPlantIds, selectedLocation);
              clearSelection();
            }}
            onApplySex={() => {
              applyMockBulkSex(queryClient, selectedPlantIds, bulkSex);
              clearSelection();
            }}
            onBulkPanelChange={setBulkPanel}
            onBulkSexChange={setBulkSex}
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
              applyMockBulkMove(queryClient, moveIds, location);
              clearSelection();
              setDraggingPlantId(null);
            }}
            onGroupByChange={setGroupBy}
            onLayoutChange={setLayout}
            onMoveLocationChange={setMoveLocationKey}
            onOpenBulkNote={() => {
              const firstSelected = selectedPlants[0];
              if (firstSelected) openDetail(firstSelected.id);
            }}
            onOpenDetail={openDetail}
            onSelectedPlantIdsChange={setSelectedPlantIds}
            onShowCulledChange={setShowCulled}
          />
        ) : view === "add-seeds" ? (
          <AddSeedsSurface
            draft={seedLotDraft}
            plants={plants}
            seedLots={seedLots}
            onDraftChange={setSeedLotDraft}
            onGerminate={(seedLotId) => {
              setSelectedSeedLotId(seedLotId);
              setAddPlantMode("germinate");
              setView("add-plants");
            }}
            onSubmit={() => {
              const created = createSeedLotFromDraft(seedLotDraft, plants);
              if (created === null) return;
              const seedLot = applyMockAddSeedLot(queryClient, created);
              setSelectedSeedLotId(seedLot.id);
              setSeedLotDraft({
                ...initialSeedLotDraft,
                source: seedLotDraft.source,
              });
            }}
            onViewChange={setView}
          />
        ) : view === "add-plants" ? (
          <AddPlantsSurface
            cloneCount={cloneCount}
            cloneLocationKey={cloneLocationKey}
            cloneMotherId={cloneMotherId}
            germinateCount={germinateCount}
            germinateLocationKey={germinateLocationKey}
            mode={addPlantMode}
            plants={plants}
            seedLots={seedLots}
            selectedSeedLotId={selectedSeedLotId}
            bootstrap={logbook.bootstrap}
            onAddSeeds={() => {
              setView("add-seeds");
            }}
            onCloneCountChange={setCloneCount}
            onCloneLocationChange={setCloneLocationKey}
            onCloneMotherChange={setCloneMotherId}
            onGerminateCountChange={setGerminateCount}
            onGerminateLocationChange={setGerminateLocationKey}
            onModeChange={setAddPlantMode}
            onSeedLotChange={setSelectedSeedLotId}
            onSow={(seedLot, location) => {
              applyMockSowPlants(queryClient, {
                seedLot,
                count: germinateCount,
                location,
              });
              setView("plants");
              clearSelection();
            }}
            onTakeClones={(mother, location, prefix) => {
              applyMockTakeClones(queryClient, {
                mother,
                count: cloneCount,
                location,
                prefix,
              });
              setView("plants");
              clearSelection();
            }}
            onViewChange={setView}
          />
        ) : (
          <PlantJournalDetail
            detail={detail}
            noteText={noteText}
            onBack={() => {
              setView("plants");
            }}
            onLogNote={() => {
              applyMockLogNote(queryClient, detail.plant, noteText);
              setNoteText("");
            }}
            onNoteTextChange={setNoteText}
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

function BreedingLogbookTopBar({
  onThemeChange,
  onViewChange,
  theme,
  todayLabel,
  view,
}: {
  onThemeChange: (theme: Theme) => void;
  onViewChange: (view: Exclude<BreedingLogbookView, "detail">) => void;
  theme: Theme;
  todayLabel: string;
  view: BreedingLogbookView;
}): ReactNode {
  const nextTheme: Theme = theme === "dark" ? "light" : "dark";

  return (
    <header className="sticky top-0 z-30 flex flex-wrap items-center gap-x-4 gap-y-3 border-b border-rule-strong bg-paper px-4 py-3 sm:px-6">
      <div className="flex min-w-0 items-baseline gap-2.5">
        <h1 className="font-serif text-fs-24 font-medium italic leading-none text-ink">
          dirt<span className="text-accent-magenta">.</span>
        </h1>
        <span
          aria-hidden="true"
          className="mb-1.5 inline-block h-px w-5 self-end bg-rule-strong"
        />
        <p className="font-mono text-fs-10 uppercase tracking-cap-field text-ink-3">
          Breeding Logbook
        </p>
      </div>
      <nav
        aria-label="Breeding logbook"
        className="order-3 flex w-full items-center gap-1.5 overflow-x-auto sm:order-none sm:w-auto"
      >
        {VIEW_TABS.map((tab) => {
          const active =
            view === tab.value || (tab.value === "plants" && view === "detail");
          return (
            <button
              key={tab.value}
              type="button"
              onClick={() => {
                onViewChange(tab.value);
              }}
              aria-current={active ? "page" : undefined}
              className={tabButtonClass(active)}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>
      <div className="ml-auto flex items-center gap-2">
        <p className="hidden font-mono text-fs-9 uppercase tracking-caps text-ink-3 sm:block">
          {todayLabel} / operator access
        </p>
        <span className="inline-flex items-center gap-2 border border-status-ok bg-paper-2 px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          <span aria-hidden="true" className="h-1.5 w-1.5 bg-status-ok" />
          Operator
        </span>
        <button
          type="button"
          aria-label={`Switch to ${nextTheme} theme`}
          onClick={() => {
            onThemeChange(nextTheme);
          }}
          className="grid h-8.5 w-8.5 place-items-center border border-rule-strong bg-paper font-mono text-fs-14 text-ink transition hover:border-ink-2"
        >
          {theme === "dark" ? "◑" : "◐"}
        </button>
      </div>
    </header>
  );
}

function PlantsSurface({
  activeCount,
  bootstrap,
  bulkPanel,
  bulkSex,
  culledCount,
  draggingPlantId,
  groupBy,
  layout,
  moveLocationKey,
  onAddPlants,
  onAddSeeds,
  onApplyCull,
  onApplyMove,
  onApplySex,
  onBulkPanelChange,
  onBulkSexChange,
  onClearSelection,
  onDragEnd,
  onDragStart,
  onDropPlant,
  onGroupByChange,
  onLayoutChange,
  onMoveLocationChange,
  onOpenBulkNote,
  onOpenDetail,
  onSelectedPlantIdsChange,
  onShowCulledChange,
  plants,
  selectedLocation,
  selectedPlantIds,
  selectedPlants,
  showCulled,
}: {
  activeCount: number;
  bootstrap: BreedingLogbookBootstrap;
  bulkPanel: BulkPanel;
  bulkSex: PlantSexKey;
  culledCount: number;
  draggingPlantId: string | null;
  groupBy: PlantGroupBy;
  layout: PlantListLayout;
  moveLocationKey: string;
  plants: readonly PlantRow[];
  selectedLocation: LocationOption;
  selectedPlantIds: ReadonlySet<string>;
  selectedPlants: readonly PlantRow[];
  showCulled: boolean;
  onAddPlants: () => void;
  onAddSeeds: () => void;
  onApplyCull: () => void;
  onApplyMove: () => void;
  onApplySex: () => void;
  onBulkPanelChange: (panel: BulkPanel) => void;
  onBulkSexChange: (sex: PlantSexKey) => void;
  onClearSelection: () => void;
  onDragEnd: () => void;
  onDragStart: (plantId: string) => void;
  onDropPlant: (location: LocationOption) => void;
  onGroupByChange: (groupBy: PlantGroupBy) => void;
  onLayoutChange: (layout: PlantListLayout) => void;
  onMoveLocationChange: (locationKey: string) => void;
  onOpenBulkNote: () => void;
  onOpenDetail: (plantId: string) => void;
  onSelectedPlantIdsChange: (plantIds: ReadonlySet<string>) => void;
  onShowCulledChange: (showCulled: boolean) => void;
}): ReactNode {
  const selectedCount = selectedPlantIds.size;
  const allVisibleSelected =
    plants.length > 0 && plants.every((plant) => selectedPlantIds.has(plant.id));
  const someVisibleSelected = plants.some((plant) => selectedPlantIds.has(plant.id));
  const listFooter = showCulled
    ? `${plants.length} plants / grouped by ${groupBy} / ${activeCount} active / ${culledCount} culled`
    : `${activeCount} active shown / grouped by ${groupBy} / ${culledCount} culled hidden`;

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
            {activeCount} active / {culledCount} culled
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
        culledCount={culledCount}
        groupBy={groupBy}
        layout={layout}
        showCulled={showCulled}
        onGroupByChange={onGroupByChange}
        onLayoutChange={onLayoutChange}
        onShowCulledChange={onShowCulledChange}
      />
      {selectedCount > 0 ? (
        <BulkActionToolbar
          bulkPanel={bulkPanel}
          bulkSex={bulkSex}
          locations={bootstrap.locations.filter(
            (location) => location.stageKey !== "culled",
          )}
          moveLocationKey={moveLocationKey}
          selectedCount={selectedCount}
          selectedLocation={selectedLocation}
          onApplyCull={onApplyCull}
          onApplyMove={onApplyMove}
          onApplySex={onApplySex}
          onBulkPanelChange={onBulkPanelChange}
          onBulkSexChange={onBulkSexChange}
          onClear={onClearSelection}
          onMoveLocationChange={onMoveLocationChange}
          onOpenNote={onOpenBulkNote}
        />
      ) : null}
      {layout === "table" ? (
        <PlantTable
          allChecked={allVisibleSelected}
          bootstrap={bootstrap}
          groupBy={groupBy}
          plants={plants}
          selectedPlantIds={selectedPlantIds}
          someChecked={someVisibleSelected}
          onOpenDetail={onOpenDetail}
          onToggleAll={toggleAllVisible}
          onTogglePlant={togglePlant}
        />
      ) : (
        <PlantBoard
          bootstrap={bootstrap}
          draggingPlantId={draggingPlantId}
          plants={plants}
          selectedPlantIds={selectedPlantIds}
          showCulled={showCulled}
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
          ? ` / ${selectedPlants.length} selected for mock-local actions`
          : ""}
      </p>
    </>
  );
}

function PlantChrome({
  culledCount,
  groupBy,
  layout,
  onGroupByChange,
  onLayoutChange,
  onShowCulledChange,
  showCulled,
}: {
  culledCount: number;
  groupBy: PlantGroupBy;
  layout: PlantListLayout;
  onGroupByChange: (groupBy: PlantGroupBy) => void;
  onLayoutChange: (layout: PlantListLayout) => void;
  onShowCulledChange: (showCulled: boolean) => void;
  showCulled: boolean;
}): ReactNode {
  return (
    <section className="flex flex-wrap items-center gap-2 border border-rule bg-paper-2 px-3 py-2.5">
      <button
        type="button"
        className="border border-rule px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink"
      >
        ⊟ Filter
      </button>
      <Segmented
        label="Group"
        options={[
          { label: "Stage", value: "stage" },
          { label: "Parents", value: "parents" },
        ]}
        value={groupBy}
        onChange={onGroupByChange}
      />
      <div className="min-w-44 flex-1 border border-rule bg-paper px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        ⌕ search plants
      </div>
      <button
        type="button"
        onClick={() => {
          onShowCulledChange(!showCulled);
        }}
        className={
          showCulled
            ? "border border-ink bg-paper px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink"
            : "border border-rule px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink"
        }
      >
        {showCulled ? "Showing culled" : `Show culled (${culledCount})`}
      </button>
      <Segmented
        label="Layout"
        options={[
          { label: "▤ Table", value: "table" },
          { label: "▥ Board", value: "board" },
        ]}
        value={layout}
        onChange={onLayoutChange}
      />
    </section>
  );
}

function BulkActionToolbar({
  bulkPanel,
  bulkSex,
  locations,
  moveLocationKey,
  onApplyCull,
  onApplyMove,
  onApplySex,
  onBulkPanelChange,
  onBulkSexChange,
  onClear,
  onMoveLocationChange,
  onOpenNote,
  selectedCount,
  selectedLocation,
}: {
  bulkPanel: BulkPanel;
  bulkSex: PlantSexKey;
  locations: readonly LocationOption[];
  moveLocationKey: string;
  selectedCount: number;
  selectedLocation: LocationOption;
  onApplyCull: () => void;
  onApplyMove: () => void;
  onApplySex: () => void;
  onBulkPanelChange: (panel: BulkPanel) => void;
  onBulkSexChange: (sex: PlantSexKey) => void;
  onClear: () => void;
  onMoveLocationChange: (locationKey: string) => void;
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
          <Button variant="primary" onClick={onApplySex}>
            Apply
          </Button>
        </div>
      ) : null}
      {bulkPanel === "move" ? (
        <div className="flex flex-wrap items-center gap-3 border-t border-rule bg-paper px-3 py-3">
          <SelectField
            label="Move to"
            value={moveLocationKey}
            options={locations.map((location) => ({
              label: location.displayName,
              value: location.key,
            }))}
            onChange={onMoveLocationChange}
          />
          <Button variant="primary" onClick={onApplyMove}>
            Move {selectedCount} →
          </Button>
          <p className="font-mono text-fs-9 uppercase tracking-caps text-ink-3">
            logs a mock move event to {selectedLocation.displayName}
          </p>
        </div>
      ) : null}
      {bulkPanel === "cull" ? (
        <div className="flex flex-wrap items-center gap-3 border-t border-rule bg-paper px-3 py-3">
          <p className="font-mono text-fs-10 uppercase tracking-caps text-status-err">
            Marks selected plants culled in mock cache. Reversible once real writes
            exist.
          </p>
          <Button variant="danger" onClick={onApplyCull}>
            x Confirm cull
          </Button>
        </div>
      ) : null}
    </section>
  );
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
  onToggleAll,
  onTogglePlant,
  plants,
  selectedPlantIds,
  someChecked,
}: {
  allChecked: boolean;
  bootstrap: BreedingLogbookBootstrap;
  groupBy: PlantGroupBy;
  plants: readonly PlantRow[];
  selectedPlantIds: ReadonlySet<string>;
  someChecked: boolean;
  onOpenDetail: (plantId: string) => void;
  onToggleAll: () => void;
  onTogglePlant: (plantId: string) => void;
}): ReactNode {
  const groups = useMemo(
    () => groupPlants(plants, bootstrap, groupBy),
    [plants, bootstrap, groupBy],
  );

  return (
    <section className="overflow-x-auto border border-rule-strong bg-paper">
      <div className="min-w-230">
        <div className="grid grid-cols-[36px_150px_42px_168px_40px_64px_72px_72px_72px_minmax(150px,1fr)] gap-2 border-b border-rule-strong bg-paper-2 px-3 py-2 font-mono text-fs-9 uppercase tracking-caps text-ink-3">
          <Checkbox
            checked={allChecked}
            indeterminate={someChecked && !allChecked}
            label="Select all visible plants"
            onChange={onToggleAll}
          />
          <span>Plant</span>
          <span>Gen</span>
          <span>Parents</span>
          <span>Sex</span>
          <span>Days</span>
          <span>Germ</span>
          <span>Veg</span>
          <span>Flwr</span>
          <span>Last note</span>
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
  plant,
  selected,
}: {
  plant: PlantRow;
  selected: boolean;
  onOpenDetail: (plantId: string) => void;
  onTogglePlant: (plantId: string) => void;
}): ReactNode {
  return (
    <div
      className={
        selected
          ? "grid grid-cols-[36px_150px_42px_168px_40px_64px_72px_72px_72px_minmax(150px,1fr)] items-center gap-2 border-b border-rule bg-accent-magenta/8 px-3 py-2.5 font-sans text-fs-11 last:border-b-0"
          : "grid grid-cols-[36px_150px_42px_168px_40px_64px_72px_72px_72px_minmax(150px,1fr)] items-center gap-2 border-b border-rule px-3 py-2.5 font-sans text-fs-11 last:border-b-0 hover:bg-paper-2"
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
        <button
          type="button"
          onClick={() => {
            onOpenDetail(plant.id);
          }}
          className="max-w-full truncate font-semibold text-ink underline-offset-2 hover:underline"
        >
          {plant.name}
        </button>
        <p className="mt-0.5 truncate font-mono text-fs-9 uppercase tracking-caps text-ink-3">
          {plant.key} / {plant.locationLabel}
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
      <span className="truncate text-ink-3">{plant.lastNote}</span>
    </div>
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
  plants,
  selectedPlantIds,
  showCulled,
}: {
  bootstrap: BreedingLogbookBootstrap;
  draggingPlantId: string | null;
  plants: readonly PlantRow[];
  selectedPlantIds: ReadonlySet<string>;
  showCulled: boolean;
  onDragEnd: () => void;
  onDragStart: (plantId: string) => void;
  onDropPlant: (location: LocationOption) => void;
  onOpenDetail: (plantId: string) => void;
  onTogglePlant: (plantId: string) => void;
}): ReactNode {
  const dropLocations = bootstrap.locations.filter((location) =>
    showCulled ? true : location.stageKey !== "culled",
  );
  const boardStages = bootstrap.stages.filter((stage) =>
    showCulled ? true : stage.key !== "culled",
  );
  const columns = boardStages.map((stage) => {
    const location =
      stage.key === "culled"
        ? CULLED_LOCATION
        : dropLocations.find((candidate) => candidate.stageKey === stage.key);
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
                  column.location.stageKey === "culled"
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
        drag a chip, or a selected set, across a column boundary to log a mock-local
        move
      </p>
    </section>
  );
}

function PlantBoardChip({
  onDragEnd,
  onDragStart,
  onOpenDetail,
  onTogglePlant,
  plant,
  selected,
}: {
  plant: PlantRow;
  selected: boolean;
  onDragEnd: () => void;
  onDragStart: (plantId: string) => void;
  onOpenDetail: (plantId: string) => void;
  onTogglePlant: (plantId: string) => void;
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
              onOpenDetail(plant.id);
            }}
            className="max-w-full truncate font-sans text-fs-12 font-semibold text-ink underline-offset-2 hover:underline"
          >
            {plant.name}
          </button>
          <p className="mt-1 truncate font-mono text-fs-9 uppercase tracking-caps text-ink-3">
            {plant.generation} /{" "}
            {plant.culledOn
              ? `culled ${shortDate(plant.culledOn)}`
              : `d${plant.stageDay}`}
          </p>
        </div>
        <span className={`font-mono text-fs-13 ${sexTextClass(plant.sexKey)}`}>
          {sexGlyph(plant.sexKey)}
        </span>
      </div>
    </li>
  );
}

function AddSeedsSurface({
  draft,
  onDraftChange,
  onGerminate,
  onSubmit,
  onViewChange,
  plants,
  seedLots,
}: {
  draft: AddSeedLotDraft;
  plants: readonly PlantRow[];
  seedLots: readonly SeedLotSummary[];
  onDraftChange: (draft: AddSeedLotDraft) => void;
  onGerminate: (seedLotId: string) => void;
  onSubmit: () => void;
  onViewChange: (view: BreedingLogbookView) => void;
}): ReactNode {
  const activePlants = plants.filter((plant) => plant.stageKey !== "culled");
  const motherOptions = activePlants
    .filter((plant) => plant.sexKey !== "male")
    .map((plant) => ({
      value: plant.id,
      label: `${plant.name} ${plant.sexKey === "female" ? "♀" : "?"}`,
    }));
  const fatherOptions = activePlants
    .filter((plant) => plant.sexKey !== "female")
    .map((plant) => ({
      value: plant.id,
      label: `${plant.name} ${plant.sexKey === "male" ? "♂" : "?"}`,
    }));
  const preview = seedLotPreview(draft, plants);
  const canSubmit = draft.source === "cross" || draft.strain.trim().length > 0;

  return (
    <>
      <SurfaceHeader
        description="Record a deterministic mock seed lot without creating plant rows."
        title="Add seeds"
        onBack={() => {
          onViewChange("plants");
        }}
      />
      <section className="grid gap-px border border-rule-strong bg-rule md:grid-cols-[minmax(360px,1fr)_minmax(280px,360px)]">
        <div className="bg-paper-2 p-5">
          <Segmented
            label="Source"
            options={[
              { label: "Our cross", value: "cross" },
              { label: "Purchased", value: "purchased" },
            ]}
            value={draft.source}
            onChange={(source) => {
              onDraftChange({ ...draft, source });
            }}
          />
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {draft.source === "cross" ? (
              <>
                <SelectField
                  label="Mother ♀"
                  value={draft.motherId}
                  options={motherOptions}
                  onChange={(motherId) => {
                    onDraftChange({ ...draft, motherId });
                  }}
                />
                <SelectField
                  label="Father ♂"
                  value={draft.fatherId}
                  options={fatherOptions}
                  onChange={(fatherId) => {
                    onDraftChange({ ...draft, fatherId });
                  }}
                />
                <SelectField
                  label="Generation"
                  value={draft.generation}
                  options={GENERATION_OPTIONS.map((generation) => ({
                    value: generation,
                    label: generation,
                  }))}
                  onChange={(generation) => {
                    onDraftChange({ ...draft, generation });
                  }}
                />
                <TextField
                  label="Prefix"
                  value={draft.prefix}
                  placeholder={preview.prefix}
                  onChange={(prefix) => {
                    onDraftChange({ ...draft, prefix });
                  }}
                />
              </>
            ) : (
              <>
                <TextField
                  label="Strain / cultivar"
                  value={draft.strain}
                  placeholder="Maruf Black"
                  onChange={(strain) => {
                    onDraftChange({ ...draft, strain });
                  }}
                />
                <TextField
                  label="Breeder / source"
                  value={draft.breeder}
                  placeholder="archive"
                  onChange={(breeder) => {
                    onDraftChange({ ...draft, breeder });
                  }}
                />
                <SelectField
                  label="Generation"
                  value={draft.generation}
                  options={GENERATION_OPTIONS.map((generation) => ({
                    value: generation,
                    label: generation,
                  }))}
                  onChange={(generation) => {
                    onDraftChange({ ...draft, generation });
                  }}
                />
                <TextField
                  label="Prefix"
                  value={draft.prefix}
                  placeholder={preview.prefix}
                  onChange={(prefix) => {
                    onDraftChange({ ...draft, prefix });
                  }}
                />
              </>
            )}
          </div>
          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-3">
            <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              {preview.label} / labels {preview.prefix}-01...
            </p>
            <Button variant="primary" disabled={!canSubmit} onClick={onSubmit}>
              Record seed lot
            </Button>
          </div>
        </div>
        <div className="bg-paper p-4">
          <h3 className="font-sans text-fs-13 font-semibold text-ink">
            Seed lots on file / {seedLots.length} lots
          </h3>
          <div className="mt-3 grid gap-2">
            {seedLots.map((lot) => (
              <div key={lot.id} className="border border-rule bg-paper-2 px-3 py-2.5">
                <p className="font-sans text-fs-12 font-semibold text-ink">
                  {lot.label}
                </p>
                <p className="mt-1 font-mono text-fs-9 uppercase tracking-caps text-ink-3">
                  {lot.source === "purchased" ? "purchased" : "in-house cross"} /{" "}
                  {lot.prefix}-... / {lot.generation}
                </p>
                <button
                  type="button"
                  onClick={() => {
                    onGerminate(lot.id);
                  }}
                  className="mt-2 border border-rule px-2 py-1 font-mono text-fs-9 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink"
                >
                  Germinate →
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}

function AddPlantsSurface({
  bootstrap,
  cloneCount,
  cloneLocationKey,
  cloneMotherId,
  germinateCount,
  germinateLocationKey,
  mode,
  onAddSeeds,
  onCloneCountChange,
  onCloneLocationChange,
  onCloneMotherChange,
  onGerminateCountChange,
  onGerminateLocationChange,
  onModeChange,
  onSeedLotChange,
  onSow,
  onTakeClones,
  onViewChange,
  plants,
  seedLots,
  selectedSeedLotId,
}: {
  bootstrap: BreedingLogbookBootstrap;
  cloneCount: number;
  cloneLocationKey: string;
  cloneMotherId: string;
  germinateCount: number;
  germinateLocationKey: string;
  mode: AddPlantMode;
  plants: readonly PlantRow[];
  seedLots: readonly SeedLotSummary[];
  selectedSeedLotId: string;
  onAddSeeds: () => void;
  onCloneCountChange: (count: number) => void;
  onCloneLocationChange: (locationKey: string) => void;
  onCloneMotherChange: (plantId: string) => void;
  onGerminateCountChange: (count: number) => void;
  onGerminateLocationChange: (locationKey: string) => void;
  onModeChange: (mode: AddPlantMode) => void;
  onSeedLotChange: (seedLotId: string) => void;
  onSow: (seedLot: SeedLotSummary, location: LocationOption) => void;
  onTakeClones: (mother: PlantRow, location: LocationOption, prefix: string) => void;
  onViewChange: (view: BreedingLogbookView) => void;
}): ReactNode {
  const selectedSeedLot =
    seedLots.find((lot) => lot.id === selectedSeedLotId) ?? seedLots[0];
  const germLocation =
    bootstrap.locations.find((location) => location.key === germinateLocationKey) ??
    bootstrap.locations[0] ??
    FALLBACK_LOCATION;
  const cloneLocations = bootstrap.locations.filter((location) =>
    ["veg", "flower"].includes(location.stageKey),
  );
  const cloneLocation =
    cloneLocations.find((location) => location.key === cloneLocationKey) ??
    cloneLocations[0] ??
    bootstrap.locations[0] ??
    FALLBACK_LOCATION;
  const cloneMothers = plants.filter(
    (plant) => plant.stageKey !== "culled" && plant.stageKey !== "germinating",
  );
  const mother =
    cloneMothers.find((plant) => plant.id === cloneMotherId) ?? cloneMothers[0];
  const clonePrefix = clonePrefixFor(mother?.name ?? "mother");
  const germPreview = selectedSeedLot
    ? previewLabels(selectedSeedLot.prefix, germinateCount)
    : [];
  const clonePreview = previewLabels(clonePrefix, cloneCount);

  return (
    <>
      <SurfaceHeader
        description="Create mock plant rows by germinating a seed lot or taking clones."
        title="Add plants"
        onBack={() => {
          onViewChange("plants");
        }}
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
              <SelectField
                label="Into tent"
                value={germinateLocationKey}
                options={bootstrap.locations
                  .filter((location) =>
                    ["germinating", "veg"].includes(location.stageKey),
                  )
                  .map((location) => ({
                    label: location.displayName,
                    value: location.key,
                  }))}
                onChange={onGerminateLocationChange}
              />
              <MockFact
                label="Label prefix"
                value={selectedSeedLot ? `${selectedSeedLot.prefix}-` : "NEW-"}
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
              <SelectField
                label="Into tent"
                value={cloneLocation.key}
                options={cloneLocations.map((location) => ({
                  label: location.displayName,
                  value: location.key,
                }))}
                onChange={onCloneLocationChange}
              />
              <MockFact label="Label prefix" value={`${clonePrefix}-`} />
            </div>
          )}
        </div>
        <div className="bg-paper p-4">
          <h3 className="font-sans text-fs-13 font-semibold text-ink">Preview</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {(mode === "germinate" ? germPreview : clonePreview)
              .slice(0, 18)
              .map((label) => (
                <span
                  key={label}
                  className="inline-flex items-center gap-2 border border-rule bg-paper-2 px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink"
                >
                  <span
                    aria-hidden="true"
                    className={
                      mode === "germinate"
                        ? "h-1.5 w-1.5 bg-leaf"
                        : "h-1.5 w-1.5 bg-sensor-vpd"
                    }
                  />
                  {label}
                </span>
              ))}
          </div>
          <p className="mt-4 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            {mode === "germinate"
              ? `${selectedSeedLot?.parentsLabel ?? "No seed lot"} / gen ${selectedSeedLot?.generation ?? "?"} / ${germLocation.displayName}`
              : `clone of ${mother?.name ?? "mother"} / gen ${mother?.generation ?? "?"} / sex ${mother ? sexLabel(mother.sexKey) : "unknown"}`}
          </p>
          <div className="mt-5 flex justify-end">
            {mode === "germinate" ? (
              <Button
                variant="primary"
                disabled={!selectedSeedLot}
                onClick={() => {
                  if (selectedSeedLot) onSow(selectedSeedLot, germLocation);
                }}
              >
                Sow {germinateCount} plants →
              </Button>
            ) : (
              <Button
                variant="primary"
                disabled={!mother}
                onClick={() => {
                  if (mother) onTakeClones(mother, cloneLocation, clonePrefix);
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
  noteText,
  onBack,
  onLogNote,
  onNoteTextChange,
}: {
  detail: PlantDetail;
  noteText: string;
  onBack: () => void;
  onLogNote: () => void;
  onNoteTextChange: (text: string) => void;
}): ReactNode {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

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
            <Fact label="Germinated" value={shortDate(detail.plant.germinatedOn)} />
            <Fact
              label="Vegged"
              value={
                detail.plant.vegStartedOn ? shortDate(detail.plant.vegStartedOn) : "-"
              }
            />
            <Fact
              label="Flowered"
              value={
                detail.plant.flowerStartedOn
                  ? shortDate(detail.plant.flowerStartedOn)
                  : "-"
              }
            />
            <Fact label="Location" value={detail.plant.locationLabel} />
          </div>
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
          <div className="border border-rule bg-paper-2 p-3">
            <textarea
              value={noteText}
              onChange={(event) => {
                onNoteTextChange(event.target.value);
              }}
              placeholder="Log an observation - leaves curling, vigour, pheno notes..."
              className="min-h-20 w-full resize-y border border-rule bg-paper p-3 font-sans text-fs-12 text-ink placeholder:text-ink-3"
            />
            <div className="mt-2 flex flex-wrap justify-end gap-2">
              <Button variant="secondary">+ Attach photo</Button>
              <Button
                variant="primary"
                disabled={noteText.trim().length === 0}
                onClick={onLogNote}
              >
                Log note
              </Button>
            </div>
          </div>
          <ol className="mt-4 grid gap-3">
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
            {detail.plant.locationLabel}
          </h3>
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
    </>
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
    <div className="flex flex-wrap items-center gap-2">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <div className="flex border border-rule bg-paper">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => {
              onChange(option.value);
            }}
            className={
              option.value === value
                ? "border-r border-rule bg-paper-2 px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink last:border-r-0"
                : "border-r border-rule px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition last:border-r-0 hover:text-ink"
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

function SelectField<TValue extends string>({
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
        value={value}
        onChange={(event) => {
          onChange(event.target.value as TValue);
        }}
        className="h-9 border border-rule bg-paper px-3 font-sans text-fs-12 text-ink"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
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

function MockFact({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div className="grid gap-1">
      <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">{label}</p>
      <span className="border border-rule bg-paper px-3 py-2 font-mono text-fs-12 uppercase tracking-caps text-ink">
        {value}
      </span>
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

function tabButtonClass(active: boolean): string {
  return active
    ? "shrink-0 border border-ink bg-paper-2 px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-ink transition"
    : "shrink-0 border border-rule px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink";
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

function stageLabel(plant: PlantRow): string {
  if (plant.stageKey === "culled")
    return `Culled ${plant.culledOn ? shortDate(plant.culledOn) : ""}`;
  return `${plant.stageKey} / d${plant.stageDay}`;
}

function groupPlants(
  plants: readonly PlantRow[],
  bootstrap: BreedingLogbookBootstrap,
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

function createSeedLotFromDraft(
  draft: AddSeedLotDraft,
  plants: readonly PlantRow[],
): Omit<SeedLotSummary, "id"> | null {
  const preview = seedLotPreview(draft, plants);
  if (draft.source === "purchased" && draft.strain.trim().length === 0) {
    return null;
  }
  return {
    label: preview.label,
    prefix: preview.prefix,
    generation: draft.generation,
    source: draft.source,
    sourceLabel:
      draft.source === "purchased"
        ? draft.breeder.trim() || "purchased source"
        : "in-house cross",
    parentsLabel: preview.parents,
    sexTypeKey: draft.source === "purchased" ? "unknown" : "regular",
    seedCount: null,
  };
}

function seedLotPreview(
  draft: AddSeedLotDraft,
  plants: readonly PlantRow[],
): { label: string; parents: string; prefix: string } {
  if (draft.source === "purchased") {
    const strain = draft.strain.trim() || "(strain)";
    const breeder = draft.breeder.trim();
    const prefix = normalizePrefix(draft.prefix) || strainPrefix(strain);
    return {
      label: `${strain}${breeder ? ` / ${breeder}` : ""} / ${draft.generation}`,
      parents: `${strain}${breeder ? ` (${breeder})` : " (purchased)"}`,
      prefix,
    };
  }
  const mother = plants.find((plant) => plant.id === draft.motherId);
  const father = plants.find((plant) => plant.id === draft.fatherId);
  const motherName = mother?.name ?? "Mother";
  const fatherName = father?.name ?? "Father";
  const prefix =
    normalizePrefix(draft.prefix) ||
    `${motherName[0] ?? "M"}${fatherName.replace(/[^A-Za-z0-9]/g, "")[0] ?? "F"}`.toUpperCase();
  return {
    label: `${motherName} x ${fatherName} / ${draft.generation}`,
    parents: `${motherName} x ${fatherName}`,
    prefix,
  };
}

function strainPrefix(strain: string): string {
  const initials = strain
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
    .slice(0, 3);
  return initials || "XX";
}

function normalizePrefix(prefix: string): string {
  return prefix
    .trim()
    .replace(/[^A-Za-z0-9]/g, "")
    .toUpperCase();
}

function clonePrefixFor(name: string): string {
  const tail = name.trim().split(/\s+/).at(-1) ?? "M";
  return `C${tail.replace(/[^A-Za-z0-9]/g, "")}`.toUpperCase();
}

function previewLabels(prefix: string, count: number): readonly string[] {
  return Array.from(
    { length: count },
    (_, index) => `${prefix}-${String(index + 1).padStart(2, "0")}`,
  );
}
