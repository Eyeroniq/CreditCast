// Accessibility gate (ROADMAP 6.3.4): axe-core, the engine behind Lighthouse's
// accessibility score, checks every page against WCAG 2.1 A + AA in both
// themes. Any violation fails the run and is listed with the elements involved.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PAGES = ["/", "/portfolio/", "/validation/", "/monitoring/", "/governance/", "/copilot/", "/glossary/"];

for (const theme of ["dark", "light"]) {
  for (const path of PAGES) {
    test(`${path} has no WCAG A/AA violations (${theme})`, async ({ page }) => {
      await page.addInitScript((t) => {
        localStorage.setItem("cc-tour-done", "1");
        localStorage.setItem("cc-theme", t);
      }, theme);
      await page.emulateMedia({ reducedMotion: "reduce" });   // settle animations before scanning
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByRole("status", { name: /^Loading/ })).toHaveCount(0);
      if (path === "/") await expect(page.locator(".verdict")).toBeVisible();
      const { violations } = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      const report = violations.map((v) => `${v.id} (${v.impact}): ${v.help}\n`
        + v.nodes.slice(0, 5).map((n) => `    ${n.target.join(" ")} — ${n.failureSummary.split("\n")[1] || ""}`).join("\n"));
      expect(report, report.join("\n")).toEqual([]);
    });
  }
}

// axe only sees what's on screen, so also scan the interactive states.
const scan = async (page) => (await new AxeBuilder({ page })
  .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze()).violations.map((v) => `${v.id}: ${v.help}`);

test("open states have no violations: tour, compare card, phone menu", async ({ page, isMobile }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");                                       // first visit: the tour opens
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(await scan(page)).toEqual([]);
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Prime borrower" }).click();
  await expect(page.locator(".verdict")).toHaveText(/Approved/);
  await page.getByRole("button", { name: /Pin to compare/ }).click();
  await expect(page.locator(".compare")).toBeVisible();
  expect(await scan(page)).toEqual([]);

  if (isMobile) {
    await page.getByRole("button", { name: /Menu/ }).click();
    await expect(page.getByRole("link", { name: "Portfolio" })).toBeVisible();
    expect(await scan(page)).toEqual([]);
  }
});

test("keyboard only: reach a slider, change the decision, then navigate", async ({ page, isMobile }) => {
  test.skip(isMobile, "physical keyboard walkthrough is a desktop check");
  await page.addInitScript(() => localStorage.setItem("cc-tour-done", "1"));
  await page.goto("/");
  await page.getByRole("button", { name: "Marginal borrower" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".verdict")).toHaveText(/Declined/);

  // Tab forward until the credit-score slider has focus; the focus ring must show.
  for (let i = 0; i < 15 && !(await page.evaluate(() => document.activeElement?.id === "f-fico")); i++) {
    await page.keyboard.press("Tab");
  }
  const slider = page.locator("#f-fico");
  await expect(slider).toBeFocused();
  expect(await slider.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe("none");
  await page.keyboard.press("End");                          // FICO 850
  await expect(page.locator(".verdict")).toHaveText(/Approved/);

  await page.getByRole("link", { name: "Portfolio" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/portfolio\/$/);
  await expect(page.getByRole("heading", { level: 1, name: "Portfolio risk" })).toBeVisible();
});
