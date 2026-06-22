import { Link, useNavigate } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  type AddSeedLotMutationInput,
  commandErrorText,
  createSeedsIdempotencyKey,
  type SeedsPendingCommand,
  seedCommandStatusLabel,
  type UpdateSeedLotInventoryInput,
  useAddSeedLotMutation,
  useSeedsPendingCommands,
  useUpdateSeedLotInventoryMutation,
} from "./seedsMutations";
import {
  useNewSeedLotPageQueries,
  useSeedLotDetailPageQueries,
  useSeedLotListPageQueries,
} from "./seedsQueries";
import type {
  SeedLotDetail,
  SeedLotSexTypeKey,
  SeedLotSource,
  SeedLotSummary,
  SeedParentPlant,
  SeedsBootstrap,
} from "./seedsTypes";

type SeedLotSourceFilter = "all" | SeedLotSource;
type SeedLotSexFilter = "all" | SeedLotSexTypeKey;
type SeedsSearchState = {
  q?: string;
  source?: SeedLotSourceFilter;
  sex?: SeedLotSexFilter;
};
type AddSeedLotDraft = {
  source: SeedLotSource;
  motherId: string;
  fatherId: string;
  generation: string;
  sexTypeKey: SeedLotSexTypeKey;
  prefix: string;
  strain: string;
  sourceName: string;
  seedCount: string;
  acquiredAt: string;
  notes: string;
};
type SeedLotInventoryDraft = {
  sexTypeKey: SeedLotSexTypeKey;
  seedCount: string;
  notes: string;
  vendorName: string;
  acquiredAt: string;
};

const GENERATION_OPTIONS = ["R1", "F1", "F2", "F3", "F4", "F5", "S1", "BX1"] as const;
const SEED_SOURCE_FILTER_VALUES = ["all", "cross", "purchased"] as const;
const SEED_SEX_FILTER_VALUES = ["all", "unknown", "feminized", "regular"] as const;
const SEED_DETAIL_ROUTE = "/seeds/$seedLotId" as const;
const SEED_EDIT_ROUTE = "/seeds/$seedLotId/edit" as const;
const NEW_SEED_LOT_ROUTE = "/seeds/new" as const;
const DATETIME_LOCAL_LENGTH = 16;
const DEFAULT_SEEDS_SEARCH = {
  q: "",
  source: "all",
  sex: "all",
} as const satisfies Required<SeedsSearchState>;
const initialSeedLotDraft: AddSeedLotDraft = {
  source: "cross",
  motherId: "",
  fatherId: "",
  generation: "F2",
  sexTypeKey: "regular",
  prefix: "",
  strain: "",
  sourceName: "",
  seedCount: "",
  acquiredAt: "",
  notes: "",
};

export function validateSeedsSearch(search: Record<string, unknown>): SeedsSearchState {
  return {
    q: typeof search.q === "string" ? search.q : DEFAULT_SEEDS_SEARCH.q,
    source: parseSearchEnum(
      search.source,
      SEED_SOURCE_FILTER_VALUES,
      DEFAULT_SEEDS_SEARCH.source,
    ),
    sex: parseSearchEnum(search.sex, SEED_SEX_FILTER_VALUES, DEFAULT_SEEDS_SEARCH.sex),
  };
}

export function normalizeSeedsSearch(
  search: SeedsSearchState,
): Required<SeedsSearchState> {
  return {
    q: search.q ?? DEFAULT_SEEDS_SEARCH.q,
    source: search.source ?? DEFAULT_SEEDS_SEARCH.source,
    sex: search.sex ?? DEFAULT_SEEDS_SEARCH.sex,
  };
}

export function SeedsListPage({
  search,
}: {
  search: Required<SeedsSearchState>;
}): ReactNode {
  const navigate = useNavigate();
  const { bootstrap, seedLots } = useSeedLotListPageQueries();
  const pendingCommands = useSeedsPendingCommands();
  const filteredSeedLots = useMemo(
    () => filterSeedLots(seedLots.seedLots, search),
    [seedLots.seedLots, search],
  );

  return (
    <main className="flex-1 overflow-auto bg-paper text-ink">
      <div className="mx-auto flex max-w-330 flex-col gap-4 px-4 pb-14 pt-4 sm:px-6">
        <section className="flex flex-col gap-3 border-b border-rule-strong pb-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              Inventory
            </p>
            <h1 className="font-sans text-fs-28 font-semibold text-ink">Seeds</h1>
            <p className="mt-1 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
              {filteredSeedLots.length} visible / {seedLots.seedLots.length} total
            </p>
          </div>
          <Link
            to={NEW_SEED_LOT_ROUTE}
            className="w-fit border border-ink bg-ink px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-paper transition hover:border-accent-magenta"
          >
            New seed lot
          </Link>
        </section>

        <PendingSeedCommandSummary commands={pendingCommands} mutationError={null} />

        <SeedLotFilters
          bootstrap={bootstrap}
          search={search}
          onQueryChange={(q) => {
            void navigate({
              to: "/seeds",
              search: (previous) => ({ ...previous, q }),
              replace: true,
            });
          }}
          onSourceChange={(source) => {
            void navigate({
              to: "/seeds",
              search: (previous) => ({ ...previous, source }),
              replace: true,
            });
          }}
          onSexChange={(sex) => {
            void navigate({
              to: "/seeds",
              search: (previous) => ({ ...previous, sex }),
              replace: true,
            });
          }}
        />

        <SeedLotStats seedLots={filteredSeedLots} />
        <SeedLotInventoryList bootstrap={bootstrap} seedLots={filteredSeedLots} />
      </div>
    </main>
  );
}

