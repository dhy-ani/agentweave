// Firestore security rules tests, run with Node's built-in test runner against
// the Firestore emulator: `npm run test:rules`.
import { after, before, beforeEach, describe, test } from "node:test";
import fs from "node:fs";
import { initializeTestEnvironment, assertFails, assertSucceeds } from "@firebase/rules-unit-testing";
import {
  doc, getDoc, setDoc, updateDoc, deleteDoc, addDoc, collection, serverTimestamp, Timestamp, setLogLevel,
} from "firebase/firestore";

// Denied writes are the point of half these tests; keep the SDK quiet about them.
setLogLevel("silent");

let env;
const ALICE = "alice";
const BOB = "bob";
const ITEM_ID = "0123456789abcdef0123456789abcdef";
const embedding = Array.from({ length: 512 }, (_, i) => i / 512);

before(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-agentweave",
    firestore: { rules: fs.readFileSync(new URL("../../firestore.rules", import.meta.url), "utf8") },
  });
});

after(() => env.cleanup());
beforeEach(() => env.clearFirestore());

const as = (uid) => env.authenticatedContext(uid).firestore();
const anon = () => env.unauthenticatedContext().firestore();

const profile = () => ({ email: "a@test.dev", displayName: "Alice", createdAt: serverTimestamp(), updatedAt: serverTimestamp() });
const look = (extra = {}) => ({ image: "boho_beach_3.jpg", caption: "Beach day", matchScore: 74.2, explanation: "Good match", occasion: "brunch", weather: "warm", savedAt: serverTimestamp(), ...extra });
const closetItem = (extra = {}) => ({ imageUrl: "https://blob.example/x.jpg", category: "top", color: "pink", description: null, embedding, addedAt: serverTimestamp(), ...extra });

async function seed(fn) {
  await env.withSecurityRulesDisabled((ctx) => fn(ctx.firestore()));
}

describe("profile", () => {
  test("the owner can create and read their profile", async () => {
    await assertSucceeds(setDoc(doc(as(ALICE), "users", ALICE), profile()));
    await assertSucceeds(getDoc(doc(as(ALICE), "users", ALICE)));
  });

  test("other users and signed-out visitors cannot read it", async () => {
    await seed((db) => setDoc(doc(db, "users", ALICE), { email: "a@test.dev" }));
    await assertFails(getDoc(doc(as(BOB), "users", ALICE)));
    await assertFails(getDoc(doc(anon(), "users", ALICE)));
  });

  test("nobody can write someone else's profile", async () => {
    await assertFails(setDoc(doc(as(BOB), "users", ALICE), profile()));
  });

  test("unknown fields and client-chosen timestamps are rejected", async () => {
    await assertFails(setDoc(doc(as(ALICE), "users", ALICE), { ...profile(), isAdmin: true }));
    await assertFails(setDoc(doc(as(ALICE), "users", ALICE), { ...profile(), createdAt: Timestamp.fromMillis(0) }));
  });

  test("updates keep createdAt and stamp updatedAt", async () => {
    await setDoc(doc(as(ALICE), "users", ALICE), profile());
    await assertSucceeds(updateDoc(doc(as(ALICE), "users", ALICE), { bodyType: "pear", updatedAt: serverTimestamp() }));
    await assertFails(updateDoc(doc(as(ALICE), "users", ALICE), { bodyType: "pear" }));
    await assertFails(updateDoc(doc(as(ALICE), "users", ALICE), { createdAt: serverTimestamp(), updatedAt: serverTimestamp() }));
  });

  test("field sizes are bounded", async () => {
    await assertFails(setDoc(doc(as(ALICE), "users", ALICE), { ...profile(), bodyType: "x".repeat(33) }));
  });
});

