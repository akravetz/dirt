// Dashboard plant card — one per plant (A/B/C/D) inside the plants strip.
// Clicking fires onSelect(code) so the parent can open the detail drawer
// (frontend.plant_detail owns the drawer itself).
//
// ARIA contract the e2e spec relies on:
//   - button[aria-label={name}]            — press-target per plant.
//   - span[role=img][aria-label="sticker"] — data-color mirrors
//     [data-color=...]                       fixture's sticker_color
//                                            (no class-name reverse lookup).
//   - svg[role="progressbar"]              — moisture bar; aria-valuenow
//     [aria-valuenow=...]                    is the semantic width.
import type { ReactNode } from "react";
import type { PlantCode, StickerColor } from "@/ui/plant-types";

interface PlantCardProps {
  code: PlantCode;
  name: string;
  stickerColor: StickerColor;
  /** Latest calibrated moisture %; null if no calibration exists. */
  moisturePct: number | null;
  onSelect: (code: PlantCode) => void;
}

// Sticker → Tailwind theme-token classes. Named tokens keep TS-15 happy
// (no arbitrary hex values); see src/styles.css @theme for the palette.
const STICKER_BG: Record<StickerColor, string> = {
  yellow: "bg-sticker-yellow",
  orange: "bg-sticker-orange",
  pink: "bg-sticker-pink",
  blue: "bg-sticker-blue",
};
const STICKER_FILL: Record<StickerColor, string> = {
  yellow: "fill-sticker-yellow",
  orange: "fill-sticker-orange",
  pink: "fill-sticker-pink",
  blue: "fill-sticker-blue",
};

export function PlantCard({
  code,
  name,
  stickerColor,
  moisturePct,
  onSelect,
}: PlantCardProps): ReactNode {
  // Clamp to [0, 100]. null moisture renders an empty bar rather than
  // collapsing the row.
  const pctRaw = moisturePct ?? 0;
  const pct = Math.round(Math.max(0, Math.min(100, pctRaw)));
  const pctLabel = moisturePct === null ? "—" : `${pct}%`;

  return (
    <button
      type="button"
      aria-label={name}
      onClick={() => {
        onSelect(code);
      }}
      className="flex flex-col gap-3 border border-rule bg-paper p-4 text-left hover:border-rule-strong"
    >
      <header className="flex items-center gap-2">
        <span
          role="img"
          aria-label="sticker"
          data-color={stickerColor}
          className={`inline-block h-3 w-3 ${STICKER_BG[stickerColor]}`}
        />
        <h3 className="font-serif text-lg italic text-ink">{name}</h3>
      </header>
      <div className="flex flex-col gap-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="font-mono text-xs uppercase tracking-caps text-ink-3">
            Soil moisture
          </span>
          <span className="font-mono text-xs uppercase tracking-caps text-ink-2">
            {pctLabel}
          </span>
        </div>
        {/* viewBox width=100 means the rect's width=pct renders as pct%
            of the strip regardless of pixel width; avoids TS-16 (no
            inline style attrs) since SVG attrs aren't HTML styles. */}
        <svg
          role="progressbar"
          aria-label={`${name} soil moisture`}
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          viewBox="0 0 100 4"
          preserveAspectRatio="none"
          className="h-2 w-full border border-rule bg-paper"
        >
          <title>
            {name} soil moisture {pctLabel}
          </title>
          <rect
            x={0}
            y={0}
            width={pct}
            height={4}
            className={STICKER_FILL[stickerColor]}
          />
        </svg>
      </div>
    </button>
  );
}
