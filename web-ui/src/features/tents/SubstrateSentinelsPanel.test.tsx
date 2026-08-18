import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import type { hostedComponents } from "@/api-client";
import { SubstrateSentinelsPanel } from "./SubstrateSentinelsPanel";

type PlantMetricHistoryCollection =
  hostedComponents["schemas"]["PlantMetricHistoryCollectionResponse"];
type PlantMetricHistoryStream =
  hostedComponents["schemas"]["PlantMetricHistoryStreamResponse"];

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
});

describe("SubstrateSentinelsPanel", () => {
  it("renders honest loading, error, and empty states", () => {
    renderPanel({ loading: true });
    expect(container?.textContent).toContain("Loading substrate history…");

    renderPanel({ error: true });
    expect(container?.textContent).toContain("Failed to load substrate history.");

    renderPanel({ history: emptyHistory() });
    expect(container?.textContent).toContain(
      "No mapped substrate sentinels for this tent.",
    );
  });

  it("renders three charts, partial metric empties, and identity-stable colors", () => {
    const history = {
      bucket: "5m",
      range: "24h",
      plants: [
        {
          grid_position: "B2",
          id: 2,
          key: "plant-b",
          name: "Plant B",
          streams: [moistureStream("probe-b", 0)],
        },
        {
          grid_position: "A1",
          id: 1,
          key: "plant-a",
          name: "Plant A",
          streams: [moistureStream("probe-a", 42)],
        },
      ],
    } satisfies PlantMetricHistoryCollection;

    renderPanel({ history });

    expect(container?.querySelectorAll("article")).toHaveLength(3);
    expect(container?.textContent).toContain("No mapped substrate EC stream");
    expect(container?.textContent).toContain("No mapped substrate pH stream");
    expect(
      container
        ?.querySelector("[aria-label='Soil moisture sparkline']")
        ?.querySelectorAll("svg path"),
    ).toHaveLength(8);
    const legendItems = [
      ...(container?.querySelectorAll("[aria-label='Series legend'] li") ?? []),
    ];
    expect(legendItems.map((item) => item.textContent)).toEqual([
      "Plant A · A1",
      "Plant B · B2",
    ]);
    expect(legendItems[0]?.querySelector("[aria-hidden='true']")?.className).toContain(
      "fill-plant-a",
    );
    expect(legendItems[1]?.querySelector("[aria-hidden='true']")?.className).toContain(
      "fill-plant-b",
    );
  });
});

function renderPanel({
  error = false,
  history,
  loading = false,
}: {
  error?: boolean;
  history?: PlantMetricHistoryCollection;
  loading?: boolean;
}): void {
  if (container === null) {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  }
  act(() => {
    root?.render(
      <SubstrateSentinelsPanel
        error={error}
        history={history}
        loading={loading}
        range="24h"
      />,
    );
  });
}

function emptyHistory(): PlantMetricHistoryCollection {
  return { bucket: "5m", plants: [], range: "24h" };
}

function moistureStream(deviceId: string, value: number): PlantMetricHistoryStream {
  return {
    accent: "moisture",
    capability_id: "substrate",
    device_id: deviceId,
    display_name: "Soil moisture",
    display_order: 10,
    display_unit: "%",
    metric: "soil_moisture_pct",
    points: [
      { ts: "2026-08-18T00:00:00Z", value },
      { ts: "2026-08-18T00:10:00Z", value: value + 1 },
    ],
    source_unit: "pct",
    value_precision: 1,
    y_max: 100,
    y_min: 0,
  };
}
