const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

(async () => {
  const executablePath =
    process.env.BROWSER_EXECUTABLE ||
    (process.platform === "win32"
      ? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
      : undefined);
  const browser = await chromium.launch({ executablePath, headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1060 },
  });
  const page = await context.newPage();
  const errors = [],
    remote = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("request", (r) => {
    if (!r.url().startsWith("http://127.0.0.1:18764")) remote.push(r.url());
  });
  const directory = path.resolve(".validation/screenshots");
  fs.mkdirSync(directory, { recursive: true });
  const configPath = path.resolve(
    ".validation/ui-data/plugin_data/astrbot_plugin_multica_bridge/config.json",
  );
  const read = () => JSON.parse(fs.readFileSync(configPath, "utf8"));
  const original = read();
  const loaded = () =>
    page.waitForFunction(() =>
      document.getElementById("save-state").textContent.includes("配置已读取"),
    );
  const saved = () =>
    page.waitForFunction(() =>
      document
        .getElementById("save-state")
        .textContent.includes("所有更改已保存"),
    );
  try {
    await page.goto("http://127.0.0.1:18764");
    await loaded();
    await page.waitForFunction(
      () => document.getElementById("active-count").textContent === "2",
    );
    assert.equal(
      await page.locator("#field-api_url").inputValue(),
      original.api_url,
    );
    assert.notEqual(
      await page.locator("#field-token").inputValue(),
      original.token,
    );
    await page.screenshot({
      path: path.join(directory, "desktop-light.png"),
      fullPage: true,
    });
    await page.evaluate(() => window.testTheme({ isDark: true }));
    await page.screenshot({
      path: path.join(directory, "desktop-dark.png"),
      fullPage: true,
    });
    await page.evaluate(() => window.testTheme({ isDark: false }));
    const overflow = [];
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      const result = await page.evaluate(() => ({
        width: innerWidth,
        scroll: document.documentElement.scrollWidth,
      }));
      assert.ok(result.scroll <= width, JSON.stringify(result));
      overflow.push(result);
      await page.screenshot({
        path: path.join(directory, `mobile-${width}.png`),
        fullPage: true,
      });
    }
    await page.setViewportSize({ width: 1440, height: 1060 });
    await page.locator("#btn-test").click();
    await page.waitForFunction(() =>
      document
        .getElementById("connection-state")
        .textContent.includes("连接成功"),
    );
    await page.locator("#btn-agents").click();
    await page.waitForFunction(
      () => document.querySelectorAll("#agent-options option").length === 2,
    );
    await page.locator("#field-default_agent_id").fill("agent-two");
    await saved();
    await page.reload();
    await loaded();
    assert.equal(
      await page.locator("#field-default_agent_id").inputValue(),
      "agent-two",
    );
    assert.equal(read().token, original.token);
    assert.equal(read().api_url, original.api_url);
    await page.locator("#field-token").fill("");
    await page.waitForTimeout(1050);
    assert.equal(read().token, original.token);
    await page.reload();
    await loaded();
    let entered;
    const intercepted = new Promise((resolve) => (entered = resolve));
    let first = true;
    await page.route("**/plugin/actions/save_config", async (route) => {
      if (first) {
        first = false;
        entered();
        await new Promise((r) => setTimeout(r, 1100));
      }
      await route.continue();
    });
    await page.locator("#field-default_agent_id").fill("agent-one");
    await intercepted;
    await page.locator("#field-default_agent_id").fill("agent-two");
    await saved();
    await page.waitForFunction(() =>
      document
        .getElementById("save-state")
        .textContent.includes("所有更改已保存"),
    );
    assert.equal(read().default_agent_id, "agent-two");
    await page.unroute("**/plugin/actions/save_config");
    await page.locator("#session-list .session-row button").first().click();
    await page.waitForFunction(
      () =>
        document.querySelectorAll("#session-list .session-row").length === 1,
    );
    assert.match(
      await page.locator("#session-list").textContent(),
      /246801357/,
    );
    assert.equal(read().token, original.token);
    await page.goto("http://127.0.0.1:18764/?locale=en-US&dark=1");
    await page.waitForFunction(
      () => document.querySelector("h1").textContent === "Multica workspace",
    );
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    await page.screenshot({
      path: path.join(directory, "desktop-english-dark.png"),
      fullPage: true,
    });
    assert.deepEqual(errors, []);
    assert.deepEqual(remote, []);
    const report = {
      browser: "Microsoft Edge via Playwright",
      sizes: [1440, 390, 320],
      overflow,
      errors,
      remoteRequests: remote,
      checks: [
        "old URL/Token retained",
        "masked Token only",
        "new settings persisted after reload",
        "empty Token keeps original",
        "save-in-flight edits retained",
        "connection test",
        "agent list",
        "exit one window only",
        "dark theme",
        "English locale",
      ],
    };
    fs.writeFileSync(
      path.resolve(".validation/ui-results.json"),
      JSON.stringify(report, null, 2),
    );
    console.log(JSON.stringify(report));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
