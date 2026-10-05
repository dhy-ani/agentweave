export const SWIPE_THRESHOLD = 80;

// Decides which action a finished drag represents. Short drags snap back so a
// tap or small wobble on the card is never read as a swipe.
export function swipeDirection(mx, my, threshold = SWIPE_THRESHOLD) {
  const absX = Math.abs(mx);
  const absY = Math.abs(my);
  if (absX >= absY && absX >= threshold) return mx > 0 ? "right" : "left";
  if (absY > absX && my <= -threshold) return "up";
  return "";
}

export const SWIPE_VECTORS = {
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
  up: { x: 0, y: -1 },
};

export const SWIPE_OUT_MS = 280;
export const FLY_OUT_DISTANCE = 800;

// While dragging the card follows the pointer and tilts with horizontal
// movement; once a direction is chosen it flies off-screen that way.
export function cardTransform(offset, dir) {
  if (dir) {
    const v = SWIPE_VECTORS[dir];
    return `translate(${v.x * FLY_OUT_DISTANCE}px, ${v.y * FLY_OUT_DISTANCE}px) rotate(${v.x * 25}deg)`;
  }
  return `translate(${offset.x}px, ${offset.y}px) rotate(${offset.x / 12}deg)`;
}

export const SWIPE_LABELS = {
  left: { emoji: "✖️", text: "PASS" },
  right: { emoji: "❤️", text: "LIKE" },
};
