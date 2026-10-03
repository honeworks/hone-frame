// Variations and the world's look guide (change 0005): one world, several ways of drawing it. The switcher
// changes the active variation for every page; "Generate everything" makes a variation's whole world.
import { api, duration, failure, field, h, icon, presetOptions, projectPath, replace, select, state, toast } from "../core.js";

export function activeVariation(project) {
  const all = project?.variations?.length ? project.variations : [{ id: "main", name: styleName(project?.style_pack), style_pack: project?.style_pack }];
  return all.find((v) => v.id === project?.variation) || all[0];
}

export function styleName(id) { return (state.presets?.style_pack || []).find((x) => x.id === id)?.name || id || ""; }

const refresh = () => window.dispatchEvent(new Event("hf:projects"));

export async function variationBar() {
  const data = await api(projectPath("/variations"));
  const label = (v) => (v.name === styleName(v.style_pack) ? v.name : `${v.name} · ${styleName(v.style_pack)}`);
  const chooser = select(data.variations.map((v) => [v.id, label(v)]), data.active, { "aria-label": "Variation", style: "width:auto;height:36px" });
  chooser.addEventListener("change", async () => {
    try { await api(projectPath(`/variations/${chooser.value}/use`), { method: "POST", body: {} }); toast("Variation switched: every page now shows its images."); refresh(); }
    catch (error) { failure(error); }
  });
  return h("div", { class: "row variation-bar" }, h("span", { class: "overline" }, "Variation"), chooser,
    h("button", { class: "btn small", onclick: () => variationDialog(data) }, icon("plus"), "New variation"),
    h("button", { class: "btn small", onclick: () => variationDialog(data, data.variations.find((v) => v.id === data.active)) }, "Edit"));
}

function variationDialog(data, current) {
  const name = h("input", { class: "input", required: true, value: current?.name || "", placeholder: "2D animated" });
  const style = select(presetOptions("style_pack"), current?.style_pack || "clean-2d-animation");
  const direction = h("input", { class: "input", value: current?.direction || "", placeholder: "warm colours, soft light, thick outlines" });
  const dialog = h("dialog", { "aria-label": current ? "Edit variation" : "New variation", style: "width:min(560px, calc(100vw - 32px))" },
    h("form", { class: "stack", onsubmit: async (e) => {
      e.preventDefault();
      try {
        const body = { name: name.value.trim(), style_pack: style.value, direction: direction.value.trim() };
        if (current) await api(projectPath(`/variations/${current.id}`), { method: "PATCH", body });
        else await api(projectPath("/variations"), { method: "POST", body: { ...body, active: true } });
        dialog.close(); toast(current ? "Variation saved." : "Variation added and shown. Its characters have no images yet: Generate everything, or each character's Generate assets.");
        refresh();
      } catch (error) { failure(error); }
    } },
    h("h2", {}, current ? `Edit ${current.name}` : "New variation"),
    h("p", { class: "caption", style: "margin:0" }, "The same world drawn another way: its characters, places and scenes stay; every image is made again in this style."),
    field("Name", name), field("Style", style), field("Style notes", direction, "A few words on how it is drawn. What things are (culture, costume) belongs in the world's look guide."),
    h("div", { class: "row" }, h("span", { class: "spacer" }), h("button", { class: "btn", type: "button", onclick: () => dialog.close() }, "Cancel"),
      h("button", { class: "btn primary", type: "submit" }, current ? "Save" : "Add"))));
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
}

export function lookPanel(project) {
  const text = h("textarea", { class: "input", style: "min-height:96px", value: project.look || project.direction || "",
    placeholder: "Costume and armour of ancient Persia and Central Asia: knee-length lamellar coats laced with cord over silk kaftans with roundel patterns, conical segmented helmets with mail curtains…" });
  const save = async () => {
    try { await api(projectPath(""), { method: "PATCH", body: { look: text.value.trim() } }); toast("Look guide saved: new images use it."); }
    catch (error) { failure(error); }
  };
  return h("section", { class: "panel", style: "margin-bottom:24px" },
    h("div", { class: "panel-head" }, h("div", {}, h("h2", {}, "Look guide"),
      h("div", { class: "caption" }, "What things in this world look like: culture, period, costume, armour, materials, buildings. Write concrete things you can see, in plain sentences, not tags. Every variation uses it.")),
    h("button", { class: "btn small", onclick: save }, "Save")), text);
}

