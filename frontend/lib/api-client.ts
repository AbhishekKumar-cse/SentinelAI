/**
 * API client wrapper that auto-attaches Firebase ID token to every request.
 * Force-refreshes the token if it's near expiry.
 */
import { auth } from "./firebase";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function getAuthHeader(): Promise<Record<string, string>> {
  try {
    const user = auth.currentUser;
    if (user) {
      // Force refresh if token is near expiry (handled by Firebase SDK when true)
      const token = await user.getIdToken(false);
      return { Authorization: `Bearer ${token}` };
    }
  } catch (e) {
    console.warn("Could not get auth token:", e);
  }
  return {};
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const authHeaders = await getAuthHeader();

  const response = await fetch(`${API_BASE}/api/v1${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorData: { error?: string; code?: string; detail?: string } = {};
    try {
      errorData = await response.json();
    } catch {}
    throw new ApiError(
      response.status,
      errorData.code || "HTTP_ERROR",
      errorData.error || errorData.detail || `HTTP ${response.status}`,
      errorData
    );
  }

  // Handle empty responses
  const text = await response.text();
  if (!text) return {} as T;
  return JSON.parse(text) as T;
}

export const api = {
  get: <T>(endpoint: string) =>
    request<T>(endpoint, { method: "GET" }),

  post: <T>(endpoint: string, data?: unknown) =>
    request<T>(endpoint, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    }),

  put: <T>(endpoint: string, data?: unknown) =>
    request<T>(endpoint, {
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
    }),

  patch: <T>(endpoint: string, data?: unknown) =>
    request<T>(endpoint, {
      method: "PATCH",
      body: data ? JSON.stringify(data) : undefined,
    }),

  delete: <T>(endpoint: string) =>
    request<T>(endpoint, { method: "DELETE" }),
};

export { ApiError };
