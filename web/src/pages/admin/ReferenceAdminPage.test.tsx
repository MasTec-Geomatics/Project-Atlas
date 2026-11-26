import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vite-plus/test";

import type { LayerRead, LoadRead, StateRead } from "@/api/generated";
import { renderRoute } from "@/test/render";

const PAGE_URL = "/admin/reference";

const STATES: StateRead[] = [
  { code: "NC", name: "North Carolina" },
  { code: "SC", name: "South Carolina" },
  { code: "TX", name: "Texas" },
];

const LAYERS: LayerRead[] = [
  { name: "boundaries.states", title: "States", group: "Boundaries" },
  { name: "hydro.wetlands", title: "Wetlands", group: "Water" },
];

const SUCCEEDED: LoadRead = {
  layer: "hydro.wetlands",
  state: "TX",
  status: "succeeded",
  stage: null,
  bytes_downloaded: null,
  bytes_total: null,
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
  stage: null,
  bytes_downloaded: null,
  bytes_total: null,
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
  loadsAfterStart?: LoadRead[];
  startLoads?: () => Response;
}

/**
 * Stub `fetch` to answer the reference endpoints the page calls.
 *
 * `loads` is the load list when the page opens; `loadsAfterStart`, if given, is the load
 * list once the Load button has been clicked.
 *
 * Returns the stub so tests can check the requests sent.
 */
