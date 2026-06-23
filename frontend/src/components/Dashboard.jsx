import React, { useState, useEffect } from "react";
import { signOut, onAuthStateChanged } from 'firebase/auth';
import { auth } from '../firebase';
import { useNavigate } from 'react-router-dom';
import FashionCard from './FashionCard';
import BodyTypeForm from './BodyTypeForm';
import WardrobeManager from './WardrobeManager';
import ShoppingPanel from './ShoppingPanel';

const API = "http://localhost:8001";

const OCCASIONS = ["casual", "work", "date night", "formal", "gym", "brunch", "party", "outdoor"];
const WEATHERS  = ["hot", "warm", "mild", "cool", "cold", "rainy", "snowy"];
const LOCATIONS = ["city", "beach", "mountains", "office", "cafe", "club", "park", "home"];
const GENDERS   = ["woman", "man", "non-binary"];

const TABS = [
  { id: "discover", label: "Discover",  icon: "✦" },
  { id: "wardrobe", label: "My Closet", icon: "👗" },
  { id: "shop",     label: "Shop",      icon: "🛍" },
];

// ── SQL helpers ───────────────────────────────────────────────────────────────

async function syncUserToSQL(firebaseUser) {
  try {
    await fetch(`${API}/users/upsert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        firebase_uid: firebaseUser.uid,
        email: firebaseUser.email,
        display_name: firebaseUser.displayName || null,
      }),
    });
  } catch (e) {
    console.warn("SQL sync failed:", e.message);
  }
}

async function saveOutfitToSQL(firebaseUser, rec, occasion, weather) {
  try {
    await fetch(`${API}/users/outfits/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        firebase_uid: firebaseUser.uid,
        image_filename: rec.image,
        caption: rec.result,
        trendiness_score: rec.trendiness_score,
        future_projection: rec.future_projection,
        occasion,
        weather,
      }),
    });
  } catch (e) {
    console.warn("Outfit save failed:", e.message);
  }
}

