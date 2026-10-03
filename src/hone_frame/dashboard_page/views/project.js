// The project home (change 0003): the brief and style, the characters, the world, the scenes and what is
// running. "Generate assets" here makes the world's places and objects; characters have their own page.
import { api, downloadProject, failure, field, h, icon, importButton, pill, presetOptions, progressBar, projectPath, range, replace, select, state, toast } from "../core.js";
import { characterTile } from "./characters.js";
import { subjectDialog } from "./subject_form.js";
import { worldDialog, worldTile } from "./world.js";
import { generateEverything, lookPanel, variationBar } from "./variations.js";

export async function render(main) {
  const data = await api(projectPath("/home"));
  const p = data.project;
  const steps = [
    [data.characters.length > 0, "Add your characters", "#/characters", "Who they are, their face, build and clothes."],
    [data.characters.some((c) => c.hero), "Generate each character", "#/characters", "One button makes the hero, turnaround, expressions, poses, outfits and actions."],
    [data.world.length > 0, "Add the world", "#/world", "Places and objects anyone in the story can use."],
    [data.scenes.length > 0, "Build scenes", "#/scenes", "Choose characters and places; the planner adds their belongings when the scene needs them."],
  ];
  const next = steps.find(([done]) => !done);
  const bar = await variationBar();
  replace(main,
    h("div", { class: "page-head" },
      h("div", { style: "max-width:760px" }, h("h1", {}, p.name),
        p.brief ? h("p", { class: "muted", style: "margin:4px 0 8px" }, p.brief) : null, bar),
      h("div", { class: "row" }, importButton("Import a file"),
        h("button", { class: "btn", onclick: () => downloadProject(p.id), title: "The whole project as a file you can edit and import again" }, "Download as file"),
        h("button", { class: "btn", onclick: () => editProject(p) }, "Edit project"),
        h("button", { class: "btn", onclick: () => worldDialog(data.world) }, "Generate assets"),
        h("button", { class: "btn primary", onclick: generateEverything, title: "Every place, object, character and scene of this variation" }, "Generate everything"))),
    lookPanel(p),
    next ? h("section", { class: "panel steps", style: "margin-bottom:24px" }, h("h2", {}, "Next step"),
      h("ol", {}, steps.map(([done, title, href, text]) => h("li", { class: done ? "done" : (title === next[1] ? "current" : "") },
        h("a", { href }, title), h("span", { class: "caption" }, ` ${text}`))))) : null,
    h("div", { class: "grid" },
      h("section", { class: "panel span-8" }, h("div", { class: "panel-head" }, h("h2", {}, "Characters", h("span", { class: "count" }, data.characters.length)),
        h("div", { class: "row" }, h("button", { class: "btn small", onclick: () => subjectDialog("character") }, icon("plus"), "Add"), h("a", { href: "#/characters" }, "Open"))),
        data.characters.length ? h("div", { class: "tiles" }, data.characters.map(characterTile)) : h("p", { class: "muted" }, "No characters yet.")),
      h("section", { class: "panel span-4" }, h("div", { class: "panel-head" }, h("h2", {}, "Activity"), h("a", { href: "#/queue" }, "Queue")),
        data.queue.length ? h("div", { class: "stack" }, data.queue.slice(0, 6).map(queueRow)) : h("p", { class: "muted", style: "margin:0" }, "Nothing is running."),
        h("hr", { class: "divider" }),
        h("div", { class: "stack", style: "gap:6px" }, h("a", { href: "#/library/images" }, `All images (${data.counts.images})`), h("a", { href: "#/sheets" }, `Sheets (${data.counts.sheets})`))),
      h("section", { class: "panel span-8" }, h("div", { class: "panel-head" }, h("h2", {}, "World", h("span", { class: "count" }, data.world.length)),
        h("a", { href: "#/world" }, "Open")),
        data.world.length ? h("div", { class: "tiles" }, data.world.map(worldTile)) : h("p", { class: "muted", style: "margin:0" }, "No places or objects yet.")),
      h("section", { class: "panel span-4" }, h("div", { class: "panel-head" }, h("h2", {}, "Scenes", h("span", { class: "count" }, data.scenes.length)),
        h("a", { href: "#/scenes/new" }, "New scene")),
        data.scenes.length ? h("div", { class: "stack", style: "gap:6px" }, data.scenes.map((s) => h("a", { href: `#/scenes/${s.id}` }, s.name)))
          : h("p", { class: "muted", style: "margin:0" }, "No scenes yet."))));
}


function queueRow(r) {
  const live = r.status === "running" || r.status === "pausing";
  return h("a", { class: "stack", href: `#/queue/${r.project}/${r.id}`, style: "color:inherit;gap:4px" },
    h("div", { class: "row", style: "justify-content:space-between;flex-wrap:nowrap" }, h("span", { style: "font-weight:600;min-width:0;overflow:hidden;text-overflow:ellipsis" }, r.title), pill(r.status)),
    h("div", { class: "row", style: "flex-wrap:nowrap" }, progressBar(r.progress, live), h("span", { class: "caption" }, `${r.accepted}/${r.outputs} · ${range(r.estimate)}`)));
}

function editProject(p) {
  const name = h("input", { class: "input", value: p.name });
  const brief = h("textarea", { class: "input", value: p.brief });
  const dialog = h("dialog", { "aria-label": "Edit project", style: "width:min(560px, calc(100vw - 32px))" },
    h("form", { class: "stack", onsubmit: async (e) => {
      e.preventDefault();
      try {
        await api(projectPath(""), { method: "PATCH", body: { name: name.value, brief: brief.value } });
        dialog.close(); toast("Project saved."); window.dispatchEvent(new Event("hf:projects"));
      } catch (error) { failure(error); }
    } }, h("h2", {}, "Edit project"), field("Name", name), field("Brief", brief, "What the story is about."),
    h("p", { class: "caption", style: "margin:0" }, "The style is set per variation (Edit next to the variation); what things look like goes in the look guide."),
    h("div", { class: "row" }, h("span", { class: "spacer" }), h("button", { class: "btn", type: "button", onclick: () => dialog.close() }, "Cancel"),
      h("button", { class: "btn primary", type: "submit" }, "Save"))));
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
}
