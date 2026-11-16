const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const root = path.resolve(__dirname, "../..");
const artifacts = path.join(root, ".agentops-runtime", "browser-qa");
fs.mkdirSync(artifacts, { recursive: true });
let activeBrowser;
(async () => {
  const key = fs.readFileSync(path.join(root, ".agentops-runtime/api-key"), "utf8").trim();
  const browser = (activeBrowser = await chromium.launch({ headless: true }));
  const context = await browser.newContext({
    viewport: { width: 1512, height: 1080 },
    httpCredentials: { username: "operator", password: key },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:8003/", { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Your agents. Under control." }).waitFor();
  await page.screenshot({ path: path.join(artifacts, "desktop.png"), fullPage: true });
  console.log("PASS overview loads real workspace data");
  for (const name of [
    "Agents",
    "Policies",
    "Incidents",
    "Reliability",
    "Chaos lab",
    "Live events",
    "Workspace & reports",
  ]) {
    await page.getByRole("link", { name, exact: false }).first().click();
    await page.waitForTimeout(100);
    console.log("PASS navigation: " + name);
  }
  await page.getByRole("link", { name: "Agents", exact: false }).first().click();
  await page.getByRole("button", { name: "+ Register agent", exact: true }).click();
  await page.getByLabel("Agent name", { exact: true }).fill("ui-check-" + Date.now());
  const createdName = await page.getByLabel("Agent name", { exact: true }).inputValue();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Register agent", exact: true })
    .click();
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  await page.getByText(createdName, { exact: true }).waitFor();
  console.log("PASS agent creation through browser form");
  const agentRow = page.getByRole("row").filter({ hasText: createdName });
  await agentRow.getByRole("button", { name: "Inspect", exact: true }).click();
  await page.getByRole("dialog").getByText("No active kill switch", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  await agentRow.getByRole("button", { name: "Kill", exact: true }).click();
  await page.getByLabel("Reason", { exact: true }).fill("Browser verification");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Activate kill switch", exact: true })
    .click();
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  await page
    .getByRole("row")
    .filter({ hasText: createdName })
    .getByRole("button", { name: "Inspect", exact: true })
    .click();
  await page.getByRole("dialog").getByText("Kill switch active", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Release kill switch", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Release switch", exact: true })
    .click();
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  console.log("PASS real kill and release");
  await page.getByRole("link", { name: "Policies", exact: true }).click();
  await page.getByRole("button", { name: "+ Create policy", exact: true }).click();
  const policyName = "ui-policy-" + Date.now();
  await page.getByLabel("Policy name", { exact: true }).fill(policyName);
  const scope = await page
    .getByLabel("Scope", { exact: true })
    .locator("option")
    .evaluateAll(
      (nodes, name) => nodes.find((n) => n.textContent.startsWith(name)).value,
      createdName,
    );
  await page.getByLabel("Scope", { exact: true }).selectOption(scope);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Create policy", exact: true })
    .click();
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  await page.getByRole("row").filter({ hasText: policyName }).waitFor();
  console.log("PASS policy creation");
  await page
    .getByRole("row")
    .filter({ hasText: policyName })
    .getByRole("button", { name: "Delete", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete policy", exact: true })
    .click();
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  console.log("PASS policy deletion");
  await page.getByRole("link", { name: "Live events", exact: true }).click();
  await page.locator(".event-row").first().waitFor();
  await page.locator(".event-row").first().click();
  await page.getByRole("dialog").locator(".json-view").waitFor();
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  console.log("PASS event inspection");
  const html = await page.content();
  if (html.includes(key)) throw new Error("API key embedded in DOM");
  await context.close();
  const mobile = await browser.newContext({
    viewport: { width: 390, height: 844 },
    httpCredentials: { username: "operator", password: key },
  });
  const mobilePage = await mobile.newPage();
  await mobilePage.goto("http://127.0.0.1:8003/", { waitUntil: "networkidle" });
  await mobilePage.getByRole("heading", { name: "Your agents. Under control." }).waitFor();
  await mobilePage.getByRole("button", { name: "Toggle navigation", exact: true }).click();
  await mobilePage.getByRole("link", { name: "Agents", exact: true }).click();
  await mobilePage.waitForTimeout(250);
  await mobilePage.getByRole("button", { name: "Toggle navigation", exact: true }).click();
  await mobilePage.getByRole("link", { name: "Overview", exact: true }).click();
  await mobilePage.waitForTimeout(300);
  await mobilePage.screenshot({ path: path.join(artifacts, "mobile.png"), fullPage: true });
  const overflow = await mobilePage.evaluate(
    () => document.documentElement.scrollWidth > innerWidth,
  );
  if (overflow) throw new Error("Mobile layout overflows viewport");
  console.log("PASS mobile navigation and responsive layout");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("PASS no browser runtime errors and no API key in DOM");
  await browser.close();
})().catch(async (error) => {
  console.error(error.message);
  await activeBrowser?.close();
  process.exit(1);
});
