export const API = (process.env.REACT_APP_API_URL || "http://localhost:8001").replace(/\/+$/, "");

export const imageUrl = (filename) => `${API}/images/${encodeURIComponent(filename)}`;

export const wardrobeImageUrl = (item) =>
  item.image_url || `${API}/wardrobe-images/${encodeURIComponent(item.filename)}`;
