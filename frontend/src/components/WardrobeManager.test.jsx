import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import WardrobeManager from "./WardrobeManager";

const SIGNED_IN = { uid: "u1", getIdToken: () => Promise.resolve("tok") };
let mockUser = SIGNED_IN;
jest.mock("../firebase", () => ({ get auth() { return { currentUser: mockUser }; } }));
jest.mock("../lib/resizeImage", () => ({ resizeImage: jest.fn() }));
jest.mock("../data/userData", () => ({ subscribeCloset: jest.fn(), addClosetItem: jest.fn(), deleteClosetItem: jest.fn() }));
const data = () => require("../data/userData");

const reply = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const STORED = { item_id: "0123456789abcdef0123456789abcdef", image_url: "/closet-images/u1/x.jpg", category: "dress", embedding: [0.1] };
const ITEMS = [
  { id: "a", imageUrl: "https://blob.test/a.jpg", category: "top", color: "pink", embedding: [1] },
  { id: "b", imageUrl: "/closet-images/u1/b.jpg", category: "bottom", color: null, embedding: [2] },
];

let push;
beforeEach(() => {
  mockUser = SIGNED_IN;
  data().subscribeCloset.mockImplementation((uid, onData) => { push = onData; return () => {}; });
  data().addClosetItem.mockResolvedValue(undefined);
  data().deleteClosetItem.mockResolvedValue(undefined);
  require("../lib/resizeImage").resizeImage.mockImplementation(f => Promise.resolve(f));
  global.URL.createObjectURL = jest.fn(() => "blob:preview");
});

function pickFile() {
  fireEvent.change(document.getElementById("wardrobe-file"), { target: { files: [new File(["x"], "dress.png")] } });
}

test("lists the user's closet from Firestore", () => {
  render(<WardrobeManager />);
  expect(data().subscribeCloset).toHaveBeenCalledWith("u1", expect.any(Function), expect.any(Function));
  act(() => push(ITEMS));
  expect(screen.getByText("2 items")).toBeInTheDocument();
  const imgs = screen.getAllByRole("img");
  expect(imgs[0]).toHaveAttribute("src", "https://blob.test/a.jpg");
  expect(imgs[1]).toHaveAttribute("src", "http://localhost:8001/closet-images/u1/b.jpg");
});

test("uploading sends the photo with the user's token, then saves the item", async () => {
  fetch.mockReturnValueOnce(reply(STORED));
  render(<WardrobeManager />);
  pickFile();
  fireEvent.change(screen.getByLabelText("Category"), { target: { value: "dress" } });
  fireEvent.change(screen.getByLabelText("Color"), { target: { value: "lavender" } });
  fireEvent.click(screen.getByRole("button", { name: "Add item" }));

  await waitFor(() => expect(data().addClosetItem).toHaveBeenCalledWith("u1", STORED, { category: "dress", color: "lavender", description: "" }));
  const [url, opts] = fetch.mock.calls[0];
  expect(url).toBe("http://localhost:8001/closet/items");
  expect(opts.headers).toEqual({ Authorization: "Bearer tok" });
  expect(opts.body.get("category")).toBe("dress");
  expect(opts.body.has("firebase_uid")).toBe(false);
  expect(screen.queryByRole("button", { name: "Add item" })).not.toBeInTheDocument();
});

