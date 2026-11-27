import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vite-plus/test";

import type {
  CheckEvent,
  CheckResult,
  LayerRead,
  SourceChecksRead,
  SourceRead,
  SourcesCheckEvent,
  StateRead,
} from "@/api/generated";
import { renderRoute } from "@/test/render";

const PAGE_URL = "/admin/reference/sources";

const STATES: StateRead[] = [
  { code: "NC", name: "North Carolina" },
  { code: "TX", name: "Texas" },
];

const LAYERS: LayerRead[] = [
  { name: "boundaries.places", title: "Cities and towns", group: "Boundaries" },
  { name: "hydro.wetlands", title: "Wetlands", group: "Water" },
];

const WETLANDS: SourceRead = {
  id: 1,
  layer: "hydro.wetlands",
  state: null,
  download_url: "https://example.gov/wetlands/{state}.zip",
  access_type: "file",
  format: "GPKG",
  source_layer: "wetlands_poly",
  field_mapping: { wetland_type: "WETLAND_TYPE", acres: "ACRES" },
  keep: null,
  clip_to_state: false,
  license: "Public domain",
  attribution: null,
  is_enabled: true,
  updated_at: "2026-11-20T12:00:00Z",
};

const PLACES_TX: SourceRead = {
  ...WETLANDS,
  id: 2,
  layer: "boundaries.places",
  state: "TX",
  download_url: "https://example.gov/tx/places.zip",
  format: "ESRI Shapefile",
  source_layer: null,
  field_mapping: { name: "NAME" },
  is_enabled: false,
};

const CHECKED: CheckResult = {
  format: "GPKG",
  layers: [
    { name: "places", fields: ["NAME", "GEOID", "POP"] },
    { name: "places_points", fields: ["NAME", "FID"] },
  ],
  source_layer: "places",
  field_mapping: { name: "NAME", geoid: "GEOID", population: null },
};

/**
 * Read the JSON body `customFetch` sent.
 */
function jsonBody(init?: RequestInit): unknown {
  if (typeof init?.body !== "string") throw new Error("Expected a JSON string body");
  return JSON.parse(init.body);
}

const NO_CHECKS: SourceChecksRead = { checked_at: null, updates: [] };

/**
 * A streamed answer, one JSON line per event.
 */
function checkStream(events: (CheckEvent | SourcesCheckEvent)[]): Response {
  const lines = events.map((event) => `${JSON.stringify(event)}\n`).join("");
  return new Response(lines, { headers: { "content-type": "application/x-ndjson" } });
}

/**
 * A streamed answer that stays open until the test sends each event.
 */
function openStream<Event>() {
  const encoder = new TextEncoder();
  let controller: ReadableStreamDefaultController<Uint8Array> | undefined;
  const body = new ReadableStream<Uint8Array>({
    start(streamController) {
      controller = streamController;
    },
  });
  return {
    response: new Response(body, { headers: { "content-type": "application/x-ndjson" } }),
    send(event: Event) {
      controller?.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
    },
    end() {
      controller?.close();
    },
  };
}

const CHECKED_STREAM: CheckEvent[] = [
  { stage: "downloading", progress_done: 1024, progress_total: 1024 },
  { stage: "unzipping", progress_done: 4096, progress_total: 4096 },
  { stage: "reading" },
  { stage: "done", result: CHECKED },
];

interface StubOptions {
  sources?: SourceRead[];
  check?: () => Response;
  save?: () => Response;
  checks?: SourceChecksRead;
  runChecks?: () => Response;
}

/**
 * Stub `fetch` to answer the reference endpoints the page calls.
 *
 * Returns the stub so tests can check the requests sent.
 */
