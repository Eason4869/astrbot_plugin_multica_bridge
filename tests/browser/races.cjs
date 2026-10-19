const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
(async () => {
  const browser = await chromium.launch({
    executablePath:
      process.env.BROWSER_EXECUTABLE ||
      "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    headless: true,
  });
  const page = await browser.newPage();
  let restore;
  try {
    await page.goto("http://127.0.0.1:18764");
    await page.waitForFunction(() =>
      document.getElementById("save-state").textContent.includes("配置已读取"),
    );
    restore = await page.locator("#field-workspace_id").inputValue();
    await page.locator("#btn-workspaces").click();
    await page.waitForFunction(() => document.querySelectorAll("#field-workspace_id option[data-workspace]").length === 2);
    if (!process.argv.includes("--clear-only")) {
      let reached, release;
      const responseWaiting = new Promise((resolve) => (reached = resolve));
      const released = new Promise((resolve) => (release = resolve));
      await page.route("**/plugin/actions/test_connection", async (route) => {
        const response = await route.fetch();
        reached();
        await released;
        await route.fulfill({ response });
      });
      await page.locator("#btn-test").click();
      await responseWaiting;
      await page
        .locator("#field-workspace_id")
        .selectOption("00000000-0000-0000-0000-000000000002");
      release();
      await page.waitForFunction(
        () => !document.getElementById("btn-test").disabled,
      );
      assert.match(
        await page.locator("#connection-state").textContent(),
        /尚未检测/,
        "Stale success must not verify new settings",
      );
      await page.unroute("**/plugin/actions/test_connection");
      await page.locator("#field-workspace_id").selectOption(restore);
      await page.waitForFunction(() =>
        document
          .getElementById("save-state")
          .textContent.includes("所有更改已保存"),
      );
    }
    let reached, release;
    const clearWaiting = new Promise((resolve) => (reached = resolve));
    const released = new Promise((resolve) => (release = resolve));
    await page.route("**/plugin/actions/save_config", async (route) => {
      if (route.request().postDataJSON().clear_token) {
        reached();
        await released;
      }
      await route.continue();
    });
    page.once("dialog", (dialog) => dialog.accept());
    await page.locator("#btn-clear-token").click();
    await clearWaiting;
    assert.equal(
      await page.locator("#field-token").isDisabled(),
      true,
      "Input must be locked during Token clear",
    );
    release();
    await page.waitForFunction(
      () => !document.getElementById("field-token").disabled,
    );
    await page.locator("#field-token").fill("ui-fixture-old-secret");
    await page.waitForFunction(() =>
      document
        .getElementById("save-state")
        .textContent.includes("所有更改已保存"),
    );
    console.log(
      "PASS: stale connection results ignored; Token clear cannot overwrite later edits",
    );
  } finally {
    if (restore)
      await page.request
        .post("http://127.0.0.1:18764/plugin/actions/save_config", {
          data: { workspace_id: restore, token: "ui-fixture-old-secret" },
        })
        .catch(() => {});
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
