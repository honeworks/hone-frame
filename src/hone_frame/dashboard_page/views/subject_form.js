// The add / edit dialog of a character, environment or asset: description, kind-specific fields, states.
import { api, failure, field, h, icon, projectPath, select, toast } from "../core.js";

const FIELDS = {
  character: [
    ["appearance", "Appearance", "Face, skin, hair, eyes: what must look the same in every picture."],
    ["proportions", "Build and proportions", "Height, build, body proportions."],
    ["features", "Distinguishing features", "Marks and objects that must always show (for example an armlet on the right upper arm)."],
    ["outfits", "Default outfit", "Clothing from head to feet, with colours and materials; name every piece."],
  ],
  environment: [
    ["anchors", "Spatial anchors", "Landmarks that fix the layout (a window over the sink, the gate on the left)."],
    ["materials", "Materials", "Walls, floors, surfaces."],
    ["viewpoints", "Viewpoints", "The views this place is usually seen from."],
    ["recurring_objects", "Recurring objects", "Objects that should stay where they are."],
  ],
  asset: [
    ["scale", "Size and scale", "Real size, or size relative to a person."],
    ["materials", "Materials", "What it is made of."],
    ["colours", "Colours", "Main colours, as words or hex codes."],
    ["details", "Distinctive details", "What makes it recognisable from any angle."],
  ],
};
const STATE_KINDS = [["outfit", "Outfit"], ["expression", "Expression"], ["condition", "Condition"], ["lighting", "Lighting"], ["other", "Other"]];

function text(value) {
  return Array.isArray(value) ? value.join("\n") : (value ?? "");  // a list: one item per line
}

function parsed(before, value) {
  return Array.isArray(before) ? value.split("\n").map((x) => x.trim()).filter(Boolean) : value.trim();
}

function stateRow(state, remove) {
  const name = h("input", { class: "input", value: state.name || "", placeholder: "battle-ready", "aria-label": "State name" });
  const kind = select(STATE_KINDS, state.kind || "outfit", { "aria-label": "State kind" });
  const description = h("textarea", { class: "input", value: state.description || "", style: "min-height:64px",
    placeholder: "What changes in this state, and what stays the same", "aria-label": "State description" });
  const row = h("div", { class: "panel stack", style: "padding:12px;gap:8px" },
    h("div", { class: "row", style: "flex-wrap:nowrap" }, name, kind,
      h("button", { class: "btn ghost small", type: "button", "aria-label": "Remove state", onclick: () => remove(row) }, icon("close"))),
    description);
  row.read = () => ({ name: name.value.trim(), kind: kind.value, description: description.value.trim() });
  return row;
}

export function subjectDialog(kind, subject) {
  const name = h("input", { class: "input", required: true, value: subject?.name || "" });
  const description = h("textarea", { class: "input", value: subject?.description || "" });
  const inputs = Object.fromEntries((FIELDS[kind] || []).map(([key]) =>
    [key, h("textarea", { class: "input", style: "min-height:64px", value: text(subject?.fields?.[key]) })]));
  const states = h("div", { class: "stack", style: "gap:8px" });
  const remove = (row) => row.remove();
  for (const state of subject?.states || []) states.append(stateRow(state, remove));
  const addState = h("button", { class: "btn small", type: "button", onclick: () => states.append(stateRow({}, remove)) }, icon("plus"), "Add state");

  async function save(event) {
    event.preventDefault();
    const fields = { ...(subject?.fields || {}) };
    for (const [key, input] of Object.entries(inputs)) {
      const before = subject?.fields?.[key];
      if (input.value === text(before)) continue;  // untouched: keep the stored value and its type
      if (input.value.trim()) fields[key] = parsed(before, input.value); else delete fields[key];
    }
    const rows = [...states.children].map((row) => row.read()).filter((s) => s.name);
    const body = { name: name.value.trim(), description: description.value.trim(), fields, states: rows };
    try {
      if (subject) await api(projectPath(`/subjects/${subject.id}`), { method: "PATCH", body });
      else await api(projectPath("/subjects"), { method: "POST", body: { kind, ...body } });
      dialog.close();
      toast(subject ? "Saved as a new version." : "Added.");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    } catch (error) { failure(error); }
  }

  const title = subject ? `Edit ${subject.name}` : `Add ${kind}`;
  const dialog = h("dialog", { "aria-label": title, style: "width:min(640px, calc(100vw - 32px))" },
    h("form", { class: "stack", onsubmit: save },
      h("h2", {}, title),
      field("Name", name),
      field("Description", description, "Who or what this is, in a few sentences."),
      (FIELDS[kind] || []).map(([key, label, hint]) => field(label, inputs[key], hint)),
      h("div", { class: "row" }, h("h3", {}, "States"), h("span", { class: "spacer" }), addState),
      h("p", { class: "caption", style: "margin:0" }, "Named changes that keep the identity: an outfit, helmet on or off, wet, damaged."),
      states,
      h("div", { class: "row" }, h("span", { class: "spacer" }),
        h("button", { class: "btn", type: "button", onclick: () => dialog.close() }, "Cancel"),
        h("button", { class: "btn primary", type: "submit" }, subject ? "Save version" : "Add"))));
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
}
