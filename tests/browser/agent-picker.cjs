const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
(async () => {
  const browser = await chromium.launch({executablePath: process.env.BROWSER_EXECUTABLE || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  try {
    await page.goto("http://127.0.0.1:18764");
    await page.waitForFunction(() => document.getElementById("save-state").textContent.includes("配置已读取"));
    assert.equal(await page.locator("#btn-agent-toggle").count(), 1);
    await page.locator("#btn-agent-toggle").click();
    await page.waitForFunction(() => document.querySelectorAll("#agent-list [role=option]").length === 3);
    await page.locator("#agent-search").fill("资料");
    assert.equal(await page.locator("#agent-list [role=option]").count(), 1);
    await page.locator("#agent-search").press("ArrowDown");
    await page.locator("#agent-search").press("Enter");
    await page.waitForFunction(() => document.getElementById("save-state").textContent.includes("所有更改已保存"));
    const cfg = await page.evaluate(async () => (await (await fetch("/plugin/config")).json()).data);
    assert.equal(cfg.default_agent_id, "agent-two");
    assert.equal(await page.locator("#field-default_agent_id").inputValue(), "资料整理助手");
    await page.locator("#btn-agent-toggle").click();
    await page.locator("#agent-search").fill("no-such-agent");
    assert.equal(await page.locator("#agent-list [role=option]").count(), 0);
    await page.locator("#agent-search").press("Escape");
    assert.equal(await page.locator("#agent-menu").isVisible(), false);
    await page.locator("#btn-agent-toggle").click();
    await page.locator("#agent-list [data-agent-id='']").click();
    await page.waitForFunction(() => document.getElementById("save-state").textContent.includes("所有更改已保存"));
    assert.equal(await page.locator("#field-default_agent_id").inputValue(), "");
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({width, height: 1000});
      await page.locator("#btn-agent-toggle").click();
      const box = await page.locator("#agent-menu").boundingBox();
      assert.ok(box.x >= 0 && box.x + box.width <= width, JSON.stringify(box));
      await page.screenshot({path: `.validation/screenshots/agent-picker-${width}.png`, fullPage: true, animations: "disabled"});
      await page.locator("#agent-search").press("Escape");
    }
    assert.deepEqual(errors, []);
    console.log("PASS: searchable agent picker, keyboard, selection, empty state, automatic mode and mobile bounds");
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
