import { authErrorMessage, POPUP_UNAVAILABLE, SILENT_ERRORS } from "./authErrors";

test.each([
  ["auth/invalid-credential", "Incorrect email or password."],
  ["auth/user-not-found", "No account uses this email. Create one below."],
  ["auth/email-already-in-use", "An account with this email already exists. Sign in instead."],
  ["auth/weak-password", "Password must be at least 6 characters."],
  ["auth/network-request-failed", "Network error. Check your connection and try again."],
  ["auth/operation-not-allowed", "This sign-in method is turned off in the Firebase console."],
])("%s has a specific message", (code, message) => {
  expect(authErrorMessage({ code })).toBe(message);
});

test("configuration problems name the fix", () => {
  expect(authErrorMessage({ code: "auth/unauthorized-domain" })).toMatch(/Authorized domains/);
});

test("unknown codes are shown rather than hidden", () => {
  expect(authErrorMessage({ code: "auth/internal-error" })).toBe("Sign-in failed (auth/internal-error).");
});

test("errors without a code get a generic message", () => {
  expect(authErrorMessage(new Error("boom"))).toBe("Sign-in failed. Please try again.");
  expect(authErrorMessage(undefined)).toBe("Sign-in failed. Please try again.");
});

test("only a blocked or unsupported popup falls back to redirect", () => {
  expect(POPUP_UNAVAILABLE.has("auth/popup-blocked")).toBe(true);
  expect(POPUP_UNAVAILABLE.has("auth/operation-not-supported-in-this-environment")).toBe(true);
  expect(POPUP_UNAVAILABLE.has("auth/popup-closed-by-user")).toBe(false);
});

test("closing the popup is silent", () => {
  expect(SILENT_ERRORS.has("auth/popup-closed-by-user")).toBe(true);
  expect(SILENT_ERRORS.has("auth/cancelled-popup-request")).toBe(true);
  expect(SILENT_ERRORS.has("auth/popup-blocked")).toBe(false);
});