export async function generateEverything() {
  const profile = select(presetOptions("profile"), "draft", { "aria-label": "Quality" });
  const rounds = h("input", { class: "input", type: "number", min: 1, max: 10, value: 2, "aria-label": "Attempts" });
  const summary = h("div", { class: "stack", style: "gap:6px" }, h("p", { class: "caption" }, "Working out what would be made…"));
  const body = () => ({ profile: profile.value, rounds: Number(rounds.value) || 2 });
  const estimate = async () => {
    try {
      const plan = await api(projectPath("/world/plan"), { method: "POST", body: body() });
      replace(summary,
        h("div", {}, h("strong", {}, `${plan.images} images`), ` in ${plan.runs.length} runs, then ${plan.scenes} scene${plan.scenes === 1 ? "" : "s"} once the characters are made.`),
        h("div", {}, `About ${duration(plan.estimate_s)}`, h("span", { class: "caption" }, plan.measured ? ` (${plan.seconds_per_image} s per image, measured on this machine)` : " (a first guess until runs have been measured)")),
        h("ul", { class: "caption", style: "margin:0;padding-left:18px" }, plan.runs.map((r) => h("li", {}, `${r.title}: ${r.images} images`, r.errors.length ? ` — ${r.errors[0]}` : "")),
          (plan.scene_runs || []).map((r) => h("li", {}, `Scene ${r.title}: ${r.images} images (after the characters)`))));
    } catch (error) { replace(summary, h("div", { class: "notice danger" }, error.message)); }
  };
  profile.addEventListener("change", estimate);
  rounds.addEventListener("change", estimate);
  const dialog = h("dialog", { "aria-label": "Generate everything", style: "width:min(640px, calc(100vw - 32px))" },
    h("form", { class: "stack", onsubmit: async (e) => {
      e.preventDefault();
      try {
        const started = await api(projectPath("/world/generate-all"), { method: "POST", body: body() });
        dialog.close();
        toast(`Queued ${started.runs.length} runs${started.scenes_after ? `; ${started.scenes_after} scenes follow when the characters are done` : ""}. Follow them in the Queue.`);
        refresh();
      } catch (error) { failure(error); }
    } },
    h("h2", {}, "Generate everything"),
    h("p", { class: "caption", style: "margin:0" }, "Every place and object without an image, every character's packs, then the scenes, for the variation shown. They run one after another; leave it overnight."),
    summary,
    h("div", { class: "row", style: "flex-wrap:nowrap" }, field("Quality", profile), field("Attempts per image", rounds)),
    h("div", { class: "row" }, h("span", { class: "spacer" }), h("button", { class: "btn", type: "button", onclick: () => dialog.close() }, "Cancel"),
      h("button", { class: "btn primary", type: "submit" }, "Start"))));
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
  estimate();
}

export async function compareSection(subjectId) {
  const rows = await api(projectPath(`/subjects/${subjectId}/compare`));
  if (rows.length < 2) return null;
  return h("section", { class: "panel", style: "margin-bottom:24px" },
    h("div", { class: "panel-head" }, h("div", {}, h("h2", {}, "Compare variations"), h("div", { class: "caption" }, "The hero in every variation of this world, side by side."))),
    h("div", { class: "tiles" }, rows.map((r) => h("div", { class: "tile" },
      h("div", { class: "thumb" }, r.hero ? h("img", { src: r.hero.url, alt: r.variation.name }) : h("span", { class: "placeholder-img" }, "Not made yet")),
      h("div", { class: "meta" }, h("span", { class: "name" }, r.variation.name), h("span", { class: "caption" }, styleName(r.variation.style_pack)))))));
}
