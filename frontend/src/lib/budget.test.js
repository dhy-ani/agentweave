import { PRESETS, PRICE_CEILING, nextMin, nextMax, formatBudget, isActivePreset } from "./budget";

describe("slider guards", () => {
  test("a new minimum must stay strictly below the maximum", () => {
    expect(nextMin(40, 100)).toBe(40);
    expect(nextMin(0, 100)).toBe(0);
    expect(nextMin(100, 100)).toBeNull();
    expect(nextMin(120, 100)).toBeNull();
  });

  test("a new maximum must stay strictly above the minimum", () => {
    expect(nextMax(150, 100)).toBe(150);
    expect(nextMax(100, 100)).toBeNull();
    expect(nextMax(80, 100)).toBeNull();
  });
});

describe("formatBudget", () => {
  test("shows a plain range below the ceiling", () => {
    expect(formatBudget(30, 120)).toBe("$30 - $120");
    expect(formatBudget(0, PRICE_CEILING - 1)).toBe("$0 - $499");
  });

  test("marks the top of the scale as open-ended", () => {
    expect(formatBudget(200, PRICE_CEILING)).toBe("$200 - $500+");
  });
});

describe("presets", () => {
  test("are ordered, valid ranges within the slider bounds", () => {
    for (const p of PRESETS) {
      expect(p.min).toBeLessThan(p.max);
      expect(p.min).toBeGreaterThanOrEqual(0);
      expect(p.max).toBeLessThanOrEqual(PRICE_CEILING);
    }
    expect(PRESETS.map(p => p.label)).toEqual(["Under $50", "$30-$100", "$50-$200", "$100-$300", "$200+"]);
  });

  test("a preset is active only when both bounds match", () => {
    const p = PRESETS[1];
    expect(isActivePreset(p, 30, 100)).toBe(true);
    expect(isActivePreset(p, 30, 99)).toBe(false);
    expect(isActivePreset(p, 31, 100)).toBe(false);
  });
});
