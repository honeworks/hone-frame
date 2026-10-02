// Presets: the built-in catalogue, useful before any project exists (brief §12).
import { h, replace, state } from "../core.js";

const NAMES = {
  style_pack: "Project style packs", character_presentation: "Character presentations", environment_presentation: "Environment presentations",
  asset_presentation: "Asset presentations", camera: "Camera and framing", lighting: "Lighting", expression: "Expressions", pose: "Poses and actions",
  interaction: "Interaction templates", state: "State templates", sheet_layout: "Sheet layouts", profile: "Generation profiles",
  selection: "Selection recipes", judging: "Judging profiles",
};

export async function render(main, [category]) {
  const cats = Object.keys(state.presets || {});
  const current = cats.includes(category) ? category : cats[0];
  replace(main, h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Presets"), h("p", { class: "muted" }, "Built in and ready before your first project. Each category can be chosen on its own; a style pack only sets defaults."))),
    h("nav", { class: "tabs", "aria-label": "Categories" }, cats.map((c) => h("a", { href: `#/presets/${c}`, "aria-current": c === current ? "page" : null }, NAMES[c] || c))),
    h("div", { class: "tiles big" }, (state.presets[current] || []).map((p) => h("article", { class: "panel stack", style: "padding:16px" },
      h("div", { class: "row" }, h("h2", {}, p.name), h("span", { class: "spacer" }), h("span", { class: "chip" }, `v${p.version}`), p.builtin ? null : h("span", { class: "chip accent" }, "Yours")),
      h("p", { style: "margin:0" }, p.description),
      p.subject_kinds.length ? h("div", { class: "chips" }, p.subject_kinds.map((k) => h("span", { class: "chip" }, k))) : null,
      p.prompt.prefix || p.prompt.suffix ? h("div", { class: "mono caption" }, [p.prompt.prefix, p.prompt.suffix].filter(Boolean).join(" … ")) : null,
      details(p)))));
}

function details(p) {
  const values = p.values || {};
  if (values.checks) return h("ul", { class: "caption", style: "margin:0;padding-left:18px" }, values.checks.map((c) => h("li", {}, `${c.name}${c.required ? "" : " (preference)"}: ${c.question}`)));
  if (values.outputs) return values.outputs.length ? h("div", { class: "chips" }, values.outputs.map((o) => h("span", { class: "chip" }, o.label))) : h("span", { class: "caption" }, values.from_states ? `One per ${values.from_states} state` : "The hero view only");
  if (values.generator) return h("div", { class: "mono caption" }, `generator ${values.generator} · editor ${values.editor} · judge ${values.judge}`);
  return null;
}
