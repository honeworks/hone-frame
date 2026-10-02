// Library: flat tabs for characters, environments, assets and images, with a details side panel.
import { api, empty, failure, h, icon, img, pill, projectPath, replace, select, state, toast, when } from "../core.js";
import { subjectDialog } from "./subject_form.js";

const TABS = [["characters", "Characters", "character"], ["environments", "Environments", "environment"], ["assets", "Assets", "asset"], ["images", "Images", null]];

export async function render(main, [tab = "characters", id]) {
  const side = h("aside", { class: "side", "aria-label": "Details" });
  const body = h("div", { class: "stack" });
  const current = tab === "search" ? "images" : tab;
  replace(main,
    h("div", { class: "page-head" }, h("div", {}, h("div", { class: "crumbs caption" }, h("a", { href: "#/projects" }, "Projects"), " / ", projectName()), h("h1", {}, projectName())),
      h("a", { class: "btn primary", href: "#/create" }, "Generate")),
    h("nav", { class: "tabs", "aria-label": "Library" }, TABS.map(([t, label]) => h("a", { href: `#/library/${t}`, "aria-current": t === current ? "page" : null }, label)),
      h("a", { href: "#/scenes" }, "Scenes")),
    h("div", { class: "layout-side" }, body, side));
  const kind = TABS.find(([t]) => t === current)?.[2];
  if (tab === "images" || tab === "search") await imagesTab(body, side, tab === "search" ? id : null, tab === "images" ? id : null);
  else await subjectsTab(body, side, kind, id);
}

function projectName() { return state.projects.find((p) => p.id === state.project)?.name || ""; }

async function subjectsTab(body, side, kind, openId) {
  const subjects = await api(projectPath(`/subjects?kind=${kind}`));
  const add = h("button", { class: "btn", onclick: () => subjectDialog(kind) }, icon("plus"), `Add ${kind === "asset" ? "asset" : kind}`);
  if (!subjects.length) {
    replace(body, empty(`No ${kind}s yet`, `Describe one; then generate its reference images.`, add));
    replace(side);
    return;
  }
  const sections = await Promise.all(subjects.map((s) => api(projectPath(`/subjects/${s.id}`))));
  replace(body, h("div", { class: "row" }, h("span", { class: "spacer" }), add),
    sections.map((s) => h("section", { class: "panel" },
      h("div", { class: "panel-head" }, h("div", {}, h("h2", {}, s.name, h("span", { class: "count" }, s.images.length)),
        h("div", { class: "caption mono" }, `${s.id} · v${s.version}`)),
        h("div", { class: "row" }, h("button", { class: "btn small", onclick: () => subjectPanel(side, s) }, "Details"),
          h("button", { class: "btn small primary", onclick: () => generateRefs(s) }, "Generate references"))),
      s.images.length ? h("div", { class: "tiles" }, s.images.slice().reverse().map((card) => tile(card, () => imagePanel(side, card.id))))
        : h("p", { class: "muted" }, "No images yet. Generate references, or import an image in Details."))));
  const open = sections.find((s) => s.id === openId) || sections[0];
  subjectPanel(side, open);
}

export function tile(card, onclick, selectable) {
  return h("div", { class: "tile", role: "button", tabindex: 0, onclick, onkeydown: (e) => { if (e.key === "Enter") onclick(); } },
    selectable || null,
    h("div", { class: "thumb" }, img(card)), h("span", { class: "badge" }, ["picked", "manual_pick", "best_available", "rejected", "uncertain"].includes(card.status) ? pill(card.status) : null),
    h("div", { class: "meta" }, h("span", { class: "name" }, card.label || card.id), h("span", { class: "caption mono" }, `${card.id} · ${card.width}×${card.height}`)));
}

