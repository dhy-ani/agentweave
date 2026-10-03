import React, { useState, useEffect } from "react";
import { signOut, onAuthStateChanged } from "firebase/auth";
import { auth } from "../firebase";
import { useNavigate } from "react-router-dom";
import FashionCard from "./FashionCard";
import BodyTypeForm from "./BodyTypeForm";
import WardrobeManager from "./WardrobeManager";
import ShoppingPanel from "./ShoppingPanel";
import SavedBoard from "./SavedBoard";
import DoodleAccents from "./DoodleAccents";
import { SparkleIcon, ClosetIcon, BagIcon, SpinnerIcon, ProfileIcon, HeartIcon } from "./icons";
import { API } from "../config";
import {
  OCCASIONS, WEATHERS, LOCATIONS, GENDERS, EMPTY_FORM,
  missingFields, buildRecommendationRequest, nextIndex, isLastCard,
} from "../lib/recommendation";

const TABS = [
  { id: "discover", label: "Discover", Icon: SparkleIcon },
  { id: "saved", label: "Saved", Icon: HeartIcon },
  { id: "wardrobe", label: "Closet", Icon: ClosetIcon },
  { id: "shop", label: "Shop", Icon: BagIcon },
];

async function postJSON(path, body, method = "POST") {
  try {
    await fetch(`${API}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    // Stryker disable next-line all: best-effort analytics call; failures are only logged
    console.warn(`${path} failed:`, e.message);
  }
}

function ChipGroup({ label, options, value, onChange }) {
  return (
    <fieldset>
      <legend className="text-xs text-muted uppercase tracking-wider mb-2">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map(o => (
          <button key={o} type="button" onClick={() => onChange(o)} aria-pressed={value === o}
            className={`px-3.5 py-1.5 rounded-full text-sm border transition-all ${
              value === o
                ? "border-brand-500 bg-brand-100 text-brand-700"
                : "border-line-strong text-muted hover:border-muted"
            }`}>
            {o}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

const Dashboard = () => {
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [tab, setTab] = useState("discover");

  const [bodyType, setBodyType] = useState(null);
  const [loadingBody, setLoadingBody] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editing, setEditing] = useState(true);

  const [results, setResults] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loadingRec, setLoadingRec] = useState(false);
  const [formError, setFormError] = useState("");
  const [saved, setSaved] = useState(false);
  const [hasInteracted, setHasInteracted] = useState(false);
  const [deckDone, setDeckDone] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);

  const navigate = useNavigate();

  // authLoading prevents a redirect on the first null emission before Firebase rehydrates.
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (user) => {
      setAuthLoading(false);
      if (user) {
        setCurrentUser(user);
        postJSON("/users/upsert", {
          firebase_uid: user.uid,
          email: user.email,
          display_name: user.displayName || null,
        });
      } else {
        navigate("/login");
      }
    });
    return unsub;
  }, [navigate]);

  useEffect(() => {
    if (currentUser && bodyType) {
      postJSON(`/users/${currentUser.uid}/profile`, {
        firebase_uid: currentUser.uid,
        email: currentUser.email,
        body_type: bodyType,
        gender: form.gender || null,
      }, "PATCH");
    }
  }, [bodyType, currentUser, form.gender]);

  const handleChange = (field, value) => setForm(f => ({ ...f, [field]: value }));

  const getRecommendation = async () => {
    const missing = missingFields(form);
    if (missing.length) {
      setFormError(`Please choose: ${missing.join(", ")}.`);
      return;
    }
    setFormError("");
    setLoadingRec(true);
    setSaved(false);
    setHasInteracted(false);
    setDeckDone(false);
    try {
      const res = await fetch(`${API}/stylegenie/trend_vector`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildRecommendationRequest(form, bodyType)),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResults(data.results || []);
      setCurrentIndex(0);
      setEditing(false);
    } catch (e) {
      setFormError("We couldn't reach the stylist service. Please try again.");
    } finally {
      setLoadingRec(false);
    }
  };

  const handleSwipe = async (dir) => {
    const rec = results[currentIndex];
    if (!rec) return;
    setHasInteracted(true);
    const uid = currentUser?.uid;

    if (dir === "up") {
      if (uid) {
        await postJSON("/users/outfits/save", {
          firebase_uid: uid,
          image_filename: rec.image,
          caption: rec.result,
          trendiness_score: rec.match_score ?? rec.trendiness_score,
          future_projection: rec.future_projection,
          occasion: form.occasion,
          weather: form.weather,
        });
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } else if (uid) {
      await postJSON("/users/swipe", {
        firebase_uid: uid,
        image_filename: rec.image,
        caption: rec.result,
        liked: dir === "right",
        occasion: form.occasion,
      });
    }
    if (dir !== "up" && isLastCard(currentIndex, results.length)) setDeckDone(true);
    setCurrentIndex(i => nextIndex(dir, i, results.length));
  };

  const logout = () => signOut(auth).then(() => navigate("/login")).catch(console.error);

  if (authLoading) return <div className="min-h-screen bg-canvas" />;

  const current = results[currentIndex];
  const showForm = bodyType && (editing || results.length === 0);

  return (
    <div className="relative min-h-screen bg-canvas pb-24 md:pb-0">
      <DoodleAccents variant="dashboard" />

      <header className="sticky top-0 z-20 bg-canvas/90 backdrop-blur border-b border-line px-4 py-3 flex items-center justify-between">
        <h1 className="font-serif text-xl font-bold text-ink">
          agent<span className="text-brand-500">weave</span>
        </h1>
        <nav aria-label="Primary" className="hidden md:flex bg-surface rounded-full p-1 gap-1">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} aria-current={tab === t.id ? "page" : undefined}
              className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
                tab === t.id ? "bg-brand-600 text-canvas shadow-soft" : "text-muted hover:text-ink"
              }`}>
              <t.Icon className="w-3.5 h-3.5" /> {t.label}
            </button>
          ))}
        </nav>
        <div className="relative">
          <button onClick={() => setProfileMenuOpen(o => !o)} aria-label="Profile menu" aria-expanded={profileMenuOpen}
            className="w-8 h-8 rounded-full border border-sage-500 text-sage-700 hover:bg-surface-2 transition-colors flex items-center justify-center">
            <ProfileIcon className="w-4 h-4" />
          </button>
          {profileMenuOpen && (
            <>
              <div className="fixed inset-0 z-20" onClick={() => setProfileMenuOpen(false)} />
              <div className="absolute right-0 mt-2 w-44 bg-surface border border-line rounded-xl shadow-xl overflow-hidden z-30">
                {currentUser?.email && <p className="px-4 pt-3 pb-2 text-xs text-muted truncate">{currentUser.email}</p>}
                <button onClick={() => { setProfileMenuOpen(false); logout(); }}
                  className="w-full text-left px-4 py-2.5 text-sm text-ink-soft hover:bg-surface-2 hover:text-ink transition-colors">
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </header>

      <main className="relative max-w-2xl mx-auto px-4 py-8">
        {tab === "discover" && (
          <div className="space-y-6">
            {!bodyType ? (
              <section className="card space-y-4">
                <div>
                  <p className="text-[11px] font-semibold tracking-wider text-sage-700">STEP 1 OF 2</p>
                  <h2 className="font-serif text-2xl font-semibold text-ink mt-1">Start with your shape</h2>
                  <p className="text-sm text-muted mt-1">
                    Upload a full-body photo. We read pose keypoints to estimate shoulder, waist and hip proportions.
                    The photo is analysed in memory and is not stored.
                  </p>
                </div>
                <BodyTypeForm setBodyType={setBodyType} setLoading={setLoadingBody} />
                {loadingBody && (
                  <div className="flex items-center gap-2 text-sm text-muted">
                    <SpinnerIcon className="w-4 h-4" /> Analysing body shape...
                  </div>
                )}
              </section>
            ) : (
              <section className="card flex items-center justify-between py-4">
                <div>
                  <p className="text-xs text-muted uppercase tracking-wider mb-1">Your body shape</p>
                  <p className="text-lg font-semibold text-brand-600 capitalize">{bodyType.replace(/_/g, " ")}</p>
                </div>
                <button onClick={() => { setBodyType(null); setResults([]); setEditing(true); }}
                  className="text-xs text-muted hover:text-ink transition-colors">
                  Re-analyse
                </button>
              </section>
            )}

            {showForm && (
              <section className="card space-y-5">
                <div>
                  <p className="text-[11px] font-semibold tracking-wider text-sage-700">STEP 2 OF 2</p>
                  <h2 className="font-serif text-2xl font-semibold text-ink mt-1">Tell us about your day</h2>
                </div>
                <ChipGroup label="Gender expression" options={GENDERS} value={form.gender} onChange={v => handleChange("gender", v)} />
                <ChipGroup label="Weather" options={WEATHERS} value={form.weather} onChange={v => handleChange("weather", v)} />
                <ChipGroup label="Occasion" options={OCCASIONS} value={form.occasion} onChange={v => handleChange("occasion", v)} />
                <ChipGroup label="Location" options={LOCATIONS} value={form.location} onChange={v => handleChange("location", v)} />
                <div>
                  <label htmlFor="occupation" className="text-xs text-muted uppercase tracking-wider mb-2 block">Occupation</label>
                  <input id="occupation" placeholder="e.g. designer, student, teacher"
                    value={form.occupation} onChange={e => handleChange("occupation", e.target.value)} className="input-field" />
                </div>
                {formError && <p role="alert" className="text-sm text-red-700">{formError}</p>}
                <button onClick={getRecommendation} disabled={loadingRec} className="btn-primary w-full text-base py-3">
                  <span className="flex items-center justify-center gap-2">
                    {loadingRec ? <><SpinnerIcon className="w-4 h-4" /> Finding your look...</> : <><SparkleIcon className="w-4 h-4" /> Get my outfit</>}
                  </span>
                </button>
              </section>
            )}

            {!showForm && current && (
              <section className="space-y-4" aria-label="Outfit recommendations">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted">
                    Look <span className="text-ink font-medium">{currentIndex + 1}</span> of {results.length}
                  </p>
                  {saved ? (
                    <span className="flex items-center gap-1 text-xs text-brand-600 font-medium" role="status">
                      <SparkleIcon className="w-3.5 h-3.5" /> Saved to your board
                    </span>
                  ) : (
                    <button onClick={() => setEditing(true)} className="text-xs text-brand-600 hover:text-brand-700">
                      Edit preferences
                    </button>
                  )}
                </div>

                <FashionCard
                  key={currentIndex}
                  image={current.image}
                  result={current.result}
                  match_score={current.match_score}
                  trendiness_score={current.trendiness_score}
                  future_projection={current.future_projection}
                  onSwipe={handleSwipe}
                />

                <div className="flex justify-center gap-1.5 pt-1" aria-hidden="true">
                  {results.map((_, i) => (
                    <span key={i} className={`h-1.5 rounded-full transition-all ${i === currentIndex ? "bg-brand-500 w-4" : "bg-line w-1.5"}`} />
                  ))}
                </div>

                {deckDone && (
                  <p className="text-center text-xs text-muted">That was the last look for these preferences.</p>
                )}

                {hasInteracted && (
                  <button onClick={() => setTab("shop")}
                    className="w-full py-3 rounded-xl border border-sage-500 hover:border-sage-600 text-sm font-semibold text-sage-700 hover:text-sage-700 transition-all flex items-center justify-center gap-2">
                    <span aria-hidden="true">{"🛒"}</span> Shop this look
                  </button>
                )}
              </section>
            )}
          </div>
        )}

        {tab === "saved" && (
          <SavedBoard firebaseUid={currentUser?.uid} onDiscover={() => setTab("discover")} />
        )}

        {tab === "wardrobe" && (
          <WardrobeManager occasion={form.occasion} weather={form.weather} bodyType={bodyType} gender={form.gender} />
        )}

        {tab === "shop" && (
          <ShoppingPanel
            styleCaption={current?.result || ""}
            occasion={form.occasion}
            bodyType={bodyType}
            gender={form.gender}
            firebaseUid={currentUser?.uid}
          />
        )}
      </main>

      <nav aria-label="Primary" className="md:hidden fixed bottom-0 inset-x-0 z-20 bg-surface/95 backdrop-blur border-t border-line grid grid-cols-4">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} aria-current={tab === t.id ? "page" : undefined}
            className={`flex flex-col items-center gap-1 py-3 text-[11px] font-medium ${tab === t.id ? "text-brand-600" : "text-muted"}`}>
            <t.Icon className="w-4 h-4" />
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  );
};

export default Dashboard;
