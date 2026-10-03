import React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "./Dashboard";

const mockNavigate = jest.fn();
let mockUser = { uid: "u1", email: "demo@agentweave.test", displayName: null };

jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => mockNavigate,
}));
jest.mock("firebase/auth", () => ({ onAuthStateChanged: jest.fn(), signOut: jest.fn() }));
jest.mock("../firebase", () => ({ auth: { currentUser: { uid: "u1" } } }));
jest.mock("../lib/resizeImage", () => ({ resizeImage: jest.fn() }));

const RESULTS = [
  { image: "boho_beach_3.jpg", result: "Look one", match_score: 81, future_projection: "Strong match" },
  { image: "minimalist_0.jpg", result: "Look two", match_score: 55, future_projection: "Good match" },
];

function routeFetch(overrides = {}) {
  fetch.mockImplementation((url, opts = {}) => {
    const path = url.replace("http://localhost:8001", "");
    const reply = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
    if (overrides[path]) return overrides[path](opts);
    if (path === "/analyze-body") return reply({ body_type: "hourglass" });
    if (path === "/stylegenie/trend_vector") return reply({ results: RESULTS });
    if (path.startsWith("/users/u1/outfits")) return reply({ outfits: [] });
    if (path.startsWith("/wardrobe/items")) return reply({ items: [] });
    return reply({ ok: true });
  });
}

const calls = (path) => fetch.mock.calls.filter(([u]) => u.endsWith(path));

// CRA's Jest preset resets mock implementations before each test.
beforeEach(() => {
  const firebaseAuth = require("firebase/auth");
  firebaseAuth.onAuthStateChanged.mockImplementation((auth, cb) => { cb(mockUser); return () => {}; });
  firebaseAuth.signOut.mockImplementation(() => Promise.resolve());
  require("../lib/resizeImage").resizeImage.mockImplementation(f => Promise.resolve(f));
  global.URL.createObjectURL = jest.fn(() => "blob:preview");
  mockUser = { uid: "u1", email: "demo@agentweave.test", displayName: null };
  mockNavigate.mockReset();
  routeFetch();
});

function renderDashboard() {
  return render(<MemoryRouter><Dashboard /></MemoryRouter>);
}

async function analyseBody() {
  const file = new File(["img"], "me.png", { type: "image/png" });
  fireEvent.change(document.getElementById("body-photo"), { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: "Analyze body shape" }));
  await screen.findByText("Tell us about your day");
}

function fillPreferences() {
  for (const name of ["woman", "warm", "brunch", "cafe"]) {
    fireEvent.click(screen.getAllByRole("button", { name })[0]);
  }
  fireEvent.change(screen.getByLabelText("Occupation"), { target: { value: "designer" } });
}

test("syncs the signed-in user and starts at step 1", () => {
  renderDashboard();
  expect(screen.getByText("Start with your shape")).toBeInTheDocument();
  const [, opts] = calls("/users/upsert")[0];
  expect(JSON.parse(opts.body)).toEqual({ firebase_uid: "u1", email: "demo@agentweave.test", display_name: null });
});

test("redirects to login when signed out", () => {
  mockUser = null;
  renderDashboard();
  expect(mockNavigate).toHaveBeenCalledWith("/login");
});

test("body analysis unlocks preferences and persists the shape", async () => {
  renderDashboard();
  await analyseBody();
  expect(screen.getByText("hourglass")).toBeInTheDocument();
  await waitFor(() => expect(calls("/users/u1/profile")).toHaveLength(1));
  expect(calls("/users/u1/profile")[0][1].method).toBe("PATCH");
});

