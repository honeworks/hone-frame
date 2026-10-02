// Create: a settings column and a larger results area with the plan before launch (brief §14).
import { api, empty, failure, field, h, presetOptions, projectPath, range, replace, select, toggle } from "../core.js";

const TASKS = [
  ["subject_references", "Reference images of a subject"], ["scene", "A scene"], ["coverage", "Camera coverage of a scene"],
  ["interaction", "A character using an object"], ["state_pair", "Before / after states"], ["sequence", "A sequence of frames"],
  ["variations", "A variation grid"],
];

export async function render(main) {
  const [subjects, scenes, sequences] = await Promise.all([api(projectPath("/subjects")), api(projectPath("/scenes")), api(projectPath("/sequences"))]);
  const opts = (rows, label) => rows.map((r) => [r.id, label(r)]);
  const ofKind = (k) => opts(subjects.filter((s) => s.kind === k), (s) => s.name);
  const c = {
    task: select(TASKS, "subject_references"),
    subject: select(opts(subjects, (s) => `${s.name} (${s.kind})`), subjects[0]?.id),
    presentation: select([["", "Style pack default"]], ""),
    scene: select(opts(scenes, (s) => s.name), scenes[0]?.id),
    sequence: select(opts(sequences, (s) => s.name), sequences[0]?.id),
    character: select(ofKind("character"), null), asset: select(ofKind("asset"), null),
    action: select(presetOptions("interaction"), "hold-cup"),
    state: select(presetOptions("state"), "empty-full"),
    cameras: h("input", { class: "input", value: "wide, medium, close-up, reverse" }),
    axes: h("textarea", { class: "input", value: "expression: happy, sad, focused\nlighting: soft-daylight, moonlight" }),
    sheet: select(presetOptions("sheet_layout", { blank: "No sheet" }), ""),
    note: h("textarea", { class: "input", placeholder: "Anything else the prompt should say." }),
    profile: select(presetOptions("profile"), "draft"),
    strategy: select([["batch", "Generate candidates, then pick"], ["sequential", "Generate, judge, then continue"]], "batch"),
    rounds: h("input", { class: "input", type: "number", min: 1, max: 10, value: 3 }),
    candidates: h("input", { class: "input", type: "number", min: 1, max: 8, value: 1 }),
    stop: select([["all_rounds", "Run all rounds"], ["stop_on_pass", "Stop when a candidate passes"]], "all_rounds"),
    retries: h("input", { class: "input", type: "number", min: 0, max: 5, value: 2 }),
  };
  const judge = toggle(true);
  const pick = toggle(true);
  const results = h("section", { class: "panel", "aria-live": "polite" });
  const go = h("button", { class: "btn primary", style: "height:44px" }, "Generate");
  const fields = h("div", { class: "stack" });

  const setPresentations = () => {
    const kind = subjects.find((s) => s.id === c.subject.value)?.kind;
    replace(c.presentation, [["", "Style pack default"], ...presetOptions(`${kind}_presentation`, { kind })].map(([v, t]) => h("option", { value: v }, t)));
  };
  setPresentations();
  c.subject.addEventListener("change", setPresentations);

  const which = () => c.task.value;
  const drawFields = () => {
    const t = which();
    const parts = {
      subject_references: () => [field("Subject", c.subject), field("Presentation", c.presentation), field("Compose a sheet when accepted", c.sheet)],
      scene: () => [field("Scene", c.scene)], coverage: () => [field("Scene", c.scene), field("Cameras", c.cameras, "Camera presets or words, comma separated.")],
      interaction: () => [field("Character", c.character), field("Object", c.asset), field("Interaction", c.action)],
      state_pair: () => [field("Subject", c.subject), field("State", c.state)], sequence: () => [field("Sequence", c.sequence)],
      variations: () => [field("Scene", c.scene), field("Axes", c.axes, "One axis per line: outfit, expression, lighting, camera, state, style or pose.")],
    }[t]();
    replace(fields, parts);
  };

  const request = () => {
    const t = which();
    const selection = { strategy: c.strategy.value, rounds: Number(c.rounds.value), candidates: Number(c.candidates.value),
      stop: c.stop.value, technical_retries: Number(c.retries.value), auto_judge: judge.input.checked, auto_pick: pick.input.checked };
    const base = { kind: t, profile: c.profile.value, selection, note: c.note.value };
    const axes = Object.fromEntries(c.axes.value.split("\n").map((l) => l.split(":")).filter((p) => p.length === 2)
      .map(([k, v]) => [k.trim(), v.split(",").map((x) => x.trim()).filter(Boolean)]));
    return {
      subject_references: { ...base, subject_id: c.subject.value, presentation: c.presentation.value || null, sheet_layout: c.sheet.value || null },
      scene: { ...base, scene_id: c.scene.value }, coverage: { ...base, scene_id: c.scene.value, cameras: c.cameras.value.split(",").map((x) => x.trim()).filter(Boolean) },
      interaction: { ...base, character_id: c.character.value, asset_id: c.asset.value, action: c.action.value },
      state_pair: { ...base, subject_id: c.subject.value, state: c.state.value }, sequence: { ...base, sequence_id: c.sequence.value },
      variations: { ...base, scene_id: c.scene.value, axes },
    }[t];
  };

  let timer = null;
  const preview = () => { clearTimeout(timer); timer = setTimeout(drawPlan, 250); };
  async function drawPlan() {
    try {
      const plan = await api(projectPath("/plan"), { method: "POST", body: request() });
      go.disabled = plan.errors.length > 0;
      replace(results, h("div", { class: "panel-head" }, h("div", {}, h("h2", {}, plan.title), h("div", { class: "caption" }, `${plan.profile.id} profile · ${plan.counts.outputs} outputs`)),
        h("div", { class: "row" }, h("span", { class: "chip" }, `${plan.counts.images} images`), h("span", { class: "chip" }, `${plan.counts.judge_calls} judge calls`), h("span", { class: "chip accent" }, range(plan.estimate)))),
      plan.errors.map((e) => h("div", { class: "notice danger", style: "margin-bottom:8px" }, e)),
      plan.warnings.map((w) => h("div", { class: "notice warning", style: "margin-bottom:8px" }, w)),
      plan.outputs.length ? h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, ["Output", "Model", "References (in order)", "Waits for"].map((x) => h("th", {}, x)))),
        h("tbody", {}, plan.outputs.map((o) => h("tr", {}, h("td", {}, h("strong", {}, o.label), h("div", { class: "caption mono" }, o.id)), h("td", { class: "mono" }, o.model),
          h("td", { style: "white-space:normal" }, o.references.length ? o.references.map((r, i) => `${i + 1}. ${r.image_id} (${r.role})`).join("  ") : (o.text_refs.length ? "Text only" : "None")),
          h("td", { class: "mono" }, o.depends_on.map((d) => d.output).join(", ") || "—")))))) : null,
      h("details", { class: "advanced", style: "margin-top:12px" }, h("summary", {}, "Advanced: effective settings"),
        h("pre", { class: "mono caption", style: "white-space:pre-wrap" }, JSON.stringify({ profile: plan.profile, selection: plan.selection, presets: plan.presets }, null, 2))));
    } catch (error) {
      go.disabled = true;
      replace(results, h("div", { class: "notice danger" }, error.message));
    }
  }

  go.addEventListener("click", async () => {
    try {
      const run = await api(projectPath("/runs"), { method: "POST", body: request() });
      location.hash = `#/queue/${run.project}/${run.id}`;
    } catch (error) { failure(error); }
  });
  c.task.addEventListener("change", () => { drawFields(); preview(); });
  for (const control of [...Object.values(c), judge.input, pick.input]) { control.addEventListener("change", preview); control.addEventListener("input", preview); }
  drawFields();

  if (!subjects.length) {
    replace(main, h("div", { class: "page-head" }, h("h1", {}, "Create")), empty("Add something to generate", "Create a character, an environment or an asset in the Library first.", h("a", { class: "btn primary", href: "#/library/characters" }, "Open Library")));
    return;
  }
  replace(main, h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Create"), h("p", { class: "muted" }, "Choose what to make; the plan shows every output, model and reference before anything runs."))),
    h("div", { class: "grid" },
      h("section", { class: "panel span-4 stack" }, field("Task", c.task), fields, field("Note", c.note), h("hr", { class: "divider" }),
        field("Profile", c.profile), field("Strategy", c.strategy),
        h("div", { class: "row", style: "flex-wrap:nowrap" }, field("Rounds", c.rounds), field("Candidates", c.candidates)),
        h("div", { class: "setting" }, h("div", {}, h("div", {}, "Auto judge"), h("div", { class: "caption" }, "Evaluate every candidate")), judge.node),
        h("div", { class: "setting" }, h("div", {}, h("div", {}, "Auto pick"), h("div", { class: "caption" }, "Needs the judge")), pick.node),
        h("details", { class: "advanced" }, h("summary", {}, "Advanced"), h("div", { class: "stack" }, field("Stopping rule", c.stop), field("Technical retries", c.retries))),
        go),
      h("div", { class: "span-8" }, results)));
  drawPlan();
}
