import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "./LoginPage";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => mockNavigate,
}));
jest.mock("firebase/auth", () => ({
  signInWithEmailAndPassword: jest.fn(),
  signInWithPopup: jest.fn(),
  signInWithRedirect: jest.fn(),
  getRedirectResult: jest.fn(),
  onAuthStateChanged: jest.fn(),
}));
jest.mock("./firebase", () => ({ auth: { name: "auth" }, googleProvider: { name: "google" } }));

const fb = () => require("firebase/auth");
const err = (code) => Object.assign(new Error(code), { code });

// CRA's Jest preset resets mock implementations before each test.
beforeEach(() => {
  mockNavigate.mockReset();
  fb().getRedirectResult.mockResolvedValue(null);
  fb().onAuthStateChanged.mockImplementation(() => () => {});
  fb().signInWithRedirect.mockResolvedValue(undefined);
});

const renderPage = () => render(<MemoryRouter><LoginPage /></MemoryRouter>);
const google = () => screen.getByRole("button", { name: /continue with google/i });

test("Google sign-in uses a popup and goes to the dashboard", async () => {
  fb().signInWithPopup.mockResolvedValue({ user: { uid: "u1" } });
  renderPage();
  fireEvent.click(google());
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/dashboard"));
  expect(fb().signInWithPopup).toHaveBeenCalledWith({ name: "auth" }, { name: "google" });
  expect(fb().signInWithRedirect).not.toHaveBeenCalled();
});

test("a blocked popup falls back to a full-page redirect", async () => {
  fb().signInWithPopup.mockRejectedValue(err("auth/popup-blocked"));
  renderPage();
  fireEvent.click(google());
  await waitFor(() => expect(fb().signInWithRedirect).toHaveBeenCalledWith({ name: "auth" }, { name: "google" }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("closing the Google window shows no error", async () => {
  fb().signInWithPopup.mockRejectedValue(err("auth/popup-closed-by-user"));
  renderPage();
  fireEvent.click(google());
  await waitFor(() => expect(fb().signInWithPopup).toHaveBeenCalled());
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(fb().signInWithRedirect).not.toHaveBeenCalled();
});

test("other Google errors are shown with their cause", async () => {
  fb().signInWithPopup.mockRejectedValue(err("auth/unauthorized-domain"));
  renderPage();
  fireEvent.click(google());
  expect(await screen.findByRole("alert")).toHaveTextContent(/Authorized domains/);
  expect(mockNavigate).not.toHaveBeenCalled();
});

test("email sign-in shows the real reason it failed", async () => {
  fb().signInWithEmailAndPassword.mockRejectedValue(err("auth/network-request-failed"));
  renderPage();
  fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: " a@b.test " } });
  fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "pw" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Network error");
  expect(fb().signInWithEmailAndPassword).toHaveBeenCalledWith({ name: "auth" }, "a@b.test", "pw");
});

test("successful email sign-in goes to the dashboard", async () => {
  fb().signInWithEmailAndPassword.mockResolvedValue({ user: { uid: "u1" } });
  renderPage();
  fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "a@b.test" } });
  fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "pw" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/dashboard"));
});

test("a returning redirect sign-in lands on the dashboard", async () => {
  fb().getRedirectResult.mockResolvedValue({ user: { uid: "u1" } });
  renderPage();
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/dashboard"));
});

test("an already signed-in user skips the login page", async () => {
  fb().onAuthStateChanged.mockImplementation((auth, cb) => { cb({ uid: "u1" }); return () => {}; });
  renderPage();
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/dashboard"));
});

test("the button shows progress while signing in and recovers after a failure", async () => {
  let fail;
  fb().signInWithEmailAndPassword.mockReturnValue(new Promise((_, rej) => { fail = () => rej(err("auth/invalid-credential")); }));
  renderPage();
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("button", { name: "Signing in…" })).toBeDisabled();
  fail();
  expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
  expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  expect(screen.getByPlaceholderText("Email")).toHaveValue("");
  expect(screen.getByPlaceholderText("Password")).toHaveValue("");
});

test("Enter in the email field signs in; other keys don't", async () => {
  fb().signInWithEmailAndPassword.mockResolvedValue({ user: { uid: "u1" } });
  renderPage();
  const email = screen.getByPlaceholderText("Email");
  fireEvent.keyDown(email, { key: "a" });
  expect(fb().signInWithEmailAndPassword).not.toHaveBeenCalled();
  fireEvent.keyDown(email, { key: "Enter" });
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/dashboard"));
});

test("a failed redirect sign-in is reported", async () => {
  fb().getRedirectResult.mockRejectedValue(err("auth/operation-not-allowed"));
  renderPage();
  expect(await screen.findByRole("alert")).toHaveTextContent("turned off");
});

test("a signed-out auth state stays on the page, and the listener is removed on unmount", async () => {
  const unsub = jest.fn();
  fb().onAuthStateChanged.mockImplementation((auth, cb) => { cb(null); return unsub; });
  const { unmount } = renderPage();
  await waitFor(() => expect(fb().onAuthStateChanged).toHaveBeenCalled());
  expect(mockNavigate).not.toHaveBeenCalled();
  unmount();
  expect(unsub).toHaveBeenCalled();
});

test("a Google failure without an error code still shows a message", async () => {
  fb().signInWithPopup.mockRejectedValue(undefined);
  renderPage();
  fireEvent.click(google());
  expect(await screen.findByRole("alert")).toHaveTextContent("Sign-in failed. Please try again.");
  expect(fb().signInWithRedirect).not.toHaveBeenCalled();
});
