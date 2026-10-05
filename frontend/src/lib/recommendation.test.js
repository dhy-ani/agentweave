import {
  EMPTY_FORM, missingFields, buildPrompt, buildRecommendationRequest, nextIndex, isLastCard,
} from "./recommendation";

const FULL = { gender: "woman", weather: "warm", occasion: "brunch", location: "cafe", occupation: "designer" };

describe("missingFields", () => {
  test("lists every field of an empty form with readable labels", () => {
    expect(missingFields(EMPTY_FORM)).toEqual(["gender expression", "weather", "occasion", "location", "occupation"]);
  });

  test("treats whitespace-only and missing values as missing", () => {
    expect(missingFields({ ...FULL, occupation: "   " })).toEqual(["occupation"]);
    expect(missingFields({ ...FULL, weather: undefined })).toEqual(["weather"]);
  });

  test("returns nothing for a complete form", () => {
    expect(missingFields(FULL)).toEqual([]);
  });
});

describe("buildPrompt", () => {
  test("describes the user, occasion and setting", () => {
    expect(buildPrompt(FULL, "hourglass")).toBe(
      "A woman with a hourglass body shape wearing a stylish outfit for brunch in warm weather at the cafe. They work as a designer."
    );
  });

  test("humanises snake_case body shapes and trims the occupation", () => {
    const p = buildPrompt({ ...FULL, occupation: "  nurse " }, "inverted_triangle");
    expect(p).toContain("inverted triangle body shape");
    expect(p).toMatch(/They work as a nurse\.$/);
  });

  test("falls back to a balanced shape when body type is unknown", () => {
    expect(buildPrompt(FULL, null)).toContain("a balanced body shape");
  });
});

test("buildRecommendationRequest matches the /stylegenie/trend_vector contract", () => {
  expect(buildRecommendationRequest(FULL, "pear")).toEqual({
    prompt: buildPrompt(FULL, "pear"),
    gender: "woman",
    body_type: "pear",
    weather: "warm",
    occasion: "brunch",
  });
});

describe("nextIndex", () => {
  test("pass and like advance to the next card", () => {
    expect(nextIndex("left", 0, 5)).toBe(1);
    expect(nextIndex("right", 3, 5)).toBe(4);
  });

  test("save keeps the current card", () => {
    expect(nextIndex("up", 2, 5)).toBe(2);
  });

  test("never moves past the last card", () => {
    expect(nextIndex("right", 4, 5)).toBe(4);
    expect(nextIndex("left", 0, 1)).toBe(0);
  });

  test("handles an empty deck", () => {
    expect(nextIndex("right", 0, 0)).toBe(0);
  });
});

describe("isLastCard", () => {
  test("is true only on the final card of a non-empty deck", () => {
    expect(isLastCard(4, 5)).toBe(true);
    expect(isLastCard(3, 5)).toBe(false);
    expect(isLastCard(0, 1)).toBe(true);
    expect(isLastCard(0, 0)).toBe(false);
  });
});
