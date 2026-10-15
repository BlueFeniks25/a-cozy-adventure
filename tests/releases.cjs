/* Run through browser.cjs: real browser, local website, mocked GitHub responses. */
const assert = require("node:assert/strict");
const path = require("node:path");
const os = require("node:os");

const repository = "https://github.com/BlueFeniks25/a-cozy-adventure";
const releasesPage = `${repository}/releases`;
const releasesApi =
  /^https:\/\/api\.github\.com\/repos\/BlueFeniks25\/a-cozy-adventure\/releases\?/;
let releaseId = 1;

function asset(tag, name = `A-Cozy-Adventure-Prism-${tag}.zip`) {
  return {
    name,
    state: "uploaded",
    browser_download_url: `${releasesPage}/download/${encodeURIComponent(tag)}/${encodeURIComponent(name)}`,
  };
}

function release(tag, published, prerelease = true, assets = [asset(tag)]) {
  return {
    id: releaseId++,
    tag_name: tag,
    name: tag,
    published_at: published,
    draft: false,
    prerelease,
    assets,
  };
}

async function checkReleases(browser, url) {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("https://cdn.modrinth.com/**", (route) => route.abort());
  let calls = [];
  let count = 0;

  async function response(handler) {
    await page.unroute(releasesApi);
    calls = [];
    await page.route(releasesApi, async (route) => {
      const request = route.request();
      const apiUrl = new URL(request.url());
      assert.equal(
        apiUrl.pathname,
        "/repos/BlueFeniks25/a-cozy-adventure/releases",
      );
      assert.equal(apiUrl.searchParams.get("per_page"), "100");
      assert.equal(request.headers().authorization, undefined);
      calls.push(Number(apiUrl.searchParams.get("page")));
      await handler(route, calls.at(-1));
    });
    await page.goto(url);
  }

  async function selected(items, tag, status, name) {
    await response((route) => route.fulfill({ json: items }));
    await page.waitForSelector("#download-release:not([hidden])");
    assert.equal(
      await page.locator("#download-version").innerText(),
      `Version ${tag}`,
    );
    assert.equal(await page.locator("#download-channel").innerText(), status);
    assert.equal(
      await page.locator("#install-download-link").getAttribute("href"),
      asset(tag, name).browser_download_url,
    );
    assert.deepEqual(calls, [1]);
    count++;
  }

  async function fallback(handler) {
    await response(handler);
    await page.waitForFunction(() =>
      /Noch keine passende|gerade nicht ermittelt/.test(
        document.getElementById("download-message").textContent,
      ),
    );
    assert.equal(
      await page.locator("#install-download-link").getAttribute("href"),
      releasesPage,
    );
    assert.equal(await page.locator("#download-release").isVisible(), false);
    count++;
  }

  try {
    const stable = release("v1.0.0", "2026-02-01T10:00:00Z", false);
    const beta = release("v1.1.0-beta.2", "2026-03-01T10:00:00Z", true, [
      asset("v1.1.0-beta.2", "A-Cozy-Adventure-v1.1.0-beta.2.zip"),
      asset("v1.1.0-beta.2"),
    ]);
    const draft = { ...release("v9.0.0", "2026-04-01T10:00:00Z"), draft: true };
    await selected([stable, draft, beta], beta.tag_name, "Beta");
    await selected([beta, stable], beta.tag_name, "Beta");
    await selected(
      [beta, { ...stable, published_at: "2026-04-01T10:00:00Z" }],
      stable.tag_name,
      "Stable",
    );
    await selected(
      [release("v0.0.1", "2026-01-01T10:00:00Z")],
      "v0.0.1",
      "Alpha",
    );
    await selected(
      [release("v0.2.0-alpha.2", "2026-01-01T10:00:00Z")],
      "v0.2.0-alpha.2",
      "Alpha",
    );
    await selected(
      [
        {
          ...release("v0.4.0", "2026-01-01T10:00:00Z"),
          name: "A Cozy Adventure Beta",
        },
      ],
      "v0.4.0",
      "Beta",
    );
    await selected(
      [release("v1.0.0-rc.1", "2026-01-01T10:00:00Z")],
      "v1.0.0-rc.1",
      "Beta",
    );
    await selected(
      [release("v9.0.0", "2026-04-01T10:00:00Z", false, []), stable],
      stable.tag_name,
      "Stable",
    );
    for (const name of [
      "A_Cozy_Adventure_v0.1.0.zip",
      "A-Cozy-Adventure.zip",
      "Prism-Instance.ZIP",
      "A-Cozy-Adventure-Installer.zip",
    ]) {
      await selected(
        [
          release("v0.1.0", "2026-01-01T10:00:00Z", true, [
            asset("v0.1.0", name),
          ]),
        ],
        "v0.1.0",
        "Alpha",
        name,
      );
    }
    const rejected = [
      "A-Cozy-Adventure-Prism-backup.zip",
      "A-Cozy-Adventure-server-v0.1.0.zip",
      "Prism-source.zip",
      "Prism-config.zip",
      "Prism-audit.zip",
      "Prism-resourcepack.zip",
      "unrelated.zip",
      "Prism.zip.sha256",
      "Prism.jar",
    ].map((name) => asset("v0.1.0", name));
    rejected.push(
      { ...asset("v0.1.0"), state: "new" },
      { ...asset("v0.1.0"), browser_download_url: "javascript:alert(1)" },
      {
        ...asset("v0.1.0"),
        browser_download_url: "https://evil.invalid/Prism.zip",
      },
      {
        ...asset("v0.1.0"),
        browser_download_url:
          "https://github.com/other/repository/releases/download/v0.1.0/Prism.zip",
      },
      null,
      {},
    );
    await fallback((route) =>
      route.fulfill({
        json: [
          {
            ...release("v0.1.0", "2026-01-01T10:00:00Z", true, rejected),
            zipball_url:
              "https://api.github.com/repos/BlueFeniks25/a-cozy-adventure/zipball/v0.1.0",
          },
        ],
      }),
    );
    await fallback((route) =>
      route.fulfill({ json: [draft, { ...stable, published_at: null }] }),
    );
    await fallback((route) => route.fulfill({ json: [] }));

    // A later API page can contain a release with a more recent publication date.
    await response((route, pageNumber) =>
      route.fulfill(
        pageNumber === 1
          ? {
              json: [stable],
              headers: {
                "Access-Control-Expose-Headers": "Link",
                Link: `<https://api.github.com/repos/BlueFeniks25/a-cozy-adventure/releases?per_page=100&page=2>; rel="next"`,
              },
            }
          : { json: [beta] },
      ),
    );
    await page.waitForSelector("#download-release:not([hidden])");
    assert.equal(
      await page.locator("#download-version").innerText(),
      `Version ${beta.tag_name}`,
    );
    assert.deepEqual(calls, [1, 2]);
    count++;

    await response((route, pageNumber) =>
      route.fulfill({
        json:
          pageNumber === 1
            ? Array.from({ length: 100 }, () => ({ ...stable, assets: [] }))
            : [beta],
      }),
    );
    await page.waitForSelector("#download-release:not([hidden])");
    assert.equal(
      await page.locator("#download-version").innerText(),
      `Version ${beta.tag_name}`,
    );
    assert.deepEqual(calls, [1, 2]);
    count++;

    for (const status of [403, 404, 503])
      await fallback((route) => route.fulfill({ status, body: "unavailable" }));
    await fallback((route) => route.abort("failed"));
    await fallback((route) =>
      route.fulfill({ contentType: "application/json", body: "not-json" }),
    );
    await fallback((route) =>
      route.fulfill({ json: { message: "rate limit" } }),
    );
    await fallback((route, pageNumber) =>
      pageNumber === 1
        ? route.fulfill({
            json: [stable],
            headers: {
              "Access-Control-Expose-Headers": "Link",
              Link: '<https://api.github.com/next>; rel="next"',
            },
          })
        : route.fulfill({ status: 503 }),
    );
    await fallback((route) =>
      route.fulfill({
        json: [stable],
        headers: {
          "Access-Control-Expose-Headers": "Link",
          Link: '<https://api.github.com/next>; rel="next"',
        },
      }),
    );
    assert.equal(calls.length, 10);

    const unsafeTag = 'v0.3.0-alpha <img src=x onerror="alert(1)">';
    await selected(
      [release(unsafeTag, "2026-05-01T10:00:00Z")],
      unsafeTag,
      "Alpha",
    );
    assert.equal(await page.locator("#download-release img").count(), 0);

    // Successful ZIP layout on desktop and mobile.
    await selected([beta], beta.tag_name, "Beta");
    await page
      .locator(".install-download")
      .screenshot({
        path: path.join(os.tmpdir(), "cozy-download-desktop.png"),
      });
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
      );
    }
    await page.setViewportSize({ width: 390, height: 900 });
    await page
      .locator(".install-download")
      .screenshot({ path: path.join(os.tmpdir(), "cozy-download-mobile.png") });

    // A stalled request leaves the initial link usable and times out after 8 seconds.
    await page.clock.install();
    await response(() => {});
    assert.equal(
      await page.locator("#install-download-link").getAttribute("href"),
      releasesPage,
    );
    await page.clock.fastForward(8001);
    await page.waitForFunction(() =>
      document
        .getElementById("download-message")
        .textContent.includes("gerade nicht ermittelt"),
    );
    assert.equal(
      await page.locator("#install-download-link").getAttribute("href"),
      releasesPage,
    );
    count++;

    const context = await browser.newContext({ javaScriptEnabled: false });
    try {
      const staticPage = await context.newPage();
      await staticPage.goto(url);
      assert.equal(
        await staticPage.locator("#install-download-link").getAttribute("href"),
        releasesPage,
      );
      assert.equal(
        await staticPage.locator("#install-download-link").isVisible(),
        true,
      );
      count++;
    } finally {
      await context.close();
    }
    assert.deepEqual(errors, []);
    console.log(
      `Release browser checks passed: ${count} scenarios, including pagination, drafts, Alpha/Beta/Stable, ZIP selection, errors, timeout, no JavaScript and responsive download layout.`,
    );
  } finally {
    await page.close();
  }
}

module.exports = { checkReleases, releasesApi, releasesPage };
