// Characters (change 0003): the list, and each character's page with all its packs, its belongings and its
// model sheet. "Generate assets" makes everything at once; each pack can be made again or added to.
import { api, empty, failure, field, h, icon, img, presetOptions, projectPath, replace, select, toast, zoomable } from "../core.js";
import { subjectDialog } from "./subject_form.js";

const LIVE = new Set(["queued", "running", "waiting", "paused"]);
export const ITEM_WORDS = {
  not_made: "Not made yet", queued: "Queued", running: "Generating…", waiting: "Waiting for the hero",
  paused: "Paused", needs_review: "Needs your choice", failed: "Failed", canceled: "Canceled", done: "Ready",
};
const ADD_HINT = {
  expression: "An expression, e.g. exhausted after battle", pose: "A pose, e.g. drawing a bow",
  outfit: "Clothing, e.g. in party clothing", state: "A state, e.g. wounded, covered in dust",
  action: "Something the character does, e.g. riding Rakhsh at full gallop", camera: "A view, e.g. from below",
};

export async function render(main, [id]) {
  if (id) return characterPage(main, id);
  const list = await api(projectPath("/characters"));
  const add = h("button", { class: "btn primary", onclick: () => subjectDialog("character") }, icon("plus"), "Add a character");
  replace(main,
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Characters"),
      h("p", { class: "muted" }, "Each character gets a hero image, then a turnaround, expressions, poses, outfits and actions made from it.")), add),
    list.length ? h("div", { class: "tiles big" }, list.map(characterTile))
      : empty("No characters yet", "Describe your first character: who they are, their face, build and clothes. Then open it and press Generate assets.", add));
  return null;
}

export function characterTile(c) {
  const ready = c.total ? Math.round((100 * c.done) / c.total) : 0;
  return h("a", { class: "tile", href: `#/characters/${c.id}` },
    h("div", { class: "thumb" }, c.hero ? img(c.hero, c.name) : h("span", { class: "placeholder-img" }, "No hero yet")),
    h("div", { class: "meta" }, h("span", { class: "name" }, c.name),
      h("span", { class: "caption" }, c.hero ? `${c.done} of ${c.total} images ready` : "Not generated yet"),
      h("div", { class: "progress", style: "margin-top:6px" }, h("span", { style: `width:${ready}%` }))));
}

async function characterPage(main, id) {
  let timer = null;
  async function draw() {
    const page = await api(projectPath(`/characters/${id}`));
    if (!main.isConnected) return;  // the person left this page while it loaded
    const live = page.packs.some((p) => p.items.some((i) => LIVE.has(i.status)));
    replace(main, header(page), hero(page), page.packs.map((p) => packSection(page, p)), belongings(page), sheetSection(page));
    clearTimeout(timer);
    if (live) timer = setTimeout(() => draw().catch(failure), 4000);
  }
  await draw();
  return () => clearTimeout(timer);
}

function header(page) {
  const s = page.subject;
  return h("div", { class: "page-head" },
    h("div", {}, h("div", { class: "crumbs caption" }, h("a", { href: "#/characters" }, "Characters"), " / ", s.name), h("h1", {}, s.name)),
    h("div", { class: "row" },
      h("button", { class: "btn", onclick: () => subjectDialog("character", s) }, "Edit details"),
      h("button", { class: "btn primary", onclick: () => generateDialog(page) }, "Generate assets")));
}

function hero(page) {
  const s = page.subject;
  const f = s.fields || {};
  const rows = [["Appearance", f.appearance], ["Build", f.proportions], ["Distinguishing features", f.features], ["Outfit", f.outfits]];
  const counts = page.packs.flatMap((p) => p.items);
  const ready = counts.filter((i) => i.image).length;
  const review = counts.filter((i) => i.status === "needs_review").length;
  return h("section", { class: "panel", style: "margin-bottom:24px" }, h("div", { class: "hero-row" },
    h("div", { class: "hero-img" }, page.hero ? img(page.hero, `${s.name}, hero`) : h("span", { class: "placeholder-img" }, "No hero yet")),
    h("div", { class: "stack" },
      h("p", { style: "margin:0" }, s.description || h("span", { class: "muted" }, "No description yet: Edit details.")),
      rows.filter(([, v]) => v).map(([k, v]) => h("div", {}, h("div", { class: "overline" }, k), h("div", {}, Array.isArray(v) ? v.join(", ") : v))),
      h("div", { class: "row" }, h("span", { class: "chip" }, `${ready} of ${counts.length} images ready`),
        review ? h("span", { class: "pill needs_review" }, `${review} need your choice`) : null),
      (page.warnings || []).map((w) => h("div", { class: "notice warning" }, w)),
      page.hero ? null : h("div", { class: "notice info" }, "Start here: press Generate assets. The hero is drawn first; every other image is made from it, on a white background."))));
}

