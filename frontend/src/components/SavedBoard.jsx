import React, { useEffect, useState } from "react";
import { imageUrl } from "../config";
import { subscribeSavedLooks, deleteLook } from "../data/userData";
import { SparkleIcon, SpinnerIcon, XIcon } from "./icons";

export default function SavedBoard({ firebaseUid, onDiscover }) {
  const [looks, setLooks] = useState([]);
  const [loading, setLoading] = useState(Boolean(firebaseUid));
  const [error, setError] = useState("");

  useEffect(() => {
    if (!firebaseUid) return undefined;
    setLoading(true);
    return subscribeSavedLooks(
      firebaseUid,
      (items) => {
        setLooks(items);
        setLoading(false);
      },
      () => {
        setError("Could not load your saved looks. Try again in a moment.");
        setLoading(false);
      },
    );
  }, [firebaseUid]);

  const remove = async (id) => {
    setError("");
    try {
      await deleteLook(firebaseUid, id);
    } catch {
      setError("Could not remove that look.");
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-serif text-2xl font-semibold text-ink">Saved looks</h2>
        <p className="text-xs text-muted mt-1">{loading ? "Loading..." : `${looks.length} ${looks.length === 1 ? "look" : "looks"}`}</p>
      </div>

      {error && <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}

      {loading && (
        <div className="flex justify-center py-12 text-muted"><SpinnerIcon className="w-6 h-6" /></div>
      )}

      {!loading && looks.length === 0 && !error && (
        <div className="card text-center py-10 space-y-3">
          <SparkleIcon className="w-6 h-6 mx-auto text-brand-400" />
          <p className="text-sm text-ink-soft">No saved looks yet.</p>
          <p className="text-xs text-muted">Swipe a card up, or tap the sparkle button, to save it here.</p>
          {onDiscover && <button onClick={onDiscover} className="btn-ghost text-sm mt-2">Find looks</button>}
        </div>
      )}

      {!loading && looks.length > 0 && (
        <ul className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {looks.map(o => (
            <li key={o.id} className="relative bg-surface border border-line rounded-2xl overflow-hidden">
              <img src={imageUrl(o.image)} alt={o.caption || "Saved look"} className="w-full aspect-[4/5] object-cover" loading="lazy" />
              <div className="p-2.5">
                <p className="text-xs text-ink line-clamp-2">{o.caption}</p>
                {(o.occasion || o.weather) && (
                  <p className="text-[11px] text-muted mt-1 capitalize">{[o.occasion, o.weather].filter(Boolean).join(" · ")}</p>
                )}
              </div>
              <button onClick={() => remove(o.id)} aria-label="Remove saved look"
                className="absolute top-2 right-2 w-7 h-7 rounded-full bg-surface/90 border border-line-strong text-ink-soft hover:text-ink flex items-center justify-center">
                <XIcon className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
