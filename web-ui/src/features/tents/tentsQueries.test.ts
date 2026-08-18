import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

describe("tent plant metric history query", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("keys and requests one collection by tent and range", async () => {
    const history = { bucket: "1h", plants: [], range: "7d" } as const;
    const fetchMock = vi.fn((_request: Request) =>
      Promise.resolve(Response.json(history, { status: 200 })),
    );
    vi.stubEnv("VITE_DIRT_API_BASE_URL", "http://localhost");
    vi.stubGlobal("fetch", fetchMock);
    const { tentPlantMetricHistoryQueryOptions } = await import("./tentsQueries");
    const options = tentPlantMetricHistoryQueryOptions(17, "7d");

    expect(options.queryKey).toEqual(["cloud.plants.metrics.history", 17, "7d"]);
    await expect(new QueryClient().fetchQuery(options)).resolves.toEqual(history);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const request = fetchMock.mock.calls.at(0)?.at(0);
    expect(request).toBeInstanceOf(Request);
    if (request === undefined) {
      throw new Error("Expected one generated-client request");
    }
    expect(request).toMatchObject({ method: "GET" });
    expect(new URL(request.url)).toMatchObject({
      pathname: "/api/tents/17/plants/metrics/history",
      search: "?range=7d",
    });
  });
});
