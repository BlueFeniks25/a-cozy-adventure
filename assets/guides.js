/* Progressive enhancement: all instructions and key records also work without JS. */
(() => {
  "use strict";
  const search = document.querySelector("#control-search");
  const category = document.querySelector("#control-category");
  const reset = document.querySelector("#control-reset");
  const rows = [...document.querySelectorAll(".control-row")];
  if (!search || !category || !reset) return;
  const normalize = (text) =>
    text
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("de");
  function filter() {
    const query = normalize(search.value.trim());
    let count = 0;
    for (const row of rows) {
      row.hidden =
        !(
          category.value === "all" || row.dataset.category === category.value
        ) ||
        !normalize(`${row.dataset.category} ${row.textContent}`).includes(
          query,
        );
      if (!row.hidden) count++;
    }
    for (const group of document.querySelectorAll("[data-controls-group]")) {
      group.hidden = ![...group.querySelectorAll(".control-row")].some(
        (row) => !row.hidden,
      );
    }
    document.querySelector("#control-count").textContent =
      `${count} von ${rows.length} Funktionen`;
    document.querySelector("#control-empty").hidden = count > 0;
  }
  search.addEventListener("input", filter);
  category.addEventListener("change", filter);
  reset.addEventListener("click", () => {
    search.value = "";
    category.value = "all";
    filter();
    search.focus();
  });
  filter();
})();
