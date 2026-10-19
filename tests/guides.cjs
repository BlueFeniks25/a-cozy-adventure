const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");
async function checkGuides(browser, page, origin, prefix, catalog) {
  const base = origin + prefix;
  assert.equal(
    await page.locator(".hero-actions .button-primary").getAttribute("href"),
    "#installation",
  );
  assert.equal(await page.locator(".guide-links a").count(), 6);
  for (const target of [
    "installation",
    "client-mods",
    "ressourcenpakete",
    "tasten",
    "hilfe",
    "katalog",
  ]) {
    await page.locator(`.guide-links a[href="#${target}"]`).click();
    assert.equal(new URL(page.url()).hash, "#" + target);
    assert.equal(await page.locator(`#${target}`).isVisible(), true);
  }
  const anchors = await page
    .locator('a[href^="#"]')
    .evaluateAll((links) => links.map((a) => a.getAttribute("href")));
  for (const href of anchors.filter((href) => href !== "#"))
    assert.equal(await page.locator(href).count(), 1, href);
  const installation = await page.locator("#installation").textContent();
  for (const text of [
    "Java 25",
    "26.3",
    "0.19.5",
    "Microsoft",
    "Prism",
    "v0.0.2",
  ])
    assert.ok(installation.includes(text), text);
  assert.match(
    await page.locator("#client-mods").textContent(),
    /Download Mods/,
  );
  assert.match(await page.locator("#client-mods").textContent(), /Pflichtmods/);
  for (const summary of await page.locator(".guide-detail > summary").all()) {
    const detail = summary.locator("..");
    if ((await detail.getAttribute("open")) !== null) await summary.click();
    await summary.focus();
    await page.keyboard.press("Enter");
    assert.equal(await detail.evaluate((el) => el.open), true);
    assert.equal(
      await summary.evaluate((el) => el === document.activeElement),
      true,
    );
    await page.keyboard.press("Enter");
    assert.equal(await detail.evaluate((el) => el.open), false);
  }
  const filenames = [
    "fresh-animations-extensions",
    "fa-player-extension",
    "fresh-animations",
    "colorful-trims-rp",
  ].map(
    (name) =>
      fs
        .readFileSync(
          path.join(__dirname, "..", "resourcepacks", name + ".pw.toml"),
          "utf8",
        )
        .match(/^filename = "(.+)"$/m)[1],
  );
  assert.deepEqual(
    await page.locator("#resource-order code").allTextContents(),
    filenames,
  );
  assert.match(
    await page.locator("#ressourcenpakete").textContent(),
    /oben.*Vorrang/,
  );
  assert.match(await page.locator("#migration").textContent(), /instance\.cfg/);
  assert.match(
    await page.locator("#migration").textContent(),
    /\.migration\.jar/,
  );
  assert.equal(await page.locator(".control-row:visible").count(), 14);
  await page.getByLabel("Funktion, Mod oder Taste suchen").fill("zOoM");
  assert.equal(await page.locator(".control-row:visible").count(), 2);
  assert.deepEqual(
    await page.locator(".control-row:visible kbd").allTextContents(),
    ["C", "F6"],
  );
  await page.getByLabel("Bereich", { exact: true }).selectOption("Inventar");
  assert.equal(await page.locator("#control-empty").isVisible(), true);
  await page
    .getByRole("button", { name: "Suche zurücksetzen", exact: true })
    .click();
  assert.equal(
    await page
      .locator("#control-search")
      .evaluate((el) => el === document.activeElement),
    true,
  );
  await page.locator("#control-category").selectOption("Kampf");
  assert.equal(await page.locator(".control-row:visible").count(), 2);
  assert.match(await page.locator("#control-count").innerText(), /2 von 14/);
  await page.locator("#control-search").fill("<img src=x onerror=alert(1)>");
  assert.equal(await page.locator(".control-row:visible").count(), 0);
  assert.equal(await page.locator('#tasten img[src="x"]').count(), 0);
  await page.locator("#control-reset").click();
  assert.equal(await page.locator(".control-row:visible").count(), 14);
  const links = await page
    .locator('.guide-section a[href^="docs/"]')
    .evaluateAll((links) => [
      ...new Set(links.map((a) => a.getAttribute("href").split("#")[0])),
    ]);
  for (const href of links)
    assert.equal((await page.request.get(base + href)).status(), 200, href);
  const images = await page
    .locator(".guide-figure img")
    .evaluateAll((imgs) =>
      imgs.map((img) => ({ src: img.getAttribute("src"), alt: img.alt })),
    );
  assert.equal(new Set(images.map((img) => img.src)).size, 7);
  for (const img of images) {
    assert.ok(img.alt.length > 20);
    const response = await page.request.get(base + img.src);
    assert.equal(response.status(), 200);
    assert.match(await response.text(), /[Ss]chema/);
  }
  for (const width of [320, 375, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page
      .locator(".guide-detail")
      .evaluateAll((ds) => ds.forEach((d) => (d.open = true)));
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
      `Guide overflow at ${width}`,
    );
    if ([390, 1440].includes(width))
      for (const target of [
        "wegweiser",
        "installation",
        "client-mods",
        "ressourcenpakete",
        "tasten",
        "migration",
      ]) {
        await page
          .locator("#" + target)
          .evaluate((el) =>
            el.scrollIntoView({ block: "start", behavior: "instant" }),
          );
        await page.screenshot({
          path: path.join(os.tmpdir(), `cozy-guide-${target}-${width}.png`),
        });
      }
  }
  const nojs = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 390, height: 900 },
  });
  await nojs.route("https://cdn.modrinth.com/**", (route) => route.abort());
  const plain = await nojs.newPage();
  await plain.goto(base);
  assert.equal(await plain.locator(".control-row").count(), 14);
  assert.equal(
    await plain
      .locator("#installation details")
      .first()
      .evaluate((el) => el.open),
    true,
  );
  assert.match(await plain.locator("#installation").innerText(), /Microsoft/);
  assert.equal(
    await plain.locator("#install-download-link").getAttribute("href"),
    "https://github.com/BlueFeniks25/a-cozy-adventure/releases",
  );
  await nojs.close();
  assert.equal(await page.locator(".mod-card").count(), catalog.total);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base);
  await page.waitForSelector(".mod-card");
  console.log(
    "Player guide checks passed: navigation, 7 SVGs, 14 sourced functions, search/filter/reset, keyboard disclosures, resource priority, migration, no JS and 6 widths.",
  );
}
module.exports = { checkGuides };
