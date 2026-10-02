// Models: what hone-models offers for each role, installed or not, with observed latency.
import { api, duration, h, replace } from "../core.js";

export async function render(main) {
  const data = await api("/models");
  const table = (title, rows, image) => h("section", { class: "panel" }, h("div", { class: "panel-head" }, h("h2", {}, title), h("span", { class: "caption" }, `${rows.length} in the registry`)),
    h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, ["Model", "Where", "Installed", image ? "References" : "Vision", "Features", "Median time"].map((t, i) => h("th", { class: i === 5 ? "num" : null }, t)))),
      h("tbody", {}, rows.map((m) => h("tr", {},
        h("td", {}, h("div", { class: "mono", style: "font-weight:500" }, m.id), h("div", { class: "caption", style: "white-space:normal;max-width:420px" }, m.note),
          m.prompt_guide ? h("div", { class: "caption", style: "white-space:normal;max-width:420px" }, `Prompting: ${m.prompt_guide}`) : null),
        h("td", {}, m.local ? "Local" : "Hosted"),
        h("td", {}, m.available ? (m.installed === "yes" ? "Yes" : "Unknown") : h("span", { class: "pill failed" }, "Not available")),
        h("td", {}, image ? (m.max_references === null ? "Unknown" : String(m.max_references)) : (m.vision === null ? "Unknown" : m.vision ? "Yes" : "No")),
        h("td", { style: "white-space:normal" }, (m.features || []).join(", ") || "—"),
        h("td", { class: "num" }, m.latency_s === null || m.latency_s === undefined ? "—" : duration(m.latency_s))))))));
  replace(main, h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Models"), h("p", { class: "muted" }, "Every model call goes through hone-models. Profiles choose which model plays which role."))),
    table("Image models: generator, editor, upscaler", data.image || [], true), table("Chat models: planner and judge", data.chat || [], false));
}
