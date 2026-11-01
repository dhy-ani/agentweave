import { API } from "../config";
import { auth } from "../firebase";

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (HTTP ${status}).`);
    this.status = status;
  }
}

// Calls the ML API. Endpoints that act on the user's own files need the
// Firebase ID token; the backend verifies it and takes the uid from it.
export async function apiRequest(path, { method = "GET", json, body, authenticated = false } = {}) {
  const headers = {};
  if (json !== undefined) headers["Content-Type"] = "application/json";
  if (authenticated) {
    const user = auth.currentUser;
    if (!user) throw new ApiError(401, "Please sign in again.");
    headers.Authorization = `Bearer ${await user.getIdToken()}`;
  }
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: json !== undefined ? JSON.stringify(json) : body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : undefined;
    throw new ApiError(res.status, detail);
  }
  return data;
}
