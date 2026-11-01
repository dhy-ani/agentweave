import {
  swipeKey, ensureProfile, updateProfile, saveLook, subscribeSavedLooks, deleteLook,
  recordSwipe, recordShopClick, subscribeCloset, addClosetItem, deleteClosetItem,
} from "./userData";

jest.mock("../firebase", () => ({ db: { name: "db" } }));
jest.mock("firebase/firestore", () => ({
  addDoc: jest.fn(), collection: jest.fn(), deleteDoc: jest.fn(), doc: jest.fn(), getDoc: jest.fn(),
  onSnapshot: jest.fn(), orderBy: jest.fn(), query: jest.fn(), serverTimestamp: jest.fn(),
  setDoc: jest.fn(), updateDoc: jest.fn(),
}));
const fs = () => require("firebase/firestore");
const TS = "<server time>";

// CRA's Jest preset resets mock implementations before each test.
beforeEach(() => {
  fs().doc.mockImplementation((db, ...parts) => ({ path: parts.join("/") }));
  fs().collection.mockImplementation((db, ...parts) => ({ path: parts.join("/") }));
  fs().serverTimestamp.mockReturnValue(TS);
  fs().orderBy.mockImplementation((field, dir) => ({ orderBy: [field, dir] }));
  fs().query.mockImplementation((ref, ...constraints) => ({ ref, constraints }));
  for (const fn of ["addDoc", "deleteDoc", "setDoc", "updateDoc"]) fs()[fn].mockResolvedValue(undefined);
});

describe("swipeKey", () => {
  test("keeps ordinary filenames", () => {
    expect(swipeKey("boho_beach_3.jpg")).toBe("boho_beach_3.jpg");
  });
  test("replaces slashes, which would create nested paths", () => {
    expect(swipeKey("a/b/c.jpg")).toBe("a_b_c.jpg");
  });
  test("avoids the reserved ids . and ..", () => {
    expect(swipeKey(".")).toBe("_.");
    expect(swipeKey("..")).toBe("_..");
  });
  test("caps the length", () => {
    expect(swipeKey("x".repeat(600))).toHaveLength(500);
  });
});

describe("ensureProfile", () => {
  const user = { uid: "u1", email: "a@test.dev", displayName: "Alice" };

  test("creates the profile with server timestamps on first sign-in", async () => {
    fs().getDoc.mockResolvedValue({ exists: () => false });
    await ensureProfile(user);
    expect(fs().setDoc).toHaveBeenCalledWith({ path: "users/u1" },
      { email: "a@test.dev", displayName: "Alice", createdAt: TS, updatedAt: TS });
  });

  test("updates only when the identity changed", async () => {
    fs().getDoc.mockResolvedValue({ exists: () => true, data: () => ({ email: "old@test.dev", displayName: "Alice" }) });
    await ensureProfile(user);
    expect(fs().updateDoc).toHaveBeenCalledWith({ path: "users/u1" },
      { email: "a@test.dev", displayName: "Alice", updatedAt: TS });
    expect(fs().setDoc).not.toHaveBeenCalled();
  });

  test("writes nothing when the profile is current", async () => {
    fs().getDoc.mockResolvedValue({ exists: () => true, data: () => ({ email: "a@test.dev", displayName: "Alice" }) });
    await ensureProfile(user);
    expect(fs().updateDoc).not.toHaveBeenCalled();
    expect(fs().setDoc).not.toHaveBeenCalled();
  });

  test("stores missing email or name as null", async () => {
    fs().getDoc.mockResolvedValue({ exists: () => false });
    await ensureProfile({ uid: "u2" });
    expect(fs().setDoc.mock.calls[0][1]).toMatchObject({ email: null, displayName: null });
  });
});

test("updateProfile stamps updatedAt", async () => {
  await updateProfile("u1", { bodyType: "pear", gender: null });
  expect(fs().updateDoc).toHaveBeenCalledWith({ path: "users/u1" }, { bodyType: "pear", gender: null, updatedAt: TS });
});

