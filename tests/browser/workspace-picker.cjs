const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const A = '00000000-0000-0000-0000-000000000001';
const B = '00000000-0000-0000-0000-000000000002';
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.BROWSER_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const page = await browser.newPage({viewport:{width:1440,height:1060}});
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  const configPath='.validation/ui-data/plugin_data/astrbot_plugin_multica_bridge/config.json';
  const saved=()=>page.waitForFunction(()=>document.getElementById('save-state').textContent.includes('所有更改已保存'));
  const loaded=()=>page.waitForFunction(()=>document.getElementById('save-state').textContent.includes('配置已读取'));
  try {
    await page.request.post('http://127.0.0.1:18764/plugin/actions/save_config',{data:{workspace_id:'',project_id:'',token:'ui-fixture-old-secret'}});
    await page.goto('http://127.0.0.1:18764'); await loaded();
    assert.equal(await page.locator('header #btn-test').count(),0,'Connection test belongs beside credentials');
    assert.equal(await page.locator('#connection #btn-test').count(),1);
    assert.equal(await page.locator('#field-workspace_id').evaluate(e=>e.tagName),'SELECT');
    await page.locator('#btn-test').click();
    await page.waitForFunction(()=>document.querySelectorAll('#field-workspace_id option[data-workspace]').length===2);
    assert.equal(await page.locator('#field-workspace_id').inputValue(),'','Never choose first workspace implicitly');
    assert.match(await page.locator('#test-result').textContent(),/连接成功/);
    assert.match(await page.locator('#test-result').textContent(),/选择/);
    assert.match(await page.locator(`#field-workspace_id option[value="${B}"]`).textContent(),/生产验证工作区/);
    assert.ok((await page.locator(`#field-workspace_id option[value="${B}"]`).textContent()).includes(B));
    await page.locator('#field-workspace_id').selectOption(B); await saved();
    assert.equal(JSON.parse(fs.readFileSync(configPath,'utf8')).workspace_id,B);
    assert.equal(JSON.parse(fs.readFileSync(configPath,'utf8')).token,'ui-fixture-old-secret');
    assert.equal(JSON.parse(fs.readFileSync(configPath,'utf8')).project_id,'');
    await page.reload(); await loaded();
    assert.equal(await page.locator('#field-workspace_id').inputValue(),B);
    await page.locator('#btn-test').click();
    await page.waitForFunction(()=>document.querySelectorAll('#field-workspace_id option[data-workspace]').length===2);
    assert.equal(await page.locator('#field-workspace_id').inputValue(),B,'Keep previously chosen workspace');
    await page.route('**/plugin/actions/test_connection',route=>route.fulfill({json:{success:true,data:{ok:false,connected:false,workspaces:[],message:'Token 无效'}}}));
    await page.locator('#btn-test').click();
    await page.waitForFunction(()=>document.getElementById('test-result').textContent.includes('Token 无效'));
    assert.equal(await page.locator('#field-workspace_id').inputValue(),B,'Failed discovery must preserve saved ID');
    assert.equal(JSON.parse(fs.readFileSync(configPath,'utf8')).workspace_id,B);
    assert.equal(await page.locator('#field-workspace_id option[data-workspace]').count(),0);
    await page.unroute('**/plugin/actions/test_connection');
    await page.locator('#btn-workspaces').click();
    await page.waitForFunction(()=>document.querySelectorAll('#field-workspace_id option[data-workspace]').length===2);
    assert.equal(await page.locator('#field-workspace_id').inputValue(),B);
    // Old connection responses must not populate the new credential context.
    let entered, release;
    const waiting=new Promise(r=>entered=r), released=new Promise(r=>release=r);
    await page.route('**/plugin/actions/test_connection',async route=>{ const response=await route.fetch(); entered(); await released; await route.fulfill({response}); });
    await page.locator('#btn-test').click(); await waiting;
    await page.locator('#field-token').fill('new-fixture-token');
    assert.equal(await page.locator('#field-workspace_id option[data-workspace]').count(),0);
    release(); await page.waitForFunction(()=>!document.getElementById('btn-test').disabled);
    assert.equal(await page.locator('#field-workspace_id option[data-workspace]').count(),0,'Ignore stale workspace response');
    await page.unroute('**/plugin/actions/test_connection');
    await page.locator('#field-token').fill('ui-fixture-old-secret'); await saved();
    await page.locator('#btn-test').click();
    await page.waitForFunction(()=>document.querySelectorAll('#field-workspace_id option[data-workspace]').length===2);
    for(const width of [1440,390,320]){
      await page.setViewportSize({width,height:1000});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.locator('#connection').scrollIntoViewIfNeeded();
      await page.screenshot({path:`.validation/screenshots/workspace-${width}.png`,fullPage:true});
    }
    assert.deepEqual(errors,[]);
    console.log('PASS: credentials-local test, automatic multi-workspace discovery, explicit selection, persistence, stale response, responsive layout');
  } finally {
    await page.request.post('http://127.0.0.1:18764/plugin/actions/save_config',{data:{workspace_id:A,project_id:'',token:'ui-fixture-old-secret'}}).catch(()=>{});
    await browser.close();
  }
})().catch(e=>{console.error(e);process.exitCode=1});