function stubApi({
  sources = [WETLANDS, PLACES_TX],
  check,
  save,
  checks = NO_CHECKS,
  runChecks,
}: StubOptions = {}) {
  const fetchStub = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";

    if (url === "/api/v1/reference/states") return Response.json(STATES);
    if (url === "/api/v1/reference/layers") return Response.json(LAYERS);
    if (url === "/api/v1/reference/loads") return Response.json([]);
    if (url === "/api/v1/reference/sources" && method === "GET") return Response.json(sources);
    if (url === "/api/v1/reference/sources/check") {
      return check ? check() : checkStream(CHECKED_STREAM);
    }
    if (url === "/api/v1/reference/sources/checks" && method === "GET") {
      return Response.json(checks);
    }
    if (url === "/api/v1/reference/sources/checks" && method === "POST") {
      return runChecks ? runChecks() : checkStream([{ stage: "done", checked: 0, total: 0 }]);
    }
    if (url.startsWith("/api/v1/reference/sources") && method !== "GET") {
      if (save) return save();
      return Response.json({ ...PLACES_TX, ...(jsonBody(init) as object) }, { status: 201 });
    }
    return new Response(null, { status: 404 });
  });

  vi.stubGlobal("fetch", fetchStub);
  return fetchStub;
}

/**
 * The requests sent to `url` with `method`.
 */
function requests(fetchStub: ReturnType<typeof stubApi>, url: string, method: string) {
  return fetchStub.mock.calls.filter(
    ([callUrl, init]) => callUrl === url && (init?.method ?? "GET") === method,
  );
}

/**
 * Pick `option` in the dropdown labelled `label`.
 */
async function pick(label: string, option: string, user = userEvent.setup()) {
  const form = screen.getByRole("dialog");
  await user.click(within(form).getByRole("combobox", { name: label }));
  await user.click(await screen.findByRole("option", { name: option }));
}

/**
 * Open Add source and fill in Cities and towns for Texas with a link.
 */
async function startNewSource(user = userEvent.setup()) {
  await user.click(await screen.findByRole("button", { name: "Add source" }));
  await pick("Layer", "Cities and towns", user);
  await pick("State", "Texas (TX)", user);
  await user.type(
    within(screen.getByRole("dialog")).getByRole("textbox", { name: "Link" }),
    "https://example.gov/places.gpkg",
  );
}

// "Now" for the date tests.
const NOW = new Date("2026-11-20T12:00:00Z");