describe("saveLook", () => {
  test("stores the look under the user's board", async () => {
    await saveLook("u1", { image: "a.jpg", result: "Caption", match_score: 74.5, future_projection: "Good match" },
      { occasion: "brunch", weather: "warm" });
    expect(fs().addDoc).toHaveBeenCalledWith({ path: "users/u1/savedLooks" }, {
      image: "a.jpg", caption: "Caption", matchScore: 74.5, explanation: "Good match",
      occasion: "brunch", weather: "warm", savedAt: TS,
    });
  });

  test("falls back to trendiness_score and omits a missing score", async () => {
    await saveLook("u1", { image: "a.jpg", result: "C", trendiness_score: 40 }, {});
    expect(fs().addDoc.mock.calls[0][1]).toMatchObject({ matchScore: 40, explanation: null, occasion: null, weather: null });
    await saveLook("u1", { image: "a.jpg", result: "C" }, {});
    expect(fs().addDoc.mock.calls[1][1]).not.toHaveProperty("matchScore");
  });
});

describe("subscriptions", () => {
  test("saved looks stream newest first with document ids", () => {
    const onData = jest.fn();
    const onError = jest.fn();
    fs().onSnapshot.mockImplementation((q, next) => {
      next({ docs: [{ id: "l1", data: () => ({ caption: "x" }) }] });
      return "unsubscribe";
    });
    expect(subscribeSavedLooks("u1", onData, onError)).toBe("unsubscribe");
    expect(fs().query).toHaveBeenCalledWith({ path: "users/u1/savedLooks" }, { orderBy: ["savedAt", "desc"] });
    expect(onData).toHaveBeenCalledWith([{ id: "l1", caption: "x" }]);
    expect(fs().onSnapshot.mock.calls[0][2]).toBe(onError);
  });

  test("the closet streams by date added", () => {
    fs().onSnapshot.mockReturnValue("unsub");
    subscribeCloset("u1", jest.fn(), jest.fn());
    expect(fs().query).toHaveBeenCalledWith({ path: "users/u1/closet" }, { orderBy: ["addedAt", "desc"] });
  });
});

test("deleteLook removes the user's own document", async () => {
  await deleteLook("u1", "l1");
  expect(fs().deleteDoc).toHaveBeenCalledWith({ path: "users/u1/savedLooks/l1" });
});

test("recordSwipe upserts one document per look", async () => {
  await recordSwipe("u1", { image: "a/b.jpg", result: "C" }, false, "");
  expect(fs().setDoc).toHaveBeenCalledWith({ path: "users/u1/swipes/a_b.jpg" },
    { image: "a/b.jpg", caption: "C", liked: false, occasion: null, recordedAt: TS });
});

test("recordShopClick appends a click", async () => {
  await recordShopClick("u1", { brand: "Zara", item: "Skirt", tier: "Budget", est_price: 60 }, "brunch");
  expect(fs().addDoc).toHaveBeenCalledWith({ path: "users/u1/shopClicks" },
    { brand: "Zara", item: "Skirt", tier: "Budget", estPrice: 60, occasion: "brunch", clickedAt: TS });
  await recordShopClick("u1", { brand: "H&M" });
  expect(fs().addDoc.mock.calls[1][1]).toEqual({ brand: "H&M", item: null, tier: null, occasion: null, clickedAt: TS });
});

test("addClosetItem keys the document by the API's item id", async () => {
  const embedding = [0.1, 0.2];
  await addClosetItem("u1", { item_id: "abc", image_url: "https://blob/x.jpg", category: "top", embedding },
    { color: "pink", description: "" });
  expect(fs().setDoc).toHaveBeenCalledWith({ path: "users/u1/closet/abc" }, {
    imageUrl: "https://blob/x.jpg", category: "top", color: "pink", description: null, embedding, addedAt: TS,
  });
});

test("deleteClosetItem removes the item document", async () => {
  await deleteClosetItem("u1", "abc");
  expect(fs().deleteDoc).toHaveBeenCalledWith({ path: "users/u1/closet/abc" });
});
