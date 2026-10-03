import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import FashionCard, { matchTone } from "./FashionCard";

const props = {
  image: "boho_beach_3.jpg",
  result: "Style match: a woman in a hat and skirt walking on the beach",
  match_score: 82.4,
  future_projection: "Strong match to your style search.",
};

test("renders the look, its match score and the explanation", () => {
  render(<FashionCard {...props} onSwipe={() => {}} />);
  expect(screen.getByRole("img")).toHaveAttribute("src", "http://localhost:8001/images/boho_beach_3.jpg");
  expect(screen.getByText("82%")).toBeInTheDocument();
  expect(screen.getByText("match")).toBeInTheDocument();
  expect(screen.getByText(props.result)).toBeInTheDocument();
  expect(screen.getByText(props.future_projection)).toBeInTheDocument();
});

test("falls back to trendiness_score, then to zero", () => {
  const { rerender } = render(<FashionCard {...props} match_score={undefined} trendiness_score={55} onSwipe={() => {}} />);
  expect(screen.getByText("55%")).toBeInTheDocument();
  rerender(<FashionCard {...props} match_score={undefined} onSwipe={() => {}} />);
  expect(screen.getByText("0%")).toBeInTheDocument();
});

test.each([
  ["Pass", "left"],
  ["Save", "up"],
  ["Like", "right"],
])("tapping %s reports a %s swipe", async (label, dir) => {
  const onSwipe = jest.fn();
  render(<FashionCard {...props} onSwipe={onSwipe} />);
  fireEvent.click(screen.getByRole("button", { name: label }));
  await waitFor(() => expect(onSwipe).toHaveBeenCalledWith(dir));
  expect(onSwipe).toHaveBeenCalledTimes(1);
});

test("pass and like buttons use the swipe emoji; save uses an icon", () => {
  render(<FashionCard {...props} onSwipe={() => {}} />);
  expect(screen.getByRole("button", { name: "Pass" })).toHaveTextContent("✖️");
  expect(screen.getByRole("button", { name: "Like" })).toHaveTextContent("❤️");
  expect(screen.getByRole("button", { name: "Save" }).querySelector("svg")).not.toBeNull();
});

test("matchTone grades scores at 40 and 70", () => {
  expect(matchTone(70)).toBe("text-sage-700");
  expect(matchTone(69.9)).toBe("text-brand-600");
  expect(matchTone(40)).toBe("text-brand-600");
  expect(matchTone(39.9)).toBe("text-muted");
});

describe("drag gestures", () => {
  // jsdom has no `onpointerdown`, so @use-gesture falls back to mouse events,
  // which is also what desktop browsers without pointer events use.
  function drag(el, dx, dy) {
    fireEvent.mouseDown(el, { buttons: 1, clientX: 200, clientY: 300 });
    fireEvent.mouseMove(window, { buttons: 1, clientX: 200 + dx / 2, clientY: 300 + dy / 2 });
    fireEvent.mouseMove(window, { buttons: 1, clientX: 200 + dx, clientY: 300 + dy });
    fireEvent.mouseUp(window, { buttons: 0, clientX: 200 + dx, clientY: 300 + dy });
  }

  const card = () => screen.getByRole("img").closest("div[style]");

  test.each([
    [200, 0, "right"],
    [-200, 0, "left"],
    [10, -200, "up"],
  ])("dragging (%i, %i) swipes %s", async (dx, dy, dir) => {
    const onSwipe = jest.fn();
    render(<FashionCard {...props} onSwipe={onSwipe} />);
    drag(card(), dx, dy);
    await waitFor(() => expect(onSwipe).toHaveBeenCalledWith(dir));
  });

  test("a short drag snaps back without swiping", async () => {
    const onSwipe = jest.fn();
    render(<FashionCard {...props} onSwipe={onSwipe} />);
    drag(card(), 30, 10);
    await new Promise(r => setTimeout(r, 50));
    expect(onSwipe).not.toHaveBeenCalled();
  });
});

test("works without an onSwipe handler", async () => {
  render(<FashionCard {...props} />);
  expect(() => fireEvent.click(screen.getByRole("button", { name: "Like" }))).not.toThrow();
});