function userWithTimers() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("/admin/reference/sources", () => {
  it("lists sources in one table per group", async () => {
    stubApi();

    renderRoute(PAGE_URL);

    const water = await screen.findByRole("table", { name: "Water" });
    const row = within(water).getByRole("row", { name: /Wetlands/ });
    expect(within(row).getByText("Federal")).toBeInTheDocument();
    expect(within(row).getByText(WETLANDS.download_url)).toBeInTheDocument();
    expect(within(row).getByText("GPKG")).toBeInTheDocument();
    expect(within(row).getByText("Yes")).toBeInTheDocument();

    const boundaries = screen.getByRole("table", { name: "Boundaries" });
    const placesRow = within(boundaries).getByRole("row", { name: /Cities and towns/ });
    expect(within(placesRow).getByText("TX")).toBeInTheDocument();
    expect(within(placesRow).getByText("No")).toBeInTheDocument();
  });

  it("says so when there are no sources", async () => {
    stubApi({ sources: [] });

    renderRoute(PAGE_URL);

    expect(await screen.findByText("No sources yet.")).toBeInTheDocument();
  });

  it("links back to the load page", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);

    await user.click(await screen.findByRole("link", { name: "Load layers" }));

    expect(await screen.findByRole("heading", { name: "Load" })).toBeInTheDocument();
  });

  it("opens the Add source form", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);

    await user.click(await screen.findByRole("button", { name: "Add source" }));

    expect(screen.getByRole("dialog", { name: "Add source" })).toBeInTheDocument();
  });

  it("disables Save until the link is checked", async () => {
    stubApi();
    renderRoute(PAGE_URL);

    await startNewSource();

    expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("checks the link for the picked layer and state", async () => {
    const fetchStub = stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await startNewSource(user);

    await user.click(screen.getByRole("button", { name: "Check link" }));

    await waitFor(() =>
      expect(requests(fetchStub, "/api/v1/reference/sources/check", "POST")).toHaveLength(1),
    );
    const [[, init]] = requests(fetchStub, "/api/v1/reference/sources/check", "POST");
    expect(jsonBody(init)).toEqual({
      layer: "boundaries.places",
      state: "TX",
      download_url: "https://example.gov/places.gpkg",
      access_type: "file",
    });
  });

  it("checks a federal source's link with the state picked to check with", async () => {
    const fetchStub = stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await user.click(await screen.findByRole("button", { name: "Add source" }));
    await pick("Layer", "Cities and towns", user);
    await pick("State", "Federal", user);
    await pick("Check with", "North Carolina (NC)", user);
    await user.type(
      screen.getByRole("textbox", { name: "Link" }),
      "https://example.gov/{state}.zip",
    );

    await user.click(screen.getByRole("button", { name: "Check link" }));

    await waitFor(() =>
      expect(requests(fetchStub, "/api/v1/reference/sources/check", "POST")).toHaveLength(1),
    );
    const [[, init]] = requests(fetchStub, "/api/v1/reference/sources/check", "POST");
    expect(jsonBody(init)).toMatchObject({ state: "NC" });
  });

  it("fills in the format, dataset layer, and matched fields after the check", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await startNewSource(user);

    await user.click(screen.getByRole("button", { name: "Check link" }));

    const form = screen.getByRole("dialog");
    expect(await within(form).findByText("GPKG")).toBeInTheDocument();
    expect(within(form).getByRole("combobox", { name: "Dataset layer" })).toHaveValue("places");
    expect(within(form).getByRole("combobox", { name: "name" })).toHaveValue("NAME");
    expect(within(form).getByRole("combobox", { name: "geoid" })).toHaveValue("GEOID");
    expect(within(form).getByRole("combobox", { name: "population" })).toHaveValue("");
  });

  it("shows the download, then the unzip, then reading, while the link is checked", async () => {
    const stream = openStream<CheckEvent>();
    stubApi({ check: () => stream.response });
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await startNewSource(user);

    await user.click(screen.getByRole("button", { name: "Check link" }));
    stream.send({ stage: "downloading", progress_done: 356515840, progress_total: 1288490188 });

    const form = screen.getByRole("dialog");
    expect(await within(form).findByText("Downloading: 340.0 MB of 1.2 GB")).toBeInTheDocument();
    expect(within(form).getByRole("progressbar", { name: "Check link progress" })).toHaveAttribute(
      "aria-valuenow",
      "28",
    );

    stream.send({ stage: "unzipping", progress_done: 644245094, progress_total: 1288490188 });
    expect(await within(form).findByText("Unzipping: 614.4 MB of 1.2 GB")).toBeInTheDocument();
    expect(within(form).getByRole("progressbar", { name: "Check link progress" })).toHaveAttribute(
      "aria-valuenow",
      "50",
    );

    stream.send({ stage: "reading" });
    expect(await within(form).findByText("Reading fields")).toBeInTheDocument();

    stream.send({ stage: "done", result: CHECKED });
    stream.end();
    expect(await within(form).findByText("GPKG")).toBeInTheDocument();
    expect(within(form).queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("shows why a link couldn't be checked", async () => {
    stubApi({
      check: () => checkStream([{ stage: "failed", error: "Download failed with status 404" }]),
    });
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await startNewSource(user);

    await user.click(screen.getByRole("button", { name: "Check link" }));

    expect(await screen.findByText("Download failed with status 404")).toBeInTheDocument();
  });

  it("saves a new source with the fields picked", async () => {
    const fetchStub = stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await startNewSource(user);
    await user.click(screen.getByRole("button", { name: "Check link" }));
    await within(screen.getByRole("dialog")).findByText("GPKG");
    await pick("population", "POP", user);
    await user.click(screen.getByRole("checkbox", { name: "Clip to the state line" }));

    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(requests(fetchStub, "/api/v1/reference/sources", "POST")).toHaveLength(1),
    );
    const [[, init]] = requests(fetchStub, "/api/v1/reference/sources", "POST");
    expect(jsonBody(init)).toEqual({
      layer: "boundaries.places",
      state: "TX",
      download_url: "https://example.gov/places.gpkg",
      access_type: "file",
      format: "GPKG",
      source_layer: "places",
      field_mapping: { name: "NAME", geoid: "GEOID", population: "POP" },
      clip_to_state: true,
      license: null,
      attribution: null,
      is_enabled: true,
    });
  });

  it("leaves unmatched columns out of the saved fields", async () => {
    const fetchStub = stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await startNewSource(user);
    await user.click(screen.getByRole("button", { name: "Check link" }));
    await within(screen.getByRole("dialog")).findByText("GPKG");

    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(requests(fetchStub, "/api/v1/reference/sources", "POST")).toHaveLength(1),
    );
    const [[, init]] = requests(fetchStub, "/api/v1/reference/sources", "POST");
    expect(jsonBody(init)).toMatchObject({ field_mapping: { name: "NAME", geoid: "GEOID" } });
  });

  it("closes the form and reloads the list after saving", async () => {
    const fetchStub = stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await startNewSource(user);
    await user.click(screen.getByRole("button", { name: "Check link" }));
    await within(screen.getByRole("dialog")).findByText("GPKG");

    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(requests(fetchStub, "/api/v1/reference/sources", "GET").length).toBeGreaterThan(1);
  });

  it("shows why a source couldn't be saved", async () => {
    stubApi({
      save: () =>
        Response.json({ detail: "boundaries.places already has a source for TX" }, { status: 409 }),
    });
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await startNewSource(user);
    await user.click(screen.getByRole("button", { name: "Check link" }));
    await within(screen.getByRole("dialog")).findByText("GPKG");

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("boundaries.places already has a source for TX"),
    ).toBeInTheDocument();
  });

  it("asks for a new check when the link changes after a check", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    await startNewSource(user);
    await user.click(screen.getByRole("button", { name: "Check link" }));
    await within(screen.getByRole("dialog")).findByText("GPKG");

    await user.type(screen.getByRole("textbox", { name: "Link" }), "x");

    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("says when sources haven't been checked for updates yet", async () => {
    stubApi();

    renderRoute(PAGE_URL);

    expect(await screen.findByText("Not checked for updates yet")).toBeInTheDocument();
  });

  it("says when every loaded layer is up to date", async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: true });
    stubApi({ checks: { checked_at: "2026-11-19T12:00:00Z", updates: [] } });

    renderRoute(PAGE_URL);

    expect(await screen.findByText("Every loaded layer is up to date.")).toBeInTheDocument();
    expect(screen.getByText("Last checked 1 day ago")).toBeInTheDocument();
  });

  it("lists the loaded layers with a newer file or a problem", async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: true });
    stubApi({
      checks: {
        checked_at: "2026-11-19T12:00:00Z",
        updates: [
          {
            layer: "hydro.wetlands",
            state: "TX",
            last_pulled: "2026-11-01T12:00:00Z",
            error: null,
          },
          {
            layer: "boundaries.places",
            state: "NC",
            last_pulled: null,
            error: "HTTP 404 from https://example.gov/nc.zip",
          },
        ],
      },
    });

    renderRoute(PAGE_URL);

    const updates = await screen.findByRole("table", { name: "Updates" });
    const wetlands = within(updates).getByRole("row", { name: /Wetlands/ });
    expect(within(wetlands).getByText("TX")).toBeInTheDocument();
    expect(within(wetlands).getByText("Newer file available")).toBeInTheDocument();
    expect(within(wetlands).getByText("2026-11-01 07:00")).toBeInTheDocument();
    const places = within(updates).getByRole("row", { name: /Cities and towns/ });
    expect(
      within(places).getByText("Couldn't check: HTTP 404 from https://example.gov/nc.zip"),
    ).toBeInTheDocument();
  });

  it("shows the check dates in the time zone and style picked in Dates", async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: true });
    stubApi({ checks: { checked_at: "2026-11-19T12:00:00Z", updates: [] } });
    const user = userWithTimers();
    renderRoute(PAGE_URL);

    await user.click(await screen.findByRole("button", { name: "Dates" }));
    await user.click(await screen.findByRole("combobox", { name: "Time zone" }));
    await user.click(await screen.findByRole("option", { name: "UTC" }));
    await user.click(screen.getByRole("radio", { name: "Full date" }));

    expect(await screen.findByText("Last checked 2026-11-19 12:00Z")).toBeInTheDocument();
  });

  it("checks every loaded source with Check for updates, then shows what it found", async () => {
    const fetchStub = stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);

    await user.click(await screen.findByRole("button", { name: "Check for updates" }));

    await waitFor(() =>
      expect(requests(fetchStub, "/api/v1/reference/sources/checks", "POST")).toHaveLength(1),
    );
    await waitFor(() =>
      expect(requests(fetchStub, "/api/v1/reference/sources/checks", "GET").length).toBeGreaterThan(
        1,
      ),
    );
  });

  it("shows each source while Check for updates runs", async () => {
    const stream = openStream<SourcesCheckEvent>();
    stubApi({ runChecks: () => stream.response });
    const user = userEvent.setup();
    renderRoute(PAGE_URL);

    await user.click(await screen.findByRole("button", { name: "Check for updates" }));
    stream.send({
      stage: "checking",
      checked: 2,
      total: 4,
      layer: "hydro.wetlands",
      state: "TX",
    });

    expect(await screen.findByText("Checking Wetlands for TX (3 of 4)")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Check for updates progress" })).toHaveAttribute(
      "aria-valuenow",
      "50",
    );
    expect(screen.getByRole("button", { name: "Check for updates" })).toBeDisabled();

    stream.send({ stage: "done", checked: 4, total: 4 });
    stream.end();
    await waitFor(() => expect(screen.queryByRole("progressbar")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Check for updates" })).toBeEnabled();
  });

  it("shows why Check for updates couldn't finish", async () => {
    stubApi({
      runChecks: () =>
        checkStream([{ stage: "failed", error: "the reference database went away" }]),
    });
    const user = userEvent.setup();
    renderRoute(PAGE_URL);

    await user.click(await screen.findByRole("button", { name: "Check for updates" }));

    expect(await screen.findByText("the reference database went away")).toBeInTheDocument();
  });

  it("opens a source's current settings with Edit", async () => {
    stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    const water = await screen.findByRole("table", { name: "Water" });

    await user.click(within(water).getByRole("button", { name: "Edit Wetlands, Federal" }));

    const form = screen.getByRole("dialog", { name: "Edit source" });
    expect(within(form).getByText("Wetlands, Federal")).toBeInTheDocument();
    expect(within(form).getByRole("textbox", { name: "Link" })).toHaveValue(WETLANDS.download_url);
    expect(within(form).getByRole("combobox", { name: "wetland_type" })).toHaveValue(
      "WETLAND_TYPE",
    );
    expect(within(form).getByRole("textbox", { name: "License" })).toHaveValue("Public domain");
    expect(within(form).getByRole("button", { name: "Save" })).toBeEnabled();
  });

  it("saves changes to a source", async () => {
    const fetchStub = stubApi();
    const user = userEvent.setup();
    renderRoute(PAGE_URL);
    const water = await screen.findByRole("table", { name: "Water" });
    await user.click(within(water).getByRole("button", { name: "Edit Wetlands, Federal" }));

    await user.click(screen.getByRole("checkbox", { name: "Enabled" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(requests(fetchStub, "/api/v1/reference/sources/1", "PATCH")).toHaveLength(1),
    );
    const [[, init]] = requests(fetchStub, "/api/v1/reference/sources/1", "PATCH");
    expect(jsonBody(init)).toEqual({
      download_url: WETLANDS.download_url,
      access_type: "file",
      format: "GPKG",
      source_layer: "wetlands_poly",
      field_mapping: WETLANDS.field_mapping,
      clip_to_state: false,
      license: "Public domain",
      attribution: null,
      is_enabled: false,
    });
  });
});
