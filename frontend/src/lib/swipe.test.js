import { swipeDirection, cardTransform, SWIPE_THRESHOLD, SWIPE_VECTORS, SWIPE_LABELS, SWIPE_OUT_MS, FLY_OUT_DISTANCE } from "./swipe";

describe("swipeDirection", () => {
  test("short drags snap back instead of swiping", () => {
    expect(swipeDirection(0, 0)).toBe("");
    expect(swipeDirection(SWIPE_THRESHOLD - 1, 0)).toBe("");
    expect(swipeDirection(-(SWIPE_THRESHOLD - 1), 0)).toBe("");
    expect(swipeDirection(0, -(SWIPE_THRESHOLD - 1))).toBe("");
  });

  test("horizontal drags past the threshold swipe left or right", () => {
    expect(swipeDirection(SWIPE_THRESHOLD, 0)).toBe("right");
    expect(swipeDirection(-SWIPE_THRESHOLD, 0)).toBe("left");
    expect(swipeDirection(300, 120)).toBe("right");
    expect(swipeDirection(-300, -120)).toBe("left");
  });

  test("a diagonal with equal components counts as horizontal", () => {
    expect(swipeDirection(100, -100)).toBe("right");
    expect(swipeDirection(-100, -100)).toBe("left");
  });

  test("dragging up past the threshold saves", () => {
    expect(swipeDirection(0, -SWIPE_THRESHOLD)).toBe("up");
    expect(swipeDirection(30, -200)).toBe("up");
  });

  test("a mostly-vertical drag saves even when it also moved sideways past the threshold", () => {
    expect(swipeDirection(100, -200)).toBe("up");
    expect(swipeDirection(-150, -300)).toBe("up");
  });

  test("an upward drag short of the threshold does nothing", () => {
    expect(swipeDirection(10, -(SWIPE_THRESHOLD - 1))).toBe("");
    expect(swipeDirection(0, 79)).toBe("");
  });

  test("dragging down never triggers an action", () => {
    expect(swipeDirection(0, 300)).toBe("");
    expect(swipeDirection(20, 120)).toBe("");
  });

  test("threshold is configurable", () => {
    expect(swipeDirection(50, 0, 40)).toBe("right");
    expect(swipeDirection(50, 0, 60)).toBe("");
  });
});

test("swipe vectors point the card off-screen in the swipe direction", () => {
  expect(SWIPE_VECTORS.left).toEqual({ x: -1, y: 0 });
  expect(SWIPE_VECTORS.right).toEqual({ x: 1, y: 0 });
  expect(SWIPE_VECTORS.up).toEqual({ x: 0, y: -1 });
});

test("only pass and like carry emoji stamps", () => {
  expect(SWIPE_LABELS.left).toEqual({ emoji: "✖️", text: "PASS" });
  expect(SWIPE_LABELS.right).toEqual({ emoji: "❤️", text: "LIKE" });
  expect(SWIPE_LABELS.up).toBeUndefined();
});

describe("cardTransform", () => {
  test("follows the pointer and tilts with horizontal drag", () => {
    expect(cardTransform({ x: 120, y: -30 }, "")).toBe("translate(120px, -30px) rotate(10deg)");
    expect(cardTransform({ x: 0, y: 0 }, "")).toBe("translate(0px, 0px) rotate(0deg)");
  });

  test("flies off-screen in the chosen direction, ignoring the drag offset", () => {
    expect(cardTransform({ x: 5, y: 5 }, "left")).toBe(`translate(${-FLY_OUT_DISTANCE}px, 0px) rotate(-25deg)`);
    expect(cardTransform({ x: 5, y: 5 }, "right")).toBe(`translate(${FLY_OUT_DISTANCE}px, 0px) rotate(25deg)`);
    expect(cardTransform({ x: 5, y: 5 }, "up")).toBe(`translate(0px, ${-FLY_OUT_DISTANCE}px) rotate(0deg)`);
  });

  test("fly-out runs long enough to see but stays snappy", () => {
    expect(SWIPE_OUT_MS).toBeGreaterThanOrEqual(150);
    expect(SWIPE_OUT_MS).toBeLessThanOrEqual(500);
  });
});