test("an unreadable photo shows an error instead of advancing", async () => {
  routeFetch({ "/analyze-body": () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ body_type: "unknown" }) }) });
  renderDashboard();
  fireEvent.change(document.getElementById("body-photo"), { target: { files: [new File(["x"], "x.png")] } });
  fireEvent.click(screen.getByRole("button", { name: "Analyze body shape" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("couldn't see a full body");
  expect(screen.queryByText("Tell us about your day")).not.toBeInTheDocument();
});

test("validates the preference form before requesting looks", async () => {
  renderDashboard();
  await analyseBody();
  fireEvent.click(screen.getByRole("button", { name: /get my outfit/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Please choose: gender expression, weather, occasion, location, occupation.");
  expect(calls("/stylegenie/trend_vector")).toHaveLength(0);
});

test("full flow: recommend, swipe, save, then shop", async () => {
  renderDashboard();
  await analyseBody();
  fillPreferences();
  fireEvent.click(screen.getByRole("button", { name: /get my outfit/i }));

  expect(await screen.findByText("Look one")).toBeInTheDocument();
  const body = JSON.parse(calls("/stylegenie/trend_vector")[0][1].body);
  expect(body).toMatchObject({ gender: "woman", body_type: "hourglass", weather: "warm", occasion: "brunch" });
  expect(screen.queryByRole("button", { name: /shop this look/i })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Like" }));
  expect(await screen.findByText("Look two")).toBeInTheDocument();
  expect(JSON.parse(calls("/users/swipe")[0][1].body)).toMatchObject({ liked: true, image_filename: "boho_beach_3.jpg" });

  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Saved to your board");
  expect(JSON.parse(calls("/users/outfits/save")[0][1].body)).toMatchObject({ image_filename: "minimalist_0.jpg", trendiness_score: 55 });
  expect(screen.getByText("Look two")).toBeInTheDocument();

  const shop = screen.getByRole("button", { name: /shop this look/i });
  expect(shop).toHaveTextContent("🛒");
  fireEvent.click(shop);
  expect(await screen.findByText("Your Budget")).toBeInTheDocument();
});

test("a pass is recorded as a dislike", async () => {
  renderDashboard();
  await analyseBody();
  fillPreferences();
  fireEvent.click(screen.getByRole("button", { name: /get my outfit/i }));
  await screen.findByText("Look one");
  fireEvent.click(screen.getByRole("button", { name: "Pass" }));
  await waitFor(() => expect(calls("/users/swipe")).toHaveLength(1));
  expect(JSON.parse(calls("/users/swipe")[0][1].body).liked).toBe(false);
});

test("a failed recommendation request shows a retry message", async () => {
  routeFetch({ "/stylegenie/trend_vector": () => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) }) });
  renderDashboard();
  await analyseBody();
  fillPreferences();
  fireEvent.click(screen.getByRole("button", { name: /get my outfit/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("couldn't reach the stylist service");
});

test("tabs switch between Discover, Saved, Closet and Shop", async () => {
  renderDashboard();
  const nav = screen.getAllByRole("navigation", { name: "Primary" })[0];
  fireEvent.click(within(nav).getByRole("button", { name: /saved/i }));
  expect(await screen.findByText("Saved looks")).toBeInTheDocument();
  fireEvent.click(within(nav).getByRole("button", { name: /closet/i }));
  expect(await screen.findByText("My closet")).toBeInTheDocument();
  fireEvent.click(within(nav).getByRole("button", { name: /shop/i }));
  expect(await screen.findByText("Your Budget")).toBeInTheDocument();
  expect(within(nav).getByRole("button", { name: /shop/i })).toHaveAttribute("aria-current", "page");
});

test("sign out lives in the profile menu", async () => {
  const { signOut } = require("firebase/auth");
  renderDashboard();
  fireEvent.click(screen.getByRole("button", { name: "Profile menu" }));
  expect(screen.getByText("demo@agentweave.test")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/login"));
  expect(signOut).toHaveBeenCalled();
});

async function recommend() {
  renderDashboard();
  await analyseBody();
  fillPreferences();
  fireEvent.click(screen.getByRole("button", { name: /get my outfit/i }));
  await screen.findByText("Look one");
}

test("shows a progress message while the photo is analysed", async () => {
  let resolve;
  routeFetch({ "/analyze-body": () => new Promise(r => { resolve = r; }) });
  renderDashboard();
  expect(screen.queryByText(/analysing body shape/i)).not.toBeInTheDocument();
  fireEvent.change(document.getElementById("body-photo"), { target: { files: [new File(["x"], "x.png")] } });
  fireEvent.click(screen.getByRole("button", { name: "Analyze body shape" }));
  expect(await screen.findByText(/analysing body shape/i)).toBeInTheDocument();
  resolve({ ok: true, status: 200, json: () => Promise.resolve({ body_type: "pear" }) });
  expect(await screen.findByText("pear")).toBeInTheDocument();
  expect(screen.queryByText(/analysing body shape/i)).not.toBeInTheDocument();
});

test("re-analyse returns to step 1 and clears results", async () => {
  await recommend();
  fireEvent.click(screen.getByRole("button", { name: "Re-analyse" }));
  expect(screen.getByText("Start with your shape")).toBeInTheDocument();
  expect(screen.queryByText("Look one")).not.toBeInTheDocument();
  await analyseBody();
  expect(screen.getByText("Tell us about your day")).toBeInTheDocument();
  expect(screen.queryByText("Look one")).not.toBeInTheDocument();
});

test("chips expose their selected state", async () => {
  renderDashboard();
  await analyseBody();
  const warm = screen.getByRole("button", { name: "warm" });
  expect(warm).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(warm);
  expect(warm).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "cold" })).toHaveAttribute("aria-pressed", "false");
});

test("recommendation request is JSON and the deck replaces the form", async () => {
  await recommend();
  const [, opts] = calls("/stylegenie/trend_vector")[0];
  expect(opts.method).toBe("POST");
  expect(opts.headers).toEqual({ "Content-Type": "application/json" });
  expect(screen.queryByText("Tell us about your day")).not.toBeInTheDocument();
  expect(screen.getByText("of 2", { exact: false })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("edit preferences reopens the form with answers kept", async () => {
  await recommend();
  fireEvent.click(screen.getByRole("button", { name: "Edit preferences" }));
  expect(screen.getByText("Tell us about your day")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "brunch" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByLabelText("Occupation")).toHaveValue("designer");
});

test("an empty result list keeps the form open", async () => {
  routeFetch({ "/stylegenie/trend_vector": () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) }) });
  renderDashboard();
  await analyseBody();
  fillPreferences();
  fireEvent.click(screen.getByRole("button", { name: /get my outfit/i }));
  await waitFor(() => expect(calls("/stylegenie/trend_vector")).toHaveLength(1));
  expect(screen.getByText("Tell us about your day")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Like" })).not.toBeInTheDocument();
});

test("the saved confirmation clears after two seconds", async () => {
  await recommend();
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Saved to your board");
  expect(screen.queryByRole("button", { name: "Edit preferences" })).not.toBeInTheDocument();
  // Real timers keep this an end-to-end check of the 2 s confirmation.
  await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument(), { timeout: 3000 });
  expect(screen.getByRole("button", { name: "Edit preferences" })).toBeInTheDocument();
});

test("the last card says so after the user acts on it", async () => {
  await recommend();
  expect(screen.queryByText(/last look/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Like" }));
  await screen.findByText("Look two");
  expect(screen.queryByText(/last look/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByRole("status");
  expect(screen.queryByText(/last look/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Like" }));
  expect(await screen.findByText(/that was the last look/i)).toBeInTheDocument();
  expect(screen.getByText("Look two")).toBeInTheDocument();
});

test("profile sync and shape updates carry the user's details", async () => {
  mockUser = { uid: "u1", email: "demo@agentweave.test", displayName: "Dee" };
  renderDashboard();
  expect(JSON.parse(calls("/users/upsert")[0][1].body).display_name).toBe("Dee");
  expect(calls("/users/upsert")[0][1].headers).toEqual({ "Content-Type": "application/json" });
  await analyseBody();
  await waitFor(() => expect(calls("/users/u1/profile")).toHaveLength(1));
  expect(JSON.parse(calls("/users/u1/profile")[0][1].body)).toEqual({ firebase_uid: "u1", email: "demo@agentweave.test", body_type: "hourglass", gender: null });
  fireEvent.click(screen.getByRole("button", { name: "woman" }));
  await waitFor(() => expect(calls("/users/u1/profile")).toHaveLength(2));
  expect(JSON.parse(calls("/users/u1/profile")[1][1].body).gender).toBe("woman");
});

test("only the active tab's content is shown and marked current", async () => {
  renderDashboard();
  const nav = screen.getAllByRole("navigation", { name: "Primary" })[0];
  expect(within(nav).getByRole("button", { name: /discover/i })).toHaveAttribute("aria-current", "page");
  expect(within(nav).getByRole("button", { name: /saved/i })).not.toHaveAttribute("aria-current");
  expect(screen.queryByText("Saved looks")).not.toBeInTheDocument();
  expect(screen.queryByText("My closet")).not.toBeInTheDocument();
  expect(screen.queryByText("Your Budget")).not.toBeInTheDocument();

  fireEvent.click(within(nav).getByRole("button", { name: /saved/i }));
  await screen.findByText("Saved looks");
  expect(screen.queryByText("Start with your shape")).not.toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: "Find looks" }));
  expect(screen.getByText("Start with your shape")).toBeInTheDocument();
});

test("the mobile tab bar switches tabs too", async () => {
  renderDashboard();
  const mobileNav = screen.getAllByRole("navigation", { name: "Primary" })[1];
  fireEvent.click(within(mobileNav).getByRole("button", { name: /closet/i }));
  expect(await screen.findByText("My closet")).toBeInTheDocument();
  expect(within(mobileNav).getByRole("button", { name: /closet/i })).toHaveAttribute("aria-current", "page");
});

test("shop receives the current look's caption", async () => {
  await recommend();
  fireEvent.click(screen.getByRole("button", { name: "Pass" }));
  await screen.findByText("Look two");
  fireEvent.click(screen.getByRole("button", { name: /shop this look/i }));
  fireEvent.click(await screen.findByRole("button", { name: /find this look online/i }));
  await waitFor(() => expect(calls("/shopping/suggest")).toHaveLength(1));
  expect(JSON.parse(calls("/shopping/suggest")[0][1].body).style_caption).toBe("Look two");
});

test("the profile menu closes when clicking outside", () => {
  renderDashboard();
  const toggle = screen.getByRole("button", { name: "Profile menu" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  fireEvent.click(document.querySelector(".fixed.inset-0"));
  expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
});
