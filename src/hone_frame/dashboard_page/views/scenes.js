// Scenes: the scene list and results, and the scene builder side panel of mockup 2.
import { api, empty, failure, field, h, icon, presetOptions, projectPath, range, replace, select, toast, toggle } from "../core.js";
import { tile } from "./library.js";

const ROLES = ["identity", "object", "environment", "outfit", "pose", "expression", "composition", "lighting", "style"];
const DEFAULT_ROLE = { character: "identity", environment: "environment", asset: "object" };

export async function render(main, [id]) {
  const [scenes, subjects] = await Promise.all([api(projectPath("/scenes")), api(projectPath("/subjects"))]);
  const current = id === "new" ? null : (scenes.find((s) => s.id === id) || scenes[0] || null);
  const detail = current ? await api(projectPath(`/scenes/${current.id}`)) : null;
  const side = h("aside", { class: "side", "aria-label": "Scene builder" });
  replace(main,
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Scenes"), h("p", { class: "muted" }, "Choose the characters and places of a scene. When you save, the planner adds the characters' belongings the description needs.")),
      h("a", { class: "btn", href: "#/scenes/new" }, icon("plus"), "New scene")),
    h("div", { class: "layout-side" }, h("div", { class: "stack" },
      scenes.length ? h("div", { class: "chips" }, scenes.map((s) => h("a", { class: `chip${s.id === current?.id ? " accent" : ""}`, href: `#/scenes/${s.id}` }, s.name))) : null,
      detail ? results(detail) : empty("No scene selected", "Build one in the panel: name it, add its references, choose the camera.")), side));
  builder(side, detail, subjects);
}

function results(detail) {
  return h("section", { class: "panel" }, h("div", { class: "panel-head" }, h("div", {}, h("h2", {}, detail.name), h("div", { class: "caption" }, detail.description)),
    h("span", { class: "caption mono" }, `${detail.id} · v${detail.version}`)),
  detail.results.length ? h("div", { class: "tiles big" }, detail.results.map((card) => h("div", { class: "stack", style: "gap:6px" },
    tile(card, () => { location.hash = `#/library/images/${card.id}`; }),
    card.status === "picked" || card.status === "manual_pick" ? h("div", { class: "row" },
      ["refine", "regenerate", "upscale"].map((op) => h("button", { class: "btn small", onclick: () => promote(card.id, op) }, op[0].toUpperCase() + op.slice(1)))) : null)))
    : h("p", { class: "muted" }, "No results yet. Generate a draft from the panel."));
}

async function promote(imageId, operation) {
  try {
    const run = await api(projectPath("/runs"), { method: "POST", body: { kind: "promote", image_id: imageId, operation } });
    location.hash = `#/queue/${run.project}/${run.id}`;
  } catch (error) { failure(error); }
}

