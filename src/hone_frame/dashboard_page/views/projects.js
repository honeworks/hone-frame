// Projects: the list, search and the create form.
import { api, empty, failure, field, h, importButton, presetOptions, replace, select, state, when } from "../core.js";
import { setProject } from "../app.js";

export async function render(main) {
  const projects = await api("/projects");
  const name = h("input", { class: "input", required: true, placeholder: "Morning at home" });
  const brief = h("textarea", { class: "input", placeholder: "What the project is about." });
  const direction = h("input", { class: "input", placeholder: "Costume, materials and buildings of this world, in plain sentences" });
  const pack = select(presetOptions("style_pack"), "cinematic-realism");
  const form = h("form", { class: "stack", onsubmit: async (e) => {
    e.preventDefault();
    try {
      const created = await api("/projects", { method: "POST", body: { name: name.value, brief: brief.value, look: direction.value, style_pack: pack.value } });
      setProject(created.id);
      window.dispatchEvent(new Event("hf:projects"));
      location.hash = "#/project";
    } catch (error) { failure(error); }
  } }, field("Name", name), field("Brief", brief), field("Look guide", direction, "What things in this world look like: culture, period, costume, materials. Concrete words."), field("First style", pack, "You can add more variations (styles) later."),
    h("button", { class: "btn primary", type: "submit" }, "Create project"));
  const filter = h("input", { class: "input", type: "search", placeholder: "Search projects", "aria-label": "Search projects" });
  const list = h("div", { class: "stack" });
  const draw = () => replace(list, projects.filter((p) => p.name.toLowerCase().includes(filter.value.toLowerCase())).map((p) =>
    h("a", { class: "panel row", href: "#/project", style: "color:inherit", onclick: () => setProject(p.id) },
      h("div", { style: "flex:1" }, h("h2", {}, p.name), h("div", { class: "caption" }, `${p.style_pack} · updated ${when(p.updated_at)}`)),
      p.id === state.project ? h("span", { class: "chip accent" }, "Current") : null)));
  filter.addEventListener("input", draw);
  draw();
  replace(main, h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Projects"), h("p", { class: "muted" }, "Each project holds its own characters, environments, assets, scenes, sheets and runs."))),
    h("div", { class: "grid" }, h("section", { class: "span-8 stack" }, filter, projects.length ? list : empty("No projects yet", "Create the first one; the presets are ready before it exists.")),
      h("section", { class: "span-4 stack" }, h("div", { class: "panel" }, h("h2", { style: "margin-bottom:12px" }, "New project"), form),
        h("div", { class: "panel stack" }, h("h2", {}, "From a file"),
          h("p", { class: "caption", style: "margin:0" }, "A TOML or JSON project file with the project, characters, belongings, places, objects and scenes (see docs/project-files.md). Importing it again updates what changed."),
          importButton("Import a project file")))));
}
