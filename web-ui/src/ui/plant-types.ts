// Shared types + sticker-palette lookups for the plants UI layer.
// Kept local to ui/ because the `boundaries` lint rule forbids
// ui/ → api-client/ (eslint.config.ts). The literal unions mirror
// contract schemas:
//   - PlantCode ↔ contracts/webapp-v1.yaml #/components/schemas/PlantCode
//   - StickerColor ↔ PlantStickerColor
// Drift surfaces in routes/index.tsx's typecheck against the real
// api-client types, so duplication here is a bounded cost.

export type PlantCode = "a" | "b" | "c" | "d";
export type StickerColor = "yellow" | "orange" | "pink" | "blue";

// Sticker → Tailwind theme-token class lookups. Named tokens keep TS-15
// happy (no arbitrary hex values); see src/styles.css @theme for the
// palette. Exported so PlantCard + PlantDetail share one source of truth.
export const STICKER_BG: Record<StickerColor, string> = {
  yellow: "bg-sticker-yellow",
  orange: "bg-sticker-orange",
  pink: "bg-sticker-pink",
  blue: "bg-sticker-blue",
};
export const STICKER_FILL: Record<StickerColor, string> = {
  yellow: "fill-sticker-yellow",
  orange: "fill-sticker-orange",
  pink: "fill-sticker-pink",
  blue: "fill-sticker-blue",
};
export const STICKER_STROKE: Record<StickerColor, string> = {
  yellow: "stroke-sticker-yellow",
  orange: "stroke-sticker-orange",
  pink: "stroke-sticker-pink",
  blue: "stroke-sticker-blue",
};
