/* Optional browser checks: run npm ci and npm test from tests/. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const os = require("node:os");
const { chromium } = require("playwright");
const { checkReleases, releasesApi, releasesPage } = require("./releases.cjs");

const root = path.resolve(__dirname, "..");
const prefix = "/a-cozy-adventure/";
const catalog = JSON.parse(
  fs.readFileSync(path.join(root, "mods.json"), "utf8"),
);
const mime = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".toml": "text/plain",
};
const server = http.createServer((request, response) => {
  const url = new URL(request.url, "http://localhost");
  if (!url.pathname.startsWith(prefix)) {
    response.writeHead(404).end();
    return;
  }
  const relative =
    decodeURIComponent(url.pathname.slice(prefix.length)) || "index.html";
  const file = path.resolve(root, relative);
  if (!file.startsWith(root + path.sep)) {
    response.writeHead(403).end();
    return;
  }
  fs.readFile(file, (error, content) => {
    if (error) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, {
      "Content-Type": mime[path.extname(file)] || "application/octet-stream",
    });
    response.end(content);
  });
});

(async () => {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route(releasesApi, (route) => route.fulfill({ json: [] }));
    await page.goto(origin + prefix);
    await page.waitForSelector(".mod-card");
    assert.equal(await page.locator(".mod-card").count(), catalog.total);
    assert.equal(
      await page.locator("#hero-count").innerText(),
      String(catalog.total),
    );
    assert.equal(
      await page.locator("#minecraft-version").innerText(),
      catalog.pack.minecraft,
    );
    await page.waitForFunction(() => {
      const icons = [...document.querySelectorAll(".mod-card .mod-icon img")];
      return icons.slice(0, 3).every((img) => img.complete);
    });
    await page.screenshot({
      path: path.join(os.tmpdir(), "cozy-adventure-desktop.png"),
      fullPage: false,
    });
    await page.locator("#katalog").scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(os.tmpdir(), "cozy-adventure-catalog.png"),
      fullPage: false,
    });
    await page.locator("#installation").scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(os.tmpdir(), "cozy-adventure-installation.png"),
      fullPage: false,
    });
    await page.locator("#search").fill("sOdIuM");
    assert.equal(await page.locator(".mod-card").count(), 1);
    await page.locator(".mod-card").click();
    assert.equal(
      await page.locator("#mod-dialog").evaluate((el) => el.open),
      true,
    );
    assert.match(await page.locator("#detail-title").innerText(), /Sodium/i);
    assert.equal(
      await page.locator("#detail-links a").first().getAttribute("href"),
      "https://www.curseforge.com/projects/394468",
    );
    await page.keyboard.press("Escape");
    assert.equal(
      await page.locator("#mod-dialog").evaluate((el) => el.open),
      false,
    );
    assert.equal(
      await page
        .locator(".mod-card")
        .evaluate((el) => el === document.activeElement),
      true,
    );
    await page.locator("#search").fill("this-mod-does-not-exist");
    assert.equal(await page.locator("#empty-state").isVisible(), true);
    await page.locator("#empty-reset").click();
    assert.equal(await page.locator(".mod-card").count(), catalog.total);
    await page.getByRole("button", { name: /^Magie/ }).click();
    assert.equal(
      await page.locator(".mod-card").count(),
      catalog.categories.find((c) => c.name === "Magie").count,
    );
    await page.locator("#search").fill("wizard");
    assert.equal(await page.locator(".mod-card").count(), 1);
    await page.locator("#reset").click();
    await page.locator("#sort").selectOption("az");
    const sorted = await page.locator(".mod-card h3").allTextContents();
    assert.deepEqual(
      sorted,
      [...sorted].sort(
        new Intl.Collator("de", { sensitivity: "base", numeric: true }).compare,
      ),
    );
    await page.locator("#sort").selectOption("za");
    assert.deepEqual(
      await page.locator(".mod-card h3").allTextContents(),
      [...sorted].reverse(),
    );
    for (const width of [320, 375, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
        true,
        `Horizontal overflow at ${width}px`,
      );
      if (width === 390) {
        await page.evaluate(() =>
          window.scrollTo({ top: 0, behavior: "instant" }),
        );
        await page.screenshot({
          path: path.join(os.tmpdir(), "cozy-adventure-mobile.png"),
          fullPage: false,
        });
        await page.locator("#search").scrollIntoViewIfNeeded();
        await page.screenshot({
          path: path.join(os.tmpdir(), "cozy-adventure-mobile-catalog.png"),
          fullPage: false,
        });
        await page.locator(".mod-card").first().click();
        assert.equal(await page.locator("#dialog-close").isVisible(), true);
        await page.locator("#dialog-close").click();
      }
    }
    // Existing Packwiz endpoint still resolves under a GitHub Pages project path.
    const packResponse = await page.request.get(origin + prefix + "pack.toml");
    assert.equal(packResponse.status(), 200);
    assert.deepEqual(
      await packResponse.body(),
      fs.readFileSync(path.join(root, "pack.toml")),
    );
    await page.waitForFunction(() =>
      document
        .getElementById("download-message")
        .textContent.includes("Noch keine passende"),
    );
    assert.equal(
      await page.locator("#install-download-link").getAttribute("href"),
      releasesPage,
    );

    // API payloads are displayed as text, and unsafe links/icons are ignored.
    const malicious = structuredClone(catalog);
    malicious.mods[0] = {
      ...malicious.mods[0],
      name: "<img src=x onerror=alert(1)>",
      description: "<script>alert(1)</script>",
      icon: "https://tracker.invalid/a.png",
      url: "javascript:alert(1)",
      metadataUrl: null,
      codeUrl: null,
      wikiUrl: null,
      featured: true,
    };
    await page.route("**/mods.json", (route) =>
      route.fulfill({ json: malicious }),
    );
    await page.reload();
    await page.waitForSelector(".mod-card");
    await page.locator("#search").fill("<img");
    assert.equal(await page.locator(".mod-card").count(), 1);
    assert.equal(await page.locator(".mod-card img").count(), 0);
    await page.locator(".mod-card").click();
    assert.equal(
      await page.locator("#detail-title").innerText(),
      malicious.mods[0].name,
    );
    assert.equal(await page.locator("#detail-title img").count(), 0);
    assert.equal(await page.locator("#detail-links a").count(), 0);
    await page.keyboard.press("Escape");
    await page.unroute("**/mods.json");

    // Missing JSON and invalid JSON both show a recoverable error state.
    await page.route("**/mods.json", (route) =>
      route.fulfill({ status: 503, body: "unavailable" }),
    );
    await page.reload();
    await page.waitForSelector("#error-state:not([hidden])");
    assert.equal(await page.locator("#search").isDisabled(), true);
    await page.unroute("**/mods.json");
    await page.locator("#retry").click();
    await page.waitForSelector(".mod-card");
    await page.route("**/mods.json", (route) =>
      route.fulfill({ json: { mods: [{}] } }),
    );
    await page.reload();
    await page.waitForSelector("#error-state:not([hidden])");
    await page.unroute("**/mods.json");
    await page.locator("#retry").click();
    await page.waitForSelector(".mod-card");

    // Broken project icons have a useful fallback.
    await page.route("https://cdn.modrinth.com/**", (route) => route.abort());
    await page.reload();
    await page.waitForSelector(".mod-card");
    await page.locator("#search").fill("sodium");
    await page.waitForFunction(
      () =>
        document.querySelector(".mod-card .mod-icon")?.textContent.length > 0,
    );
    const reduced = await browser.newContext({ reducedMotion: "reduce" });
    await reduced.route(releasesApi, (route) => route.fulfill({ json: [] }));
    const reducedPage = await reduced.newPage();
    await reducedPage.goto(origin + prefix);
    assert.equal(
      await reducedPage.evaluate(
        () => getComputedStyle(document.documentElement).scrollBehavior,
      ),
      "auto",
    );
    await reduced.close();
    await checkReleases(browser, origin + prefix);
    assert.deepEqual(errors, []);
    console.log(
      `Browser checks passed: ${catalog.total} mods; search, combined filters, sorting, dialogs, 6 viewport widths, project paths, text safety, errors, icon fallback and reduced motion.`,
    );
    console.log(
      `Screenshots: ${path.join(os.tmpdir(), "cozy-adventure-desktop.png")} and ${path.join(os.tmpdir(), "cozy-adventure-mobile.png")}`,
    );
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => {
  console.error(error);
  server.close();
  process.exitCode = 1;
});
