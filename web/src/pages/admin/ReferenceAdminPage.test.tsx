import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vite-plus/test";

import type { LoadRead, StateRead } from "@/api/generated";
import { renderRoute } from "@/test/render";

const PAGE_URL = "/admin/reference";

const STATES: StateRead[] = [
  { code: "NC", name: "North Carolina" },
  { code: "SC", name: "South Carolina" },
  { code: "TX", name: "Texas" },
];

const LAYERS = ["boundaries.states", "hydro.wetlands"];

const SUCCEEDED: LoadRead = {
  layer: "hydro.wetlands",
  state: "TX",
  status: "succeeded",
  rows_loaded: 2233909,
  source_version: "2026-10-01",
  error: null,
  started_at: "2026-11-17T01:00:00Z",
  finished_at: "2026-11-17T01:40:00Z",
};

const FAILED: LoadRead = {
  layer: "boundaries.states",
  state: "TX",
  status: "failed",
  rows_loaded: null,
  source_version: null,
  error: "Download failed with status 404",
  started_at: "2026-11-17T02:00:00Z",
  finished_at: "2026-11-17T02:01:00Z",
};

const RUNNING: LoadRead = {
  ...SUCCEEDED,
  status: "running",
  rows_loaded: null,
  source_version: null,
  finished_at: null,
};

/**
 * Read the JSON body `customFetch` sent.
 */
function jsonBody(init?: RequestInit): unknown {
  if (typeof init?.body !== "string") throw new Error("Expected a JSON string body");
  return JSON.parse(init.body);
}

interface StubOptions {
  loads?: LoadRead[];
  startLoads?: () => Response;
}

/**
 * Stub `fetch` to answer the reference endpoints the page calls.
 *
 * Returns the stub so tests can check the requests sent.
 */
function stubApi({ loads = [], startLoads }: StubOptions = {}) {
  const fetchStub = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";

    if (url === "/api/v1/reference/states") return Response.json(STATES);
    if (url === "/api/v1/reference/layers") return Response.json(LAYERS);
    if (url === "/api/v1/reference/loads" && method === "GET") return Response.json(loads);
    if (url === "/api/v1/reference/loads" && method === "POST") {
      return startLoads ? startLoads() : Response.json({ loads: jsonBody(init) }, { status: 202 });
    }
    return new Response(null, { status: 404 });
  });

  vi.stubGlobal("fetch", fetchStub);
  return fetchStub;
}

function loadRequestCount(fetchStub: ReturnType<typeof stubApi>, method: string): number {
  return fetchStub.mock.calls.filter(
    ([url, init]) => url === "/api/v1/reference/loads" && (init?.method ?? "GET") === method,
  ).length;
}

