// Zoom slider — 1×–4× absolute zoom control.
//
// A native <input type="range"> with step 0.1. The parent is notified on
// every `onChange` with the new value (for live local feedback) and on
// `onCommit` when the user releases the handle — `onCommit` is what
// fires the POST /api/ptz/zoom request, so dragging the handle produces
// exactly one network call at drop time rather than one per intermediate
// tick.
//
// The plan description accepts either "the drop position" or "a
// debounced sequence ending at the drop position"; one-POST-on-release
// is the simpler of the two and matches how the backend's zoom service
// prefers absolute setpoints.
//
// ARIA contract the e2e spec relies on:
//   - <section aria-label="Manual"> container — matches the mockup
//     reference (docs/plans/refs/live.png, right-rail "MANUAL" header).
//   - <input type="range" aria-label="Zoom"> exposes min/max/step/value
//     via the native range role; Playwright's `input[type=range]` and
//     `getByLabel("Zoom")` both target it.
import type { ChangeEvent, ReactNode } from "react";

const ZOOM_MIN = 1;
const ZOOM_MAX = 4;
const ZOOM_STEP = 0.1;

interface ZoomSliderProps {
  /** Current zoom (absolute multiplier). */
  value: number;
  /** Live feedback as the user drags. No network call. */
  onChange: (next: number) => void;
  /** Fires once when the user releases the handle. Hook network call here. */
  onCommit: (next: number) => void;
}

export function ZoomSlider({ value, onChange, onCommit }: ZoomSliderProps): ReactNode {
  const handleInput = (event: ChangeEvent<HTMLInputElement>) => {
    const next = Number(event.currentTarget.value);
    if (Number.isFinite(next)) {
      onChange(next);
    }
  };
  const commit = (event: { currentTarget: HTMLInputElement }) => {
    const next = Number(event.currentTarget.value);
    if (Number.isFinite(next)) {
      onCommit(next);
    }
  };

  return (
    <section
      aria-label="Manual"
      className="flex flex-col gap-3 border border-rule-strong bg-paper-2 p-4"
    >
      <header>
        <h2 className="font-sans text-fs-10 font-semibold uppercase tracking-cap-med text-ink-3">
          Manual
        </h2>
      </header>
      <p className="font-serif text-fs-13 italic text-ink-3">
        Click any point on the feed to re-center the camera there.
      </p>
      <label className="flex flex-col gap-2">
        <span className="flex items-baseline justify-between font-mono text-fs-10 uppercase tracking-caps text-ink-3">
          <span>Zoom</span>
          <span className="font-semibold text-ink">{value.toFixed(1)}×</span>
        </span>
        <input
          type="range"
          aria-label="Zoom"
          min={ZOOM_MIN}
          max={ZOOM_MAX}
          step={ZOOM_STEP}
          value={value}
          onChange={handleInput}
          onMouseUp={commit}
          onTouchEnd={commit}
          onKeyUp={commit}
          className="zoom-slider"
        />
        <span
          aria-hidden="true"
          className="flex justify-between font-mono text-fs-10 uppercase tracking-cap-narrow text-ink-3"
        >
          <span>1×</span>
          <span>2×</span>
          <span>3×</span>
          <span>4×</span>
        </span>
      </label>
    </section>
  );
}
