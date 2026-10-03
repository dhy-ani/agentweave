import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ShoppingPanel from "./ShoppingPanel";

const brand = (name, extra = {}) => ({
  brand: name, tier: "Budget", item: "Maxi dress", est_price: 45, price_range: "$20-$80",
  within_budget: true, search_url: `https://shop.example/${name}`, relevance: 0.6, style_note: "Good value", ...extra,
});

const RESPONSE = {
  within_budget: [brand("H&M"), brand("Zara")],
  outside_budget: [brand("Reformation", { tier: "Premium", est_price: 220 })],
  price_range: { min: 0, max: 150 },
};

const reply = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });

test("asks for a recommendation first when there is no look to shop", () => {
  render(<ShoppingPanel styleCaption="" />);
  expect(screen.getByText(/get an outfit recommendation first/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /find this look online/i })).toBeDisabled();
});

test("presets update the budget label", () => {
  render(<ShoppingPanel styleCaption="boho dress" />);
  expect(screen.getByText("$0 - $150")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "$100-$300" }));
  expect(screen.getByText("$100 - $300")).toBeInTheDocument();
});

test("sliders cannot cross each other", () => {
  render(<ShoppingPanel styleCaption="boho dress" />);
  const [minSlider, maxSlider] = screen.getAllByRole("slider");
  fireEvent.change(minSlider, { target: { value: "200" } });
  expect(screen.getByText("$0 - $150")).toBeInTheDocument();
  fireEvent.change(maxSlider, { target: { value: "500" } });
  expect(screen.getByText("$0 - $500+")).toBeInTheDocument();
});

test("fetches in-budget and stretch picks and opens the retailer", async () => {
  fetch.mockReturnValueOnce(reply(RESPONSE)).mockReturnValueOnce(reply({ ok: true }));
  const open = jest.spyOn(window, "open").mockImplementation(() => null);
  render(<ShoppingPanel styleCaption="boho dress" occasion="brunch" firebaseUid="u1" />);
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));

  expect(await screen.findByText("H&M")).toBeInTheDocument();
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({ style_caption: "boho dress", occasion: "brunch", price_min: 0, price_max: 150 });

  const cta = screen.getByRole("button", { name: /shop on h&m/i });
  expect(cta).toHaveTextContent("🛒");
  fireEvent.click(cta);
  await waitFor(() => expect(open).toHaveBeenCalledWith("https://shop.example/H&M", "_blank", "noopener,noreferrer"));
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({ firebase_uid: "u1", brand: "H&M" });

  fireEvent.click(screen.getByRole("button", { name: /stretch picks/i }));
  expect(screen.getByText("Reformation")).toBeInTheDocument();
  expect(screen.getByText("STRETCH")).toBeInTheDocument();
});

test("shows an error when the shopping service fails", async () => {
  fetch.mockReturnValueOnce(reply({}, 500));
  render(<ShoppingPanel styleCaption="boho dress" />);
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not load store suggestions");
});

const bodyOf = (call) => JSON.parse(call[1].body);

test("treats a whitespace-only caption as missing", () => {
  render(<ShoppingPanel styleCaption="   " />);
  expect(screen.getByRole("button", { name: /find this look online/i })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));
  expect(fetch).not.toHaveBeenCalled();
});

test("sends defaults for missing context and a JSON content type", async () => {
  fetch.mockReturnValueOnce(reply(RESPONSE));
  render(<ShoppingPanel styleCaption="boho dress" />);
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));
  await screen.findByText("H&M");
  const [url, opts] = fetch.mock.calls[0];
  expect(url).toBe("http://localhost:8001/shopping/suggest");
  expect(opts.method).toBe("POST");
  expect(opts.headers).toEqual({ "Content-Type": "application/json" });
  expect(bodyOf(fetch.mock.calls[0])).toEqual({
    style_caption: "boho dress", occasion: "casual", body_type: "", gender: "", price_min: 0, price_max: 150,
  });
});

test("passes body type, gender and the chosen budget through", async () => {
  fetch.mockReturnValueOnce(reply(RESPONSE));
  render(<ShoppingPanel styleCaption="boho dress" bodyType="pear" gender="woman" />);
  fireEvent.click(screen.getByRole("button", { name: "$50-$200" }));
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));
  await screen.findByText("H&M");
  expect(bodyOf(fetch.mock.calls[0])).toMatchObject({ body_type: "pear", gender: "woman", price_min: 50, price_max: 200 });
});

