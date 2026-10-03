export const OCCASIONS = ["casual", "work", "date night", "formal", "gym", "brunch", "party", "outdoor"];
export const WEATHERS = ["hot", "warm", "mild", "cool", "cold", "rainy", "snowy"];
export const LOCATIONS = ["city", "beach", "mountains", "office", "cafe", "club", "park", "home"];
export const GENDERS = ["woman", "man", "non-binary"];

export const EMPTY_FORM = { gender: "", weather: "", occasion: "", location: "", occupation: "" };

const FIELD_LABELS = {
  gender: "gender expression",
  weather: "weather",
  occasion: "occasion",
  location: "location",
  occupation: "occupation",
};

export function missingFields(form) {
  return Object.keys(EMPTY_FORM)
    .filter(k => !String(form[k] ?? "").trim())
    .map(k => FIELD_LABELS[k]);
}

export function buildPrompt(form, bodyType) {
  const shape = bodyType ? bodyType.replace(/_/g, " ") : "balanced";
  return (
    `A ${form.gender} with a ${shape} body shape wearing a stylish outfit for ` +
    `${form.occasion} in ${form.weather} weather at the ${form.location}. ` +
    `They work as a ${form.occupation.trim()}.`
  );
}

export function buildRecommendationRequest(form, bodyType) {
  return {
    prompt: buildPrompt(form, bodyType),
    gender: form.gender,
    body_type: bodyType,
    weather: form.weather,
    occasion: form.occasion,
  };
}

// Pass and like advance the deck; save keeps the card so the user can still
// like or pass on it afterwards.
export function nextIndex(dir, index, total) {
  if (dir === "up") return index;
  return Math.min(index + 1, Math.max(total - 1, 0));
}

export function isLastCard(index, total) {
  return total > 0 && index >= total - 1;
}
