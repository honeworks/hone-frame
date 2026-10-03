// The world (change 0003): places and objects that belong to the project, not to one character.
import { api, empty, failure, h, icon, img, projectPath, replace, toast } from "../core.js";
import { subjectDialog } from "./subject_form.js";
import { packSection } from "./characters.js";

export async function render(main) {
  const world = await api(projectPath("/world"));
  const places = world.filter((s) => s.kind === "environment");
  const objects = world.filter((s) => s.kind === "asset");
  const section = (title, text, kind, rows) => h("section", { class: "panel", style: "margin-bottom:24px" },
    h("div", { class: "panel-head" }, h("div", {}, h("h2", {}, title, h("span", { class: "count" }, rows.length)), h("div", { class: "caption" }, text)),
      h("button", { class: "btn small", onclick: () => subjectDialog(kind) }, icon("plus"), kind === "environment" ? "Add a place" : "Add an object")),
    rows.length ? h("div", { class: "tiles" }, rows.map(worldTile)) : h("p", { class: "muted", style: "margin:0" }, "None yet."));
  replace(main,
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "World"),
      h("p", { class: "muted" }, "Places and objects anyone in the story can use. Objects that belong to one character are added on that character's page.")),
    h("button", { class: "btn primary", onclick: () => worldDialog(world) }, "Generate assets")),
    world.length ? null : empty("Nothing in the world yet", "Add the places your scenes happen in, and the objects everyone shares."),
    section("Places", "Where scenes happen.", "environment", places),
    section("Objects", "Shared objects: a horse, a banner, a throne.", "asset", objects),
    await Promise.all(objects.map(async (o) => {  // each object's hero and views (change 0005)
      const row = await api(projectPath(`/objects/${o.id}`));
      return packSection({ subject: { id: o.id, name: o.name } }, { ...row, label: `Object: ${o.name}` });
    })));
}

export function worldTile(s) {
  return h("div", { class: "tile", role: "button", tabindex: 0, onclick: () => subjectDialog(s.kind, s),
    onkeydown: (e) => { if (e.key === "Enter") subjectDialog(s.kind, s); } },
  h("div", { class: "thumb" }, s.hero ? img(s.hero, s.name) : h("span", { class: "placeholder-img" }, "Not made yet")),
  h("div", { class: "meta" }, h("span", { class: "name" }, s.name), h("span", { class: "caption" }, s.kind === "environment" ? "Place" : "Object")));
}

export function worldDialog(world) {
  if (!world.length) { toast("Add a place or an object first (World page).", true); return; }
  const boxes = world.map((s) => [s, h("input", { type: "checkbox", checked: !s.hero })]);
  const dialog = h("dialog", { "aria-label": "Generate world assets", style: "width:min(560px, calc(100vw - 32px))" },
    h("form", { class: "stack", onsubmit: async (e) => {
      e.preventDefault();
      const ids = boxes.filter(([, b]) => b.checked).map(([s]) => s.id);
      if (!ids.length) { toast("Tick at least one.", true); return; }
      try {
        const runs = await api(projectPath("/world/generate"), { method: "POST", body: { subject_ids: ids } });
        dialog.close(); toast(`Queued ${runs.length} place${runs.length === 1 ? "" : "s"} and objects. Follow them in the Queue.`);
        window.dispatchEvent(new HashChangeEvent("hashchange"));
      } catch (error) { failure(error); }
    } },
    h("h2", {}, "Generate world assets"),
    h("p", { class: "caption", style: "margin:0" }, "Places and shared objects. Those without an image are ticked. Characters and their belongings are generated on each character's page."),
    h("div", { class: "stack", style: "gap:8px;max-height:50vh;overflow-y:auto" }, boxes.map(([s, box]) =>
      h("label", { class: "row", style: "flex-wrap:nowrap" }, box, h("span", { style: "font-weight:600" }, s.name),
        h("span", { class: "caption" }, `${s.kind === "environment" ? "place" : "object"}${s.hero ? " · already made" : ""}`)))),
    h("div", { class: "row" }, h("span", { class: "spacer" }), h("button", { class: "btn", type: "button", onclick: () => dialog.close() }, "Cancel"),
      h("button", { class: "btn primary", type: "submit" }, "Generate"))));
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
}