async function recordSwipeToSQL(firebaseUser, rec, liked, occasion) {
  try {
    await fetch(`${API}/users/swipe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        firebase_uid: firebaseUser.uid,
        image_filename: rec.image,
        caption: rec.result,
        liked,
        occasion,
      }),
    });
  } catch (e) {
    console.warn("Swipe record failed:", e.message);
  }
}

async function patchBodyType(firebaseUser, bodyType, gender) {
  try {
    await fetch(`${API}/users/${firebaseUser.uid}/profile`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        firebase_uid: firebaseUser.uid,
        email: firebaseUser.email,
        body_type: bodyType,
        gender: gender || null,
      }),
    });
  } catch (e) {
    console.warn("Profile patch failed:", e.message);
  }
}

// ── Main component ────────────────────────────────────────────────────────────

const Dashboard = () => {
  const [currentUser, setCurrentUser] = useState(null);
  const [tab, setTab] = useState("discover");

  const [bodyType, setBodyType]       = useState(null);
  const [loadingBody, setLoadingBody] = useState(false);

  const [form, setForm] = useState({
    weather: "", occasion: "", location: "", occupation: "", gender: "",
  });

  const [results, setResults]         = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loadingRec, setLoadingRec]   = useState(false);
  const [saved, setSaved]             = useState(false);

  const navigate = useNavigate();

  // Sync Firebase user → SQL on mount / auth change
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (user) => {
      if (user) {
        setCurrentUser(user);
        syncUserToSQL(user);
      } else {
        navigate("/login");
      }
    });
    return unsub;
  }, [navigate]);

  // Persist body type to SQL whenever it changes
  useEffect(() => {
    if (currentUser && bodyType) {
      patchBodyType(currentUser, bodyType, form.gender);
    }
  }, [bodyType, currentUser, form.gender]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = (field, value) => setForm(f => ({ ...f, [field]: value }));

  const getRecommendation = async () => {
    const missing = Object.entries(form).filter(([, v]) => !v.trim());
    if (missing.length) {
      alert(`Please fill in: ${missing.map(([k]) => k).join(", ")}`);
      return;
    }
    setLoadingRec(true);
    setSaved(false);
    try {
      const prompt = `A ${form.gender} with a ${bodyType || "balanced"} body shape wearing a stylish outfit for a ${form.occasion} in ${form.weather} weather at the ${form.location}. They work as a ${form.occupation}.`;
      const res = await fetch(`${API}/stylegenie/trend_vector`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          gender: form.gender,
          body_type: bodyType,
          weather: form.weather,
          occasion: form.occasion,
        }),
      });
      const data = await res.json();
      setResults(data.results || []);
      setCurrentIndex(0);
    } catch (e) {
      alert("Request failed: " + e.message);
    } finally {
      setLoadingRec(false);
    }
  };

  const handleSwipe = async (dir) => {
    const rec = results[currentIndex];
    if (!rec) return;

    if (dir === "up") {
      // Save to SQL
      if (currentUser) await saveOutfitToSQL(currentUser, rec, form.occasion, form.weather);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }

    if (dir === "right") {
      if (currentUser) await recordSwipeToSQL(currentUser, rec, true, form.occasion);
      if (currentIndex < results.length - 1) setCurrentIndex(i => i + 1);
    }

    if (dir === "left") {
      if (currentUser) await recordSwipeToSQL(currentUser, rec, false, form.occasion);
      if (currentIndex < results.length - 1) setCurrentIndex(i => i + 1);
    }
  };

  const logout = () =>
    signOut(auth).then(() => navigate("/login")).catch(console.error);

  return (
    <div className="min-h-screen bg-neutral-950">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-20 bg-neutral-950/80 backdrop-blur border-b border-neutral-800 px-4 py-3 flex items-center justify-between">
        <h1 className="font-serif text-xl font-bold text-white">
          agent<span className="text-brand-500">weave</span>
        </h1>
        <div className="flex items-center gap-2">
          <div className="flex bg-neutral-900 rounded-full p-1 gap-1">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
                  tab === t.id
                    ? "bg-brand-600 text-white shadow"
                    : "text-neutral-400 hover:text-neutral-200"
                }`}>
                {t.icon} {t.label}
              </button>
            ))}
          </div>
          <button onClick={logout} className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors px-2">
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">

        {/* ── DISCOVER TAB ───────────────────────────────────────────────── */}
        {tab === "discover" && (
          <div className="space-y-6">

            {/* Body type step */}
            {!bodyType ? (
              <div className="card">
                <BodyTypeForm setBodyType={setBodyType} setLoading={setLoadingBody} />
                {loadingBody && (
                  <div className="mt-4 flex items-center gap-2 text-sm text-neutral-400">
                    <span className="animate-spin">⟳</span> Analysing body shape…
                  </div>
                )}
              </div>
            ) : (
              <div className="card flex items-center justify-between">
                <div>
                  <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Your body type</p>
                  <p className="text-lg font-semibold text-brand-400 capitalize">{bodyType}</p>
                </div>
                <button onClick={() => { setBodyType(null); setResults([]); }}
                  className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">
                  Re-analyse
                </button>
              </div>
            )}

            {/* Preference form */}
            {bodyType && (
              <div className="card space-y-4">
                <h2 className="font-serif text-lg font-semibold text-white">Tell us about your day</h2>

                {/* Gender */}
                <div>
                  <label className="text-xs text-neutral-400 uppercase tracking-wider mb-2 block">Gender expression</label>
                  <div className="flex flex-wrap gap-2">
                    {GENDERS.map(g => (
                      <button key={g} onClick={() => handleChange("gender", g)}
                        className={`px-4 py-1.5 rounded-full text-sm border transition-all ${form.gender === g ? "border-brand-500 bg-brand-600/20 text-brand-300" : "border-neutral-700 text-neutral-400 hover:border-neutral-500"}`}>
                        {g}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Weather */}
                <div>
                  <label className="text-xs text-neutral-400 uppercase tracking-wider mb-2 block">Weather</label>
                  <div className="flex flex-wrap gap-2">
                    {WEATHERS.map(w => (
                      <button key={w} onClick={() => handleChange("weather", w)}
                        className={`px-3 py-1 rounded-full text-sm border transition-all ${form.weather === w ? "border-brand-500 bg-brand-600/20 text-brand-300" : "border-neutral-700 text-neutral-400 hover:border-neutral-500"}`}>
                        {w}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Occasion */}
                <div>
                  <label className="text-xs text-neutral-400 uppercase tracking-wider mb-2 block">Occasion</label>
                  <div className="flex flex-wrap gap-2">
                    {OCCASIONS.map(o => (
                      <button key={o} onClick={() => handleChange("occasion", o)}
                        className={`px-3 py-1 rounded-full text-sm border transition-all ${form.occasion === o ? "border-brand-500 bg-brand-600/20 text-brand-300" : "border-neutral-700 text-neutral-400 hover:border-neutral-500"}`}>
                        {o}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Location */}
                <div>
                  <label className="text-xs text-neutral-400 uppercase tracking-wider mb-2 block">Location</label>
                  <div className="flex flex-wrap gap-2">
                    {LOCATIONS.map(l => (
                      <button key={l} onClick={() => handleChange("location", l)}
                        className={`px-3 py-1 rounded-full text-sm border transition-all ${form.location === l ? "border-brand-500 bg-brand-600/20 text-brand-300" : "border-neutral-700 text-neutral-400 hover:border-neutral-500"}`}>
                        {l}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Occupation */}
                <div>
                  <label className="text-xs text-neutral-400 uppercase tracking-wider mb-2 block">Occupation</label>
                  <input placeholder="e.g. designer, student, teacher…"
                    value={form.occupation}
                    onChange={e => handleChange("occupation", e.target.value)}
                    className="input-field" />
                </div>

                <button onClick={getRecommendation} disabled={loadingRec}
                  className="btn-primary w-full text-base py-3">
                  {loadingRec ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="animate-spin">⟳</span> Finding your look…
                    </span>
                  ) : "✦ Get My Outfit"}
                </button>
              </div>
            )}

            {/* Results */}
            {results.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-neutral-400">
                    Look <span className="text-white font-medium">{currentIndex + 1}</span> of {results.length}
                  </p>
                  {saved && <span className="text-xs text-brand-400 font-medium animate-pulse">✦ Saved!</span>}
                </div>

                <FashionCard
                  image={results[currentIndex].image}
                  result={results[currentIndex].result}
                  trendiness_score={results[currentIndex].trendiness_score}
                  future_projection={results[currentIndex].future_projection}
                  onSwipe={handleSwipe}
                />

                <div className="flex justify-center gap-1.5 pt-2">
                  {results.map((_, i) => (
                    <button key={i} onClick={() => setCurrentIndex(i)}
                      className={`h-1.5 rounded-full transition-all ${i === currentIndex ? "bg-brand-500 w-4" : "bg-neutral-700 w-1.5"}`} />
                  ))}
                </div>

                <p className="text-center text-xs text-neutral-600">Swipe left/right to browse · swipe up to save</p>

                <button onClick={() => setTab("shop")}
                  className="w-full py-2.5 rounded-xl border border-neutral-700 hover:border-brand-500 text-sm font-medium text-neutral-300 hover:text-white transition-all flex items-center justify-center gap-2">
                  🛍 Shop this look
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── WARDROBE TAB ───────────────────────────────────────────────── */}
        {tab === "wardrobe" && (
          <WardrobeManager
            occasion={form.occasion}
            weather={form.weather}
            bodyType={bodyType}
            gender={form.gender}
          />
        )}

        {/* ── SHOP TAB ───────────────────────────────────────────────────── */}
        {tab === "shop" && (
          <ShoppingPanel
            styleCaption={results[currentIndex]?.result || ""}
            occasion={form.occasion}
            bodyType={bodyType}
            gender={form.gender}
            firebaseUid={currentUser?.uid}
          />
        )}

      </main>
    </div>
  );
};

export default Dashboard;
