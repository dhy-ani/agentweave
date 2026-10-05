import React, { useState, useEffect, useRef, useCallback } from "react";
import { auth } from "../firebase";
import { HangerIcon, SparkleIcon, SpinnerIcon, XIcon } from "./icons";
import { API, imageUrl, wardrobeImageUrl } from "../config";
import { resizeImage } from "../lib/resizeImage";

const CATEGORIES = ["top", "bottom", "dress", "outerwear", "shoes", "accessory", "other"];
const EMPTY = { category: "top", color: "", description: "" };

export default function WardrobeManager({ occasion, weather, bodyType, gender }) {
  const [items, setItems] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState(null);
  const [preview, setPreview] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const fileRef = useRef();

  const uid = auth.currentUser?.uid;

  const fetchItems = useCallback(async () => {
    if (!uid) return;
    try {
      const r = await fetch(`${API}/wardrobe/items?firebase_uid=${encodeURIComponent(uid)}`);
      const d = await r.json();
      setItems(d.items || []);
    } catch {
      setError("Could not load your closet.");
    }
  }, [uid]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const handleFile = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setError("");
    setPreview({ file: f, url: URL.createObjectURL(f) });
  };

  const handleUpload = async () => {
    if (!preview?.file || !uid) return;
    setUploading(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", await resizeImage(preview.file));
      fd.append("firebase_uid", uid);
      fd.append("category", form.category);
      fd.append("color", form.color);
      fd.append("description", form.description);
      const r = await fetch(`${API}/wardrobe/upload`, { method: "POST", body: fd });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || `Upload failed (HTTP ${r.status}).`);
      }
      setPreview(null);
      setForm(EMPTY);
      if (fileRef.current) fileRef.current.value = "";
      await fetchItems();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (itemUuid) => {
    if (!uid) return;
    try {
      await fetch(`${API}/wardrobe/items/${itemUuid}?firebase_uid=${encodeURIComponent(uid)}`, { method: "DELETE" });
    } finally {
      await fetchItems();
    }
  };

  const handleSuggest = async () => {
    if (!uid || items.length === 0) return;
    setSuggesting(true);
    setSuggestion(null);
    setError("");
    try {
      const r = await fetch(`${API}/wardrobe/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          firebase_uid: uid,
          occasion: occasion || "casual",
          weather: weather || "mild",
          gender: gender || "",
          body_type: bodyType || "",
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSuggestion(await r.json());
    } catch {
      setError("Could not build a suggestion right now.");
    } finally {
      setSuggesting(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-serif text-2xl font-semibold text-ink">My closet</h2>
        <p className="text-xs text-muted mt-1">{items.length} {items.length === 1 ? "item" : "items"}</p>
      </div>

      {error && <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}

      <section className="card space-y-4">
        <h3 className="text-sm font-semibold text-ink">Add a clothing photo</h3>
        <input ref={fileRef} type="file" accept="image/*" onChange={handleFile} className="hidden" id="wardrobe-file" />
        <label htmlFor="wardrobe-file"
          className="flex flex-col items-center justify-center border-2 border-dashed border-line-strong hover:border-brand-500 rounded-xl py-8 cursor-pointer transition-colors">
          {preview ? (
            <img src={preview.url} alt="Selected clothing item" className="h-40 object-contain rounded-lg" />
          ) : (
            <>
              <HangerIcon className="w-8 h-8 mb-2 text-muted" />
              <span className="text-sm text-muted">Click to upload a clothing photo</span>
            </>
          )}
        </label>

        {preview && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <select aria-label="Category" value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} className="input-field">
                {CATEGORIES.map(c => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
              </select>
              <input aria-label="Color" placeholder="Color (e.g. navy)" value={form.color}
                onChange={e => setForm(f => ({ ...f, color: e.target.value }))} className="input-field" />
              <input aria-label="Description" placeholder="Description" value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))} className="input-field" />
            </div>
            <button onClick={handleUpload} disabled={uploading} className="btn-primary w-full">
              {uploading ? "Uploading..." : "Add item"}
            </button>
          </>
        )}
      </section>

      {items.length > 0 && (
        <ul className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {items.map(item => (
            <li key={item.item_uuid} className="relative group bg-surface border border-line rounded-xl overflow-hidden">
              <img src={wardrobeImageUrl(item)} alt={item.description || item.category} className="w-full aspect-square object-cover" loading="lazy" />
              <div className="p-2">
                <p className="text-xs font-medium text-ink-soft capitalize">{item.category}</p>
                {item.color && <p className="text-xs text-muted">{item.color}</p>}
              </div>
              <button onClick={() => handleDelete(item.item_uuid)} aria-label={`Remove ${item.category}`}
                className="absolute top-2 right-2 w-7 h-7 bg-surface/90 border border-line-strong hover:border-red-500 text-ink rounded-full opacity-100 md:opacity-0 md:group-hover:opacity-100 focus:opacity-100 transition-opacity flex items-center justify-center">
                <XIcon className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {items.length > 0 && (
        <section className="card space-y-4">
          <h3 className="font-serif text-xl font-semibold text-ink">What should I wear?</h3>
          <button onClick={handleSuggest} disabled={suggesting} className="btn-primary w-full flex items-center justify-center gap-2">
            {suggesting ? <><SpinnerIcon className="w-4 h-4" /> Thinking...</> : <><SparkleIcon className="w-4 h-4" /> Suggest an outfit from my closet</>}
          </button>

          {suggestion && (
            <div className="space-y-4 pt-2 border-t border-line">
              <p className="text-sm text-ink-soft leading-relaxed">{suggestion.suggestion}</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {(suggestion.outfit || []).map(item => (
                  <div key={item.item_uuid} className="bg-surface-2 rounded-xl overflow-hidden">
                    <img src={wardrobeImageUrl(item)} alt={item.description || item.category} className="w-full aspect-square object-cover" />
                    <p className="text-xs text-center text-muted py-1 capitalize">{item.category}</p>
                  </div>
                ))}
              </div>
              {suggestion.trend_inspiration?.image && (
                <div>
                  <p className="text-xs text-muted mb-2">Closest look in the curated collection:</p>
                  <div className="flex gap-3 items-start">
                    <img src={imageUrl(suggestion.trend_inspiration.image)} alt="Inspiration" className="w-24 h-24 object-cover rounded-lg" />
                    <p className="text-xs text-muted flex-1 leading-relaxed">{suggestion.trend_inspiration.caption}</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
