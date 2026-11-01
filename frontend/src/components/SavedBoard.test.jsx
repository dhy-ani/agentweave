import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import SavedBoard from "./SavedBoard";

jest.mock("../data/userData", () => ({ subscribeSavedLooks: jest.fn(), deleteLook: jest.fn() }));
const data = () => require("../data/userData");

const LOOKS = [
  { id: "a", image: "boho_beach_3.jpg", caption: "Beach day", occasion: "brunch", weather: "warm" },
  { id: "b", image: "minimalist_0.jpg", caption: "Clean lines", occasion: null, weather: null },
];

// Captures the subscription callbacks so tests can push snapshots.
let push;
let fail;
beforeEach(() => {
  push = undefined;
  fail = undefined;
  data().subscribeSavedLooks.mockImplementation((uid, onData, onError) => {
    push = onData;
    fail = onError;
    return jest.fn();
  });
  data().deleteLook.mockResolvedValue(undefined);
});

test("subscribes to the signed-in user's looks and lists them", () => {
  render(<SavedBoard firebaseUid="u1" />);
  expect(data().subscribeSavedLooks).toHaveBeenCalledWith("u1", expect.any(Function), expect.any(Function));
  act(() => push(LOOKS));
  expect(screen.getByText("Beach day")).toBeInTheDocument();
  expect(screen.getByText("Clean lines")).toBeInTheDocument();
  expect(screen.getByText("2 looks")).toBeInTheDocument();
  expect(screen.getByText("brunch · warm")).toBeInTheDocument();
  expect(screen.getAllByRole("img")[0]).toHaveAttribute("src", "http://localhost:8001/images/boho_beach_3.jpg");
});

test("shows a loading state until the first snapshot", () => {
  render(<SavedBoard firebaseUid="u1" />);
  expect(screen.getByText("Loading...")).toBeInTheDocument();
  expect(screen.queryByText("No saved looks yet.")).not.toBeInTheDocument();
  act(() => push([]));
  expect(screen.getByText("0 looks")).toBeInTheDocument();
  expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
});

test("uses the singular for one look", () => {
  render(<SavedBoard firebaseUid="u1" />);
  act(() => push([LOOKS[0]]));
  expect(screen.getByText("1 look")).toBeInTheDocument();
});

test("updates live when another tab saves a look", () => {
  render(<SavedBoard firebaseUid="u1" />);
  act(() => push([LOOKS[0]]));
  act(() => push(LOOKS));
  expect(screen.getByText("Clean lines")).toBeInTheDocument();
});

test("shows an empty state that links back to Discover", () => {
  const onDiscover = jest.fn();
  render(<SavedBoard firebaseUid="u1" onDiscover={onDiscover} />);
  act(() => push([]));
  fireEvent.click(screen.getByRole("button", { name: "Find looks" }));
  expect(onDiscover).toHaveBeenCalled();
});

test("reports a load failure instead of an empty board", () => {
  render(<SavedBoard firebaseUid="u1" />);
  act(() => fail(new Error("permission-denied")));
  expect(screen.getByRole("alert")).toHaveTextContent("Could not load your saved looks");
  expect(screen.queryByText("No saved looks yet.")).not.toBeInTheDocument();
});

test("does nothing without a signed-in user", () => {
  render(<SavedBoard firebaseUid={undefined} />);
  expect(data().subscribeSavedLooks).not.toHaveBeenCalled();
  expect(screen.getByText("0 looks")).toBeInTheDocument();
});

test("unsubscribes when unmounted", () => {
  const { unmount } = render(<SavedBoard firebaseUid="u1" />);
  const unsubscribe = data().subscribeSavedLooks.mock.results[0].value;
  unmount();
  expect(unsubscribe).toHaveBeenCalled();
});

test("removing a look deletes it from the user's board", async () => {
  render(<SavedBoard firebaseUid="u1" />);
  act(() => push(LOOKS));
  fireEvent.click(screen.getAllByRole("button", { name: "Remove saved look" })[0]);
  await waitFor(() => expect(data().deleteLook).toHaveBeenCalledWith("u1", "a"));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("a failed delete is reported", async () => {
  data().deleteLook.mockRejectedValueOnce(new Error("offline"));
  render(<SavedBoard firebaseUid="u1" />);
  act(() => push(LOOKS));
  fireEvent.click(screen.getAllByRole("button", { name: "Remove saved look" })[0]);
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not remove that look.");
});

test("falls back to generic alt text and shows a single context field", () => {
  render(<SavedBoard firebaseUid="u1" />);
  act(() => push([{ id: "c", image: "a.jpg", caption: null, occasion: null, weather: "rainy" }]));
  expect(screen.getByAltText("Saved look")).toBeInTheDocument();
  expect(screen.getByText("rainy")).toBeInTheDocument();
});

test("omits the context line when neither occasion nor weather is known", () => {
  const { container } = render(<SavedBoard firebaseUid="u1" />);
  act(() => push([LOOKS[1]]));
  expect(container.querySelectorAll("li p")).toHaveLength(1);
});
