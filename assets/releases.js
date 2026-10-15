"use strict";

(() => {
  const repository = "https://github.com/BlueFeniks25/a-cozy-adventure";
  const api =
    "https://api.github.com/repos/BlueFeniks25/a-cozy-adventure/releases";
  const link = document.getElementById("install-download-link");
  const message = document.getElementById("download-message");

  function installationZip(asset) {
    if (!asset || asset.state !== "uploaded" || typeof asset.name !== "string")
      return false;
    const name = asset.name.toLowerCase();
    if (!name.endsWith(".zip")) return false;
    // Assets only: GitHub's generated zipball_url is never an installation ZIP.
    if (
      /(?:^|[\W_])(backup|server|sources?|config|audit|resourcepacks?)(?:[\W_]|$)/.test(
        name,
      )
    )
      return false;
    const installer =
      /(?:^|[\W_])(prism(?:launcher)?|multimc|install(?:er|ation)?)(?:[\W_]|$)/.test(
        name,
      );
    const pack = /^a[-_. ]cozy[-_. ]adventure(?:[-_. ]v?\d[^/]*)?\.zip$/.test(
      name,
    );
    if (!installer && !pack) return false;
    try {
      const url = new URL(asset.browser_download_url);
      // Only direct download links for this repository, never API or arbitrary URLs.
      return (
        url.origin === "https://github.com" &&
        !url.username &&
        !url.password &&
        url.pathname
          .toLowerCase()
          .startsWith("/bluefeniks25/a-cozy-adventure/releases/download/")
      );
    } catch {
      return false;
    }
  }

  function findRelease(releases) {
    return releases
      .filter(
        (release) =>
          release &&
          release.draft === false &&
          typeof release.prerelease === "boolean" &&
          typeof release.tag_name === "string" &&
          release.tag_name.trim() &&
          Number.isFinite(Date.parse(release.published_at)) &&
          Array.isArray(release.assets),
      )
      .sort(
        (a, b) =>
          Date.parse(b.published_at) - Date.parse(a.published_at) ||
          String(b.id).localeCompare(String(a.id), "en", { numeric: true }),
      )
      .map((release) => ({
        release,
        asset: release.assets.filter(installationZip).sort((a, b) => {
          // Prefer an explicitly labelled Prism asset over the legacy pack ZIP name.
          const priority = (asset) =>
            /prism|multimc/i.test(asset.name)
              ? 0
              : /install/i.test(asset.name)
                ? 1
                : 2;
          return (
            priority(a) - priority(b) ||
            a.name.localeCompare(b.name, "en", { numeric: true })
          );
        })[0],
      }))
      .find((candidate) => candidate.asset);
  }

  function channel(release) {
    if (!release.prerelease) return "Stable";
    // Untagged pre-releases default to Alpha; beta / RC must be named explicitly.
    const label = `${release.tag_name} ${release.name || ""}`;
    return /(?:^|[^a-z])(?:beta|rc)(?:[^a-z]|$)/i.test(label)
      ? "Beta"
      : "Alpha";
  }

  async function loadRelease() {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const releases = [];
      // The API lists by creation date; publication order can differ. Inspect all pages.
      for (let page = 1; ; page++) {
        if (page > 10) throw new Error("Release pagination limit reached");
        const response = await fetch(`${api}?per_page=100&page=${page}`, {
          headers: { Accept: "application/vnd.github+json" },
          credentials: "omit",
          referrerPolicy: "no-referrer",
          cache: "no-cache",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Releases unavailable");
        const data = await response.json();
        if (!Array.isArray(data)) throw new Error("Invalid release data");
        releases.push(...data);
        if (
          !response.headers.get("Link")?.includes('rel="next"') &&
          data.length < 100
        )
          break;
      }
      const selected = findRelease(releases);
      if (!selected) {
        message.textContent =
          "Noch keine passende Installations-ZIP verfügbar. Schau auf unserer Releases-Seite vorbei.";
        return;
      }
      const { release, asset } = selected;
      const status = channel(release);
      document.getElementById("download-version").textContent =
        `Version ${release.tag_name}`;
      const badge = document.getElementById("download-channel");
      badge.textContent = status;
      badge.dataset.channel = status.toLowerCase();
      document.getElementById("download-release").hidden = false;
      message.textContent =
        "Für Prism Launcher bereit – herunterladen und importieren.";
      link.href = asset.browser_download_url;
      link.textContent = "Installations-ZIP herunterladen ↓";
      link.setAttribute(
        "aria-label",
        `Installations-ZIP ${release.tag_name} (${status}) herunterladen`,
      );
      link.classList.replace("button-secondary", "button-primary");
    } catch {
      message.textContent =
        "Der Download konnte gerade nicht ermittelt werden. Alle Versionen findest du auf GitHub.";
      link.href = `${repository}/releases`;
    } finally {
      clearTimeout(timer);
    }
  }

  loadRelease();
})();
