/**
 * API Client Configuration
 * Educational Note: We create an axios instance with base configuration
 * to avoid repeating the base URL and headers in every request.
 * This is the single source of truth for API communication.
 */

import axios, { AxiosError } from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';
import { getAccessToken, getRefreshToken, setSession, clearSession } from '../auth/session';
import { createLogger } from '@/lib/logger';

const log = createLogger('api-client');

// Base host URL (without /api/v1 path) - used for file URLs, static assets.
// When VITE_API_HOST is set to "" (Docker via nginx proxy), same-origin requests
// are used. When unset (local dev), falls back to localhost:5001.
const envHost = import.meta.env.VITE_API_HOST;
export const API_HOST = envHost !== undefined ? envHost : 'http://localhost:5001';

// Full API URL (with /api/v1 path) - used for API requests
const envApiUrl = import.meta.env.VITE_API_URL;
const API_BASE_URL = envApiUrl !== undefined ? envApiUrl : `${API_HOST}/api/v1`;

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

const attachAuthHeader = (config: any) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
};

// Attach auth header to all requests
api.interceptors.request.use(
  (config) => {
    return attachAuthHeader(config);
  },
  (error) => {
    log.error({ err: error }, 'request interceptor error');
    return Promise.reject(error);
  }
);

// Ensure global axios requests (non-api instance) include auth header too
axios.interceptors.request.use(attachAuthHeader);

// ---------- Auto-refresh on 401 ----------
// Educational Note: When the JWT expires (default ~1 hour), API calls return 401.
// Instead of forcing re-login, we intercept the 401, use the stored refresh_token
// to get a new token pair, then transparently retry the original request.
// A shared `refreshPromise` ensures concurrent 401s trigger only one refresh call;
// all queued requests wait on the same promise.

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
      refresh_token: refreshToken,
    });
    if (data?.success && data.session?.access_token) {
      setSession(data.session.access_token, data.session.refresh_token);
      return true;
    }
  } catch (err) {
    log.error({ err }, 'token refresh failed');
  }

  clearSession();
  return false;
}

// Shared 401 error handler used by both the `api` instance and global `axios` interceptors.
// Educational Note: axios.create() instances have separate interceptor chains, so registering
// on both the `api` instance AND the global `axios` default won't double-fire for `api` requests.
// The shared `refreshPromise` correctly deduplicates concurrent refresh attempts across both.
async function handle401Error(error: AxiosError, retryWith: typeof api | typeof axios): Promise<any> {
  const status = error.response?.status;
  const originalRequest = error.config as InternalAxiosRequestConfig & { _retried?: boolean };

  // Skip refresh for auth routes (avoid infinite loop) and already-retried requests
  const isAuthRoute = originalRequest?.url?.includes('/auth/');
  if (status === 401 && originalRequest && !originalRequest._retried && !isAuthRoute) {
    // Deduplicate concurrent refresh attempts
    if (!refreshPromise) {
      refreshPromise = tryRefreshToken().finally(() => { refreshPromise = null; });
    }

    const refreshed = await refreshPromise;
    if (refreshed) {
      originalRequest._retried = true;
      // Update the header with the fresh token and retry
      originalRequest.headers.Authorization = `Bearer ${getAccessToken()}`;
      return retryWith(originalRequest);
    }
  }

  log.error({ status, data: error.response?.data }, 'API response error');
  return Promise.reject(error);
}

// Response interceptor: auto-refresh expired tokens, log other errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => handle401Error(error, api)
);

// Also cover the 22+ files that use the global `axios` instance directly
// (studio APIs, chats, sources, settings, etc.)
axios.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => handle401Error(error, axios)
);

/**
 * Build an authenticated URL for browser elements that can't send Authorization headers.
 *
 * Educational Note: Elements like <img>, <video>, <audio>, and <iframe> make their own
 * HTTP requests without axios interceptors. We append the JWT as a query parameter
 * so the backend auth middleware can validate it. The backend checks ?token= as a
 * fallback when no Authorization header is present.
 *
 * @param url - Absolute URL or path starting with /api/. If it's a full URL (starts with http),
 *              the token is appended directly. If it's a path, API_HOST is prepended first.
 */
export function getAuthUrl(url: string): string {
  const token = getAccessToken();
  const fullUrl = url.startsWith('http') ? url : `${API_HOST}${url}`;
  if (!token) return fullUrl;
  const separator = fullUrl.includes('?') ? '&' : '?';
  return `${fullUrl}${separator}token=${token}`;
}

export { API_BASE_URL };
