import {afterEach, describe, expect, it, vi} from "vite-plus/test";

import {ApiError, customFetch} from "@/api/fetcher";

function stubFetch(implementation: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(implementation));
}

async function catchError(promise: Promise<unknown>): Promise<unknown> {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  throw new Error("Expected the request to throw");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("customFetch", () => {
  it("returns the data, status, and headers for a 2xx JSON response", async () => {
    stubFetch(async () => Response.json([{ code: "TX" }], { status: 200 }));

    const result = await customFetch<{ data: unknown; status: number; headers: Headers }>(
      "/api/v1/reference/states",
      { method: "GET" },
    );

    expect(result.data).toEqual([{ code: "TX" }]);
    expect(result.status).toBe(200);
    expect(result.headers.get("content-type")).toBe("application/json");
  });

  it("returns null data for a 204 response", async () => {
    stubFetch(async () => new Response(null, { status: 204 }));

    const result = await customFetch<{ data: unknown }>("/api/v1/thing", { method: "DELETE" });

    expect(result.data).toBeNull();
  });

  it("throws ApiError with the status and FastAPI's error body for a JSON error", async () => {
    const detail = [{ loc: ["body", "url"], msg: "Field required", type: "missing" }];
    stubFetch(async () => Response.json({ detail }, { status: 422 }));

    const error = await catchError(customFetch("/api/v1/reference/sources/1", { method: "PATCH" }));

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      method: "PATCH",
      url: "/api/v1/reference/sources/1",
      status: 422,
      body: { detail },
      message: "PATCH /api/v1/reference/sources/1 failed with status 422",
    });
  });

  it("throws ApiError with the status and the text body for an error that is not JSON", async () => {
    stubFetch(async () => new Response("<h1>502 Bad Gateway</h1>", { status: 502 }));

    const error = await catchError(customFetch("/api/v1/reference/states", { method: "GET" }));

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 502, body: "<h1>502 Bad Gateway</h1>" });
  });

  it("throws ApiError with status 0 and the original error as its cause when no response arrives", async () => {
    const networkError = new TypeError("Failed to fetch");
    stubFetch(async () => {
      throw networkError;
    });

    const error = await catchError(customFetch("/api/v1/reference/states", { method: "GET" }));

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 0,
      body: null,
      cause: networkError,
      message: "GET /api/v1/reference/states failed before a response arrived",
    });
  });

  it("rethrows the abort error unchanged when the request is cancelled", async () => {
    const controller = new AbortController();
    const abortError = new DOMException("The operation was aborted.", "AbortError");
    stubFetch(async () => {
      controller.abort();
      throw abortError;
    });

    const error = await catchError(
      customFetch("/api/v1/reference/states", { method: "GET", signal: controller.signal }),
    );

    expect(error).toBe(abortError);
  });
});
