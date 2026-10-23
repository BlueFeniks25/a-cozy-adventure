const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
async function checkGuides(browser, page, origin, prefix) {
  assert.equal(await page.locator('.hero-actions .button-primary').getAttribute('href'), '#installation');
  assert.match(await page.locator('.hero-actions .button-primary').innerText(), /A Cozy Adventure installieren/);
  assert.equal(await page.locator('.guide-links a').count(), 6);
  const anchors = await page.locator('a[href^="#"]').evaluateAll(as => as.map(a => a.getAttribute('href')));
  for (const href of anchors.filter(h => h !== '#')) assert.equal(await page.locator(href).count(), 1, href);
  for (const a of await page.locator('.guide-links a').all()) {
    const href = await a.getAttribute('href');
    await a.click();
    assert.equal(new URL(page.url()).hash, href);
  }
  const installation = await page.locator('#installation').textContent();
  for (const text of ['CurseForge', '26.3', '0.19.5', '5.0.0-rc.5', 'Microsoft', 'minehost140.host-unlimited.de:15156', 'Neustart', 'Bestätigung', 'mods']) assert.ok(installation.includes(text), text);
  for (const summary of await page.locator('.guide-detail > summary').all()) {
    const detail = summary.locator('..');
    if (await detail.evaluate(e => e.open)) await summary.click();
    await summary.focus(); await page.keyboard.press('Enter');
    assert.equal(await detail.evaluate(e => e.open), true);
  }
  const filenames = ['fresh-animations-extensions','fa-player-extension','fresh-animations','colorful-trims-rp'].map(name => fs.readFileSync(path.join(__dirname,'..','resourcepacks',name+'.pw.toml'),'utf8').match(/^filename = "(.+)"$/m)[1]);
  assert.deepEqual(await page.locator('#resource-order code').allTextContents(), filenames);
  assert.match(await page.locator('#ressourcenpakete').textContent(), /optional und empfohlen/);
  assert.match(await page.locator('#tasten').textContent(), /nicht automatisch vorgegeben/);
  assert.equal(await page.locator('a[href$="options.txt"], a[href$=".zip"], #migration, #install-download-link').count(), 0);
  const links = await page.locator('a[href^="docs/"]').evaluateAll(as => [...new Set(as.map(a=>a.getAttribute('href').split('#')[0]))]);
  for (const href of links) assert.equal((await page.request.get(origin+prefix+href)).status(),200,href);
  for (const width of [320,375,390,768,1024,1440]) {
    await page.setViewportSize({width,height:900});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth), `Guide overflow at ${width}`);
  }
  const nojs = await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:900}});
  try {
    const plain=await nojs.newPage(); await plain.goto(origin+prefix);
    await plain.locator('#installation details').nth(2).locator('summary').click();
    assert.match(await plain.locator('#installation').innerText(), /automodpack-5.0.0-rc.5.jar/);
    assert.equal(await plain.locator('#installation details').first().evaluate(e=>e.open),true);
  } finally { await nojs.close(); }
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(origin+prefix); await page.waitForSelector('.mod-card');
  console.log('Guide checks passed: CurseForge, manual AutoModpack, server, resource priority, keyboard navigation, no JS, 6 widths.');
}
module.exports={checkGuides};
