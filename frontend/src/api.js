export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const STORAGE_KEY = "animeszn_access_key";

export function getStoredKey() {
  return localStorage.getItem(STORAGE_KEY) || "";
}

export function setStoredKey(key) {
  localStorage.setItem(STORAGE_KEY, key);
}

export function clearStoredKey() {
  localStorage.removeItem(STORAGE_KEY);
}

export class UnauthorizedError extends Error {
  constructor() {
    super("Unauthorized");
    this.name = "UnauthorizedError";
  }
}

// Wraps fetch with the stored access key attached, and clears it on a 401 so the app's
// access gate reappears cleanly instead of silently failing every subsequent request.
export async function apiFetch(path, options = {}) {
  const headers = { ...options.headers, "X-AnimeSZN-Key": getStoredKey() };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    clearStoredKey();
    throw new UnauthorizedError();
  }
  return res;
}
