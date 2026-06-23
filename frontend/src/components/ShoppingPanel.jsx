import React, { useState } from "react";

const API = "http://localhost:8001";

const TIER_STYLES = {
  Budget:    { badge: "bg-emerald-900/50 text-emerald-300 border-emerald-700",  dot: "bg-emerald-400" },
  "Mid-Range": { badge: "bg-blue-900/50 text-blue-300 border-blue-700",        dot: "bg-blue-400" },
  Premium:   { badge: "bg-purple-900/50 text-purple-300 border-purple-700",    dot: "bg-purple-400" },
  Luxury:    { badge: "bg-amber-900/50 text-amber-300 border-amber-700",       dot: "bg-amber-400" },
};

function PriceSlider({ label, value, min, max, step = 5, onChange }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-neutral-400">
        <span>{label}</span>
        <span className="text-white font-medium">${value}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full accent-brand-500 bg-neutral-700 cursor-pointer"
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
    <div className={`relative bg-neutral-900 border rounded-2xl p-4 space-y-3 transition-all hover:border-neutral-600 ${isOutside ? "border-neutral-800 opacity-80" : "border-neutral-700"}`}>
      {isOutside && (
        <div className="absolute -top-2 -right-2 bg-amber-500 text-neutral-900 text-[10px] font-bold px-2 py-0.5 rounded-full">
          STRETCH
        </div>
      )}

      {/* Brand + tier */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-white text-sm">{s.brand}</p>
          <p className="text-xs text-neutral-500 mt-0.5">{s.item}</p>
        </div>
        <span className={`text-[10px] font-medium border px-2 py-0.5 rounded-full shrink-0 ${styles.badge}`}>
          {s.tier}
        </span>
      </div>

      {/* Price */}
      <div className="flex items-baseline gap-1.5">
        <span className="text-lg font-bold text-white">${s.est_price}</span>
        <span className="text-xs text-neutral-500">avg · {s.price_range}</span>
      </div>

      {/* Style note */}
      <p className="text-xs text-neutral-400 leading-relaxed">{s.style_note}</p>

      {/* CTA */}
      <button
        onClick={handleClick}
        className="flex items-center justify-center gap-1.5 w-full py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-sm font-medium text-neutral-200 transition-colors border border-neutral-700 hover:border-neutral-500"
      >
        Shop on {s.brand}
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
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

  const hasCaption = styleCaption && styleCaption.trim().length > 0;

  const fetchSuggestions = async () => {
    if (!hasCaption) return;
    setLoading(true);
    setResults(null);
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
      const d = await r.json();
      setResults(d);
    } catch (e) {
      alert("Shopping suggestions failed: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Price range */}
      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-serif text-lg font-semibold text-white">Your Budget</h3>
          <span className="text-sm text-brand-400 font-medium">
            ${priceMin} – ${priceMax === 500 ? "500+" : priceMax}
          </span>
        </div>

        <PriceSlider label="Minimum" value={priceMin} min={0} max={490} onChange={v => { if (v < priceMax) setPriceMin(v); }} />
        <PriceSlider label="Maximum" value={priceMax} min={10} max={500} onChange={v => { if (v > priceMin) setPriceMax(v); }} />

        <div className="flex gap-2 flex-wrap">
          {[[0,50,"Under $50"],[30,100,"$30–$100"],[50,200,"$50–$200"],[100,300,"$100–$300"],[200,500,"$200+"]].map(([mn,mx,label]) => (
            <button key={label} onClick={() => { setPriceMin(mn); setPriceMax(mx); }}
              className={`text-xs px-3 py-1 rounded-full border transition-all ${priceMin===mn && priceMax===mx ? "border-brand-500 bg-brand-600/20 text-brand-300" : "border-neutral-700 text-neutral-400 hover:border-neutral-500"}`}>
              {label}
            </button>
          ))}
        </div>

        {!hasCaption && (
          <p className="text-xs text-neutral-500 italic">
            Get an outfit recommendation first, then shop for it here.
          </p>
        )}

        <button
          onClick={fetchSuggestions}
          disabled={loading || !hasCaption}
          className={`w-full py-2.5 rounded-xl font-medium text-sm transition-all ${hasCaption ? "btn-primary" : "bg-neutral-800 text-neutral-500 cursor-not-allowed"}`}
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin">⟳</span> Finding stores…
            </span>
          ) : "🛍 Find This Look Online"}
        </button>
      </div>

      {/* Results */}
      {results && (
        <div className="space-y-4">
          {/* Tabs */}
          <div className="flex gap-1 bg-neutral-900 rounded-full p-1 border border-neutral-800">
            <button
              onClick={() => setActiveTab("within")}
              className={`flex-1 py-2 rounded-full text-sm font-medium transition-all ${activeTab === "within" ? "bg-brand-600 text-white" : "text-neutral-400 hover:text-neutral-200"}`}
            >
              In Budget
              <span className="ml-1.5 text-xs opacity-70">({results.within_budget.length})</span>
            </button>
            <button
              onClick={() => setActiveTab("outside")}
              className={`flex-1 py-2 rounded-full text-sm font-medium transition-all ${activeTab === "outside" ? "bg-amber-600 text-white" : "text-neutral-400 hover:text-neutral-200"}`}
            >
              Stretch Picks
              <span className="ml-1.5 text-xs opacity-70">({results.outside_budget.length})</span>
            </button>
          </div>

          {activeTab === "within" && (
            <>
              {results.within_budget.length === 0 ? (
                <div className="card text-center text-neutral-400 text-sm py-8">
                  No brands fall within this budget range.<br />
                  <button onClick={() => setActiveTab("outside")} className="mt-2 text-amber-400 underline text-xs">See stretch picks →</button>
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
              <p className="text-xs text-neutral-500 italic px-1">
                These are outside your <span className="text-white">${results.price_range.min}–${results.price_range.max}</span> range — shown in case you love the style enough to stretch.
              </p>
              {results.outside_budget.length === 0 ? (
                <div className="card text-center text-neutral-400 text-sm py-8">No stretch picks — all brands fit your budget! 🎉</div>
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
              <div key={tier} className="flex items-center gap-1.5 text-xs text-neutral-500">
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
