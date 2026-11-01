// Firebase Auth error codes -> messages a user can act on. Unknown codes still
// show the code so a broken configuration is diagnosable instead of looking
// like a wrong password.
const MESSAGES = {
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/wrong-password": "Incorrect email or password.",
  "auth/user-not-found": "No account uses this email. Create one below.",
  "auth/invalid-email": "That email address doesn't look right.",
  "auth/missing-password": "Enter your password.",
  "auth/user-disabled": "This account has been disabled.",
  "auth/too-many-requests": "Too many attempts. Wait a minute and try again.",
  "auth/email-already-in-use": "An account with this email already exists. Sign in instead.",
  "auth/weak-password": "Password must be at least 6 characters.",
  "auth/network-request-failed": "Network error. Check your connection and try again.",
  "auth/popup-closed-by-user": "The Google window was closed before sign-in finished.",
  "auth/cancelled-popup-request": "The Google window was closed before sign-in finished.",
  "auth/unauthorized-domain": "This site isn't authorised for sign-in yet. Add it under Firebase Authentication > Settings > Authorized domains.",
  "auth/operation-not-allowed": "This sign-in method is turned off in the Firebase console.",
  "auth/invalid-api-key": "The app's Firebase configuration is missing or invalid.",
};

export function authErrorMessage(error) {
  const code = error?.code;
  if (code && MESSAGES[code]) return MESSAGES[code];
  return code ? `Sign-in failed (${code}).` : "Sign-in failed. Please try again.";
}

// Errors where the popup could not be used at all, so a full-page redirect is
// the only remaining option.
export const POPUP_UNAVAILABLE = new Set([
  "auth/popup-blocked",
  "auth/operation-not-supported-in-this-environment",
]);

// Dismissing the Google window is not an error worth shouting about.
export const SILENT_ERRORS = new Set(["auth/popup-closed-by-user", "auth/cancelled-popup-request"]);