function stubApi({ loads = [], loadsAfterStart, startLoads }: StubOptions = {}) {
  let currentLoads = loads;
  const fetchStub = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";

    if (url === "/api/v1/reference/states") return Response.json(STATES);
    if (url === "/api/v1/reference/layers") return Response.json(LAYERS);
    if (url === "/api/v1/reference/loads" && method === "GET") return Response.json(currentLoads);
    if (url === "/api/v1/reference/loads" && method === "POST") {
      if (startLoads) return startLoads();
      currentLoads = loadsAfterStart ?? currentLoads;
      return Response.json({ loads: jsonBody(init) }, { status: 202 });
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

/**
 * A finished load of a layer for a state.
 */
function finishedLoad(layer: string, state: string, status: "succeeded" | "failed"): LoadRead {
  return status === "succeeded" ? { ...SUCCEEDED, layer, state } : { ...FAILED, layer, state };
}

function userWithTimers() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}

async function addState(name: string, user = userEvent.setup()) {
  await user.type(await screen.findByRole("combobox", { name: "States" }), name);
  await user.click(await screen.findByRole("option", { name: new RegExp(name, "i") }));
}

/**
 * Add NC, check its Wetlands box, and click Load.
 */
async function loadWetlandsForNC(user = userEvent.setup()) {
  await addState("NC", user);
  await user.click(screen.getByRole("checkbox", { name: "Load Wetlands for NC" }));
  await user.click(screen.getByRole("button", { name: "Load" }));
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/**
 * The row headings named `name`, one in each group's table.
 */
function rowHeaders(name: string) {
  return screen.queryAllByRole("rowheader", { name });
}

describe("/admin/reference load table", () => {
  it("shows only the States box until a state is picked", async () => {
    const fetchStub = stubApi();

    renderRoute(PAGE_URL);

    expect(await screen.findByRole("combobox", { name: "States" })).toBeInTheDocument();
    await waitFor(() => expect(loadRequestCount(fetchStub, "GET")).toBe(1));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("links to the sources page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([])),
    );
    const user = userEvent.setup();
    renderRoute(PAGE_URL);

    await user.click(await screen.findByRole("link", { name: "Sources" }));

    expect(await screen.findByRole("button", { name: "Add source" })).toBeInTheDocument();
  });

  it("shows one table per group, under its readable name", async () => {
    stubApi();
    renderRoute(PAGE_URL);

    await addState("NC");

    expect(await screen.findByRole("table", { name: "Boundaries" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Water" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Water" })).toBeInTheDocument();
  });

  it("shows one column per layer, by its readable name", async () => {
    stubApi();
    renderRoute(PAGE_URL);

    await addState("NC");

    for (const layer of LAYERS) {
      expect(await screen.findByRole("columnheader", { name: layer.title })).toBeInTheDocument();
    }
  });

  it("adds a row for a state found by its code", async () => {
    stubApi();
    renderRoute(PAGE_URL);

    await addState("NC");

    await waitFor(() => expect(rowHeaders("NC")).toHaveLength(2));
  });

  it("adds a row for a state found by its full name", async () => {
    stubApi();
    renderRoute(PAGE_URL);

    await addState("South Carolina");

    await waitFor(() => expect(rowHeaders("SC")).toHaveLength(2));
  });

  it("adds a row for each state with a running load", async () => {
    stubApi({ loads: [RUNNING] });

    renderRoute(PAGE_URL);

    await waitFor(() => expect(rowHeaders("TX")).toHaveLength(2));
    expect(rowHeaders("NC")).toHaveLength(0);
  });

  it("leaves out loads that finished before the page opened", async () => {
    const fetchStub = stubApi({ loads: [SUCCEEDED, FAILED] });

    renderRoute(PAGE_URL);

    await waitFor(() => expect(loadRequestCount(fetchStub, "GET")).toBe(1));
    expect(rowHeaders("TX")).toHaveLength(0);
    expect(screen.queryByText("succeeded")).not.toBeInTheDocument();
    expect(screen.queryByText("failed")).not.toBeInTheDocument();
  });

  it("shows one All states row, not a row per state, when All states is picked", async () => {
    stubApi();
    renderRoute(PAGE_URL);

    await addState("All states");

    await waitFor(() => expect(rowHeaders("All states")).toHaveLength(2));
    expect(rowHeaders("NC")).toHaveLength(0);
  });

  it("replaces All states with a state picked after it", async () => {
    stubApi();
    renderRoute(PAGE_URL);
    await addState("All states");

    await addState("NC");

    await waitFor(() => expect(rowHeaders("NC")).toHaveLength(2));
    expect(rowHeaders("All states")).toHaveLength(0);
  });

  it("replaces picked states with All states", async () => {
    stubApi();
    renderRoute(PAGE_URL);
    await addState("NC");

    await addState("All states");

    await waitFor(() => expect(rowHeaders("All states")).toHaveLength(2));
    expect(rowHeaders("NC")).toHaveLength(0);
  });

  it("removes every state with the Clear states button", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");
    await addState("SC");

    await user.click(screen.getByRole("button", { name: "Clear states" }));

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("removes the last state picked with Backspace", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");
    await addState("SC");

    await user.type(screen.getByRole("combobox", { name: "States" }), "{Backspace}");

    expect(rowHeaders("SC")).toHaveLength(0);
    expect(rowHeaders("NC")).toHaveLength(2);
  });

  it("drops a removed state's checked boxes", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");
    await user.click(screen.getByRole("checkbox", { name: "Load Wetlands for NC" }));

    await user.click(screen.getByRole("button", { name: "Clear states" }));
    await addState("NC", user);

    expect(screen.getByRole("checkbox", { name: "Load Wetlands for NC" })).not.toBeChecked();
    expect(screen.getByText("0 loads selected")).toBeInTheDocument();
  });

  it("loads a layer for every state from the All states column", async () => {
    const fetchStub = stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("All states");

    await user.click(screen.getByRole("checkbox", { name: "Load Wetlands for All states" }));
    await user.click(screen.getByRole("button", { name: "Load" }));

    await waitFor(() => expect(loadRequestCount(fetchStub, "POST")).toBe(1));
    const [, init] = fetchStub.mock.calls.find(([, call]) => call?.method === "POST")!;
    expect(jsonBody(init)).toEqual(
      STATES.map(({ code }) => ({ layer: "hydro.wetlands", state: code })),
    );
  });

  it("shows how many states are done in the All states column", async () => {
    stubApi({
      loadsAfterStart: [
        finishedLoad("hydro.wetlands", "NC", "succeeded"),
        { ...RUNNING, state: "SC" },
      ],
    });
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("All states");

    await user.click(screen.getByRole("checkbox", { name: "Load Wetlands for All states" }));
    await user.click(screen.getByRole("button", { name: "Load" }));

    const cell = await screen.findByRole("cell", { name: /Wetlands for All states/ });
    expect(await within(cell).findByText("1 of 3 states done")).toBeInTheDocument();
    expect(within(cell).getByRole("progressbar")).toBeInTheDocument();
  });

  it("lists the states that failed in the All states column", async () => {
    stubApi({
      loadsAfterStart: [
        finishedLoad("hydro.wetlands", "NC", "succeeded"),
        finishedLoad("hydro.wetlands", "SC", "succeeded"),
        finishedLoad("hydro.wetlands", "TX", "failed"),
      ],
    });
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("All states");

    await user.click(screen.getByRole("checkbox", { name: "Load Wetlands for All states" }));
    await user.click(screen.getByRole("button", { name: "Load" }));

    const cell = await screen.findByRole("cell", { name: /Wetlands for All states/ });
    expect(await within(cell).findByText("2 succeeded, 1 failed")).toBeInTheDocument();
    expect(within(cell).getByText("TX: Download failed with status 404")).toBeInTheDocument();
  });

  it("checks a layer for every state from its column heading", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");
    await addState("SC");

    await user.click(screen.getByRole("checkbox", { name: "Wetlands" }));

    expect(screen.getByRole("checkbox", { name: "Load Wetlands for NC" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Load Wetlands for SC" })).toBeChecked();
    expect(screen.getByText("2 loads selected")).toBeInTheDocument();
  });

  it("unchecks a layer for every state from its column heading", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");
    await addState("SC");
    await user.click(screen.getByRole("checkbox", { name: "Wetlands" }));

    await user.click(screen.getByRole("checkbox", { name: "Wetlands" }));

    expect(screen.getByText("0 loads selected")).toBeInTheDocument();
  });

  it("checks every layer in a table for a state from its row heading", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");
    await addState("SC");

    const water = screen.getByRole("table", { name: "Water" });
    await user.click(within(water).getByRole("checkbox", { name: "NC" }));

    expect(screen.getByRole("checkbox", { name: "Load Wetlands for NC" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Load Wetlands for SC" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Load States for NC" })).not.toBeChecked();
  });

  it("checks every box with Select all", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");
    await addState("SC");

    await user.click(screen.getByRole("button", { name: "Select all" }));

    expect(screen.getByText("4 loads selected")).toBeInTheDocument();
  });

  it("unchecks every box with Clear", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");
    await user.click(screen.getByRole("button", { name: "Select all" }));

    await user.click(screen.getByRole("button", { name: "Clear" }));

    expect(screen.getByText("0 loads selected")).toBeInTheDocument();
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

    await user.click(screen.getByRole("checkbox", { name: "Load Wetlands for NC" }));
    await user.click(screen.getByRole("checkbox", { name: "Load States for NC" }));

    expect(screen.getByText("2 loads selected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load" })).toBeEnabled();
  });

  it("sends every checked box as one load request", async () => {
    const fetchStub = stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await addState("NC");
    await addState("SC");

    await user.click(screen.getByRole("checkbox", { name: "Load Wetlands for NC" }));
    await user.click(screen.getByRole("checkbox", { name: "Load Wetlands for SC" }));
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

    const checkbox = screen.getByRole("checkbox", { name: "Load Wetlands for NC" });
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

    await user.click(screen.getByRole("checkbox", { name: "Load Wetlands for NC" }));
    await user.click(screen.getByRole("button", { name: "Load" }));

    expect(await screen.findByText(problems[0])).toBeInTheDocument();
  });

  it("shows a moving progress bar for a running load", async () => {
    stubApi({ loads: [RUNNING] });

    renderRoute(PAGE_URL);

    const cell = await screen.findByRole("cell", { name: /Wetlands for TX/ });
    expect(within(cell).getByRole("progressbar")).toBeInTheDocument();
  });

  it("shows how much of a running load has downloaded", async () => {
    stubApi({
      loads: [
        { ...RUNNING, stage: "downloading", bytes_downloaded: 356515840, bytes_total: 1288490188 },
      ],
    });

    renderRoute(PAGE_URL);

    const cell = await screen.findByRole("cell", { name: /Wetlands for TX/ });
    expect(within(cell).getByText("Downloading: 340.0 MB of 1.2 GB")).toBeInTheDocument();
    expect(within(cell).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "28");
  });

  it("shows a running load's download when its size isn't known", async () => {
    stubApi({ loads: [{ ...RUNNING, stage: "downloading", bytes_downloaded: 5242880 }] });

    renderRoute(PAGE_URL);

    const cell = await screen.findByRole("cell", { name: /Wetlands for TX/ });
    expect(within(cell).getByText("Downloading: 5.0 MB")).toBeInTheDocument();
  });

  it("shows when a running load is copying data", async () => {
    stubApi({ loads: [{ ...RUNNING, stage: "copying" }] });

    renderRoute(PAGE_URL);

    const cell = await screen.findByRole("cell", { name: /Wetlands for TX/ });
    expect(within(cell).getByText("Copying data")).toBeInTheDocument();
  });

  it("shows when a running load is swapping data", async () => {
    stubApi({ loads: [{ ...RUNNING, stage: "swapping" }] });

    renderRoute(PAGE_URL);

    const cell = await screen.findByRole("cell", { name: /Wetlands for TX/ });
    expect(within(cell).getByText("Swapping data")).toBeInTheDocument();
  });

  it("shows waiting for a requested load that hasn't started", async () => {
    stubApi();
    renderRoute(PAGE_URL);

    await loadWetlandsForNC();

    const cell = await screen.findByRole("cell", { name: /Wetlands for NC/ });
    expect(await within(cell).findByText("waiting")).toBeInTheDocument();
  });

  it("shows the row count after a requested load succeeds", async () => {
    stubApi({ loadsAfterStart: [finishedLoad("hydro.wetlands", "NC", "succeeded")] });
    renderRoute(PAGE_URL);

    await loadWetlandsForNC();

    const cell = await screen.findByRole("cell", { name: /Wetlands for NC/ });
    expect(await within(cell).findByText("succeeded")).toBeInTheDocument();
    expect(within(cell).getByText("2,233,909 rows")).toBeInTheDocument();
  });

  it("shows the error after a requested load fails", async () => {
    stubApi({ loadsAfterStart: [finishedLoad("hydro.wetlands", "NC", "failed")] });
    renderRoute(PAGE_URL);

    await loadWetlandsForNC();

    const cell = await screen.findByRole("cell", { name: /Wetlands for NC/ });
    expect(await within(cell).findByText("failed")).toBeInTheDocument();
    expect(within(cell).getByText("Download failed with status 404")).toBeInTheDocument();
  });

  it("clears the page 5 seconds after the last load finishes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    stubApi({ loadsAfterStart: [finishedLoad("hydro.wetlands", "NC", "succeeded")] });
    renderRoute(PAGE_URL);
    await loadWetlandsForNC(userWithTimers());
    await screen.findByText("succeeded");

    await vi.advanceTimersByTimeAsync(5000);

    await waitFor(() => expect(screen.queryByText("succeeded")).not.toBeInTheDocument());
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("keeps asking for load status while a requested load is waiting", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchStub = stubApi();
    renderRoute(PAGE_URL);
    await loadWetlandsForNC(userWithTimers());
    await screen.findByText("waiting");
    const before = loadRequestCount(fetchStub, "GET");

    await vi.advanceTimersByTimeAsync(3000);

    await waitFor(() => expect(loadRequestCount(fetchStub, "GET")).toBeGreaterThan(before));
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
    await waitFor(() => expect(loadRequestCount(fetchStub, "GET")).toBe(1));

    await vi.advanceTimersByTimeAsync(3000);

    expect(loadRequestCount(fetchStub, "GET")).toBe(1);
  });
});

