// Smoke tests across the whole cockpit (ROADMAP 6.3.7). Run on desktop and
// phone sizes against a real API with trained models (see playwright.config).
import { expect, test } from "@playwright/test";

const PAGES = [
  ["/", "Score an applicant"],
  ["/portfolio/", "Portfolio risk"],
  ["/validation/", "Model quality"],
  ["/monitoring/", "Stability & drift"],
  ["/governance/", "Fairness & explanations"],
  ["/copilot/", "Risk Copilot"],
  ["/glossary/", "Glossary"],
];

// The guided tour would cover the page on a first visit; mark it as seen.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("cc-tour-done", "1"));
});

for (const [path, title] of PAGES) {
  test(`${title}: loads with data, no errors, no sideways scroll`, async ({ page }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(page.getByRole("status", { name: /^Loading/ })).toHaveCount(0);   // skeletons gone
    await expect(page.locator(".error-state")).toHaveCount(0);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    expect(errors).toEqual([]);
  });
}

test("sample applicants score live, and Apply on a what-if gets a decline approved", async ({ page }) => {
  await page.goto("/");
  const verdict = page.locator(".verdict");

  await page.getByRole("button", { name: "Prime borrower" }).click();
  await expect(verdict).toHaveText(/Approved/);

  await page.getByRole("button", { name: "High-risk borrower" }).click();
  await expect(verdict).toHaveText(/Declined/);
  await expect(page.locator(".reasons li").first()).toBeVisible();

  await page.getByRole("button", { name: "Marginal borrower" }).click();
  await expect(verdict).toHaveText(/Declined/);
  const apply = page.getByRole("button", { name: /^Apply:/ }).first();
  // The what-if search runs after scoring; under parallel test load on a small
  // machine the pair can take several seconds, so allow extra time here.
  await expect(apply).toBeVisible({ timeout: 25_000 });
  await apply.click();
  await expect(verdict).toHaveText(/Approved/);
});

test("changing a slider value re-scores without pressing anything", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Marginal borrower" }).click();
  const verdict = page.locator(".verdict");
  await expect(verdict).toHaveText(/Declined/);
  const fico = page.getByLabel("Credit score (FICO) value");
  await fico.fill("790");
  await expect(verdict).toHaveText(/Approved/);
});

test("clicking a grade bar filters the loan table", async ({ page }) => {
  await page.goto("/portfolio/");
  await expect(page.getByText(/Showing 1–\d+ of 1,000 loans/)).toBeVisible();
  await page.locator(".recharts-wrapper").first().locator(".recharts-bar-rectangle path").nth(5).click();
  await expect(page.getByRole("button", { name: /Remove filter: Grade B/ })).toBeVisible();
  await expect(page.getByText(/filtered from 1,000/)).toBeVisible();
});

test("theme toggle switches to light and survives a reload", async ({ page }) => {
  await page.goto("/glossary/");
  const menu = page.getByRole("button", { name: /Menu/ });
  if (await menu.isVisible()) await menu.click();             // phones: nav is collapsed
  await page.getByRole("button", { name: /Colour theme/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("the tour starts on a first visit and closes with Esc", async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem("cc-tour-done"));   // runs after beforeEach's
  await page.goto("/");
  const card = page.getByRole("dialog");
  await expect(card).toContainText("Step 1 of 8");
  await page.getByRole("button", { name: "Next ›" }).click();
  await expect(card).toContainText("Score an applicant live");
  await page.keyboard.press("Escape");
  await expect(card).toHaveCount(0);
});

test("pinning two applicants compares them side by side", async ({ page }) => {
  await page.goto("/");
  const verdict = page.locator(".verdict");
  const pin = page.getByRole("button", { name: /Pin to compare/ });

  await page.getByRole("button", { name: "Prime borrower" }).click();
  await expect(verdict).toHaveText(/Approved/);
  await pin.click();
  await expect(page.getByRole("button", { name: "✓ Pinned" })).toBeDisabled();

  await page.getByRole("button", { name: "High-risk borrower" }).click();
  await expect(verdict).toHaveText(/Declined/);
  await pin.click();

  const compare = page.locator(".compare");
  await expect(compare.getByRole("columnheader", { name: /Prime borrower/ })).toBeVisible();
  await expect(compare.getByRole("columnheader", { name: /High-risk borrower/ })).toBeVisible();
  await expect(compare.locator("td.best", { hasText: "Approved" })).toBeVisible();

  await compare.getByRole("button", { name: "Load Prime borrower into the form" }).click();
  await expect(verdict).toHaveText(/Approved/);
  await compare.getByRole("button", { name: "Clear all" }).click();
  await expect(compare).toHaveCount(0);
});

for (const [path, title] of PAGES.filter(([p]) => !["/", "/glossary/"].includes(p))) {
  test(`${title}: shows a one-sentence verdict with an icon`, async ({ page }) => {
    await page.goto(path);
    const verdict = page.locator(".verdict-banner");
    await expect(verdict).toBeVisible();
    await expect(verdict.locator(".verdict-icon")).toHaveText(/[✓⚠✗ℹ]/);
    await expect(verdict).toHaveText(/\w.{20,}\./);
  });
}

test("dragging the drift chart's handle zooms in, and Reset zoom restores it", async ({ page, isMobile }) => {
  test.skip(isMobile, "mouse drag; the phone run covers the page without it");
  await page.goto("/monitoring/");
  const handle = page.locator(".recharts-brush-traveller").first();
  await handle.scrollIntoViewIfNeeded();
  const bars = page.locator(".recharts-bar-rectangle");
  const all = await bars.count();
  const box = await handle.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + 300, box.y + box.height / 2, { steps: 10 });
  await page.mouse.up();
  await expect(page.getByRole("button", { name: "Reset zoom" })).toBeVisible();
  expect(await bars.count()).toBeLessThan(all);
  await page.getByRole("button", { name: "Reset zoom" }).click();
  await expect(bars).toHaveCount(all);
});