function packSection(page, pack) {
  const isHero = pack.id === "hero";
  const ready = pack.items.filter((i) => i.image).length;
  const actions = isHero
    ? h("button", { class: "btn small", onclick: () => redrawHero(page) }, "Draw a new hero")
    : h("div", { class: "row" },
      pack.custom ? h("button", { class: "btn small", onclick: () => addItem(page, pack) }, icon("plus"), "Add") : null,
      pack.items.length ? h("button", { class: "btn small", onclick: () => regenerate(page, pack) }, "Regenerate") : null);
  return h("section", { class: "panel", style: "margin-bottom:24px" },
    h("div", { class: "panel-head" }, h("div", {}, h("h2", {}, pack.label, h("span", { class: "count" }, `${ready}/${pack.items.length}`)),
      h("div", { class: "caption" }, pack.description)), actions),
    pack.items.length ? h("div", { class: "tiles" }, pack.items.map((item) => itemTile(page, pack, item)))
      : h("p", { class: "muted", style: "margin:0" }, emptyPack(pack)));
}

function emptyPack(pack) {
  if (pack.id === "outfits") return "No outfits yet. Add one here, or add outfit states in Edit details.";
  if (pack.id === "states") return "No states yet (wet, wounded, at night…). Add one here, or in Edit details.";
  if (pack.id === "actions") return "Add a belonging below to see the character using it, or add an action of your own.";
  return "Nothing here yet.";
}

function itemTile(page, pack, item) {
  const status = item.image && !LIVE.has(item.status) && item.status !== "needs_review" ? "done" : item.status;
  return h("div", { class: "tile", role: "button", tabindex: 0, onclick: () => itemDialog(page, pack, item),
    onkeydown: (e) => { if (e.key === "Enter") itemDialog(page, pack, item); } },
  h("div", { class: `thumb${pack.id === "expressions" ? " square" : ""}` }, item.image ? img(item.image, `${page.subject.name}, ${item.item}`)
    : h("span", { class: "placeholder-img" }, ITEM_WORDS[status] || status)),
  h("div", { class: "meta" }, h("span", { class: "name" }, item.item),
    h("span", { class: `pill ${status === "not_made" ? "" : status}` }, ITEM_WORDS[status] || status)));
}

function itemDialog(page, pack, item) {
  const note = h("textarea", { class: "input", placeholder: "What was wrong and what you want instead, e.g. both hands empty, seen from directly behind" });
  const pick = async (imageId) => {
    try {
      await api(`/runs/${projectId()}/${item.run}/pick`, { method: "POST", body: { output: item.output, image: imageId } });
      dialog.close(); toast(`${item.item}: your choice is used from now on.`); refresh();
    } catch (error) { failure(error); }
  };
  const again = async () => {
    try {
      await api(`/runs/${projectId()}/${item.run}/rerun`, { method: "POST", body: { output: item.output, note: note.value } });
      dialog.close(); toast(`${item.item}: a new attempt is queued.`); refresh();
    } catch (error) { failure(error); }
  };
  const chosen = item.image?.id;
  const dialog = h("dialog", { "aria-label": `${pack.label}: ${item.item}`, style: "width:min(880px, calc(100vw - 32px))" },
    h("div", { class: "stack" },
      h("div", { class: "row" }, h("h2", {}, `${pack.label}: ${item.item}`), h("span", { class: "spacer" }),
        h("span", { class: `pill ${item.status}` }, ITEM_WORDS[item.status] || item.status)),
      item.reason ? h("p", { class: "caption", style: "margin:0" }, item.reason) : null,
      item.candidates.length ? h("div", { class: "candidates" }, item.candidates.map((c) => candidate(c, c.id === chosen, () => pick(c.id))))
        : h("p", { class: "muted" }, item.run ? "No candidates yet: it is still being made." : "Not made yet. Use Generate assets or Regenerate on this pack."),
      item.run ? h("div", { class: "stack", style: "gap:8px" },
        field("None of these? Say what to change and generate it again", note),
        h("div", { class: "row" }, h("a", { href: `#/queue/${projectId()}/${item.run}`, onclick: () => dialog.close() }, "Open the run"), h("span", { class: "spacer" }),
          h("button", { class: "btn", onclick: () => dialog.close() }, "Close"),
          h("button", { class: "btn primary", onclick: again }, "Generate again")))
        : h("div", { class: "row" }, h("span", { class: "spacer" }), h("button", { class: "btn", onclick: () => dialog.close() }, "Close"))));
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
}

