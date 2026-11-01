import {
  addDoc, collection, deleteDoc, doc, getDoc, onSnapshot, orderBy, query,
  serverTimestamp, setDoc, updateDoc,
} from "firebase/firestore";
import { db } from "../firebase";

// All user data lives under users/{uid}; firestore.rules restricts every path
// below to its owner and validates each write.
const userDoc = (uid) => doc(db, "users", uid);
const sub = (uid, name) => collection(db, "users", uid, name);

// Firestore ids cannot contain "/" and cannot be "." or "..".
export function swipeKey(image) {
  const key = String(image).replace(/\//g, "_").slice(0, 500);
  return key === "." || key === ".." ? `_${key}` : key;
}

export async function ensureProfile(user) {
  const ref = userDoc(user.uid);
  const snap = await getDoc(ref);
  const identity = { email: user.email || null, displayName: user.displayName || null };
  if (!snap.exists()) {
    await setDoc(ref, { ...identity, createdAt: serverTimestamp(), updatedAt: serverTimestamp() });
  } else {
    const current = snap.data();
    if (current.email !== identity.email || current.displayName !== identity.displayName) {
      await updateDoc(ref, { ...identity, updatedAt: serverTimestamp() });
    }
  }
}

export function updateProfile(uid, fields) {
  return updateDoc(userDoc(uid), { ...fields, updatedAt: serverTimestamp() });
}

export function saveLook(uid, rec, { occasion, weather }) {
  const score = rec.match_score ?? rec.trendiness_score;
  return addDoc(sub(uid, "savedLooks"), {
    image: rec.image,
    caption: rec.result,
    ...(typeof score === "number" ? { matchScore: score } : {}),
    explanation: rec.future_projection || null,
    occasion: occasion || null,
    weather: weather || null,
    savedAt: serverTimestamp(),
  });
}

function subscribe(q, onData, onError) {
  return onSnapshot(
    q,
    (snap) => onData(snap.docs.map((d) => ({ id: d.id, ...d.data() }))),
    onError,
  );
}

export function subscribeSavedLooks(uid, onData, onError) {
  return subscribe(query(sub(uid, "savedLooks"), orderBy("savedAt", "desc")), onData, onError);
}

export function deleteLook(uid, lookId) {
  return deleteDoc(doc(db, "users", uid, "savedLooks", lookId));
}

export function recordSwipe(uid, rec, liked, occasion) {
  return setDoc(doc(db, "users", uid, "swipes", swipeKey(rec.image)), {
    image: rec.image,
    caption: rec.result || null,
    liked,
    occasion: occasion || null,
    recordedAt: serverTimestamp(),
  });
}

export function recordShopClick(uid, brand, occasion) {
  return addDoc(sub(uid, "shopClicks"), {
    brand: brand.brand,
    item: brand.item || null,
    tier: brand.tier || null,
    ...(typeof brand.est_price === "number" ? { estPrice: brand.est_price } : {}),
    occasion: occasion || null,
    clickedAt: serverTimestamp(),
  });
}

export function subscribeCloset(uid, onData, onError) {
  return subscribe(query(sub(uid, "closet"), orderBy("addedAt", "desc")), onData, onError);
}

export function addClosetItem(uid, item, { color, description }) {
  return setDoc(doc(db, "users", uid, "closet", item.item_id), {
    imageUrl: item.image_url,
    category: item.category,
    color: color || null,
    description: description || null,
    embedding: item.embedding,
    addedAt: serverTimestamp(),
  });
}

export function deleteClosetItem(uid, itemId) {
  return deleteDoc(doc(db, "users", uid, "closet", itemId));
}
