import { ApiError } from "@/api/fetcher";
import type { CheckEvent, CheckRequest } from "@/api/generated";

const URL = "/api/v1/reference/sources/check";

/**
 * Check a source link, calling `onEvent` as each part of the answer arrives.
 *
 * The API answers this one request as a stream of JSON lines: the download's progress,
 * then reading, then the result or why it failed. The generated client waits for the
 * whole answer, so this reads the stream itself.
 *
 * Throws  `ApiError` when the API refuses the request (422 for an unknown layer or state)
 * or no response arrives. Stopping it with `signal` rejects with the abort error.
 */
export async function checkSource(
  data: CheckRequest,
  onEvent: (event: CheckEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }
    throw new ApiError({ method: "POST", url: URL, status: 0, body: null, cause: error });
  }

  if (!response.ok || response.body === null) {
    const text = await response.text();
    let body: unknown = text;
    try {
      body = JSON.parse(text);
    } catch {
      // Not JSON, such as a proxy's error page; keep the text.
    }
    throw new ApiError({ method: "POST", url: URL, status: response.status, body });
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffered = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffered += value;
    const lines = buffered.split("\n");
    buffered = lines.pop() ?? "";
    for (const line of lines) {
      if (line.trim() !== "") {
        onEvent(JSON.parse(line) as CheckEvent);
      }
    }
  }
  if (buffered.trim() !== "") {
    onEvent(JSON.parse(buffered) as CheckEvent);
  }
}
