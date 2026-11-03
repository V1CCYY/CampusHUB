(function () {
  "use strict";

  const preview = document.getElementById("mapaPreview");
  if (!preview) return;

  const previewLabel = preview.querySelector(".mapa-preview-label");
  const previewPath = preview.querySelector(".mapa-preview-path");
  const previewDesc = preview.querySelector(".mapa-preview-desc");

  const badgeColors = {
    publico: "#38bdf8",
    logado: "#2dd4bf",
    admin: "#f97316",
  };

  function updatePreview(el) {
    const name = el.querySelector(".mapa-node-name")
      ? el.querySelector(".mapa-node-name").textContent
      : el.textContent.trim();
    const path = el.querySelector(".mapa-node-path")
      ? el.querySelector(".mapa-node-path").textContent
      : el.getAttribute("href");
    const desc = el.getAttribute("data-desc") || "";
    const badge = el.getAttribute("data-badge") || "publico";

    previewLabel.textContent = name;
    previewPath.textContent = path;
    previewDesc.textContent = desc;
    preview.style.borderLeftColor = badgeColors[badge] || "#38bdf8";
  }

  document.querySelectorAll(".mapa-node, .mapa-child, .mapa-node-root").forEach((el) => {
    el.addEventListener("mouseenter", () => updatePreview(el));
    el.addEventListener("focus", () => updatePreview(el));
  });

  const filters = document.querySelectorAll(".mapa-filter");
  const cols = document.querySelectorAll(".mapa-col");

  filters.forEach((btn) => {
    btn.addEventListener("click", () => {
      filters.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const filter = btn.getAttribute("data-filter");

      cols.forEach((col) => {
        const node = col.querySelector(".mapa-node");
        const badge = node ? node.getAttribute("data-badge") : "publico";
        const matches = filter === "todos" || filter === badge;
        col.classList.toggle("mapa-dim", !matches);
      });
    });
  });

  const search = document.querySelector(".mapa-search");
  if (search) {
    search.addEventListener("input", () => {
      const term = search.value.trim().toLowerCase();

      cols.forEach((col) => {
        if (!term) {
          col.classList.remove("mapa-dim", "mapa-match");
          return;
        }

        const text = col.textContent.toLowerCase();
        const matches = text.includes(term);
        col.classList.toggle("mapa-dim", !matches);
        col.classList.toggle("mapa-match", matches);
      });

      const activeFilter = document.querySelector(".mapa-filter.active");
      if (activeFilter && activeFilter.getAttribute("data-filter") !== "todos" && !term) {
        activeFilter.click();
      }
    });
  }
})();