function candidate(c, chosen, use) {
  const ev = c.evaluation;
  const failed = ev ? ev.checks.filter((k) => k.verdict !== "pass") : [];
  return h("div", { class: `cand${chosen ? " current" : ""}` },
    h("div", { class: "thumb" }, img(c)),
    h("div", { class: "foot" }, h("span", { class: "mono caption" }, c.id), ev ? h("span", { class: "mono" }, ev.overall.toFixed(2)) : null),
    h("div", { class: "stack", style: "padding:0 12px 12px;gap:6px" },
      ev ? (failed.length ? failed.map((k) => h("div", { class: "caption" }, h("strong", {}, `${k.name}: `), k.finding || k.verdict))
        : h("div", { class: "caption" }, "Every check passed.")) : h("div", { class: "caption" }, "Not judged."),
      chosen ? h("span", { class: "chip accent" }, "In use") : h("button", { class: "btn small", onclick: use }, "Use this one")));
}

function belongings(page) {
  const s = page.subject;
  return h("section", { class: "panel", style: "margin-bottom:24px" },
    h("div", { class: "panel-head" }, h("div", {}, h("h2", {}, "Belongings"),
      h("div", { class: "caption" }, `Objects that belong to ${s.name} (a weapon, a ring, a horse's saddle). Each gets its own image and an action image of ${s.name} using it; scenes add them when the description needs them.`)),
    h("button", { class: "btn small", onclick: () => subjectDialog("asset", null, { owner: s.id }) }, icon("plus"), "Add a belonging")),
    page.assets.length ? h("div", { class: "tiles" }, page.assets.map((a) => h("div", { class: "tile", role: "button", tabindex: 0, onclick: () => subjectDialog("asset", a) },
      h("div", { class: "thumb" }, a.hero ? img(a.hero, a.name) : h("span", { class: "placeholder-img" }, "Not made yet")),
      h("div", { class: "meta" }, h("span", { class: "name" }, a.name), h("span", { class: "caption" }, a.description)))))
      : h("p", { class: "muted", style: "margin:0" }, "No belongings yet."));
}

function sheetSection(page) {
  const sheet = page.sheet;
  const compose = async () => {
    try { await api(projectPath(`/characters/${page.subject.id}/sheet`), { method: "POST", body: {} }); toast("Model sheet composed."); refresh(); }
    catch (error) { failure(error); }
  };
  const exportIt = async () => {
    try { location.href = (await api(projectPath("/exports"), { method: "POST", body: { kind: "sheet", id: sheet.id, sources: true } })).url; }
    catch (error) { failure(error); }
  };
  return h("section", { class: "panel" },
    h("div", { class: "panel-head" }, h("div", {}, h("h2", {}, "Model sheet"),
      h("div", { class: "caption" }, "The hero and turnaround in a row, the expressions below and the description: composed from the images in use, no model is called.")),
    h("div", { class: "row" }, sheet ? h("button", { class: "btn small", onclick: exportIt }, icon("download"), "Export") : null,
      h("button", { class: "btn small primary", onclick: compose, disabled: page.hero ? null : true }, sheet ? "Compose again" : "Compose"))),
    sheet?.url ? zoomable(h("img", { class: "preview-img", src: `${sheet.url}?v=${sheet.version}`, alt: `${page.subject.name} model sheet` }), sheet.url, `${page.subject.name} model sheet`)
      : h("p", { class: "muted", style: "margin:0" }, page.hero ? "Not composed yet." : "Generate the character first."));
}

// --------------------------------------------------------------------------------------------- actions