export function NewSeedLotPage(): ReactNode {
  const navigate = useNavigate();
  const { bootstrap, seedLots, seedParentPlants } = useNewSeedLotPageQueries();
  const pendingCommands = useSeedsPendingCommands();
  const addSeedLotMutation = useAddSeedLotMutation();
  const [draft, setDraft] = useState<AddSeedLotDraft>(initialSeedLotDraft);

  return (
    <main className="flex-1 overflow-auto bg-paper text-ink">
      <div className="mx-auto flex max-w-330 flex-col gap-4 px-4 pb-14 pt-4 sm:px-6">
        <SurfaceHeader
          backLabel="Back to seeds"
          description="Queue a seed-lot command without creating plant rows."
          title="New seed lot"
          onBack={() => {
            void navigate({ to: "/seeds" });
          }}
        />
        <PendingSeedCommandSummary
          commands={pendingCommands.filter(
            (command) => command.operation === "add-seeds",
          )}
          mutationError={mutationErrorText(addSeedLotMutation.error)}
        />
        <AddSeedLotForm
          bootstrap={bootstrap}
          draft={draft}
          mutationPending={addSeedLotMutation.isPending}
          seedLots={seedLots.seedLots}
          seedParentPlants={seedParentPlants}
          onDraftChange={setDraft}
          onSubmit={(input) => {
            addSeedLotMutation.mutate(input, {
              onSuccess: () => {
                setDraft({
                  ...initialSeedLotDraft,
                  source: draft.source,
                });
                void navigate({ to: "/seeds" });
              },
            });
          }}
        />
      </div>
    </main>
  );
}

export function SeedLotDetailPage({
  editMode = false,
  seedLotId,
}: {
  editMode?: boolean;
  seedLotId: string;
}): ReactNode {
  const navigate = useNavigate();
  const { bootstrap, detail } = useSeedLotDetailPageQueries(seedLotId);
  const pendingCommands = useSeedsPendingCommands();
  const updateMutation = useUpdateSeedLotInventoryMutation();
  const relatedPendingCommands = pendingCommands.filter(
    (command) => command.seedLotId === seedLotId,
  );

  return (
    <main className="flex-1 overflow-auto bg-paper text-ink">
      <div className="mx-auto flex max-w-330 flex-col gap-4 px-4 pb-14 pt-4 sm:px-6">
        <SurfaceHeader
          backLabel="Back to seeds"
          description={
            editMode
              ? "Edit seed-lot-owned inventory facts only."
              : "Line and cross identity are read-only from this workspace."
          }
          title={detail.label}
          onBack={() => {
            void navigate({ to: "/seeds" });
          }}
        />
        <PendingSeedCommandSummary
          commands={relatedPendingCommands}
          mutationError={mutationErrorText(updateMutation.error)}
        />
        {editMode ? (
          <SeedLotEditSurface
            bootstrap={bootstrap}
            detail={detail}
            mutationPending={updateMutation.isPending}
            pendingCommands={relatedPendingCommands}
            onCancel={() => {
              void navigate({
                to: "/seeds/$seedLotId",
                params: { seedLotId: detail.id },
              });
            }}
            onSubmit={(input) => {
              updateMutation.mutate(input, {
                onSuccess: () => {
                  void navigate({
                    to: "/seeds/$seedLotId",
                    params: { seedLotId: detail.id },
                  });
                },
              });
            }}
          />
        ) : (
          <SeedLotDetailSurface
            bootstrap={bootstrap}
            detail={detail}
            pendingCommands={relatedPendingCommands}
          />
        )}
      </div>
    </main>
  );
}

