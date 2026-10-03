import React, { useState } from "react";
import { BagIcon, SpinnerIcon, SparkleIcon } from "./icons";
import { API } from "../config";
import { PRESETS, nextMin, nextMax, formatBudget, isActivePreset } from "../lib/budget";

const TIER_STYLES = {
  Budget:      { badge: "bg-sage-100 text-sage-700 border-sage-300", dot: "bg-sage-400" },
  "Mid-Range": { badge: "bg-sky-100 text-sky-600 border-sky-300",    dot: "bg-sky-400" },
  Premium:     { badge: "bg-brand-100 text-brand-700 border-brand-200", dot: "bg-brand-400" },
  Luxury:      { badge: "bg-lagoon text-canvas border-lagoon",      dot: "bg-lagoon" },
};

function PriceSlider({ label, value, min, max, step = 5, onChange }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted">
        <span>{label}</span>
        <span className="text-ink font-medium">${value}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full accent-brand-500 bg-line cursor-pointer"
      />
    </div>
  );
}

function BrandCard({ s, isOutside, firebaseUid, occasion }) {
  const styles = TIER_STYLES[s.tier] || TIER_STYLES.Budget;

  const handleClick = async () => {
    if (firebaseUid) {
      try {
        await fetch(`${API}/users/shopping/click`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            firebase_uid: firebaseUid,
            brand: s.brand,
            item: s.item,
            tier: s.tier,
            est_price: s.est_price,
            occasion: occasion || null,
          }),
        });
      } catch {}
    }
    window.open(s.search_url, "_blank", "noopener,noreferrer");
  };

  return (
    <div className={`relative bg-surface border rounded-2xl p-4 space-y-3 transition-all hover:border-muted ${isOutside ? "border-line opacity-80" : "border-line-strong"}`}>
      {isOutside && (
        <div className="absolute -top-2 -right-2 bg-sage-400 text-ink text-[10px] font-bold px-2 py-0.5 rounded-full">
          STRETCH
        </div>
      )}

      {/* Brand + tier */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-ink text-sm">{s.brand}</p>
          <p className="text-xs text-muted mt-0.5">{s.item}</p>
        </div>
        <span className={`text-[10px] font-medium border px-2 py-0.5 rounded-full shrink-0 ${styles.badge}`}>
          {s.tier}
        </span>
      </div>

      {/* Price */}
      <div className="flex items-baseline gap-1.5">
        <span className="text-lg font-bold text-ink">${s.est_price}</span>
        <span className="text-xs text-muted">avg · {s.price_range}</span>
      </div>

      {/* Style note */}
      <p className="text-xs text-muted leading-relaxed">{s.style_note}</p>

      {/* CTA */}
      <button
        onClick={handleClick}
        className="flex items-center justify-center gap-1.5 w-full py-2 rounded-xl bg-surface-2 hover:bg-line text-sm font-medium text-ink transition-colors border border-line-strong hover:border-muted"
      >
        <span aria-hidden="true">{"\uD83D\uDED2"}</span> Shop on {s.brand}
      </button>
    </div>
  );
}

