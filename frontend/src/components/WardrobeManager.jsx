import React, { useState, useEffect, useRef } from 'react';
import { auth } from '../firebase';

const API = process.env.REACT_APP_API_URL || 'http://localhost:8001';
const CATEGORIES = ['top', 'bottom', 'dress', 'outerwear', 'shoes', 'accessory', 'other'];

export default function WardrobeManager({ occasion, weather, bodyType, gender }) {
  const [items, setItems] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState(null);
  const [preview, setPreview] = useState(null);
  const [form, setForm] = useState({ category: 'top', color: '', description: '' });
  const fileRef = useRef();

  const uid = auth.currentUser?.uid;

  const fetchItems = async () => {
    if (!uid) return;
    try {
      const r = await fetch(`${API}/wardrobe/items?firebase_uid=${uid}`);
      const d = await r.json();
      setItems(d.items || []);
    } catch {}
  };

  useEffect(() => { fetchItems(); }, [uid]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFile = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setPreview({ file: f, url: URL.createObjectURL(f) });
  };

  const handleUpload = async () => {
    if (!preview?.file) return;
    if (!uid) { alert('Please sign in first.'); return; }
    setUploading(true);
    const fd = new FormData();
    fd.append('file', preview.file);
    fd.append('firebase_uid', uid);
    fd.append('category', form.category);
    fd.append('color', form.color);
    fd.append('description', form.description);
    try {
      const r = await fetch(`${API}/wardrobe/upload`, { method: 'POST', body: fd });
      if (r.ok) {
        setPreview(null);
        setForm({ category: 'top', color: '', description: '' });
        if (fileRef.current) fileRef.current.value = '';
        await fetchItems();
      } else {
        const e = await r.json();
        alert(e.detail || 'Upload failed');
      }
    } catch (e) {
      alert('Upload failed: ' + e.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (item_uuid) => {
    if (!uid) return;
    await fetch(`${API}/wardrobe/items/${item_uuid}?firebase_uid=${uid}`, { method: 'DELETE' });
    await fetchItems();
  };

  const handleSuggest = async () => {
    if (items.length === 0) { alert('Add some clothes first!'); return; }
    if (!uid) { alert('Please sign in first.'); return; }
    setSuggesting(true);
    setSuggestion(null);
    try {
      const r = await fetch(`${API}/wardrobe/suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          firebase_uid: uid,
          occasion: occasion || 'casual',
          weather: weather || 'mild',
          gender: gender || '',
          body_type: bodyType || '',
        }),
      });
      const d = await r.json();
      setSuggestion(d);
    } catch (e) {
      alert('Suggestion failed: ' + e.message);
    } finally {
      setSuggesting(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Upload panel */}
      <div className="card space-y-4">
        <h2 className="font-serif text-xl font-semibold text-white">Add to Wardrobe</h2>

        <input ref={fileRef} type="file" accept="image/*" onChange={handleFile}
          className="hidden" id="wardrobe-file" />
        <label htmlFor="wardrobe-file"
          className="flex flex-col items-center justify-center border-2 border-dashed border-neutral-700 hover:border-brand-500 rounded-xl py-8 cursor-pointer transition-colors">
          {preview ? (
            <img src={preview.url} alt="preview" className="h-40 object-contain rounded-lg" />
          ) : (
            <>
              <span className="text-3xl mb-2">👕</span>
              <span className="text-sm text-neutral-400">Click to upload a clothing photo</span>
            </>
          )}
        </label>

        {preview && (
          <>
            <div className="grid grid-cols-3 gap-3">
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} className="input-field">
                {CATEGORIES.map(c => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
              </select>
              <input placeholder="Color (e.g. navy)" value={form.color}
                onChange={e => setForm(f => ({ ...f, color: e.target.value }))} className="input-field" />
              <input placeholder="Description" value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))} className="input-field" />
            </div>
            <button onClick={handleUpload} disabled={uploading} className="btn-primary w-full">
              {uploading ? 'Uploading…' : 'Add Item'}
            </button>
          </>
        )}
      </div>

      {/* Wardrobe grid */}
      {items.length > 0 && (
        <div>
          <h2 className="font-serif text-xl font-semibold text-white mb-4">
            My Closet <span className="text-sm font-sans font-normal text-neutral-400">({items.length} items)</span>
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {items.map(item => (
              <div key={item.item_uuid} className="relative group bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
                <img src={`${API}/wardrobe-images/${item.filename}`}
                  alt={item.description || item.category}
                  className="w-full aspect-square object-cover" />
                <div className="p-2">
                  <p className="text-xs font-medium text-neutral-300 capitalize">{item.category}</p>
                  {item.color && <p className="text-xs text-neutral-500">{item.color}</p>}
                </div>
                <button onClick={() => handleDelete(item.item_uuid)}
                  className="absolute top-2 right-2 w-6 h-6 bg-red-900/80 hover:bg-red-700 text-white rounded-full text-xs opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Outfit suggestion */}
      {items.length > 0 && (
        <div className="card space-y-4">
          <h2 className="font-serif text-xl font-semibold text-white">What Should I Wear?</h2>
          <button onClick={handleSuggest} disabled={suggesting} className="btn-primary w-full">
            {suggesting ? 'Thinking…' : '✨ Suggest Outfit from My Closet'}
          </button>

          {suggestion && (
            <div className="space-y-4 pt-2 border-t border-neutral-800">
              <p className="text-sm text-neutral-300 leading-relaxed">{suggestion.suggestion}</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {suggestion.outfit.map(item => (
                  <div key={item.item_uuid} className="bg-neutral-800 rounded-xl overflow-hidden">
                    <img src={`${API}/wardrobe-images/${item.filename}`}
                      alt={item.description || item.category}
                      className="w-full aspect-square object-cover" />
                    <p className="text-xs text-center text-neutral-400 py-1 capitalize">{item.category}</p>
                  </div>
                ))}
              </div>
              {suggestion.trend_inspiration?.image && (
                <div>
                  <p className="text-xs text-neutral-500 mb-2">Trend inspiration from Pinterest:</p>
                  <div className="flex gap-3 items-start">
                    <img src={`${API}/images/${suggestion.trend_inspiration.image}`}
                      alt="trend" className="w-24 h-24 object-cover rounded-lg" />
                    <p className="text-xs text-neutral-400 flex-1 leading-relaxed">
                      {suggestion.trend_inspiration.caption}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
