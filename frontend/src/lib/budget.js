export const PRICE_FLOOR = 0;
export const PRICE_CEILING = 500;

export const PRESETS = [
  { min: 0, max: 50, label: "Under $50" },
  { min: 30, max: 100, label: "$30-$100" },
  { min: 50, max: 200, label: "$50-$200" },
  { min: 100, max: 300, label: "$100-$300" },
  { min: 200, max: 500, label: "$200+" },
];

// Sliders must never cross: a new minimum is rejected unless it stays below
// the current maximum, and vice versa.
export function nextMin(candidate, currentMax) {
  return candidate < currentMax ? candidate : null;
}

export function nextMax(candidate, currentMin) {
  return candidate > currentMin ? candidate : null;
}

export function formatBudget(min, max) {
  return `$${min} - $${max >= PRICE_CEILING ? `${PRICE_CEILING}+` : max}`;
}

export function isActivePreset(preset, min, max) {
  return preset.min === min && preset.max === max;
}
