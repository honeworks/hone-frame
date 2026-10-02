// Settings: project defaults, appearance, connections (names only, never values) and usage.
import { api, failure, field, h, presetOptions, projectPath, replace, select, state, toast, toggle } from "../core.js";
import { applyTheme } from "../app.js";

export async function render(main) {
  const project = await api(projectPath());
  const d = project.defaults;
  const profile = select(presetOptions("profile"), d.profile);
  const strategy = select([["batch", "Generate candidates, then pick"], ["sequential", "Generate, judge, then continue"]], d.selection.strategy);
  const rounds = h("input", { class: "input", type: "number", min: 1, max: 10, value: d.selection.rounds });
  const candidates = h("input", { class: "input", type: "number", min: 1, max: 8, value: d.selection.candidates });
  const stop = select([["all_rounds", "Run all rounds"], ["stop_on_pass", "Stop when a candidate passes"]], d.selection.stop);
  const judge = toggle(d.selection.auto_judge);
  const pick = toggle(d.selection.auto_pick);
  const retries = h("input", { class: "input", type: "number", min: 0, max: 5, value: d.selection.technical_retries });
  const pack = select(presetOptions("style_pack"), project.style_pack);
  const theme = select([["system", "Follow the system"], ["light", "Light"], ["dark", "Dark"]], state.settings?.theme || "system");
  const save = async () => {
    try {
      await api(projectPath(), { method: "PATCH", body: { style_pack: pack.value, defaults: { ...d, profile: profile.value, selection: {
        strategy: strategy.value, rounds: Number(rounds.value), candidates: Number(candidates.value), stop: stop.value,
        auto_judge: judge.input.checked, auto_pick: pick.input.checked, technical_retries: Number(retries.value) } } } });
      state.settings = await api("/workspace/settings", { method: "PATCH", body: { theme: theme.value } });
      applyTheme(theme.value);
      toast("Settings saved. New requests use them; running jobs keep theirs.");
    } catch (error) { failure(error); }
  };
  replace(main, h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Settings"), h("p", { class: "muted" }, "Project defaults apply to new requests; a request can override them, and a running job never changes.")),
    h("button", { class: "btn primary", onclick: save }, "Save settings")),
  h("div", { class: "grid" },
    h("section", { class: "panel span-6 stack" }, h("h2", {}, "Generation defaults"), field("Style pack", pack), field("Profile", profile),
      field("Strategy", strategy), h("div", { class: "row" }, field("Rounds per output", rounds), field("Candidates per round", candidates)),
      field("Stopping rule", stop), field("Technical retries", retries, "For model or service failures; they never add creative rounds."),
      h("div", { class: "setting" }, h("div", {}, h("div", { style: "font-weight:500" }, "Auto judge"), h("div", { class: "caption" }, "Evaluate every candidate with the judge model")), judge.node),
      h("div", { class: "setting" }, h("div", {}, h("div", { style: "font-weight:500" }, "Auto pick"), h("div", { class: "caption" }, "Needs the judge: picks the best candidate that passes")), pick.node)),
    h("section", { class: "panel span-6 stack" }, h("h2", {}, "Appearance"), field("Theme", theme),
      h("hr", { class: "divider" }), h("h2", {}, "Connections"),
      h("p", { class: "caption" }, "Models come from hone-models: its packaged catalogue, ~/.config/hone/models.toml and ./hone-models.toml. API keys stay in environment variables or .env, and are never shown or exported here."),
      h("hr", { class: "divider" }), h("h2", {}, "Workspace"), h("p", { class: "mono caption" }, project.id))));
}
