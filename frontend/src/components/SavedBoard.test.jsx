import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SavedBoard from "./SavedBoard";

const okJson = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });

const OUTFITS = [
  { id: 1, image_filename: "boho_beach_3.jpg", caption: "Beach day", occasion: "brunch", weather: "warm" },
  { id: 2, image_filename: "minimalist_0.jpg", caption: "Clean lines", occasion: null, weather: null },
];

test("lists saved looks for the signed-in user", async () => {
  fetch.mockReturnValueOnce(okJson({ outfits: OUTFITS }));
  render(<SavedBoard firebaseUid="u 1" />);
  expect(await screen.findByText("Beach day")).toBeInTheDocument();
  expect(screen.getByText("Clean lines")).toBeInTheDocument();
  expect(screen.getByText("2 looks")).toBeInTheDocument();
  expect(screen.getByText("brunch · warm")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("http://localhost:8001/users/u%201/outfits");
});

test("uses the singular for one look", async () => {
  fetch.mockReturnValueOnce(okJson({ outfits: [OUTFITS[0]] }));
  render(<SavedBoard firebaseUid="u1" />);
  expect(await screen.findByText("1 look")).toBeInTheDocument();
});

test("shows an empty state that links back to Discover", async () => {
  fetch.mockReturnValueOnce(okJson({ detail: "User not found" }, 404));
  const onDiscover = jest.fn();
  render(<SavedBoard firebaseUid="new-user" onDiscover={onDiscover} />);
  expect(await screen.findByText("No saved looks yet.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Find looks" }));
  expect(onDiscover).toHaveBeenCalled();
});

test("reports a load failure", async () => {
  fetch.mockReturnValueOnce(okJson({}, 500));
  render(<SavedBoard firebaseUid="u1" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not load your saved looks");
  expect(screen.queryByText("No saved looks yet.")).not.toBeInTheDocument();
});

test("does nothing without a signed-in user", () => {
  render(<SavedBoard firebaseUid={undefined} />);
  expect(fetch).not.toHaveBeenCalled();
});

test("removes a look optimistically", async () => {
  fetch.mockReturnValueOnce(okJson({ outfits: OUTFITS })).mockReturnValueOnce(okJson({ deleted: true }));
  render(<SavedBoard firebaseUid="u1" />);
  await screen.findByText("Beach day");
  fireEvent.click(screen.getAllByRole("button", { name: "Remove saved look" })[0]);
  expect(screen.queryByText("Beach day")).not.toBeInTheDocument();
  expect(fetch).toHaveBeenLastCalledWith("http://localhost:8001/users/outfits/1?firebase_uid=u1", { method: "DELETE" });
  expect(screen.getByText("1 look")).toBeInTheDocument();
});

test("restores the look if the delete fails", async () => {
  fetch.mockReturnValueOnce(okJson({ outfits: OUTFITS })).mockReturnValueOnce(okJson({}, 500));
  render(<SavedBoard firebaseUid="u1" />);
  await screen.findByText("Beach day");
  fireEvent.click(screen.getAllByRole("button", { name: "Remove saved look" })[0]);
  await waitFor(() => expect(screen.getByText("Beach day")).toBeInTheDocument());
  expect(screen.getByRole("alert")).toHaveTextContent("Could not remove that look.");
});

test("shows a loading state until the request resolves", async () => {
  let resolve;
  fetch.mockReturnValueOnce(new Promise(r => { resolve = r; }));
  render(<SavedBoard firebaseUid="u1" />);
  expect(screen.getByText("Loading...")).toBeInTheDocument();
  expect(screen.queryByText("No saved looks yet.")).not.toBeInTheDocument();
  expect(screen.queryByRole("list")).not.toBeInTheDocument();
  resolve({ ok: true, status: 200, json: () => Promise.resolve({ outfits: [] }) });
  expect(await screen.findByText("0 looks")).toBeInTheDocument();
  expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
});

test("handles a response without an outfits array", async () => {
  fetch.mockReturnValueOnce(okJson({}));
  render(<SavedBoard firebaseUid="u1" />);
  expect(await screen.findByText("No saved looks yet.")).toBeInTheDocument();
  expect(screen.queryByRole("list")).not.toBeInTheDocument();
});

test("falls back to generic alt text and shows a single context field", async () => {
  fetch.mockReturnValueOnce(okJson({ outfits: [{ id: 9, image_filename: "a.jpg", caption: null, occasion: null, weather: "rainy" }] }));
  render(<SavedBoard firebaseUid="u1" />);
  expect(await screen.findByAltText("Saved look")).toBeInTheDocument();
  expect(screen.getByText("rainy")).toBeInTheDocument();
});

test("omits the context line when neither occasion nor weather is known", async () => {
  fetch.mockReturnValueOnce(okJson({ outfits: [OUTFITS[1]] }));
  const { container } = render(<SavedBoard firebaseUid="u1" />);
  await screen.findByText("Clean lines");
  expect(container.querySelectorAll("li p")).toHaveLength(1);
});

test("a network failure on load shows the error, not the empty state", async () => {
  fetch.mockReturnValueOnce(Promise.reject(new Error("offline")));
  render(<SavedBoard firebaseUid="u1" />);
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(screen.queryByText("No saved looks yet.")).not.toBeInTheDocument();
});
