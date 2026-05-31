import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MoistureComparisonChart } from "./MoistureComparisonChart";

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

describe("MoistureComparisonChart", () => {
  it("renders selected and comparison plant values and lets comparison plants toggle off", () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    act(() => {
      root?.render(
        <MoistureComparisonChart
          selectedPlantId="a"
          unit="%"
          hoverIndex={0}
          onHoverIndex={vi.fn()}
          series={[
            {
              plantId: "a",
              name: "Plant A",
              stickerColor: "yellow",
              latestValue: 52,
              points: [{ ts: "2026-05-01T00:00:00Z", value: 52 }],
            },
            {
              plantId: "b",
              name: "Plant B",
              stickerColor: "orange",
              latestValue: 64,
              points: [{ ts: "2026-05-01T00:00:00Z", value: 64 }],
            },
          ]}
        />,
      );
    });

    expect(container.querySelector("[role='tooltip']")?.textContent).toContain(
      "Plant A52%",
    );
    expect(container.querySelector("[role='tooltip']")?.textContent).toContain(
      "Plant B64%",
    );

    const plantBButton = [...container.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("Plant B"),
    );
    expect(plantBButton).not.toBeUndefined();

    act(() => {
      plantBButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(container.querySelector("[role='tooltip']")?.textContent).toContain(
      "Plant A52%",
    );
    expect(container.querySelector("[role='tooltip']")?.textContent).not.toContain(
      "Plant B64%",
    );
  });
});
