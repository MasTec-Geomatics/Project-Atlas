import { ApiError } from "@/api/fetcher";
import type { CheckEvent, CheckRequest, SourcesCheckEvent } from "@/api/generated";

/**
 * Send a request to an endpoint that streams its answer, calling `onEvent` as each line
 * arrives.
 *
 * Those endpoints answer one request as a stream of JSON lines, so the page can show how
 * far along the work is. The generated client waits for the whole answer, so this reads
 * the stream itself.
 *
 * Throws `ApiError` when the API refuses the request or no response arrives. Stopping it
 * with `signal` rejects with the abort error.
 */
async function postStream<Event>(
  url: string,
  data: unknown,
  onEvent: (event: Event) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: data === undefined ? undefined : JSON.stringify(data),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }
    throw new ApiError({ method: "POST", url, status: 0, body: null, cause: error });
  }

  if (!response.ok || response.body === null) {
    const text = await response.text();
    let body: unknown = text;
    try {
      body = JSON.parse(text);
    } catch {
      // Not JSON, such as a proxy's error page; keep the text.
    }
    throw new ApiError({ method: "POST", url, status: response.status, body });
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
        onEvent(JSON.parse(line) as Event);
      }
    }
  }
  if (buffered.trim() !== "") {
    onEvent(JSON.parse(buffered) as Event);
  }
}

/**
 * Check a source link: the download's progress, the unzip's, reading, then the result or
 * why it failed.
 */
export function checkSource(
  data: CheckRequest,
  onEvent: (event: CheckEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return postStream("/api/v1/reference/sources/check", data, onEvent, signal);
}

/**
 * Check every loaded source for a newer file: each layer and state as it's checked, then
 * how many were checked, or why the check couldn't finish.
 */
export function runSourceChecks(
  onEvent: (event: SourcesCheckEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return postStream("/api/v1/reference/sources/checks", undefined, onEvent, signal);
}
