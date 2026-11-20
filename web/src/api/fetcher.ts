/**
 * Error thrown for any API response outside the 2xx range.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown) {
    super(`API request failed with status ${status}`);
    this.name = "APIError";
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
 * Fetch function used by every generated API call.
 *
 * Returns the same `{ data, status, headers }` shape Orval generates,
 * and throws an `ApiError` when the response is not 2xx, so TanStack
 * Query puts the query or mutation into its error state.
 */
export const customFetch = async <T>(url: string, options: RequestInit): Promise<T> => {
  const response = await fetch(url, options);
  const text = [204, 205, 304].includes(response.status) ? "" : await response.text();
  const data: unknown = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new ApiError(response.status, data);
  }

  return { data, status: response.status, headers: response.headers } as T;
};
