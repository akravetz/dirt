// Live camera feed.
//
// Renders an <img> pointing at /api/feed/live.jpg with a cache-busting
// query param `?t=<ms>` that ticks every ~10s so the browser re-fetches
// the frame. The server intentionally returns a single JPEG (no MJPEG
// multipart), so the cheapest "auto-refresh" model is to rotate the src.
//
// Clicking anywhere on the feed translates the pointer's pixel
// coordinates into normalized [-1, 1] frame coordinates (frame center =
// 0, right / down positive) and invokes `onLook(x, y)`. Parent wires
// that to POST /api/ptz/look via the api-client.
//
// The clickable surface is a real <button type="button"> wrapping the
// <img>, so:
//   - it has native keyboard focus / Enter / Space handling (a11y);
//   - Playwright's default click + coordinate-targeted click both
//     dispatch against it; `clientX/clientY - rect.left/top` gives the
//     click's position relative to the button's box, which is what the
//     onClick handler reads.
// Space/Enter fires a button click at the element's center — a
// reasonable "re-center" default for keyboard-only users. No separate
// onKeyDown / onKeyUp handler is needed; the native button behavior
// covers it, and the click handler detects the center case (clientX/Y
// at rect midpoint → x=0, y=0) automatically.
//
// ARIA contract the e2e spec relies on:
//   - <figure aria-label="Live camera feed"> container — locator anchor.
//   - <button aria-label="Live camera feed"> — the press target.
//   - <img alt=""> inside — the alt is on the button; the img is
//     presentational. The refreshed src is observable via its `src`
//     attribute and its wire request on /api/feed/live.jpg. The cache-
//     bust param keeps each fetch a distinct request in the network
//     panel.
import { type ReactNode, useCallback, useEffect, useState } from "react";

/** Poll cadence (ms) for src cache-bust. Plan description asks for ~10s. */
const REFRESH_MS = 10_000;

interface CameraFeedProps {
  /**
   * Callback invoked when the user clicks the feed.
   * Coordinates are normalized to [-1, 1] with frame center = (0, 0),
   * right / down positive — matches contracts/webapp-v1.yaml
   * PTZLookRequest.
   */
  onLook: (x: number, y: number) => void;
  /** External refresh trigger for PTZ moves that should fetch a new frame now. */
  refreshKey?: number;
}

export function CameraFeed({ onLook, refreshKey = 0 }: CameraFeedProps): ReactNode {
  // Tick drives the cache-bust query param. Starts at mount-time so the
  // first src already has a unique query; subsequent ticks fire every
  // REFRESH_MS.
  const [tick, setTick] = useState<number>(() => Date.now());

  useEffect(() => {
    const handle = setInterval(() => {
      setTick(Date.now());
    }, REFRESH_MS);
    return () => {
      clearInterval(handle);
    };
  }, []);

  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      const btn = event.currentTarget;
      const rect = btn.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      // Normalize pointer to [-1, 1]: center = 0, right / down positive.
      const px = event.clientX - rect.left;
      const py = event.clientY - rect.top;
      const x = (px / rect.width) * 2 - 1;
      const y = (py / rect.height) * 2 - 1;
      onLook(clamp11(x), clamp11(y));
    },
    [onLook],
  );

  const src = `/api/feed/live.jpg?t=${tick}-${refreshKey}`;

  return (
    <figure
      aria-label="Live camera feed"
      className="flex flex-col gap-0 border border-ink bg-ink p-0 ring-1 ring-accent-purple ring-inset"
    >
      <button
        type="button"
        aria-label="Live camera feed"
        onClick={handleClick}
        // 16:9 aspect ratio keeps the click surface a meaningful size
        // regardless of the loaded image's natural dimensions (a 1×1
        // placeholder, a low-res debug frame, etc. would otherwise
        // collapse the element to a single pixel).
        className="relative block aspect-video w-full cursor-crosshair p-0"
      >
        <img
          alt=""
          src={src}
          className="absolute inset-0 block h-full w-full select-none object-contain"
          draggable={false}
        />
      </button>
    </figure>
  );
}

function clamp11(n: number): number {
  if (n < -1) return -1;
  if (n > 1) return 1;
  return n;
}
