/**
 * Custom React hooks for API calls with comprehensive error handling
 */

import { useState, useCallback } from "react";
import { apiRequest, APIError } from "@/lib/api-client";
import { getApiBaseUrl } from "@/lib/api";
import { useAuthToken } from "./useAuthToken";

export interface UseApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  execute: (...args: unknown[]) => Promise<T | null>;
  reset: () => void;
}

export function useApi<T>(
  apiCall: (...args: unknown[]) => Promise<T>,
  options?: {
    onSuccess?: (data: T) => void;
    onError?: (error: APIError) => void;
    immediate?: boolean;
  }
): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(options?.immediate || false);

  const execute = useCallback(
    async (...args: unknown[]) => {
      setLoading(true);
      setError(null);

      try {
        const result = await apiCall(...args);
        setData(result);
        options?.onSuccess?.(result);
        return result;
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "An error occurred";
        setError(errorMessage);
        options?.onError?.(err as APIError);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [apiCall, options]
  );

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, error, loading, execute, reset };
}

export interface UseAuthApiState<T> extends UseApiState<T> {
  token: string | null;
}

export function useAuthApi<T>(
  apiCall: (token: string, ...args: unknown[]) => Promise<T>,
  options?: {
    onSuccess?: (data: T) => void;
    onError?: (error: APIError) => void;
    immediate?: boolean;
  }
): UseAuthApiState<T> {
  const { token } = useAuthToken();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(options?.immediate || false);

  const execute = useCallback(
    async (...args: unknown[]) => {
      if (!token) {
        setError("Authentication required");
        return null;
      }

      setLoading(true);
      setError(null);

      try {
        const result = await apiCall(token, ...args);
        setData(result);
        options?.onSuccess?.(result);
        return result;
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "An error occurred";
        setError(errorMessage);
        options?.onError?.(err as APIError);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [token, apiCall, options]
  );

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, error, loading, execute, reset, token };
}

// Specialized hook for GET requests with auto-fetch
export function useApiQuery<T>(
  endpoint: string,
  options?: {
    enabled?: boolean;
    refetchInterval?: number;
    onSuccess?: (data: T) => void;
    onError?: (error: APIError) => void;
  }
): UseApiState<T> & { refetch: () => void } {
  const { token } = useAuthToken();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(options?.enabled !== false);

  const fetchData = useCallback(async () => {
    if (!token || options?.enabled === false) {
      setLoading(false);
      return null;
    }

    setLoading(true);
    setError(null);

    try {
      const baseUrl = getApiBaseUrl();
      const result = await apiRequest<T>(`${baseUrl}${endpoint}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(result);
      options?.onSuccess?.(result);
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "An error occurred";
      setError(errorMessage);
      options?.onError?.(err as APIError);
      return null;
    } finally {
      setLoading(false);
    }
  }, [endpoint, token, options]);

  const execute = fetchData;
  const refetch = fetchData;

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  // Auto-fetch on mount if enabled
  useState(() => {
    if (options?.enabled !== false && token) {
      fetchData();
    }
  });

  // Set up interval if specified
  useState(() => {
    if (options?.refetchInterval && options?.enabled !== false && token) {
      const interval = setInterval(fetchData, options.refetchInterval);
      return () => clearInterval(interval);
    }
  });

  return { data, error, loading, execute, reset, refetch };
}

// Hook for mutations (POST, PUT, DELETE)
export function useApiMutation<T, TVariables = void>(
  mutationFn: (variables: TVariables) => Promise<T>,
  options?: {
    onSuccess?: (data: T, variables: TVariables) => void;
    onError?: (error: APIError, variables: TVariables) => void;
  }
): UseApiState<T> & {
  mutate: (variables: TVariables) => Promise<T | null>;
  mutateAsync: (variables: TVariables) => Promise<T>;
} {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const mutate = useCallback(
    async (variables: TVariables) => {
      setLoading(true);
      setError(null);

      try {
        const result = await mutationFn(variables);
        setData(result);
        options?.onSuccess?.(result, variables);
        return result;
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "An error occurred";
        setError(errorMessage);
        options?.onError?.(err as APIError, variables);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [mutationFn, options]
  );

  const mutateAsync = useCallback(
    async (variables: TVariables) => {
      setLoading(true);
      setError(null);

      try {
        const result = await mutationFn(variables);
        setData(result);
        options?.onSuccess?.(result, variables);
        return result;
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "An error occurred";
        setError(errorMessage);
        options?.onError?.(err as APIError, variables);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [mutationFn, options]
  );

  const execute = mutate as (...args: unknown[]) => Promise<T | null>;

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, error, loading, execute, reset, mutate, mutateAsync };
}
