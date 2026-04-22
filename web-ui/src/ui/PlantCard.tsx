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
import {
  type PlantCode,
  STICKER_BG,
  STICKER_FILL,
  type StickerColor,
} from "@/ui/plant-types";

export type PlantCardStatus = "primary" | "secondary" | "retired";

interface PlantCardProps {
  code: PlantCode;
  name: string;
  stickerColor: StickerColor;
  status: PlantCardStatus;
  /** Latest calibrated moisture %; null if no calibration exists. */
  moisturePct: number | null;
  onSelect: (code: PlantCode) => void;
}

export function PlantCard({
  code,
  name,
  stickerColor,
  status,
  moisturePct,
  onSelect,
}: PlantCardProps): ReactNode {
  // Clamp to [0, 100]. null moisture renders an empty bar rather than
  // collapsing the row.
  const pctRaw = moisturePct ?? 0;
  const pct = Math.round(Math.max(0, Math.min(100, pctRaw)));
  const pctLabel = moisturePct === null ? "—" : `${pct}%`;

  const topBorder = status === "primary" ? "border-t-2 border-accent-magenta" : "";

  return (
    <button
      type="button"
      aria-label={name}
      data-status={status}
      onClick={() => {
        onSelect(code);
      }}
      className={`flex flex-col gap-3 bg-paper-2 px-4.5 py-4 pb-3.5 text-left transition hover:bg-paper-3 ${topBorder}`}
    >
      <header className="flex items-center gap-2">
        <span
          role="img"
          aria-label="sticker"
          data-color={stickerColor}
          className={`inline-block h-2.5 w-2.5 border border-ink ${STICKER_BG[stickerColor]}`}
        />
        <h3 className="font-sans text-fs-14 font-semibold text-ink">{name}</h3>
      </header>
      <div className="flex flex-col gap-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="font-mono text-fs-10 uppercase tracking-caps text-ink-3">
            Soil moisture
          </span>
          <span className="font-mono text-fs-11 tabular-nums text-ink-2">
            {pctLabel}
          </span>
        </div>
        <svg
          role="progressbar"
          aria-label={`${name} soil moisture`}
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          viewBox="0 0 100 4"
          preserveAspectRatio="none"
          className="h-2 w-full border border-rule-strong bg-paper"
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
