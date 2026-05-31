import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { MarkdownDocument } from "./MarkdownDocument";

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

describe("MarkdownDocument", () => {
  it("renders Markdown structure and links", () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    act(() => {
      root?.render(
        <MarkdownDocument
          bodyMarkdown={[
            "# Plant A",
            "",
            "See [overview](https://example.com/overview).",
            "",
            "- thriving",
          ].join("\n")}
        />,
      );
    });

    expect(container.querySelector("h1")?.textContent).toBe("Plant A");
    expect(container.querySelector("a")?.getAttribute("href")).toBe(
      "https://example.com/overview",
    );
    expect(container.querySelector("li")?.textContent).toBe("thriving");
  });
});
