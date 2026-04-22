// Dashboard plants strip — four plant cards (A/B/C/D) under the
// sparklines row. Thin composition around PlantCard; the dashboard
// route owns the selected-plant state that drives frontend.plant_detail.
//
// ARIA contract: section[role=region][aria-label="Plants"] is the
// landmark under which the spec scopes its card queries. Per-card ARIA
// is owned by PlantCard.
import type { ReactNode } from "react";
import { PlantCard, type PlantCardStatus } from "@/ui/PlantCard";
import type { PlantCode, StickerColor } from "@/ui/plant-types";

interface StripPlant {
  code: PlantCode;
  name: string;
  sticker_color: StickerColor;
  status: PlantCardStatus;
  moisture_pct: number | null;
}

interface PlantsStripProps {
  plants: readonly StripPlant[];
  /** Grow day number from /api/grow/current; appended to the section
   * header as "Plants · Day N". null hides the suffix while the grow
   * query is loading. */
  dayNumber: number | null;
  onSelect: (code: PlantCode) => void;
}

export function PlantsStrip({
  plants,
  dayNumber,
  onSelect,
}: PlantsStripProps): ReactNode {
  return (
    <section aria-label="Plants" className="flex flex-col">
      <header className="flex items-baseline justify-between border-b border-rule px-0.5 py-2">
        <h2 className="font-sans text-fs-11 font-semibold uppercase tracking-cap-wide text-ink-2">
          {dayNumber === null ? "Plants" : `Plants · Day ${dayNumber}`}
        </h2>
      </header>
      <div className="grid grid-cols-1 border border-rule-strong bg-paper-2 sm:grid-cols-2 lg:grid-cols-4">
        {plants.map((plant) => (
          <PlantCard
            key={plant.code}
            code={plant.code}
            name={plant.name}
            stickerColor={plant.sticker_color}
            status={plant.status}
            moisturePct={plant.moisture_pct}
            onSelect={onSelect}
          />
        ))}
      </div>
    </section>
  );
}
