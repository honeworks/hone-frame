// Overview: four real metrics, the live queue and recent images (brief §14, §16).
import { api, duration, empty, h, img, pill, progressBar, projectPath, range, replace, state } from "../core.js";

export async function render(main) {
  const data = await api(projectPath("/overview"));
  const project = state.projects.find((p) => p.id === state.project);
  const m = data.metrics;
  const metric = (label, value, none) => h("div", { class: "panel span-3 metric" }, h("span", { class: "overline" }, label),
    h("span", { class: `value${value === null ? " none" : ""}` }, value === null ? "—" : value),
    value === null ? h("span", { class: "caption" }, none) : null);
  replace(main,
    h("div", { class: "page-head" }, h("div", {}, h("div", { class: "crumbs caption" }, h("a", { href: "#/projects" }, "Projects"), " / ", project?.name),
      h("h1", {}, project?.name || "Overview"), project?.brief ? h("p", { class: "muted" }, project.brief) : null),
      h("a", { class: "btn primary", href: "#/create" }, "Generate")),
    h("div", { class: "grid" },
      metric("Images generated today", m.images_today, "No generation has run yet."),
      metric("Queued · running", `${m.queued} · ${m.running}`, ""),
      metric("Median render time today", m.median_render_s === null ? null : duration(m.median_render_s), "Nothing rendered today."),
      metric("GPU time today", m.gpu_s_today === null ? null : duration(m.gpu_s_today), "No local GPU work today."),
      h("section", { class: "panel span-8" }, h("div", { class: "panel-head" }, h("h2", {}, "Live queue"), h("a", { href: "#/queue" }, "Open queue")),
        data.queue.length ? h("div", { class: "stack" }, data.queue.map(queueRow)) : h("p", { class: "muted" }, "Nothing is queued or running.")),
      h("section", { class: "panel span-4" }, h("h2", {}, "This project"), h("div", { class: "stack", style: "margin-top:12px" },
        [["Characters", data.counts.character, "#/library/characters"], ["Environments", data.counts.environment, "#/library/environments"],
          ["Assets", data.counts.asset, "#/library/assets"], ["Images", data.counts.images, "#/library/images"],
          ["Scenes", data.counts.scenes, "#/scenes"], ["Sheets", data.counts.sheets, "#/sheets"]].map(([label, n, href]) =>
          h("a", { class: "row", href, style: "justify-content:space-between;color:inherit" }, h("span", {}, label), h("span", { class: "count" }, n))))),
      h("section", { class: "panel span-12" }, h("div", { class: "panel-head" }, h("h2", {}, "Recent images"), h("a", { href: "#/library/images" }, "View all")),
        data.recent.length ? h("div", { class: "tiles" }, data.recent.map((card) => h("a", { class: "tile", href: `#/library/images/${card.id}` },
          h("div", { class: "thumb" }, img(card)), h("div", { class: "meta" }, h("span", { class: "name" }, card.label || card.id),
            h("span", { class: "caption mono" }, `${card.id} · ${card.width} × ${card.height}`)))))
          : empty("No images yet", "Add a character, an environment or an asset in the Library, then generate its references.",
            h("a", { class: "btn primary", href: "#/library/characters" }, "Open Library")))));
}

function queueRow(r) {
  const live = r.status === "running" || r.status === "pausing";
  return h("a", { class: "row", href: `#/queue/${r.project}/${r.id}`, style: "color:inherit;justify-content:space-between" },
    h("div", { style: "min-width:0" }, h("div", { style: "font-weight:600" }, r.title), h("div", { class: "caption" }, `${r.model || r.profile} · round ${r.round || "—"} of ${r.rounds}`)),
    h("div", { class: "row" }, progressBar(r.progress, live), pill(r.status), h("span", { class: "caption" }, range(r.estimate))));
}