function subjectPanel(side, s) {
  if (!s) { replace(side); return; }
  const file = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp", "aria-label": "Import an image" });
  file.addEventListener("change", async () => {
    const chosen = file.files?.[0];
    if (!chosen) return;
    try {
      await api(projectPath(`/images?subject=${s.id}&label=${encodeURIComponent("Hero")}`), { method: "POST", raw: { body: chosen, type: chosen.type, name: chosen.name } });
      toast("Image imported."); window.dispatchEvent(new HashChangeEvent("hashchange"));
    } catch (error) { failure(error); }
  });
  replace(side, h("div", { class: "panel stack" },
    h("div", { class: "row" }, h("h2", {}, s.name), h("span", { class: "spacer" }), h("span", { class: "chip" }, s.kind)),
    s.cover ? h("img", { class: "preview-img", src: s.cover.url, alt: s.name }) : null,
    h("p", { style: "margin:0" }, s.description || h("span", { class: "muted" }, "No description.")),
    Object.entries(s.fields || {}).map(([k, v]) => h("div", { class: "caption" }, h("strong", {}, `${k}: `), Array.isArray(v) ? v.join(", ") : String(v))),
    s.states?.length ? h("div", {}, h("div", { class: "overline" }, "States"), h("div", { class: "chips" }, s.states.map((st) => h("span", { class: "chip", title: st.description }, `${st.name} · ${st.kind}`)))) : null,
    h("div", {}, h("div", { class: "overline" }, "References"), h("div", { class: "caption" }, s.reference_images?.length ? s.reference_images.join(", ") : "None chosen: its accepted hero is used.")),
    h("div", { class: "row" }, h("button", { class: "btn small", onclick: () => subjectDialog(s.kind, s) }, "Edit"), h("label", { class: "btn small" }, "Import image", file)),
    h("details", { class: "advanced" }, h("summary", {}, `History (${s.versions.length} versions)`),
      h("ul", { class: "caption", style: "padding-left:18px" }, s.versions.slice().reverse().map((v) => h("li", {}, `v${v.version} · ${when(v.updated_at)} · ${v.description.slice(0, 80)}`))))));
  file.hidden = true;
}

async function imagePanel(side, id) {
  const data = await api(projectPath(`/images/${id}`));
  const r = data.record;
  const ev = r.evaluation;
  replace(side, h("div", { class: "panel stack" },
    h("div", { class: "row" }, h("h2", { class: "mono" }, r.id), h("span", { class: "spacer" }), pill(r.status)),
    h("img", { class: "preview-img", src: data.url, alt: r.label || r.id }),
    h("div", { class: "caption" }, `${r.width} × ${r.height} · ${r.source} · ${when(r.created_at)}`),
    r.generation ? h("div", { class: "stack", style: "gap:4px" }, h("div", { class: "overline" }, "Generation"),
      h("div", { class: "mono caption" }, `${r.generation.model} · seed ${r.generation.seed ?? "—"}${r.run_id ? ` · run ${r.run_id} ${r.output_id} r${r.round}c${r.candidate}` : ""}`),
      h("details", { class: "advanced" }, h("summary", {}, "Prompt"), h("p", { class: "mono caption", style: "white-space:pre-wrap" }, r.generation.prompt)),
      r.generation.references.length ? h("div", { class: "caption" }, "References: ", r.generation.references.map((u) => `${u.image_id} (${u.role})`).join(", ")) : null) : null,
    ev ? h("div", { class: "stack", style: "gap:4px" }, h("div", { class: "overline" }, `Evaluation · overall ${ev.overall.toFixed(2)}`),
      ev.checks.map((c) => h("div", { class: "row caption", style: "flex-wrap:nowrap;align-items:flex-start" }, pill(c.verdict === "pass" ? "pass" : c.verdict === "fail" ? "fail" : "uncertain"), h("span", {}, `${c.name}: ${c.finding}`)))) : null,
    r.parent ? h("div", { class: "caption" }, `Made from ${r.parent}`) : null,
    h("div", { class: "caption" }, data.uses.length ? `Used by: ${data.uses.join(", ")}` : "Not used anywhere yet."),
    h("div", { class: "row" }, r.subjects.length === 1 ? h("button", { class: "btn small", onclick: () => useAsReference(r) }, "Use as reference") : null,
      h("button", { class: "btn small danger", onclick: () => remove(r, data.uses) }, "Delete"))));
}