test("a valid slider move updates the range", () => {
  render(<ShoppingPanel styleCaption="boho dress" />);
  const [minSlider, maxSlider] = screen.getAllByRole("slider");
  fireEvent.change(minSlider, { target: { value: "40" } });
  expect(screen.getByText("$40 - $150")).toBeInTheDocument();
  fireEvent.change(maxSlider, { target: { value: "30" } });
  expect(screen.getByText("$40 - $150")).toBeInTheDocument();
});

test("shows a loading label while stores are fetched", async () => {
  let resolve;
  fetch.mockReturnValueOnce(new Promise(r => { resolve = r; }));
  render(<ShoppingPanel styleCaption="boho dress" />);
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));
  expect(screen.getByRole("button", { name: /finding stores/i })).toBeDisabled();
  resolve({ ok: true, status: 200, json: () => Promise.resolve(RESPONSE) });
  expect(await screen.findByText("H&M")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /find this look online/i })).toBeEnabled();
});

test("does not record clicks for signed-out users, and sends a null occasion", async () => {
  const open = jest.spyOn(window, "open").mockImplementation(() => null);
  fetch.mockReturnValueOnce(reply(RESPONSE)).mockReturnValue(reply({ ok: true }));
  const { unmount } = render(<ShoppingPanel styleCaption="boho dress" />);
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));
  fireEvent.click(await screen.findByRole("button", { name: /shop on zara/i }));
  await waitFor(() => expect(open).toHaveBeenCalled());
  expect(fetch).toHaveBeenCalledTimes(1);
  unmount();

  fetch.mockClear();
  fetch.mockReturnValueOnce(reply(RESPONSE)).mockReturnValue(reply({ ok: true }));
  render(<ShoppingPanel styleCaption="boho dress" firebaseUid="u1" />);
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));
  fireEvent.click(await screen.findByRole("button", { name: /shop on zara/i }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  const [url, opts] = fetch.mock.calls[1];
  expect(url).toBe("http://localhost:8001/users/shopping/click");
  expect(opts.method).toBe("POST");
  expect(opts.headers).toEqual({ "Content-Type": "application/json" });
  expect(bodyOf(fetch.mock.calls[1])).toEqual({ firebase_uid: "u1", brand: "Zara", item: "Maxi dress", tier: "Budget", est_price: 45, occasion: null });
});

test("empty in-budget results point to stretch picks, and back", async () => {
  fetch.mockReturnValueOnce(reply({ ...RESPONSE, within_budget: [] }));
  render(<ShoppingPanel styleCaption="boho dress" />);
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));
  expect(await screen.findByText(/no brands fall within this budget/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "See stretch picks" }));
  expect(screen.getByText("Reformation")).toBeInTheDocument();
  expect(screen.queryByText(/no brands fall within/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /in budget/i }));
  expect(screen.queryByText("Reformation")).not.toBeInTheDocument();
  expect(screen.getByText(/no brands fall within this budget/i)).toBeInTheDocument();
});

test("empty stretch picks say every brand fits", async () => {
  fetch.mockReturnValueOnce(reply({ ...RESPONSE, outside_budget: [] }));
  render(<ShoppingPanel styleCaption="boho dress" />);
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));
  await screen.findByText("H&M");
  expect(screen.queryByText(/all brands fit your budget/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /stretch picks/i }));
  expect(screen.getByText(/all brands fit your budget/i)).toBeInTheDocument();
  expect(screen.queryByText("H&M")).not.toBeInTheDocument();
});

test("tabs show counts, unknown tiers fall back gracefully, and the legend lists every tier", async () => {
  fetch.mockReturnValueOnce(reply({ ...RESPONSE, within_budget: [brand("H&M", { tier: "Mystery" })] }));
  render(<ShoppingPanel styleCaption="boho dress" />);
  fireEvent.click(screen.getByRole("button", { name: /find this look online/i }));
  await screen.findByText("H&M");
  expect(screen.getByRole("button", { name: /in budget/i })).toHaveTextContent("(1)");
  expect(screen.getByRole("button", { name: /stretch picks/i })).toHaveTextContent("(1)");
  expect(screen.getByText("Mystery")).toBeInTheDocument();
  expect(screen.queryByText("STRETCH")).not.toBeInTheDocument();
  for (const tier of ["Budget", "Mid-Range", "Premium", "Luxury"]) expect(screen.getAllByText(tier).length).toBeGreaterThan(0);
});