async function addState(name: string) {
  const user = userEvent.setup();
  await user.type(await screen.findByRole("combobox", { name: "Add a state" }), name);
  await user.click(await screen.findByRole("option", { name: new RegExp(name, "i") }));
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("/admin/reference load table", () => {
  it("shows one column per layer", async () => {
    stubApi();

    renderRoute(PAGE_URL);

    for (const layer of LAYERS) {
      expect(await screen.findByRole("columnheader", { name: layer })).toBeInTheDocument();
    }
  });

  it("lists a row for each state that already has a load", async () => {
    stubApi({ loads: [SUCCEEDED] });

    renderRoute(PAGE_URL);

    expect(await screen.findByRole("rowheader", { name: "TX" })).toBeInTheDocument();
    expect(screen.queryByRole("rowheader", { name: "NC" })).not.toBeInTheDocument();
  });

  it("adds a row for a state found by its code", async () => {
    stubApi();
    renderRoute(PAGE_URL);

    await addState("NC");

    expect(await screen.findByRole("rowheader", { name: "NC" })).toBeInTheDocument();
  });

  it("adds a row for a state found by its full name", async () => {
    stubApi();
    renderRoute(PAGE_URL);

    await addState("South Carolina");

    expect(await screen.findByRole("rowheader", { name: "SC" })).toBeInTheDocument();
  });

  it("disables the Load button until a box is checked", async () => {
    stubApi();
    renderRoute(PAGE_URL);

    await addState("NC");

    expect(screen.getByRole("button", { name: "Load" })).toBeDisabled();
  });

  it("shows how many loads are selected", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");

    await user.click(screen.getByRole("checkbox", { name: "Load hydro.wetlands for NC" }));
    await user.click(screen.getByRole("checkbox", { name: "Load boundaries.states for NC" }));

    expect(screen.getByText("2 loads selected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load" })).toBeEnabled();
  });

  it("sends every checked box as one load request", async () => {
    const fetchStub = stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");
    await addState("SC");

    await user.click(screen.getByRole("checkbox", { name: "Load hydro.wetlands for NC" }));
    await user.click(screen.getByRole("checkbox", { name: "Load hydro.wetlands for SC" }));
    await user.click(screen.getByRole("button", { name: "Load" }));

    await waitFor(() => expect(loadRequestCount(fetchStub, "POST")).toBe(1));
    const [, init] = fetchStub.mock.calls.find(([, call]) => call?.method === "POST")!;
    expect(jsonBody(init)).toEqual([
      { layer: "hydro.wetlands", state: "NC" },
      { layer: "hydro.wetlands", state: "SC" },
    ]);
  });

  it("clears the checked boxes after the loads start", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");

    const checkbox = screen.getByRole("checkbox", { name: "Load hydro.wetlands for NC" });
    await user.click(checkbox);
    await user.click(screen.getByRole("button", { name: "Load" }));

    await waitFor(() => expect(checkbox).not.toBeChecked());
  });

  it("shows every problem when the loads can't start", async () => {
    const problems = ["No enabled source for hydro.wetlands in NC"];
    stubApi({ startLoads: () => Response.json({ detail: problems }, { status: 422 }) });
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");

    await user.click(screen.getByRole("checkbox", { name: "Load hydro.wetlands for NC" }));
    await user.click(screen.getByRole("button", { name: "Load" }));

    expect(await screen.findByText(problems[0])).toBeInTheDocument();
  });

  it("shows a moving progress bar for a running load", async () => {
    stubApi({ loads: [RUNNING] });

    renderRoute(PAGE_URL);

    const cell = await screen.findByRole("cell", { name: /hydro\.wetlands for TX/ });
    expect(within(cell).getByRole("progressbar")).toBeInTheDocument();
  });

  it("shows the row count for a load that succeeded", async () => {
    stubApi({ loads: [SUCCEEDED] });

    renderRoute(PAGE_URL);

    const cell = await screen.findByRole("cell", { name: /hydro\.wetlands for TX/ });
    expect(within(cell).getByText("succeeded")).toBeInTheDocument();
    expect(within(cell).getByText("2,233,909 rows")).toBeInTheDocument();
  });

  it("shows the error for a load that failed", async () => {
    stubApi({ loads: [FAILED] });

    renderRoute(PAGE_URL);

    const cell = await screen.findByRole("cell", { name: /boundaries\.states for TX/ });
    expect(within(cell).getByText("failed")).toBeInTheDocument();
    expect(within(cell).getByText("Download failed with status 404")).toBeInTheDocument();
  });

  it("asks for load status every 3 seconds while a load is running", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchStub = stubApi({ loads: [RUNNING] });
    renderRoute(PAGE_URL);
    await screen.findByRole("progressbar");
    const before = loadRequestCount(fetchStub, "GET");

    await vi.advanceTimersByTimeAsync(3000);

    await waitFor(() => expect(loadRequestCount(fetchStub, "GET")).toBeGreaterThan(before));
  });

  it("stops asking for load status when no load is running", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchStub = stubApi({ loads: [SUCCEEDED] });
    renderRoute(PAGE_URL);
    await screen.findByText("succeeded");
    const before = loadRequestCount(fetchStub, "GET");

    await vi.advanceTimersByTimeAsync(3000);

    expect(loadRequestCount(fetchStub, "GET")).toBe(before);
  });
});
