/**
 * Details of a failed API request, used to build an `ApiError`.
 */
interface ApiErrorDetails {
  /** HTTP method, for example `GET`. */
  method: string;
  /** Request URL, for example `/api/v1/reference/states`. */
  url: string;
  /** HTTP status code, or `0` when no response arrived. */
  status: number;
  /** Response body: parsed JSON, plain text, or `null` when there was none. */
  body: unknown;
  /** The original error, when no response arrived. */
  cause?: unknown;
}

/**
 * Error thrown by every generated API call that fails.
 *
 * A request fails when the API answers outside the 2xx range, or when no response
 * arrives at all (the API is down or the network failed), which has status `0`.
 */
export class ApiError extends Error {
  readonly method: string;
  readonly url: string;
  readonly status: number;
  readonly body: unknown;

  constructor({ method, url, status, body, cause }: ApiErrorDetails) {
    const reason =
      status === 0 ? "failed before a response arrived" : `failed with status ${status}`;
    super(`${method} ${url} ${reason}`, { cause });
    this.name = "ApiError";
    this.method = method;
    this.url = url;
    this.status = status;
    this.body = body;
  }
}

/**
 * Error type Orval uses for every generated hook.
 *
 * Orval passes each endpoint's error schema as `_Error`. It is not
 * used, because `customFetch` always throws `ApiError`.
 */
export type ErrorType<_Error> = ApiError;

/**
 * Parse a response body as JSON, falling back to the raw text.
 *
 * FastAPI answers in JSON, but a proxy or server in front of it can answer
 * with an HTML or plain-text error page.
 */
function parseBody(text: string): unknown {
  if (text === "") {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/**
 * Fetch function used by every generated API call.
 *
 * Returns the same `{ data, status, headers }` shape Orval generates. Throws an
 * `ApiError` when the response is not 2xx or no response arrives, so TanStack
 * Query puts the query or mutation into its error state. A cancelled request's
 * abort error is rethrown unchanged, so TanStack Query handles it as a cancel.
 */
export const customFetch = async <T>(url: string, options: RequestInit): Promise<T> => {
  const method = (options.method ?? "GET").toUpperCase();

  let response: Response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (options.signal?.aborted) {
      throw error;
    }
    throw new ApiError({ method, url, status: 0, body: null, cause: error });
  }

  const text = [204, 205, 304].includes(response.status) ? "" : await response.text();
  const body = parseBody(text);

  if (!response.ok) {
    throw new ApiError({ method, url, status: response.status, body });
  }

  return { data: body, status: response.status, headers: response.headers } as T;
};
