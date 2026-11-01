export const API = (process.env.REACT_APP_API_URL || "http://localhost:8001").replace(/\/+$/, "");

export const imageUrl = (filename) => `${API}/images/${encodeURIComponent(filename)}`;

// Closet photos come back from the API either as full URLs (Vercel Blob) or as
// API-relative paths (local storage).
export const closetImageUrl = (url) => (/^https?:\/\//.test(url) ? url : `${API}${url}`);