function generateDialog(page) {
  const belongings = page.assets.length ? [{ id: "assets", label: "Belongings", custom: null, items: page.assets.map((a) => ({ item: a.name, image: a.hero })) }] : [];
  const packs = [...page.packs, ...belongings];
  const boxes = {};
  const extras = {};
  const rows = packs.map((p) => {
    const hasHero = Boolean(page.hero);
    const fresh = p.id === "assets" ? p.items.some((i) => !i.image) : true;  // belongings: only when one has no image
    const box = h("input", { type: "checkbox", checked: p.id === "hero" ? !hasHero : fresh, disabled: p.id === "hero" && !hasHero ? true : null });
    boxes[p.id] = box;
    const extra = p.custom ? h("textarea", { class: "input", style: "min-height:40px", placeholder: `Your own, one per line. ${ADD_HINT[p.custom] || ""}`, "aria-label": `Your own ${p.label}` }) : null;
    if (extra) extras[p.id] = extra;
    const what = p.id === "assets" ? `${p.items.map((i) => i.item).join(", ")}. Those without an image are always made before the actions that use them.`
      : p.id === "hero" ? (hasHero ? "Already made. Tick to draw a new one (the others are then made from it)." : "Drawn first; everything else is made from it.")
      : `${p.items.length} image${p.items.length === 1 ? "" : "s"}${p.items.length ? ": " + p.items.slice(0, 6).map((i) => i.item).join(", ") + (p.items.length > 6 ? "…" : "") : ""}`;
    return h("div", { class: "pack-choice" }, h("label", { class: "row", style: "flex-wrap:nowrap;align-items:flex-start" }, box,
      h("div", {}, h("div", { style: "font-weight:600" }, p.label), h("div", { class: "caption" }, what))), extra);
  });
  const profile = select(presetOptions("profile"), "draft", { "aria-label": "Quality" });
  const rounds = h("input", { class: "input", type: "number", min: 1, max: 10, value: 2, "aria-label": "Attempts" });
  const submit = async (event) => {
    event.preventDefault();
    const chosen = packs.filter((p) => boxes[p.id].checked).map((p) => p.id);
    const custom = Object.fromEntries(Object.entries(extras).map(([k, t]) => [k, t.value.split("\n").map((x) => x.trim()).filter(Boolean)]).filter(([, v]) => v.length));
    for (const key of Object.keys(custom)) if (!chosen.includes(key)) chosen.push(key);
    const redraw = boxes.hero.checked && Boolean(page.hero);
    if (!chosen.filter((p) => p !== "hero").length && !boxes.hero.checked) { toast("Tick at least one part.", true); return; }
    await generate(page, { packs: chosen.filter((p) => p !== "hero" || redraw), custom, redraw_hero: redraw, profile: profile.value,
      selection: { rounds: Number(rounds.value) || 2 } });
    dialog.close();
  };
  const dialog = h("dialog", { "aria-label": "Generate assets", style: "width:min(640px, calc(100vw - 32px))" },
    h("form", { class: "stack", onsubmit: submit },
      h("h2", {}, `Generate assets for ${page.subject.name}`),
      h("p", { class: "caption", style: "margin:0" }, "Everything is made by default, on a plain white background. Untick what you don't want now; you can make any part again later."),
      h("div", { class: "stack", style: "gap:8px;max-height:52vh;overflow-y:auto" }, rows),
      h("div", { class: "row", style: "flex-wrap:nowrap" }, field("Quality", profile, "Draft is fast; Final is slower and better at side and back views."),
        field("Attempts per image", rounds, "The judge keeps the best one.")),
      h("div", { class: "row" }, h("span", { class: "spacer" }), h("button", { class: "btn", type: "button", onclick: () => dialog.close() }, "Cancel"),
        h("button", { class: "btn primary", type: "submit" }, "Generate"))));
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
}

async function generate(page, body) {
  try {
    const run = await api(projectPath(`/characters/${page.subject.id}/generate`), { method: "POST", body });
    toast(`Queued: ${run.outputs} image${run.outputs === 1 ? "" : "s"} for ${page.subject.name}. This page updates as they arrive.`);
    refresh();
  } catch (error) { failure(error); }
}

function regenerate(page, pack) {
  if (!confirm(`Make every ${pack.label.toLowerCase()} image of ${page.subject.name} again? The current images stay until you choose new ones.`)) return;
  generate(page, { packs: [pack.id] });
}

function redrawHero(page) {
  if (!confirm(`Draw a new hero for ${page.subject.name}? Only the hero is drawn; regenerate the other packs afterwards so they match it.`)) return;
  generate(page, { packs: ["hero"], redraw_hero: true });
}

function addItem(page, pack) {
  const text = h("input", { class: "input", required: true, placeholder: ADD_HINT[pack.custom] || "Describe it" });
  const dialog = h("dialog", { "aria-label": `Add to ${pack.label}` },
    h("form", { class: "stack", onsubmit: async (e) => { e.preventDefault(); await generate(page, { packs: [pack.id], custom: { [pack.id]: [text.value.trim()] }, only_custom: true }); dialog.close(); } },
      h("h2", {}, `Add to ${pack.label}`), field("What should it show?", text, `${page.subject.name} is drawn from the hero, on a white background.`),
      h("div", { class: "row" }, h("span", { class: "spacer" }), h("button", { class: "btn", type: "button", onclick: () => dialog.close() }, "Cancel"),
        h("button", { class: "btn primary", type: "submit" }, "Generate"))));
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
  text.focus();
}

function projectId() { return projectPath("").split("/")[2]; }
function refresh() { window.dispatchEvent(new HashChangeEvent("hashchange")); }
