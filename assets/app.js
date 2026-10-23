"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const symbols = {
    "Alle Mods": "▦",
    Abenteuer: "⚔",
    Magie: "✧",
    Bauen: "⌂",
    Welt: "♧",
    Tiere: "♞",
    "Küche & Garten": "♧",
    Komfort: "◇",
    Atmosphäre: "☾",
    Performance: "ϟ",
    Bibliotheken: "▤",
    Sonstiges: "·",
  };
  const collator = new Intl.Collator("de", {
    sensitivity: "base",
    numeric: true,
  });
  const state = { mods: [], categories: [], category: "Alle Mods" };
  const dialog = $("mod-dialog");
  let lastTrigger;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function safeUrl(value, icon = false) {
    if (typeof value !== "string") return null;
    try {
      const url = new URL(value);
      if (url.protocol !== "https:" || url.username || url.password)
        return null;
      if (
        icon &&
        url.hostname !== "cdn.modrinth.com" &&
        !url.hostname.endsWith(".forgecdn.net")
      )
        return null;
      return url.href;
    } catch {
      return null;
    }
  }

  function modIcon(mod) {
    const wrapper = element("span", "mod-icon");
    wrapper.setAttribute("aria-hidden", "true");
    const initials =
      mod.name
        .replace(/[^\p{L}\p{N} ]/gu, "")
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((s) => s[0])
        .join("") || "✧";
    wrapper.textContent = initials;
    const url = safeUrl(mod.icon, true);
    if (url) {
      const image = document.createElement("img");
      image.alt = "";
      image.loading = "lazy";
      image.decoding = "async";
      image.referrerPolicy = "no-referrer";
      wrapper.classList.add("is-loading");
      image.addEventListener(
        "load",
        () => {
          wrapper.replaceChildren(image);
          wrapper.classList.remove("is-loading");
        },
        { once: true },
      );
      image.addEventListener(
        "error",
        () => {
          wrapper.textContent = initials;
          wrapper.classList.remove("is-loading");
        },
        { once: true },
      );
      wrapper.append(image);
      image.src = url;
    }
    return wrapper;
  }

  function badge(category) {
    const node = element("span", "category-badge", category);
    node.dataset.category = category;
    return node;
  }

  function renderCategories() {
    const fragment = document.createDocumentFragment();
    for (const category of [
      { name: "Alle Mods", count: state.mods.length },
      ...state.categories,
    ]) {
      const button = element("button", "category-button");
      button.type = "button";
      button.setAttribute(
        "aria-pressed",
        String(category.name === state.category),
      );
      const symbol = element(
        "span",
        "category-symbol",
        symbols[category.name] || "·",
      );
      symbol.setAttribute("aria-hidden", "true");
      button.append(
        symbol,
        element("span", "category-label", category.name),
        element("span", "category-count", String(category.count)),
      );
      button.addEventListener("click", () => {
        state.category = category.name;
        for (const item of $("categories").children)
          item.setAttribute("aria-pressed", String(item === button));
        renderMods();
      });
      fragment.append(button);
    }
    $("categories").replaceChildren(fragment);
  }

  function card(mod) {
    const button = element("button", "mod-card");
    button.type = "button";
    button.setAttribute("aria-label", `${mod.name} – Details anzeigen`);
    const header = element("div", "mod-card-header");
    const title = element("div");
    title.append(
      element("h3", "", mod.name),
      element("div", "card-source", mod.source),
    );
    header.append(modIcon(mod), title);
    const footer = element("div", "mod-card-footer");
    const arrow = element("span", "card-arrow", "↗");
    arrow.setAttribute("aria-hidden", "true");
    footer.append(badge(mod.categories[0]), arrow);
    button.append(
      header,
      element("p", "mod-card-description", mod.description),
      footer,
    );
    button.addEventListener("click", () => openDetail(mod, button));
    return button;
  }

  function normalize(text) {
    return text
      .toLocaleLowerCase("de")
      .normalize("NFD")
      .replace(/\p{M}/gu, "")
      .replace(/ß/g, "ss");
  }

  function renderMods() {
    const query = normalize($("search").value.trim());
    const filtered = state.mods.filter(
      (mod) =>
        (state.category === "Alle Mods" ||
          mod.categories.includes(state.category)) &&
        (normalize(mod.name).includes(query) ||
          normalize(mod.packwizName || "").includes(query)),
    );
    const sort = $("sort").value;
    filtered.sort((a, b) => {
      if (sort === "recommended" && a.featured !== b.featured)
        return Number(b.featured) - Number(a.featured);
      return collator.compare(a.name, b.name) * (sort === "za" ? -1 : 1);
    });
    const fragment = document.createDocumentFragment();
    for (const mod of filtered) fragment.append(card(mod));
    $("mod-grid").replaceChildren(fragment);
    $("result-count").replaceChildren(
      element("strong", "", String(filtered.length)),
      document.createTextNode(
        ` von ${state.mods.length} Mods${state.category !== "Alle Mods" ? ` · ${state.category}` : " · für deine nächste Entdeckung"}`,
      ),
    );
    $("empty-state").hidden = filtered.length !== 0;
    $("catalog-footnote").hidden = filtered.length === 0;
    $("reset").hidden = !query && state.category === "Alle Mods";
  }

  function addFact(label, value) {
    if (value)
      $("detail-facts").append(
        element("dt", "", label),
        element("dd", "", value),
      );
  }

  function addLink(label, value) {
    const url = safeUrl(value);
    if (
      !url ||
      [...$("detail-links").children].some((node) => node.href === url)
    )
      return;
    const link = element("a", "", `${label} ↗`);
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    $("detail-links").append(link);
  }

  function openDetail(mod, trigger) {
    lastTrigger = trigger;
    const title = element("h2", "", mod.name);
    title.id = "detail-title";
    const heading = element("div");
    heading.append(title, element("div", "card-source", mod.source));
    $("detail-header").replaceChildren(modIcon(mod), heading);
    $("detail-description").textContent = mod.description;
    $("detail-categories").replaceChildren(...mod.categories.map(badge));
    $("detail-original").hidden = !mod.originalSummary;
    $("detail-summary").textContent = mod.originalSummary || "";
    $("detail-attribution").textContent =
      `Original-Kurzbeschreibung · ${mod.metadataSource || mod.source}`;
    $("detail-facts").replaceChildren();
    addFact("Im Pack", mod.packwizName);
    if (mod.version) addFact("Version", mod.version);
    if (mod.role === "bootstrap") addFact("Installation", "AutoModpack vor dem Serverbeitritt selbst installieren");
    addFact("Datei", mod.filename);
    addFact(
      "Umgebung",
      { both: "Client & Server", client: "Client", server: "Server" }[
        mod.side
      ] || mod.side,
    );
    addFact("Quelle", mod.source);
    addFact("Projekt-ID", mod.projectId);
    addFact("Lizenzangabe", mod.license);
    addFact(
      "Entwickler",
      Array.isArray(mod.authors) ? mod.authors.join(", ") : null,
    );
    const fallback = [];
    if (!mod.metadataSource)
      fallback.push(
        "Zusätzliche Projektinformationen sind derzeit nicht verfügbar. Name und Dateiangaben stammen aus unserem Modpack.",
      );
    if (mod.descriptionKind === "category-fallback")
      fallback.push(
        "Der deutsche Kurztext beschreibt die automatisch zugeordnete Kategorie. Mehr zur konkreten Mod findest du auf der Projektseite.",
      );
    $("detail-fallback").textContent = fallback.join(" ");
    $("detail-fallback").hidden = fallback.length === 0;
    $("detail-links").replaceChildren();
    addLink(`Auf ${mod.source} ansehen`, mod.url);
    addLink(`Projekt auf ${mod.metadataSource || "Modrinth"}`, mod.metadataUrl);
    addLink("Quellcode", mod.codeUrl);
    addLink("Wiki", mod.wikiUrl);
    dialog.showModal();
  }

  function resetFilters() {
    $("search").value = "";
    state.category = "Alle Mods";
    renderCategories();
    renderMods();
  }

  function validateCatalog(data) {
    if (
      data?.schemaVersion !== 1 ||
      !data.pack ||
      !Array.isArray(data.mods) ||
      !Array.isArray(data.categories) ||
      data.mods.length === 0
    )
      throw new Error("Invalid catalog");
    for (const mod of data.mods) {
      if (
        typeof mod.name !== "string" ||
        typeof mod.description !== "string" ||
        typeof mod.source !== "string" ||
        !Array.isArray(mod.categories) ||
        !mod.categories.length ||
        !mod.categories.every((v) => typeof v === "string")
      )
        throw new Error("Invalid mod");
    }
    for (const category of data.categories) {
      if (
        typeof category.name !== "string" ||
        !Number.isInteger(category.count)
      )
        throw new Error("Invalid category");
    }
  }

  async function loadCatalog() {
    $("catalog-content").setAttribute("aria-busy", "true");
    $("error-state").hidden = true;
    $("retry").disabled = true;
    try {
      const response = await fetch("mods.json", { cache: "no-cache" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      validateCatalog(data);
      state.mods = data.mods;
      state.categories = data.categories;
      $("hero-count").textContent = String(data.mods.length);
      $("minecraft-version").textContent = data.pack.minecraft || "–";
      $("fabric-version").textContent = data.pack.fabric || "–";
      $("search").disabled = false;
      $("sort").disabled = false;
      renderCategories();
      renderMods();
    } catch {
      $("result-count").textContent = "Modliste derzeit nicht verfügbar";
      $("error-state").hidden = false;
      $("hero-count").textContent = "–";
      $("minecraft-version").textContent = "–";
      $("fabric-version").textContent = "–";
    } finally {
      $("catalog-content").setAttribute("aria-busy", "false");
      $("retry").disabled = false;
    }
  }

  $("search").addEventListener("input", renderMods);
  $("sort").addEventListener("change", renderMods);
  $("reset").addEventListener("click", resetFilters);
  $("empty-reset").addEventListener("click", () => {
    resetFilters();
    $("search").focus();
  });
  $("retry").addEventListener("click", loadCatalog);
  $("dialog-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    const bounds = dialog.getBoundingClientRect();
    if (
      event.target === dialog &&
      (event.clientX < bounds.left ||
        event.clientX > bounds.right ||
        event.clientY < bounds.top ||
        event.clientY > bounds.bottom)
    )
      dialog.close();
  });
  dialog.addEventListener("close", () => {
    lastTrigger?.focus();
  });
  loadCatalog();
})();
