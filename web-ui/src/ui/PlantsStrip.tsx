// Dashboard plants strip — four plant cards (A/B/C/D) under the
// sparklines row. Thin composition around PlantCard; the dashboard
// route owns the selected-plant state that drives frontend.plant_detail.
//
// ARIA contract: section[role=region][aria-label="Plants"] is the
// landmark under which the spec scopes its card queries. Per-card ARIA
// is owned by PlantCard.
import type { ReactNode } from "react";
import { PlantCard } from "@/ui/PlantCard";
import type { PlantCode, StickerColor } from "@/ui/plant-types";

interface StripPlant {
  code: PlantCode;
  name: string;
  sticker_color: StickerColor;
  moisture_pct: number | null;
}

interface PlantsStripProps {
  plants: readonly StripPlant[];
  onSelect: (code: PlantCode) => void;
}

export function PlantsStrip({ plants, onSelect }: PlantsStripProps): ReactNode {
  return (
    <section aria-label="Plants" className="flex flex-col gap-3">
      <header className="flex items-baseline justify-between">
        <h2 className="font-mono text-xs uppercase tracking-caps text-ink-2">Plants</h2>
      </header>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {plants.map((plant) => (
          <PlantCard
            key={plant.code}
            code={plant.code}
            name={plant.name}
            stickerColor={plant.sticker_color}
            moisturePct={plant.moisture_pct}
            onSelect={onSelect}
          />
        ))}
      </div>
    </section>
  );
}
