/**
 * API Client with comprehensive error handling and retry logic
 */

import { clearAuthToken, AUTH_EXPIRED_EVENT } from "./auth";

export class APIError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public details?: unknown
  ) {
    super(message);
    this.name = "APIError";
  }
}

export class NetworkError extends APIError {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

export class AuthenticationError extends APIError {
  constructor(message: string = "Authentication required") {
    super(message, 401);
    this.name = "AuthenticationError";
  }
}

export class ValidationError extends APIError {
  constructor(message: string, details?: unknown) {
    super(message, 400, details);
    this.name = "ValidationError";
  }
}

export class ServerError extends APIError {
  constructor(message: string = "Server error occurred") {
    super(message, 500);
    this.name = "ServerError";
  }
}

interface RetryOptions {
  maxRetries?: number;
  retryDelay?: number;
  retryableStatuses?: number[];
}

const DEFAULT_RETRY_OPTIONS: RetryOptions = {
  maxRetries: 3,
  retryDelay: 1000,
  retryableStatuses: [408, 429, 500, 502, 503, 504],
};

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function apiRequest<T>(
  input: RequestInfo | URL,
  init?: RequestInit & { retryOptions?: RetryOptions }
): Promise<T> {
  const { retryOptions, ...fetchInit } = init || {};
  const options = { ...DEFAULT_RETRY_OPTIONS, ...retryOptions };

  let lastError: Error | null = null;
  let attempt = 0;

  while (attempt <= (options.maxRetries || 0)) {
    try {
      const response = await fetch(input, {
        // Default to cookie-bearing requests so auth works for callers that
        // don't manually pass an Authorization header. Callers can still
        // override by passing credentials: "omit" in init.
        credentials: "include",
        ...fetchInit,
        headers: {
          "Content-Type": "application/json",
          ...fetchInit.headers,
        },
      });

      // Handle authentication errors
      if (response.status === 401) {
        if (typeof window !== "undefined") {
          clearAuthToken();
          window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
        }
        throw new AuthenticationError("Session expired. Please log in again.");
      }

      // Check if response should be retried
      if (
        options.retryableStatuses?.includes(response.status) &&
        attempt < (options.maxRetries || 0)
      ) {
        attempt++;
        await sleep((options.retryDelay || 1000) * attempt);
        continue;
      }

      // Handle non-OK responses
      if (!response.ok) {
        let errorMessage = `Request failed with status ${response.status}`;
        let errorDetails: unknown = null;

        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
          errorDetails = errorData;
        } catch {
          errorMessage = await response.text().catch(() => errorMessage);
        }

        if (response.status >= 400 && response.status < 500) {
          throw new ValidationError(errorMessage, errorDetails);
        } else if (response.status >= 500) {
          throw new ServerError(errorMessage);
        }

        throw new APIError(errorMessage, response.status, errorDetails);
      }

      // Parse successful response
      const contentType = response.headers.get("content-type");
      if (contentType?.includes("application/json")) {
        return (await response.json()) as T;
      }

      // Return empty object for non-JSON responses
      return {} as T;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Don't retry on client errors (400-499) or auth errors
      if (
        error instanceof ValidationError ||
        error instanceof AuthenticationError
      ) {
        throw error;
      }

      // Retry on network errors
      if (error instanceof TypeError && attempt < (options.maxRetries || 0)) {
        attempt++;
        await sleep((options.retryDelay || 1000) * attempt);
        continue;
      }

      // If it's the last attempt, throw the error
      if (attempt >= (options.maxRetries || 0)) {
        if (error instanceof APIError) {
          throw error;
        }
        throw new NetworkError(
          lastError?.message || "Network request failed"
        );
      }

      attempt++;
      await sleep((options.retryDelay || 1000) * attempt);
    }
  }

  throw new NetworkError(
    lastError?.message || "Request failed after retries"
  );
}

export function createAuthHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
  };
}

export function buildQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const entries = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);

  return entries.length > 0 ? `?${entries.join("&")}` : "";
}