test("if saving the record fails, the uploaded photo is deleted again", async () => {
  fetch.mockReturnValueOnce(reply(STORED)).mockReturnValueOnce(reply({ deleted: true }));
  data().addClosetItem.mockRejectedValueOnce(new Error("Missing or insufficient permissions."));
  render(<WardrobeManager />);
  pickFile();
  fireEvent.click(screen.getByRole("button", { name: "Add item" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Missing or insufficient permissions.");
  expect(fetch).toHaveBeenLastCalledWith(`http://localhost:8001/closet/items/${STORED.item_id}`,
    expect.objectContaining({ method: "DELETE", headers: { Authorization: "Bearer tok" } }));
});

test("an upload rejected by the API shows its reason", async () => {
  fetch.mockReturnValueOnce(reply({ detail: "Image too large (max 4.5 MB)." }, 413));
  render(<WardrobeManager />);
  pickFile();
  fireEvent.click(screen.getByRole("button", { name: "Add item" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Image too large");
  expect(data().addClosetItem).not.toHaveBeenCalled();
});

test("deleting removes the record and the stored photo", async () => {
  fetch.mockReturnValueOnce(reply({ deleted: true }));
  render(<WardrobeManager />);
  act(() => push(ITEMS));
  fireEvent.click(screen.getByRole("button", { name: "Remove top" }));
  await waitFor(() => expect(data().deleteClosetItem).toHaveBeenCalledWith("u1", "a"));
  expect(fetch).toHaveBeenCalledWith("http://localhost:8001/closet/items/a", expect.objectContaining({ method: "DELETE" }));
});

test("a failed delete is reported", async () => {
  data().deleteClosetItem.mockRejectedValueOnce(new Error("offline"));
  render(<WardrobeManager />);
  act(() => push(ITEMS));
  fireEvent.click(screen.getByRole("button", { name: "Remove top" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not remove that item.");
});

test("suggestions send the closet embeddings and show the chosen items", async () => {
  fetch.mockReturnValueOnce(reply({
    suggestion: "A soft top with relaxed trousers.",
    outfit: [{ id: "b", category: "bottom" }, { id: "missing", category: "shoes" }],
    trend_inspiration: { image: "boho_beach_3.jpg", caption: "Beach day" },
  }));
  render(<WardrobeManager occasion="brunch" weather="warm" bodyType="pear" gender="woman" />);
  act(() => push(ITEMS));
  fireEvent.click(screen.getByRole("button", { name: /suggest an outfit/i }));

  expect(await screen.findByText("A soft top with relaxed trousers.")).toBeInTheDocument();
  const [url, opts] = fetch.mock.calls[0];
  expect(url).toBe("http://localhost:8001/closet/suggest");
  expect(opts.headers).toEqual({ "Content-Type": "application/json", Authorization: "Bearer tok" });
  expect(JSON.parse(opts.body)).toEqual({
    occasion: "brunch", weather: "warm", gender: "woman", body_type: "pear",
    items: [{ id: "a", category: "top", embedding: [1] }, { id: "b", category: "bottom", embedding: [2] }],
  });
  expect(screen.getAllByText("bottom")).toHaveLength(2);
  expect(screen.getByAltText("Inspiration")).toHaveAttribute("src", "http://localhost:8001/images/boho_beach_3.jpg");
});

test("suggestion defaults fill in missing context", async () => {
  fetch.mockReturnValueOnce(reply({ suggestion: "x", outfit: [] }));
  render(<WardrobeManager />);
  act(() => push(ITEMS));
  fireEvent.click(screen.getByRole("button", { name: /suggest an outfit/i }));
  await screen.findByText("x");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({ occasion: "casual", weather: "mild", gender: "", body_type: "" });
});

test("a failed suggestion is reported", async () => {
  fetch.mockReturnValueOnce(reply({}, 500));
  render(<WardrobeManager />);
  act(() => push(ITEMS));
  fireEvent.click(screen.getByRole("button", { name: /suggest an outfit/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not build a suggestion right now.");
});

test("a closet that cannot load says so", () => {
  data().subscribeCloset.mockImplementation((uid, onData, onError) => { onError(new Error("denied")); return () => {}; });
  render(<WardrobeManager />);
  expect(screen.getByRole("alert")).toHaveTextContent("Could not load your closet.");
});

test("a signed-out visitor gets no closet subscription", () => {
  mockUser = null;
  render(<WardrobeManager />);
  expect(data().subscribeCloset).not.toHaveBeenCalled();
  expect(screen.getByText("0 items")).toBeInTheDocument();
});

test("an empty closet shows no list and no suggestion button", () => {
  render(<WardrobeManager />);
  act(() => push([]));
  expect(screen.queryByRole("list")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /suggest an outfit/i })).not.toBeInTheDocument();
});

test("one item is counted in the singular, with its color and a fallback alt text", () => {
  render(<WardrobeManager />);
  act(() => push([{ ...ITEMS[1], description: null }]));
  expect(screen.getByText("1 item")).toBeInTheDocument();
  expect(screen.getByAltText("bottom")).toBeInTheDocument();
  act(() => push([{ ...ITEMS[0], description: "Linen shirt" }]));
  expect(screen.getByAltText("Linen shirt")).toBeInTheDocument();
  expect(screen.getByText("pink")).toBeInTheDocument();
});

test("choosing no file leaves the form closed", () => {
  render(<WardrobeManager />);
  fireEvent.change(document.getElementById("wardrobe-file"), { target: { files: [] } });
  expect(screen.queryByRole("button", { name: "Add item" })).not.toBeInTheDocument();
});

test("categories are offered with readable labels", () => {
  render(<WardrobeManager />);
  pickFile();
  expect(screen.getByRole("option", { name: "Outerwear" })).toHaveValue("outerwear");
});

test("while uploading the button is disabled, and the form resets afterwards", async () => {
  let finish;
  fetch.mockReturnValueOnce(new Promise(r => { finish = () => r({ ok: true, status: 200, json: () => Promise.resolve(STORED) }); }));
  render(<WardrobeManager />);
  pickFile();
  fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Silk slip" } });
  fireEvent.click(screen.getByRole("button", { name: "Add item" }));
  expect(await screen.findByRole("button", { name: "Uploading..." })).toBeDisabled();
  const [, opts] = fetch.mock.calls[0];
  expect(opts.method).toBe("POST");
  expect(opts.body.get("file")).toBeInstanceOf(File);
  await act(async () => finish());
  await waitFor(() => expect(data().addClosetItem).toHaveBeenCalledWith("u1", STORED, expect.objectContaining({ description: "Silk slip" })));
  expect(document.getElementById("wardrobe-file").value).toBe("");
  pickFile();
  expect(screen.getByLabelText("Description")).toHaveValue("");
});

test("a failed upload re-enables the button and falls back to a generic message", async () => {
  require("../lib/resizeImage").resizeImage.mockRejectedValueOnce({});
  render(<WardrobeManager />);
  pickFile();
  fireEvent.click(screen.getByRole("button", { name: "Add item" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Upload failed.");
  expect(screen.getByRole("button", { name: "Add item" })).toBeEnabled();
  pickFile();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("deleting sends the user's token", async () => {
  fetch.mockReturnValueOnce(reply({ deleted: true }));
  render(<WardrobeManager />);
  act(() => push(ITEMS));
  fireEvent.click(screen.getByRole("button", { name: "Remove top" }));
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(fetch.mock.calls[0][1].headers).toEqual({ Authorization: "Bearer tok" });
});

test("asking again clears the previous suggestion and disables the button meanwhile", async () => {
  fetch.mockReturnValueOnce(reply({ suggestion: "first idea", outfit: [] }));
  render(<WardrobeManager />);
  act(() => push(ITEMS));
  fireEvent.click(screen.getByRole("button", { name: /suggest an outfit/i }));
  await screen.findByText("first idea");
  let finish;
  fetch.mockReturnValueOnce(new Promise(r => { finish = () => r({ ok: false, status: 500, json: () => Promise.resolve({}) }); }));
  fireEvent.click(screen.getByRole("button", { name: /suggest an outfit/i }));
  expect(await screen.findByRole("button", { name: /thinking/i })).toBeDisabled();
  expect(screen.queryByText("first idea")).not.toBeInTheDocument();
  await act(async () => finish());
  expect(await screen.findByRole("button", { name: /suggest an outfit/i })).toBeEnabled();
});
