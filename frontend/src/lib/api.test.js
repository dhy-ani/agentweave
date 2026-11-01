import { apiRequest, ApiError } from "./api";

let mockCurrentUser = null;
jest.mock("../firebase", () => ({
  get auth() {
    return { currentUser: mockCurrentUser };
  },
}));

const reply = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });

beforeEach(() => {
  mockCurrentUser = null;
});

test("GET is the default and returns the parsed body", async () => {
  fetch.mockReturnValueOnce(reply({ ok: 1 }));
  await expect(apiRequest("/health")).resolves.toEqual({ ok: 1 });
  expect(fetch).toHaveBeenCalledWith("http://localhost:8001/health", { method: "GET", headers: {}, body: undefined });
});

test("JSON bodies are serialised with a content type", async () => {
  fetch.mockReturnValueOnce(reply({}));
  await apiRequest("/x", { method: "POST", json: { a: 1 } });
  expect(fetch).toHaveBeenCalledWith("http://localhost:8001/x",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: '{"a":1}' });
});

test("form bodies are passed through untouched", async () => {
  const fd = new FormData();
  fetch.mockReturnValueOnce(reply({}));
  await apiRequest("/x", { method: "POST", body: fd });
  expect(fetch.mock.calls[0][1]).toEqual({ method: "POST", headers: {}, body: fd });
});

test("authenticated calls send the Firebase ID token", async () => {
  mockCurrentUser = { getIdToken: jest.fn(() => Promise.resolve("tok-123")) };
  fetch.mockReturnValueOnce(reply({}));
  await apiRequest("/closet/items", { method: "POST", body: "b", authenticated: true });
  expect(fetch.mock.calls[0][1].headers).toEqual({ Authorization: "Bearer tok-123" });
});

test("authenticated calls without a user fail before reaching the network", async () => {
  await expect(apiRequest("/closet/items", { authenticated: true })).rejects.toMatchObject({ status: 401 });
  expect(fetch).not.toHaveBeenCalled();
});

test("error responses become ApiError with the server's detail", async () => {
  fetch.mockReturnValueOnce(reply({ detail: "Image too large" }, 413));
  const err = await apiRequest("/analyze-body").catch((e) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err.status).toBe(413);
  expect(err.message).toBe("Image too large");
});

test("errors without a string detail get a generic message", async () => {
  fetch.mockReturnValueOnce(reply({ detail: [{ msg: "x" }] }, 422));
  await expect(apiRequest("/x")).rejects.toThrow("Request failed (HTTP 422).");
  fetch.mockReturnValueOnce(Promise.resolve({ ok: false, status: 502, json: () => Promise.reject(new Error("not json")) }));
  await expect(apiRequest("/x")).rejects.toThrow("Request failed (HTTP 502).");
});