// "Now" for the date tests: 3 days, 10 hours, and 20 minutes after SUCCEEDED finished.
const NOW = new Date("2026-11-20T12:00:00Z");

/**
 * Open the Dates menu and pick a time zone and a style.
 */
async function pickDates(timeZone: string, style: string, user = userWithTimers()) {
  await user.click(await screen.findByRole("button", { name: "Dates" }));
  await user.click(await screen.findByRole("combobox", { name: "Time zone" }));
  await user.click(await screen.findByRole("option", { name: timeZone }));
  await user.click(screen.getByRole("radio", { name: style }));
}

describe("/admin/reference last updated", () => {
  it("shows how long ago each box was last updated", async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: true });
    stubApi({ loads: [SUCCEEDED] });
    renderRoute(PAGE_URL);

    await addState("TX", userWithTimers());

    const cell = await screen.findByRole("cell", { name: /Wetlands for TX/ });
    expect(await within(cell).findByText("Updated 3 days ago")).toBeInTheDocument();
  });

  it("shows when a box's last load failed", async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: true });
    stubApi({ loads: [FAILED] });
    renderRoute(PAGE_URL);

    await addState("TX", userWithTimers());

    const cell = await screen.findByRole("cell", { name: /States for TX/ });
    expect(await within(cell).findByText("Failed 3 days ago")).toBeInTheDocument();
  });

  it("shows when a box has never been loaded", async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: true });
    stubApi({ loads: [SUCCEEDED] });
    renderRoute(PAGE_URL);

    await addState("NC", userWithTimers());

    const cell = await screen.findByRole("cell", { name: /Wetlands for NC/ });
    expect(await within(cell).findByText("Never loaded")).toBeInTheDocument();
  });

  it("shows the date and local time once a load is 7 days old", async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: true });
    stubApi({ loads: [{ ...SUCCEEDED, finished_at: "2026-10-20T12:00:00Z" }] });
    renderRoute(PAGE_URL);

    await addState("TX", userWithTimers());

    const cell = await screen.findByRole("cell", { name: /Wetlands for TX/ });
    expect(await within(cell).findByText("Updated 2026-10-20 08:00")).toBeInTheDocument();
  });

  it("shows UTC times with a Z when UTC is picked", async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: true });
    stubApi({ loads: [SUCCEEDED] });
    const user = userWithTimers();
    renderRoute(PAGE_URL);
    await addState("TX", user);

    await pickDates("UTC", "Full date", user);

    const cell = await screen.findByRole("cell", { name: /Wetlands for TX/ });
    expect(await within(cell).findByText("Updated 2026-11-17 01:40Z")).toBeInTheDocument();
  });

  it("shows times in any time zone picked", async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: true });
    stubApi({ loads: [SUCCEEDED] });
    const user = userWithTimers();
    renderRoute(PAGE_URL);
    await addState("TX", user);

    await pickDates("America/Chicago", "Full date", user);

    const cell = await screen.findByRole("cell", { name: /Wetlands for TX/ });
    expect(await within(cell).findByText("Updated 2026-11-16 19:40")).toBeInTheDocument();
  });

  it("keeps the picked date settings after the page is opened again", async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: true });
    stubApi({ loads: [SUCCEEDED] });
    const user = userWithTimers();
    const first = renderRoute(PAGE_URL);
    await pickDates("UTC", "Full date", user);
    first.unmount();

    renderRoute(PAGE_URL);
    await addState("TX", user);

    const cell = await screen.findByRole("cell", { name: /Wetlands for TX/ });
    expect(await within(cell).findByText("Updated 2026-11-17 01:40Z")).toBeInTheDocument();
  });
});
