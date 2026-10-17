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