async function useAsReference(r) {
  try {
    await api(projectPath(`/subjects/${r.subjects[0].subject_id}`), { method: "PATCH", body: { reference_images: [r.id] } });
    toast(`${r.id} is now the reference. Scenes and sheets on the older version show "Update available".`);
  } catch (error) { failure(error); }
}

async function remove(r, uses) {
  if (uses.length) { toast(`${r.id} is used by ${uses.join(", ")}; remove those uses first.`, true); return; }
  if (!confirm(`Delete ${r.id}? The file is removed from the project.`)) return;
  try { await api(projectPath(`/images/${r.id}`), { method: "DELETE" }); toast("Deleted."); window.dispatchEvent(new HashChangeEvent("hashchange")); }
  catch (error) { failure(error); }
}

async function imagesTab(body, side, query, openId) {
  const kind = select([["", "All kinds"], ["character", "Characters"], ["environment", "Environments"], ["asset", "Assets"], ["scene", "Scenes"]], "", { "aria-label": "Kind" });
  const status = select([["", "Any status"], ["picked", "Picked"], ["manual_pick", "Picked by you"], ["best_available", "Best available"], ["candidate", "Candidate"], ["rejected", "Rejected"], ["uncertain", "Uncertain"], ["imported", "Imported"]], "", { "aria-label": "Status" });
  const text = h("input", { class: "input", type: "search", placeholder: "Filter by label, id or prompt", value: query || "", "aria-label": "Filter" });
  const grid = h("div");
  const chosen = new Set();
  const bar = h("div", { class: "row", hidden: true });
  const all = await api(projectPath("/images"));
  const draw = () => {
    const q = text.value.toLowerCase();
    const rows = all.filter((c) => (!kind.value || c.kind === kind.value) && (!status.value || c.status === status.value)
      && (!q || `${c.id} ${c.label} ${c.model || ""}`.toLowerCase().includes(q)));
    replace(grid, rows.length ? h("div", { class: "tiles" }, rows.map((card) => {
      const box = h("input", { type: "checkbox", class: "select-box", "aria-label": `Select ${card.id}`, checked: chosen.has(card.id) });
      box.addEventListener("click", (e) => { e.stopPropagation(); if (box.checked) chosen.add(card.id); else chosen.delete(card.id); bar.hidden = !chosen.size; });
      return tile(card, () => imagePanel(side, card.id), box);
    })) : empty("No images match", "Change the filters, or generate images from Create."));
  };
  replace(bar, h("button", { class: "btn small", onclick: () => exportSelection([...chosen]) }, icon("download"), "Export"),
    h("button", { class: "btn small", onclick: () => { location.hash = "#/sheets/new"; sessionStorage.setItem("hf.sheet", JSON.stringify([...chosen])); } }, "Compose sheet"));
  for (const control of [kind, status, text]) control.addEventListener("input", draw);
  for (const control of [kind, status]) control.style.width = "auto";
  text.style.flex = "1";
  replace(body, h("div", { class: "row" }, kind, status, text), bar, grid);
  draw();
  if (openId) imagePanel(side, openId);
}

async function exportSelection(ids) {
  try {
    const sheet = await api(projectPath("/sheets"), { method: "POST", body: { name: "Selection", layout: "contact-grid", images: ids } });
    const done = await api(projectPath("/exports"), { method: "POST", body: { kind: "sheet", id: sheet.id, sources: true } });
    location.href = done.url;
  } catch (error) { failure(error); }
}

async function generateRefs(s) {
  try {
    const run = await api(projectPath("/runs"), { method: "POST", body: { kind: "subject_references", subject_id: s.id, presentation: null } });
    toast(`Queued: ${run.title}.`);
    location.hash = `#/queue/${run.project}/${run.id}`;
  } catch (error) { failure(error); }
}
