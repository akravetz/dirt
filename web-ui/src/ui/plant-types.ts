// Shared type unions used by the plants UI layer. Kept local to ui/
// because the `boundaries` lint rule forbids ui/ → api-client/
// (eslint.config.ts). These literal unions mirror contract schemas:
//   - PlantCode ↔ contracts/webapp-v1.yaml #/components/schemas/PlantCode
//   - StickerColor ↔ PlantStickerColor
// A drift surfaces in routes/index.tsx's typecheck against the real
// api-client types, so duplication here is a bounded cost.

export type PlantCode = "a" | "b" | "c" | "d";
export type StickerColor = "yellow" | "orange" | "pink" | "blue";
