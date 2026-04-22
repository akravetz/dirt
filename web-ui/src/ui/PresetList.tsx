// Preset list — overview + plant_a..d rows.
//
// Each row is a <button> carrying the preset's label and a small color
// chip reflecting the preset's sticker_color (plant_a..d). Clicking a
// row fires `onSelect(id)` so the parent can issue
// POST /api/ptz/preset/{id}.
//
// ARIA contract the e2e spec relies on:
//   - <section aria-label="Presets"> container — locator anchor.
//   - One <button aria-label={label}> per preset; the button's
//     accessible name matches the preset's label (e.g. "Plant A"), so
//     Playwright can click it via getByRole("button", { name: ... }).
//   - data-preset-id on each button mirrors the id that will appear in
//     the POST URL — the spec asserts the id captured from network
//     matches the button the user clicked.
//
// Rejected: role="tablist" / role="tab" / aria-selected. Presets are
// action buttons, not a tab set. Using the tab roles would suggest
// navigation to a panel that doesn't exist.
import type { ReactNode } from "react";

import { STICKER_BG, type StickerColor } from "@/ui/plant-types";

/**
 * Preset row data shape — mirrors the subset of
 * contracts/webapp-v1.yaml #/components/schemas/PTZPreset that the list
 * needs to render. Full PTZState.presets entries carry extra motor-frame
 * fields (yaw/pitch/zoom) that the list doesn't surface.
 */
export interface PresetRow {
  id: string;
  label: string;
  stickerColor: StickerColor | null;
}

interface PresetListProps {
  presets: readonly PresetRow[];
  /** Preset currently applied on the camera (from PTZState.preset). */
  activeId: string | null;
  onSelect: (id: string) => void;
}

export function PresetList({
  presets,
  activeId,
  onSelect,
}: PresetListProps): ReactNode {
  return (
    <section
      aria-label="Presets"
      className="flex flex-col border border-rule-strong bg-paper-2"
    >
      <header className="border-b border-rule-strong px-3.5 py-2">
        <h2 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
          Presets
        </h2>
      </header>
      <ul className="flex flex-col">
        {presets.map((preset) => {
          const active = preset.id === activeId;
          const chipClass =
            preset.stickerColor !== null
              ? `${STICKER_BG[preset.stickerColor]} border border-ink`
              : "border border-rule bg-paper";
          return (
            <li key={preset.id}>
              <button
                type="button"
                aria-label={preset.label}
                data-preset-id={preset.id}
                data-active={active}
                onClick={() => {
                  onSelect(preset.id);
                }}
                className={
                  active
                    ? "flex w-full items-center gap-2.5 border-b border-rule bg-ink px-2.5 py-2 text-left text-paper last:border-b-0"
                    : "flex w-full items-center gap-2.5 border-b border-rule px-2.5 py-2 text-left text-ink transition hover:bg-paper-3 last:border-b-0"
                }
              >
                <span
                  aria-hidden="true"
                  className={`inline-block h-2.5 w-2.5 ${chipClass}`}
                />
                <span className="font-sans text-fs-12">{preset.label}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
