// Copilot chat (6.2.8). The agents need an LLM key, so these tests stand in
// for the two agent endpoints with page.route; the page, the stream parser and
// the UI states are the real ones.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const TEAM = {
  llm_ready: true, model: "test-model",
  agents: [
    { id: "analyst", title: "Portfolio Analyst", tools: ["portfolio_summary"] },
    { id: "fairness", title: "Fairness Auditor", tools: ["fairness_report"] },
  ],
};
const sse = (events) => events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
const ANSWER = [
  { type: "plan", agents: [{ specialist: "fairness", title: "Fairness Auditor" }] },
  { type: "agent_start", specialist: "fairness", title: "Fairness Auditor" },
  { type: "agent_done", specialist: "fairness", title: "Fairness Auditor",
    text: "The lowest approval ratio is **0.799**, just under the 0.8 rule.", charts: [],
    trace: [{ agent: "Fairness Auditor", tool: "fairness_report", args: {} }] },
  { type: "done", answer: "The lowest approval ratio is **0.799**, just under the 0.8 rule.", charts: [],
    trace: [{ agent: "Fairness Auditor", tool: "fairness_report", args: {} }],
    agents: [{ specialist: "fairness", title: "Fairness Auditor" }] },
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("cc-tour-done", "1"));
  await page.route("**/api/agent/team", (r) => r.fulfill({ json: TEAM }));
});

test("a suggested question streams an answer with a tool trace, kept after reload", async ({ page }) => {
  await page.route("**/api/agent/chat/stream", (r) =>
    r.fulfill({ status: 200, contentType: "text/event-stream", body: sse(ANSWER) }));
  await page.goto("/copilot/");
  await page.getByRole("button", { name: "Is the model fair?" }).click();

  const answer = page.locator(".msg.assistant");
  await expect(answer).toContainText("lowest approval ratio is 0.799");
  await expect(answer.locator("b")).toHaveText("0.799");          // markdown bold rendered
  await answer.getByText(/How I got this · 1 tool call/).click();
  await expect(answer.getByText("fairness_report")).toBeVisible();
  await expect(answer.getByRole("button", { name: "Copy answer" })).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze()).violations
    .map((v) => v.id)).toEqual([]);

  await page.reload();                                           // history survives
  await expect(page.locator(".msg.user")).toHaveText("Is the model fair?");
  await page.getByRole("button", { name: /New chat/ }).click();
  await expect(page.locator(".msg")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Is the model fair?" })).toBeVisible();
});

test("rate limited: friendly message and a countdown that blocks asking", async ({ page }) => {
  await page.route("**/api/agent/chat/stream", (r) => r.fulfill({
    status: 429, headers: { "retry-after": "30" },
    json: { detail: "Too many requests — please try again in a minute." },
  }));
  await page.goto("/copilot/");
  await page.getByLabel("Ask the risk team").fill("Which segment drives most loss?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.locator(".msg.assistant")).toContainText("try again");
  await expect(page.getByRole("status").filter({ hasText: "You can ask again in" })).toContainText(/\d+s/);
  await expect(page.getByLabel("Ask the risk team")).toBeDisabled();
});

test("no LLM key: the page explains how to switch the agents on", async ({ page }) => {
  await page.route("**/api/agent/team", (r) => r.fulfill({ json: { ...TEAM, llm_ready: false } }));
  await page.goto("/copilot/");
  await expect(page.locator(".verdict-banner")).toContainText("Copilot is offline");
  await expect(page.getByRole("link", { name: "console.groq.com" })).toBeVisible();
  await expect(page.getByLabel("Ask the risk team")).toBeDisabled();
});