function builder(side, scene, subjects) {
  const byId = Object.fromEntries(subjects.map((s) => [s.id, s]));
  const refs = (scene?.refs || []).map((r) => ({ ...r }));
  const name = h("input", { class: "input", value: scene?.name || "", placeholder: "Coffee scene", "aria-label": "Scene name" });
  const description = h("textarea", { class: "input", value: scene?.description || "", placeholder: "What happens, where, in what mood." });
  const action = h("input", { class: "input", value: scene?.action || "", placeholder: "She lifts the cup and smiles" });
  const camera = select(presetOptions("camera", { blank: "Default" }), scene?.camera || "medium");
  const expression = select(presetOptions("expression", { blank: "Any" }), scene?.expression || "");
  const lighting = select(presetOptions("lighting", { blank: "Project default" }), scene?.lighting || "");
  const pose = select(presetOptions("pose", { blank: "Any" }), scene?.pose || "");
  const profile = select(presetOptions("profile"), "draft");
  const judge = toggle(true);
  const pick = toggle(true);
  const rounds = h("input", { class: "input", type: "number", min: 1, max: 10, value: 3, "aria-label": "Rounds" });
  const refList = h("div", { class: "stack", style: "gap:8px" });
  const planBox = h("div", { class: "stack", style: "gap:6px" });
  const kindWord = (s) => s.kind === "character" ? "character" : (s.owner ? `belongs to ${byId[s.owner]?.name || s.owner}` : (s.kind === "environment" ? "place" : "object"));
  const rank = (s) => (s.kind === "character" ? 0 : s.owner ? 2 : 1);
  const ordered = [...subjects].sort((a, b) => rank(a) - rank(b));
  const adder = select([["", "Add a character, place or object…"], ...ordered.map((s) => [s.id, `${s.name} (${kindWord(s)})`])], "", { "aria-label": "Add a reference" });
  adder.addEventListener("change", () => {
    if (!adder.value) return;
    refs.push({ subject_id: adder.value, role: DEFAULT_ROLE[byId[adder.value].kind], image_ids: [] });
    adder.value = ""; drawRefs(); preview();
  });

  const data = () => ({ id: scene?.id || "", name: name.value || "Untitled scene", description: description.value, action: action.value,
    camera: camera.value || null, expression: expression.value || null, lighting: lighting.value || null, pose: pose.value || null,
    refs: refs.map((r) => ({ subject_id: r.subject_id, role: r.role, image_ids: r.image_ids || [], state: r.state || null, suggested: Boolean(r.suggested) })) });
  const selection = () => ({ rounds: Number(rounds.value) || 3, auto_judge: judge.input.checked, auto_pick: pick.input.checked && judge.input.checked });

  function drawRefs() {
    replace(refList, refs.length ? refs.map((r, i) => {
      const s = byId[r.subject_id] || { name: r.subject_id, kind: "" };
      const role = select(ROLES.map((x) => [x, x[0].toUpperCase() + x.slice(1)]), r.role, { "aria-label": `Role of ${s.name}`, style: "width:auto;height:32px" });
      role.addEventListener("change", () => { r.role = role.value; preview(); });
      return h("div", { class: "ref" }, s.cover ? h("img", { class: "thumb-sm", src: s.cover.url, alt: "" }) : h("span", { class: "thumb-sm" }),
        h("div", { class: "who" }, h("div", {}, s.name),
          h("div", { class: "caption" }, r.suggested ? "suggested by the planner · " : "", kindWord(s))), role,
        h("button", { class: "btn ghost small", "aria-label": `Remove ${s.name}`, onclick: () => { refs.splice(i, 1); drawRefs(); preview(); } }, icon("close")));
    }) : h("p", { class: "caption" }, "No references yet. Only what you add here is sent to the model."));
  }

  let pending = null;
  function preview() {
    clearTimeout(pending);
    pending = setTimeout(async () => {
      if (!scene?.id) { replace(planBox, h("p", { class: "caption" }, "Save the scene to see the exact plan.")); return; }
      try {
        const plan = await api(projectPath("/plan"), { method: "POST", body: { kind: "scene", scene_id: scene.id, profile: profile.value, selection: selection() } });
        const out = plan.outputs[0];
        replace(planBox, h("div", { class: "overline" }, "What will be sent"),
          out ? h("div", { class: "caption mono" }, `${out.model} · ${out.references.map((r, n) => `${n + 1}. ${byId[r.subject_id]?.name || r.image_id} (${r.role})`).join("  ")}`) : null,
          h("div", { class: "caption" }, `${plan.counts.images} images · ${plan.counts.judge_calls} judge calls · ${range(plan.estimate)}`),
          [...plan.errors.map((e) => h("div", { class: "notice danger" }, e)), ...plan.warnings.map((w) => h("div", { class: "notice warning" }, w))]);
      } catch (error) { replace(planBox, h("div", { class: "notice danger" }, error.message)); }
    }, 300);
  }

  async function save(suggest = !scene?.id) {
    try {
      const saved = await api(projectPath("/scenes"), { method: "POST", body: { ...data(), suggest: suggest === true } });
      toast(saved.suggestion ? `Saved. ${saved.suggestion}` : (scene?.id ? `Saved version ${saved.version}.` : "Scene saved."));
      location.hash = `#/scenes/${saved.id}`;
      return saved;
    } catch (error) { failure(error); return null; }
  }

  async function generate(kind, extra = {}) {
    const saved = await save(false);
    if (!saved) return;
    try {
      const run = await api(projectPath("/runs"), { method: "POST", body: { kind, scene_id: saved.id, profile: profile.value, selection: selection(), ...extra } });
      location.hash = `#/queue/${run.project}/${run.id}`;
    } catch (error) { failure(error); }
  }

  async function exportPack() {
    try { location.href = (await api(projectPath("/exports"), { method: "POST", body: { kind: "pack", id: scene.id } })).url; }
    catch (error) { failure(error); }
  }

  for (const control of [camera, expression, lighting, pose, profile, rounds, judge.input, pick.input]) control.addEventListener("change", preview);
  drawRefs();
  preview();
  const row = (label, control) => h("div", { class: "form-row" }, h("span", {}, label), control);
  replace(side, h("div", { class: "panel stack" },
    h("div", { class: "row" }, name), description,
    h("h3", {}, "References"), refList, adder,
    h("hr", { class: "divider" }), h("h3", {}, "Scene setup"), field("Action", action),
    row("Camera", camera), row("Expression", expression), row("Pose", pose), row("Lighting", lighting), row("Profile", profile),
    h("hr", { class: "divider" }), h("h3", {}, "Generation settings"),
    h("div", { class: "setting" }, h("div", {}, h("div", {}, "Auto judge"), h("div", { class: "caption" }, "Evaluate and score results automatically")), judge.node),
    h("div", { class: "setting" }, h("div", {}, h("div", {}, "Auto pick"), h("div", { class: "caption" }, "Select the best result that passes; needs the judge")), pick.node),
    row("Rounds", rounds), planBox,
    h("button", { class: "btn primary", style: "height:44px", onclick: () => generate("scene") }, "Generate scene"),
    h("div", { class: "row" }, h("button", { class: "btn small", onclick: () => save() }, "Save"),
      h("button", { class: "btn small", title: "Ask the planner again which belongings this scene needs", onclick: () => save(true) }, "Suggest belongings"),
      h("button", { class: "btn small", onclick: () => generate("coverage", { cameras: ["wide", "medium", "close-up", "reverse"] }) }, "Coverage"),
      h("button", { class: "btn small", onclick: () => { const st = prompt("State template (e.g. empty-full, dry-wet)", "empty-full"); if (st) generate("state_pair", { state: st }); } }, "State pair"),
      scene?.id ? h("button", { class: "btn small", onclick: exportPack }, icon("download"), "Pack") : null)));
}