export default function ShoppingPanel({ styleCaption, occasion, bodyType, gender, firebaseUid }) {
  const [priceMin, setPriceMin] = useState(0);
  const [priceMax, setPriceMax] = useState(150);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("within");
  const [error, setError] = useState("");

  const hasCaption = styleCaption && styleCaption.trim().length > 0;

  const fetchSuggestions = async () => {
    if (!hasCaption) return;
    setLoading(true);
    setResults(null);
    setError("");
    try {
      const r = await fetch(`${API}/shopping/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          style_caption: styleCaption,
          occasion: occasion || "casual",
          body_type: bodyType || "",
          gender: gender || "",
          price_min: priceMin,
          price_max: priceMax,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResults(await r.json());
    } catch (e) {
      setError("Could not load store suggestions. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <h2 className="font-serif text-2xl font-semibold text-ink">Shop this look</h2>
      {error && <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}
      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-serif text-lg font-semibold text-ink">Your Budget</h3>
          <span className="text-sm text-brand-600 font-medium">
            {formatBudget(priceMin, priceMax)}
          </span>
        </div>

        <PriceSlider label="Minimum" value={priceMin} min={0} max={490} onChange={v => { const n = nextMin(v, priceMax); if (n !== null) setPriceMin(n); }} />
        <PriceSlider label="Maximum" value={priceMax} min={10} max={500} onChange={v => { const n = nextMax(v, priceMin); if (n !== null) setPriceMax(n); }} />

        <div className="flex gap-2 flex-wrap">
          {PRESETS.map(({ min: mn, max: mx, label }) => (
            <button key={label} onClick={() => { setPriceMin(mn); setPriceMax(mx); }}
              className={`text-xs px-3 py-1 rounded-full border transition-all ${isActivePreset({ min: mn, max: mx }, priceMin, priceMax) ? "border-brand-500 bg-brand-100 text-brand-600" : "border-line-strong text-muted hover:border-muted"}`}>
              {label}
            </button>
          ))}
        </div>

        {!hasCaption && (
          <p className="text-xs text-muted italic">
            Get an outfit recommendation first, then shop for it here.
          </p>
        )}

        <button
          onClick={fetchSuggestions}
          disabled={loading || !hasCaption}
          className={`w-full py-2.5 rounded-xl font-medium text-sm transition-all ${hasCaption ? "btn-primary" : "bg-surface-2 text-muted cursor-not-allowed"}`}
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <SpinnerIcon className="w-4 h-4" /> Finding stores…
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <BagIcon className="w-4 h-4" /> Find This Look Online
            </span>
          )}
        </button>
      </div>

      {/* Results */}
      {results && (
        <div className="space-y-4">
          {/* Tabs */}
          <div className="flex gap-1 bg-surface rounded-full p-1 border border-line">
            <button
              onClick={() => setActiveTab("within")}
              className={`flex-1 py-2 rounded-full text-sm font-medium transition-all ${activeTab === "within" ? "bg-brand-600 text-canvas" : "text-muted hover:text-ink"}`}
            >
              In Budget
              <span className="ml-1.5 text-xs opacity-70">({results.within_budget.length})</span>
            </button>
            <button
              onClick={() => setActiveTab("outside")}
              className={`flex-1 py-2 rounded-full text-sm font-medium transition-all ${activeTab === "outside" ? "bg-sage-600 text-canvas" : "text-muted hover:text-ink"}`}
            >
              Stretch Picks
              <span className="ml-1.5 text-xs opacity-70">({results.outside_budget.length})</span>
            </button>
          </div>

          {activeTab === "within" && (
            <>
              {results.within_budget.length === 0 ? (
                <div className="card text-center text-muted text-sm py-8">
                  No brands fall within this budget range.<br />
                  <button onClick={() => setActiveTab("outside")} className="mt-2 text-sage-700 underline text-xs">See stretch picks</button>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {results.within_budget.map(s => <BrandCard key={s.brand} s={s} isOutside={false} firebaseUid={firebaseUid} occasion={occasion} />)}
                </div>
              )}
            </>
          )}

          {activeTab === "outside" && (
            <>
              <p className="text-xs text-muted italic px-1">
                These are outside your <span className="text-ink">${results.price_range.min}–${results.price_range.max}</span> range — shown in case you love the style enough to stretch.
              </p>
              {results.outside_budget.length === 0 ? (
                <div className="card text-center text-muted text-sm py-8 flex items-center justify-center gap-2">
                  <SparkleIcon className="w-4 h-4 text-sage-600" /> No stretch picks — all brands fit your budget!
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {results.outside_budget.map(s => <BrandCard key={s.brand} s={s} isOutside={true} firebaseUid={firebaseUid} occasion={occasion} />)}
                </div>
              )}
            </>
          )}

          {/* Legend */}
          <div className="flex flex-wrap gap-3 px-1">
            {Object.entries(TIER_STYLES).map(([tier, style]) => (
              <div key={tier} className="flex items-center gap-1.5 text-xs text-muted">
                <span className={`w-2 h-2 rounded-full ${style.dot}`} />
                {tier}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