describe("saved looks", () => {
  const looks = (db, uid = ALICE) => collection(db, "users", uid, "savedLooks");

  test("the owner can save, list and delete looks", async () => {
    const ref = await assertSucceeds(addDoc(looks(as(ALICE)), look()));
    await assertSucceeds(getDoc(ref));
    await assertSucceeds(deleteDoc(ref));
  });

  test("another user cannot read, add to or delete from the board", async () => {
    await seed((db) => setDoc(doc(db, "users", ALICE, "savedLooks", "l1"), { image: "a.jpg", caption: "c" }));
    await assertFails(getDoc(doc(as(BOB), "users", ALICE, "savedLooks", "l1")));
    await assertFails(addDoc(looks(as(BOB)), look()));
    await assertFails(deleteDoc(doc(as(BOB), "users", ALICE, "savedLooks", "l1")));
  });

  test("required fields, score range and timestamps are enforced", async () => {
    const { caption, ...noCaption } = look();
    await assertFails(addDoc(looks(as(ALICE)), noCaption));
    await assertFails(addDoc(looks(as(ALICE)), look({ matchScore: 150 })));
    await assertFails(addDoc(looks(as(ALICE)), look({ matchScore: "high" })));
    await assertFails(addDoc(looks(as(ALICE)), look({ savedAt: Timestamp.now() })));
    await assertFails(addDoc(looks(as(ALICE)), look({ secret: 1 })));
  });

  test("saved looks are immutable", async () => {
    const ref = await addDoc(looks(as(ALICE)), look());
    await assertFails(updateDoc(ref, { caption: "edited" }));
  });
});

describe("swipes", () => {
  const swipe = (db, liked = true) => setDoc(doc(db, "users", ALICE, "swipes", "boho_beach_3.jpg"),
    { image: "boho_beach_3.jpg", caption: "c", liked, occasion: "brunch", recordedAt: serverTimestamp() });

  test("the owner can record and change a swipe", async () => {
    await assertSucceeds(swipe(as(ALICE), true));
    await assertSucceeds(swipe(as(ALICE), false));
  });

  test("liked must be a boolean and others cannot write", async () => {
    await assertFails(swipe(as(ALICE), "yes"));
    await assertFails(swipe(as(BOB)));
  });
});

describe("closet", () => {
  const item = (db, id = ITEM_ID, data = closetItem()) => setDoc(doc(db, "users", ALICE, "closet", id), data);

  test("the owner can add, read and delete an item", async () => {
    await assertSucceeds(item(as(ALICE)));
    await assertSucceeds(getDoc(doc(as(ALICE), "users", ALICE, "closet", ITEM_ID)));
    await assertSucceeds(deleteDoc(doc(as(ALICE), "users", ALICE, "closet", ITEM_ID)));
  });

  test("ids must be API-issued uuids and categories must be known", async () => {
    await assertFails(item(as(ALICE), "my-item"));
    await assertFails(item(as(ALICE), ITEM_ID, closetItem({ category: "spaceship" })));
  });

  test("an embedding must have exactly 512 values", async () => {
    await assertFails(item(as(ALICE), ITEM_ID, closetItem({ embedding: embedding.slice(1) })));
    await assertFails(item(as(ALICE), ITEM_ID, closetItem({ embedding: "nope" })));
  });

  test("only labels can be edited after upload", async () => {
    await item(as(ALICE));
    const ref = doc(as(ALICE), "users", ALICE, "closet", ITEM_ID);
    await assertSucceeds(updateDoc(ref, { color: "navy", description: "linen" }));
    await assertFails(updateDoc(ref, { imageUrl: "https://evil.example/x.jpg" }));
    await assertFails(updateDoc(ref, { embedding: embedding.map(() => 0) }));
  });

  test("another user cannot see or add to the closet", async () => {
    await item(as(ALICE));
    await assertFails(getDoc(doc(as(BOB), "users", ALICE, "closet", ITEM_ID)));
    await assertFails(setDoc(doc(as(BOB), "users", ALICE, "closet", "fedcba9876543210fedcba9876543210"), closetItem()));
  });
});

describe("shop clicks", () => {
  const clicks = (db) => collection(db, "users", ALICE, "shopClicks");
  const click = () => ({ brand: "Zara", item: "Slip skirt", tier: "Budget", estPrice: 60, occasion: "brunch", clickedAt: serverTimestamp() });

  test("clicks are append-only", async () => {
    const ref = await assertSucceeds(addDoc(clicks(as(ALICE)), click()));
    await assertFails(updateDoc(ref, { brand: "H&M" }));
    await assertFails(deleteDoc(ref));
  });

  test("price must be a number", async () => {
    await assertFails(addDoc(clicks(as(ALICE)), { ...click(), estPrice: "60" }));
  });
});

test("collections outside users/{uid} are closed", async () => {
  await assertFails(setDoc(doc(as(ALICE), "admin", "config"), { open: true }));
  await assertFails(getDoc(doc(as(ALICE), "users", ALICE, "secrets", "x")));
});