export function SeedStatusScreen({
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

export function filterSeedLots(
  seedLots: readonly SeedLotSummary[],
  search: Required<SeedsSearchState>,
): readonly SeedLotSummary[] {
  const query = normalizeSearchText(search.q);
  return seedLots.filter((seedLot) => {
    if (search.source !== "all" && seedLot.source !== search.source) return false;
    if (search.sex !== "all" && seedLot.sexTypeKey !== search.sex) return false;
    if (query.length === 0) return true;
    return normalizeSearchText(seedLotSearchText(seedLot)).includes(query);
  });
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

function SeedLotFilters({
  bootstrap,
  onQueryChange,
  onSexChange,
  onSourceChange,
  search,
}: {
  bootstrap: SeedsBootstrap;
  onQueryChange: (query: string) => void;
  onSexChange: (sex: SeedLotSexFilter) => void;
  onSourceChange: (source: SeedLotSourceFilter) => void;
  search: Required<SeedsSearchState>;
}): ReactNode {
  return (
    <section className="grid gap-3 border border-rule-strong bg-paper-2 p-3 md:grid-cols-[minmax(240px,1fr)_auto_auto] md:items-end">
      <label className="grid gap-1">
        <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          Search
        </span>
        <input
          value={search.q}
          placeholder="prefix, strain, parents, source"
          onChange={(event) => {
            onQueryChange(event.target.value);
          }}
          className="h-9 border border-rule bg-paper px-3 font-sans text-fs-12 text-ink placeholder:text-ink-3"
        />
      </label>
      <Segmented
        label="Source"
        options={[
          { label: "All", value: "all" },
          { label: "Cross", value: "cross" },
          { label: "Purchased", value: "purchased" },
        ]}
        value={search.source}
        onChange={onSourceChange}
      />
      <Segmented
        label="Seed type"
        options={[
          { label: "All", value: "all" },
          ...bootstrap.seedLotSexTypes.map((sexType) => ({
            label: sexType.displayName,
            value: sexType.key,
          })),
        ]}
        value={search.sex}
        onChange={onSexChange}
      />
    </section>
  );
}

function SeedLotStats({
  seedLots,
}: {
  seedLots: readonly SeedLotSummary[];
}): ReactNode {
  const purchasedCount = seedLots.filter(
    (seedLot) => seedLot.source === "purchased",
  ).length;
  const crossCount = seedLots.length - purchasedCount;
  const countedSeeds = seedLots.reduce(
    (total, seedLot) => total + (seedLot.seedCount ?? 0),
    0,
  );
  return (
    <section className="grid gap-px border border-rule-strong bg-rule sm:grid-cols-3">
      <StatBlock label="Lots" value={String(seedLots.length)} />
      <StatBlock
        label="Cross / purchased"
        value={`${crossCount} / ${purchasedCount}`}
      />
      <StatBlock label="Counted seeds" value={String(countedSeeds)} />
    </section>
  );
}

function StatBlock({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div className="bg-paper-2 px-3 py-2.5">
      <p className="font-mono text-fs-9 uppercase tracking-caps text-ink-3">{label}</p>
      <p className="mt-1 font-mono text-fs-18 text-ink">{value}</p>
    </div>
  );
}

function SeedLotInventoryList({
  bootstrap,
  seedLots,
}: {
  bootstrap: SeedsBootstrap;
  seedLots: readonly SeedLotSummary[];
}): ReactNode {
  if (seedLots.length === 0) {
    return (
      <section className="border border-rule bg-paper-2 p-5">
        <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          No seed lots match these filters.
        </p>
      </section>
    );
  }
  return (
    <section className="grid gap-px border border-rule-strong bg-rule">
      <div className="hidden bg-paper-3 px-3 py-2 font-mono text-fs-9 uppercase tracking-caps text-ink-3 md:grid md:grid-cols-[1.2fr_0.9fr_0.7fr_0.5fr_0.5fr]">
        <span>Line</span>
        <span>Parents / source</span>
        <span>Seed type</span>
        <span>Count</span>
        <span>Action</span>
      </div>
      {seedLots.map((seedLot) => (
        <SeedLotInventoryRow key={seedLot.id} bootstrap={bootstrap} seedLot={seedLot} />
      ))}
    </section>
  );
}

function SeedLotInventoryRow({
  bootstrap,
  seedLot,
}: {
  bootstrap: SeedsBootstrap;
  seedLot: SeedLotSummary;
}): ReactNode {
  return (
    <article className="grid gap-3 bg-paper px-3 py-3 md:grid-cols-[1.2fr_0.9fr_0.7fr_0.5fr_0.5fr] md:items-center">
      <div className="min-w-0">
        <Link
          to={SEED_DETAIL_ROUTE}
          params={{ seedLotId: seedLot.id }}
          className="font-sans text-fs-14 font-semibold text-ink underline-offset-2 hover:underline"
        >
          {seedLotPrimaryLabel(seedLot)}
        </Link>
        <p className="mt-1 truncate font-mono text-fs-9 uppercase tracking-caps text-ink-3">
          {seedLot.sourceLabel} / {seedLot.generation}
        </p>
      </div>
      <p className="font-sans text-fs-12 text-ink-2">{seedLot.parentsLabel}</p>
      <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {seedLotSexTypeDisplayName(bootstrap, seedLot.sexTypeKey)}
      </p>
      <p className="font-mono text-fs-12 text-ink">
        {seedLot.seedCount === null ? "-" : seedLot.seedCount}
      </p>
      <Link
        to={SEED_EDIT_ROUTE}
        params={{ seedLotId: seedLot.id }}
        className="w-fit border border-rule px-2.5 py-1.5 font-mono text-fs-9 uppercase tracking-caps text-ink-3 transition hover:border-rule-strong hover:text-ink"
      >
        Edit
      </Link>
    </article>
  );
}

function AddSeedLotForm({
  bootstrap,
  draft,
  mutationPending,
  onDraftChange,
  onSubmit,
  seedLots,
  seedParentPlants,
}: {
  bootstrap: SeedsBootstrap;
  draft: AddSeedLotDraft;
  mutationPending: boolean;
  onDraftChange: (draft: AddSeedLotDraft) => void;
  onSubmit: (input: AddSeedLotMutationInput) => void;
  seedLots: readonly SeedLotSummary[];
  seedParentPlants: readonly SeedParentPlant[];
}): ReactNode {
  const activePlants = seedParentPlants.filter(isActiveSeedParent);
  const motherOptions = activePlants
    .filter((plant) => plant.sexKey !== "male")
    .map((plant) => ({
      value: plant.id,
      label: `${plant.name} / ${plant.sexKey}`,
    }));
  const fatherOptions = activePlants
    .filter((plant) => plant.sexKey !== "female")
    .map((plant) => ({
      value: plant.id,
      label: `${plant.name} / ${plant.sexKey}`,
    }));
  const resolvedDraft = {
    ...draft,
    motherId: resolveSelectedValue(draft.motherId, motherOptions),
    fatherId: resolveSelectedValue(draft.fatherId, fatherOptions),
  };
  const preview = seedLotPreview(resolvedDraft, seedParentPlants);
  const seedCount = seedCountFromDraft(draft.seedCount);
  const acquiredAt = datetimeLocalToUtcIsoOrNull(draft.acquiredAt);
  const canSubmit =
    draft.source === "cross"
      ? resolvedDraft.motherId.length > 0 &&
        resolvedDraft.fatherId.length > 0 &&
        resolvedDraft.motherId !== resolvedDraft.fatherId
      : draft.strain.trim().length > 0 && draft.sourceName.trim().length > 0;
  const input =
    canSubmit && seedCount !== undefined && acquiredAt !== undefined
      ? createSeedLotInputFromDraft(
          resolvedDraft,
          seedParentPlants,
          seedCount,
          acquiredAt,
        )
      : null;

  return (
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
                label="Seed parent"
                value={resolvedDraft.motherId}
                options={motherOptions}
                onChange={(motherId) => {
                  onDraftChange({ ...draft, motherId });
                }}
              />
              <SelectField
                label="Pollen parent"
                value={resolvedDraft.fatherId}
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
              <SelectField
                label="Seed type"
                value={draft.sexTypeKey}
                options={seedLotSexTypeOptions(bootstrap)}
                onChange={(sexTypeKey) => {
                  onDraftChange({ ...draft, sexTypeKey });
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
                value={draft.sourceName}
                placeholder="archive"
                onChange={(sourceName) => {
                  onDraftChange({ ...draft, sourceName });
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
              <SelectField
                label="Seed type"
                value={draft.sexTypeKey}
                options={seedLotSexTypeOptions(bootstrap)}
                onChange={(sexTypeKey) => {
                  onDraftChange({ ...draft, sexTypeKey });
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
              <DateTimeField
                label="Acquired at"
                value={draft.acquiredAt}
                onChange={(acquiredAtValue) => {
                  onDraftChange({ ...draft, acquiredAt: acquiredAtValue });
                }}
              />
            </>
          )}
          <TextField
            label="Seed count"
            value={draft.seedCount}
            placeholder="unknown"
            inputMode="numeric"
            onChange={(nextSeedCount) => {
              onDraftChange({ ...draft, seedCount: nextSeedCount });
            }}
          />
          <TextareaField
            label="Notes"
            value={draft.notes}
            placeholder="storage, packaging, viability"
            onChange={(notes) => {
              onDraftChange({ ...draft, notes });
            }}
          />
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-3">
          <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            {preview.label} / plant label prefix {preview.prefix}-
          </p>
          <Button
            variant="primary"
            disabled={input === null || mutationPending}
            onClick={() => {
              if (input !== null) onSubmit(input);
            }}
          >
            {mutationPending ? "Queueing" : "Record seed lot"}
          </Button>
        </div>
      </div>
      <div className="bg-paper p-4">
        <h3 className="font-sans text-fs-13 font-semibold text-ink">
          Seed lots on file / {seedLots.length} lots
        </h3>
        <div className="mt-3 grid gap-2">
          {seedLots.slice(0, 8).map((seedLot) => (
            <Link
              key={seedLot.id}
              to={SEED_DETAIL_ROUTE}
              params={{ seedLotId: seedLot.id }}
              className="block border border-rule bg-paper-2 px-3 py-2.5 transition hover:border-rule-strong"
            >
              <p className="font-sans text-fs-12 font-semibold text-ink">
                {seedLotPrimaryLabel(seedLot)}
              </p>
              <p className="mt-1 font-mono text-fs-9 uppercase tracking-caps text-ink-3">
                {seedLot.cultivar} /{" "}
                {seedLotSexTypeDisplayName(bootstrap, seedLot.sexTypeKey)}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

function SeedLotDetailSurface({
  bootstrap,
  detail,
  pendingCommands,
}: {
  bootstrap: SeedsBootstrap;
  detail: SeedLotDetail;
  pendingCommands: readonly SeedsPendingCommand[];
}): ReactNode {
  const hasActivePendingCommand = pendingCommands.some(isActiveSeedCommand);
  return (
    <>
      <section className="grid gap-px border border-rule-strong bg-rule md:grid-cols-[1fr_1fr]">
        <div className="bg-paper-2 p-4">
          <h2 className="font-sans text-fs-16 font-semibold text-ink">
            Inventory facts
          </h2>
          <dl className="mt-3 grid gap-2">
            <FactRow
              label="Seed type"
              value={seedLotSexTypeDisplayName(bootstrap, detail.sexTypeKey)}
            />
            <FactRow label="Seed count" value={seedCountLabel(detail.seedCount)} />
            <FactRow label="Vendor" value={detail.vendorName ?? "-"} />
            <FactRow label="Acquired" value={formatDateTimeOrDash(detail.acquiredAt)} />
            <FactRow label="Created plants" value={String(detail.createdPlantCount)} />
          </dl>
          <p className="mt-3 border-t border-rule pt-3 font-sans text-fs-12 text-ink-2">
            {detail.notes?.trim() || "No seed-lot notes yet."}
          </p>
          <div className="mt-4">
            <Link
              to={SEED_EDIT_ROUTE}
              params={{ seedLotId: detail.id }}
              className={
                hasActivePendingCommand
                  ? "pointer-events-none border border-rule bg-paper-3 px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-ink-3"
                  : "border border-rule-strong bg-paper px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-ink transition hover:border-ink-2"
              }
            >
              Edit inventory
            </Link>
          </div>
        </div>
        <SeedLotIdentityPanel detail={detail} />
      </section>
      <SeedLotSourcePanel detail={detail} />
    </>
  );
}

function SeedLotEditSurface({
  bootstrap,
  detail,
  mutationPending,
  onCancel,
  onSubmit,
  pendingCommands,
}: {
  bootstrap: SeedsBootstrap;
  detail: SeedLotDetail;
  mutationPending: boolean;
  onCancel: () => void;
  onSubmit: (input: UpdateSeedLotInventoryInput) => void;
  pendingCommands: readonly SeedsPendingCommand[];
}): ReactNode {
  const [draft, setDraft] = useState<SeedLotInventoryDraft>(() =>
    seedLotInventoryDraftFromDetail(detail),
  );

  useEffect(() => {
    setDraft(seedLotInventoryDraftFromDetail(detail));
  }, [detail]);

  const seedCount = seedCountFromDraft(draft.seedCount);
  const acquiredAt = datetimeLocalToUtcIsoOrNull(draft.acquiredAt);
  const activePendingCommand = pendingCommands.some(isActiveSeedCommand);
  const updatesChanged = seedLotInventoryDraftChanged(detail, draft);
  const vendorValid = !detail.isPurchased || draft.vendorName.trim().length > 0;
  const input =
    updatesChanged &&
    vendorValid &&
    seedCount !== undefined &&
    acquiredAt !== undefined &&
    !activePendingCommand
      ? seedLotInventoryInputFromDraft(detail, draft, seedCount, acquiredAt)
      : null;

  return (
    <section className="grid gap-px border border-rule-strong bg-rule md:grid-cols-[minmax(360px,1fr)_minmax(280px,420px)]">
      <div className="bg-paper-2 p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <SelectField
            label="Seed type"
            value={draft.sexTypeKey}
            options={seedLotSexTypeOptions(bootstrap)}
            onChange={(sexTypeKey) => {
              setDraft({ ...draft, sexTypeKey });
            }}
          />
          <TextField
            label="Seed count"
            value={draft.seedCount}
            placeholder="unknown"
            inputMode="numeric"
            onChange={(seedCountValue) => {
              setDraft({ ...draft, seedCount: seedCountValue });
            }}
          />
          {detail.isPurchased ? (
            <>
              <TextField
                label="Vendor"
                value={draft.vendorName}
                placeholder="required"
                onChange={(vendorName) => {
                  setDraft({ ...draft, vendorName });
                }}
              />
              <DateTimeField
                label="Acquired at"
                value={draft.acquiredAt}
                onChange={(acquiredAtValue) => {
                  setDraft({ ...draft, acquiredAt: acquiredAtValue });
                }}
              />
            </>
          ) : null}
          <TextareaField
            label="Notes"
            value={draft.notes}
            placeholder="storage, packaging, viability"
            onChange={(notes) => {
              setDraft({ ...draft, notes });
            }}
          />
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-3">
          <p className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            {activePendingCommand
              ? "seed-lot command pending"
              : "line and cross identity stay read-only"}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" disabled={mutationPending} onClick={onCancel}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={input === null || mutationPending}
              onClick={() => {
                if (input !== null) onSubmit(input);
              }}
            >
              {mutationPending ? "Queueing" : "Save inventory"}
            </Button>
          </div>
        </div>
      </div>
      <SeedLotIdentityPanel detail={detail} />
    </section>
  );
}

function SeedLotIdentityPanel({ detail }: { detail: SeedLotDetail }): ReactNode {
  return (
    <div className="bg-paper p-4">
      <h2 className="font-sans text-fs-16 font-semibold text-ink">
        Read-only identity
      </h2>
      <dl className="mt-3 grid gap-2">
        <FactRow label="Prefix" value={detail.prefix} />
        <FactRow label="Strain" value={detail.strain} />
        <FactRow label="Cultivar" value={detail.cultivar} />
        <FactRow label="Generation" value={detail.generation} />
        <FactRow label="Source" value={detail.sourceLabel} />
        <FactRow label="Parents" value={detail.parentsLabel} />
      </dl>
    </div>
  );
}

function SeedLotSourcePanel({ detail }: { detail: SeedLotDetail }): ReactNode {
  return (
    <section className="grid gap-px border border-rule-strong bg-rule md:grid-cols-2">
      <div className="bg-paper-2 p-4">
        <h2 className="font-sans text-fs-16 font-semibold text-ink">Line</h2>
        <dl className="mt-3 grid gap-2">
          <FactRow label="Line id" value={String(detail.sourceLineId)} />
          <FactRow label="Source name" value={detail.line?.sourceName ?? "-"} />
          <FactRow label="Description" value={detail.line?.description ?? "-"} />
        </dl>
      </div>
      <div className="bg-paper p-4">
        <h2 className="font-sans text-fs-16 font-semibold text-ink">Cross context</h2>
        {detail.cross === null ? (
          <p className="mt-3 font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            Purchased lot; no cross event owns this seed lot.
          </p>
        ) : (
          <dl className="mt-3 grid gap-2">
            <FactRow label="Cross id" value={String(detail.cross.sourceCrossEventId)} />
            <FactRow label="Seed parent" value={detail.cross.seedParentLabel} />
            <FactRow label="Pollen parent" value={detail.cross.pollenParentLabel} />
            <FactRow
              label="Pollinated"
              value={formatDateTimeOrDash(detail.cross.pollinatedAt)}
            />
            <FactRow label="Cross notes" value={detail.cross.notes ?? "-"} />
          </dl>
        )}
      </div>
    </section>
  );
}

function PendingSeedCommandSummary({
  commands,
  mutationError,
}: {
  commands: readonly SeedsPendingCommand[];
  mutationError: string | null;
}): ReactNode {
  if (commands.length === 0 && mutationError === null) return null;
  return (
    <section className="border border-status-warn bg-paper-2 px-3 py-2.5">
      <div className="grid gap-1">
        {mutationError ? <InlineError text={mutationError} /> : null}
        {commands.map((command) => {
          const error = commandErrorText(command);
          return (
            <p
              key={command.commandId}
              className={
                error
                  ? "font-mono text-fs-10 uppercase tracking-caps text-status-err"
                  : command.command.status === "succeeded"
                    ? "font-mono text-fs-10 uppercase tracking-caps text-status-ok"
                    : "font-mono text-fs-10 uppercase tracking-caps text-status-warn"
              }
            >
              {command.label} / {seedCommandStatusLabel(command)}
            </p>
          );
        })}
      </div>
    </section>
  );
}

function SurfaceHeader({
  backLabel,
  description,
  onBack,
  title,
}: {
  backLabel: string;
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
        {backLabel}
      </button>
      <div>
        <h1 className="font-sans text-fs-22 font-semibold text-ink">{title}</h1>
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
      <div className="flex max-w-full flex-wrap gap-px bg-rule">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => {
              onChange(option.value);
            }}
            className={
              option.value === value
                ? "bg-paper-2 px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink"
                : "bg-paper px-2.5 py-1.5 font-mono text-fs-10 uppercase tracking-caps text-ink-3 transition hover:text-ink"
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
  variant: "primary" | "secondary";
}): ReactNode {
  const className =
    variant === "primary"
      ? "border border-ink bg-ink px-3 py-2 font-mono text-fs-10 uppercase tracking-caps text-paper transition hover:border-accent-magenta disabled:cursor-not-allowed disabled:border-rule-strong disabled:bg-paper-3 disabled:text-ink-3"
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
  inputMode,
  label,
  onChange,
  placeholder,
  value,
}: {
  inputMode?: "numeric";
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
        inputMode={inputMode}
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
  onChange,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  value: string;
}): ReactNode {
  return (
    <label className="grid gap-1">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <input
        type="datetime-local"
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="h-9 border border-rule bg-paper px-3 font-sans text-fs-12 text-ink"
      />
    </label>
  );
}

function TextareaField({
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
    <label className="grid gap-1 sm:col-span-2">
      <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
        {label}
      </span>
      <textarea
        value={value}
        placeholder={placeholder}
        rows={4}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="min-h-24 border border-rule bg-paper px-3 py-2 font-sans text-fs-12 text-ink placeholder:text-ink-3"
      />
    </label>
  );
}

function FactRow({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div className="grid gap-1 border-b border-rule pb-2 last:border-b-0 last:pb-0 sm:grid-cols-[140px_1fr]">
      <dt className="font-mono text-fs-9 uppercase tracking-caps text-ink-3">
        {label}
      </dt>
      <dd className="min-w-0 break-words font-sans text-fs-12 text-ink">{value}</dd>
    </div>
  );
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

function isActiveSeedCommand(command: SeedsPendingCommand): boolean {
  return (
    command.command.status !== "succeeded" &&
    command.command.status !== "failed" &&
    command.command.status !== "rejected" &&
    command.command.status !== "expired"
  );
}

function seedLotSexTypeOptions(
  bootstrap: SeedsBootstrap,
): readonly { label: string; value: SeedLotSexTypeKey }[] {
  return bootstrap.seedLotSexTypes.map((sexType) => ({
    label: sexType.displayName,
    value: sexType.key,
  }));
}

function seedLotSexTypeDisplayName(
  bootstrap: SeedsBootstrap,
  sexTypeKey: SeedLotSexTypeKey,
): string {
  return (
    bootstrap.seedLotSexTypes.find((sexType) => sexType.key === sexTypeKey)
      ?.displayName ?? sexTypeKey
  );
}

function seedLotInventoryDraftFromDetail(detail: SeedLotDetail): SeedLotInventoryDraft {
  return {
    sexTypeKey: detail.sexTypeKey,
    seedCount: detail.seedCount === null ? "" : String(detail.seedCount),
    notes: detail.notes ?? "",
    vendorName: detail.vendorName ?? "",
    acquiredAt: datetimeLocalFromIso(detail.acquiredAt),
  };
}

function seedLotInventoryDraftChanged(
  detail: SeedLotDetail,
  draft: SeedLotInventoryDraft,
): boolean {
  const current = seedLotInventoryDraftFromDetail(detail);
  return (
    draft.sexTypeKey !== current.sexTypeKey ||
    draft.seedCount !== current.seedCount ||
    draft.notes !== current.notes ||
    draft.vendorName !== current.vendorName ||
    draft.acquiredAt !== current.acquiredAt
  );
}

function seedLotInventoryInputFromDraft(
  detail: SeedLotDetail,
  draft: SeedLotInventoryDraft,
  seedCount: number | null,
  acquiredAt: string | null,
): UpdateSeedLotInventoryInput {
  return {
    idempotencyKey: createSeedsIdempotencyKey("update-seed-lot"),
    seedLotId: detail.id,
    sourceSeedLotId: detail.sourceSeedLotId,
    label: seedLotPrimaryLabel(detail),
    sexTypeKey: draft.sexTypeKey,
    seedCount,
    notes: emptyToNull(draft.notes),
    vendorName: detail.isPurchased ? emptyToNull(draft.vendorName) : null,
    acquiredAt: detail.isPurchased ? acquiredAt : null,
  };
}

function createSeedLotInputFromDraft(
  draft: AddSeedLotDraft,
  seedParentPlants: readonly SeedParentPlant[],
  seedCount: number | null,
  acquiredAt: string | null,
): AddSeedLotMutationInput | null {
  const preview = seedLotPreview(draft, seedParentPlants);
  const mother = seedParentPlants.find((plant) => plant.id === draft.motherId);
  const father = seedParentPlants.find((plant) => plant.id === draft.fatherId);
  if (draft.source === "cross" && (mother === undefined || father === undefined)) {
    return null;
  }
  if (draft.source === "cross" && mother?.key === father?.key) return null;
  if (
    draft.source === "purchased" &&
    (draft.strain.trim().length === 0 || draft.sourceName.trim().length === 0)
  ) {
    return null;
  }
  return {
    idempotencyKey: createSeedsIdempotencyKey("add-seeds"),
    source: draft.source,
    prefix: preview.prefix,
    generation: draft.generation,
    sexTypeKey: draft.sexTypeKey,
    strain: draft.source === "purchased" ? draft.strain.trim() : null,
    cultivar: draft.source === "purchased" ? draft.generation : null,
    sourceName: draft.source === "purchased" ? draft.sourceName.trim() : null,
    vendorName: draft.source === "purchased" ? emptyToNull(draft.sourceName) : null,
    acquiredAt: draft.source === "purchased" ? acquiredAt : null,
    seedParentPlantKey: draft.source === "cross" ? (mother?.key ?? null) : null,
    pollenParentPlantKey: draft.source === "cross" ? (father?.key ?? null) : null,
    seedCount,
    notes: emptyToNull(draft.notes),
  };
}

function seedLotPreview(
  draft: AddSeedLotDraft,
  seedParentPlants: readonly SeedParentPlant[],
): { label: string; parents: string; prefix: string } {
  if (draft.source === "purchased") {
    const strain = draft.strain.trim() || "(strain)";
    const sourceName = draft.sourceName.trim();
    const prefix = normalizePrefix(draft.prefix) || strainPrefix(strain);
    return {
      label: `${strain}${sourceName ? ` / ${sourceName}` : ""} / ${draft.generation}`,
      parents: `${strain}${sourceName ? ` (${sourceName})` : " (purchased)"}`,
      prefix,
    };
  }
  const mother = seedParentPlants.find((plant) => plant.id === draft.motherId);
  const father = seedParentPlants.find((plant) => plant.id === draft.fatherId);
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

function isActiveSeedParent(plant: SeedParentPlant): boolean {
  return plant.stageKey !== "culled" && plant.stageKey !== "harvested";
}

function resolveSelectedValue<TValue extends string>(
  value: TValue,
  options: readonly { value: TValue }[],
): TValue {
  return options.some((option) => option.value === value)
    ? value
    : (options[0]?.value ?? value);
}

function seedLotSearchText(seedLot: SeedLotSummary): string {
  return [
    seedLot.label,
    seedLot.prefix,
    seedLot.strain,
    seedLot.cultivar,
    seedLot.generation,
    seedLot.sourceLabel,
    seedLot.parentsLabel,
    seedLot.sexTypeKey,
  ].join(" ");
}

function normalizeSearchText(value: string): string {
  return value.trim().toLowerCase();
}

function seedLotPrimaryLabel(seedLot: SeedLotSummary): string {
  const prefix = seedLot.prefix.trim() || "Seed lot";
  return `${prefix} / ${seedLot.strain}`;
}

function seedCountLabel(seedCount: number | null): string {
  return seedCount === null ? "unknown" : String(seedCount);
}

function seedCountFromDraft(value: string): number | null | undefined {
  const trimmed = value.trim();
  if (trimmed.length === 0) return null;
  const parsed = Number(trimmed);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : undefined;
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length === 0 ? null : trimmed;
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

function datetimeLocalFromIso(value: string | null): string {
  if (value === null) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return dateToDatetimeLocal(parsed);
}

function datetimeLocalToUtcIsoOrNull(value: string): string | null | undefined {
  if (value.trim().length === 0) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return undefined;
  return parsed.toISOString();
}

function dateToDatetimeLocal(value: Date): string {
  const offsetMs = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offsetMs)
    .toISOString()
    .slice(0, DATETIME_LOCAL_LENGTH);
}

function formatDateTimeOrDash(value: string | null): string {
  if (value === null) return "-";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}
