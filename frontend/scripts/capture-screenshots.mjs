// Captures README screenshots of the running app.
// Prerequisites: backend on :8001, `npm run emulators`, and the frontend
// started with REACT_APP_USE_AUTH_EMULATOR=true (default URL below).
// Usage: node scripts/capture-screenshots.mjs [appUrl] [chromePath]
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import path from "node:path";

const APP = process.argv[2] || "http://localhost:3100";
const API = process.env.API_URL || "http://localhost:8001";
const CHROME = process.argv[3] || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const OUT = path.resolve("..", "docs", "images");
const EMAIL = "demo@agentweave.test";
const PASSWORD = "weave-demo-2026";

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
const shot = async (name) => {
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(OUT, `${name}.png`) });
  console.log("saved", name);
};

await page.goto(`${APP}/#/signup`);
await page.getByPlaceholder("Email").fill(EMAIL);
await page.getByPlaceholder("Password").fill(PASSWORD);
await shot("01-sign-up");
await page.getByRole("button", { name: "Create account" }).click();
if (!(await page.getByText("Start with your shape").isVisible({ timeout: 4000 }).catch(() => false))) {
  await page.goto(`${APP}/#/login`);
  await page.getByPlaceholder("Email").fill(EMAIL);
  await page.getByPlaceholder("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
}
await page.getByText("Start with your shape").waitFor();
await shot("02-body-photo");

const photo = await (await fetch(`${API}/images/boho_beach_3.jpg`)).arrayBuffer();
await page.setInputFiles("#body-photo", { name: "me.jpg", mimeType: "image/jpeg", buffer: Buffer.from(photo) });
await page.getByRole("button", { name: "Analyze body shape" }).click();
await page.getByText("Tell us about your day").waitFor({ timeout: 30000 });
for (const chip of ["woman", "warm", "brunch", "beach"]) await page.getByRole("button", { name: chip, exact: true }).click();
await page.getByLabel("Occupation").fill("designer");
await shot("03-preferences");

await page.getByRole("button", { name: /get my outfit/i }).click();
await page.getByText(/Look 1 of/).waitFor({ timeout: 30000 });
await page.getByText(/Look 1 of/).scrollIntoViewIfNeeded();
await shot("04-swipe-deck");

await page.getByRole("button", { name: "Save", exact: true }).click();
await page.getByRole("status").waitFor();
await page.getByRole("button", { name: "Like", exact: true }).click();
await page.getByRole("button", { name: /shop this look/i }).scrollIntoViewIfNeeded();
await shot("05-after-like");

const nav = page.getByRole("navigation", { name: "Primary" }).last();
await nav.getByRole("button", { name: /saved/i }).click();
await page.getByText("Saved looks").waitFor();
await shot("06-saved-board");

await nav.getByRole("button", { name: /shop/i }).click();
await page.getByRole("button", { name: /find this look online/i }).click();
await page.getByRole("button", { name: /shop on/i }).first().waitFor({ timeout: 30000 });
await shot("07-shop");

await nav.getByRole("button", { name: /closet/i }).click();
await page.getByText("My closet").waitFor();
await shot("08-closet");

await browser.close();
