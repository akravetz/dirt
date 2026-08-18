import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Sparkline } from "./Sparkline";

let root: Root | null = null;
let container: HTMLDivElement | null = null;

afterEach(() => {
  if (root !== null) {
    act(() => {
      root?.unmount();
    });
  }
  container?.remove();
  root = null;
  container = null;
  vi.restoreAllMocks();
});

describe("Sparkline", () => {
  it("formats tooltip values with the supplied precision", () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    act(() => {
      root?.render(
        <Sparkline
          name="Soil moisture"
          unit="raw"
          valuePrecision={0}
          series={[
            {
              color: "moisture",
              id: "soil-moisture",
              label: "Soil moisture",
              points: [{ ts: "2026-05-01T00:00:00Z", value: 1810 }],
            },
          ]}
          hoverTimestamp="2026-05-01T00:00:00Z"
          onHoverTimestamp={vi.fn()}
        />,
      );
    });

    expect(container.querySelector("[role='tooltip']")?.textContent).toBe("1810 raw");
  });

  it("renders explicit gaps and keeps the shared crosshair on missing buckets", () => {
    vi.spyOn(SVGElement.prototype, "getBoundingClientRect").mockReturnValue({
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: 100,
      bottom: 40,
      width: 100,
      height: 40,
      toJSON: () => ({}),
    });
    const onHoverTimestamp = vi.fn();

    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    act(() => {
      root?.render(
        <Sparkline
          name="Dehumidifier"
          unit="%"
          series={[
            {
              color: "humidity",
              id: "dehumidifier",
              label: "Dehumidifier",
              points: [
                { ts: "2026-05-01T00:00:00Z", value: 0 },
                { ts: "2026-05-01T04:00:00Z", value: null },
                { ts: "2026-05-01T08:00:00Z", value: 50 },
                { ts: "2026-05-01T12:00:00Z", value: null },
                { ts: "2026-05-01T16:00:00Z", value: 100 },
              ],
            },
          ]}
          hoverTimestamp="2026-05-01T04:00:00Z"
          onHoverTimestamp={onHoverTimestamp}
          yMin={0}
          yMax={100}
        />,
      );
    });

    const pathCount = container.querySelectorAll("svg path").length;
    expect(pathCount).toBe(6);

    const crosshairLine = container.querySelector("g[aria-label='crosshair'] line");
    expect(crosshairLine?.getAttribute("x1")).toBe("25");
    expect(container.querySelector("g[aria-label='crosshair'] circle")).toBeNull();
    expect(container.querySelector("[role='tooltip']")).toBeNull();

    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    act(() => {
      svg?.dispatchEvent(
        new MouseEvent("pointermove", {
          bubbles: true,
          clientX: 50,
          clientY: 20,
        }),
      );
    });

    expect(onHoverTimestamp).toHaveBeenCalledWith("2026-05-01T08:00:00Z");
  });

  it("renders independently identified series and preserves zero in the tooltip", () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    act(() => {
      root?.render(
        <Sparkline
          name="Substrate EC"
          unit="mS/cm"
          valuePrecision={2}
          series={[
            {
              color: "plant-a",
              id: "plant-a-ec",
              label: "Plant A",
              points: [{ ts: "2026-05-01T00:00:00Z", value: 0 }],
            },
            {
              color: "plant-b",
              id: "plant-b-ec",
              label: "Plant B",
              points: [{ ts: "2026-05-01T00:00:00Z", value: 1.25 }],
            },
          ]}
          hoverTimestamp="2026-05-01T00:00:00Z"
          onHoverTimestamp={vi.fn()}
        />,
      );
    });

    expect(container.querySelector("[aria-label='Series legend']")?.textContent).toBe(
      "Plant APlant B",
    );
    expect(container.querySelector("[role='tooltip']")?.textContent).toBe(
      "Plant A: 0.00mS/cmPlant B: 1.25mS/cm",
    );
    expect(container.querySelectorAll("g[aria-label='crosshair'] circle")).toHaveLength(
      2,
    );
  });
});
