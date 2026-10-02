// Sheets: saved sheets and the composer. Composition is Python on the server; no model is called.
import { api, empty, failure, field, h, icon, img, presetOptions, projectPath, replace, select, toast, zoomable } from "../core.js";

export async function render(main, [id]) {
  const [sheets, images] = await Promise.all([api(projectPath("/sheets")), api(projectPath("/images"))]);
  const current = id === "new" ? null : sheets.find((s) => s.id === id) || null;
  const list = sheets.length ? h("div", { class: "tiles big" }, sheets.map((s) => h("a", { class: "tile", href: `#/sheets/${s.id}` },
    h("div", { class: "thumb", style: "aspect-ratio:16/10" }, s.url ? zoomable(h("img", { src: s.url, alt: s.recipe.name }), s.url, s.recipe.name) : h("span", { class: "caption" }, "Not composed")),
    h("div", { class: "meta" }, h("span", { class: "name" }, s.recipe.name), h("span", { class: "caption mono" }, `${s.id} · v${s.version} · ${s.recipe.images.length} images`)))))
    : empty("No sheets yet", "Compose one from saved images; layout and labels stay editable.");
  const side = h("aside", { class: "side" });
  replace(main, h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Sheets"), h("p", { class: "muted" }, "Sheets are compositions of saved images. Recomposing never calls a model.")),
    h("a", { class: "btn", href: "#/sheets/new" }, icon("plus"), "New sheet")),
  h("div", { class: "layout-side" }, h("div", {}, id || !sheets.length ? composer(current, images) : list), side));
  if (current) {
    replace(side, h("div", { class: "panel stack" }, h("h2", {}, current.recipe.name), current.url ? zoomable(h("img", { class: "preview-img", src: current.url, alt: current.recipe.name }), current.url, current.recipe.name) : null,
      h("div", { class: "row" }, h("button", { class: "btn small", onclick: () => exportSheet(current.id) }, icon("download"), "Export with originals"))));
  } else if (!id) replace(side, h("div", { class: "panel" }, h("p", { class: "caption", style: "margin:0" }, "Open a sheet to edit it, or start a new one.")));
}

async function exportSheet(id) {
  try { location.href = (await api(projectPath("/exports"), { method: "POST", body: { kind: "sheet", id, sources: true } })).url; }
  catch (error) { failure(error); }
}

function composer(sheet, images) {
  const recipe = sheet?.recipe || {};
  let preselected = [];
  try { preselected = JSON.parse(sessionStorage.getItem("hf.sheet") || "[]"); sessionStorage.removeItem("hf.sheet"); } catch { preselected = []; }
  const chosen = [...(recipe.images || preselected)];
  const name = h("input", { class: "input", value: recipe.name || "", placeholder: "Woman turnaround" });
  const layout = select(presetOptions("sheet_layout"), recipe.layout || "four-view-turnaround");
  const labels = h("input", { class: "input", value: (recipe.labels || []).join(", "), placeholder: "Front, 3/4, Side, Back" });
  const columns = h("input", { class: "input", type: "number", min: 0, max: 12, value: recipe.columns ?? "", placeholder: "From layout" });
  const palette = h("input", { class: "input", value: (recipe.palette || []).join(", "), placeholder: "#1F4FE0, #C9A27E" });
  const notes = h("textarea", { class: "input", value: recipe.notes || "" });
  const fit = select([["contain", "Fit whole image"], ["cover", "Fill the cell (crop)"]], recipe.fit || "contain");
  const page = h("input", { class: "input", value: recipe.page || "auto", placeholder: "auto or 3000x2000" });
  const meta = h("input", { type: "checkbox", checked: recipe.show_meta });
  const picker = h("div", { class: "tiles" });
  const order = h("div", { class: "caption mono" });
  const drawPicker = () => {
    replace(order, chosen.length ? `Order: ${chosen.join(" → ")}` : "Select images in the order they should appear.");
    replace(picker, images.map((card) => {
      const n = chosen.indexOf(card.id);
      return h("button", { class: `tile${n >= 0 ? " selected" : ""}`, "aria-pressed": n >= 0 ? "true" : "false", onclick: () => {
        if (n >= 0) chosen.splice(n, 1); else chosen.push(card.id);
        drawPicker();
      } }, h("div", { class: "thumb" }, img(card)), n >= 0 ? h("span", { class: "badge chip accent" }, String(n + 1)) : null,
      h("div", { class: "meta" }, h("span", { class: "name" }, card.label || card.id), h("span", { class: "caption mono" }, card.id)));
    }));
  };
  drawPicker();
  const split = (v) => v.split(",").map((x) => x.trim()).filter(Boolean);
  const compose = async () => {
    try {
      const saved = await api(projectPath("/sheets"), { method: "POST", body: { id: sheet?.id || null, recipe: {
        name: name.value || "Sheet", layout: layout.value, images: chosen, labels: split(labels.value), columns: columns.value === "" ? null : Number(columns.value),
        palette: split(palette.value), notes: notes.value, fit: fit.value, page: page.value || "auto", show_meta: meta.checked } } });
      toast(`Composed version ${saved.version}.`);
      location.hash = `#/sheets/${saved.id}`;
    } catch (error) { failure(error); }
  };
  if (!images.length) return empty("No images to compose", "Generate or import images first.");
  return h("div", { class: "stack" }, h("section", { class: "panel stack" },
    h("div", { class: "grid" }, h("div", { class: "span-6" }, field("Name", name)), h("div", { class: "span-6" }, field("Layout", layout)),
      h("div", { class: "span-6" }, field("Labels", labels, "One per image, comma separated.")), h("div", { class: "span-3" }, field("Columns", columns)),
      h("div", { class: "span-3" }, field("Fit", fit)), h("div", { class: "span-6" }, field("Palette", palette, "Hex colours drawn as swatches.")),
      h("div", { class: "span-6" }, field("Page size", page, "A larger page is a larger canvas; images are never enlarged.")),
      h("div", { class: "span-12" }, field("Notes", notes))),
    h("label", { class: "row" }, meta, "Print image ids and sizes under labels"),
    h("div", { class: "row" }, order, h("span", { class: "spacer" }), h("button", { class: "btn primary", onclick: compose }, "Compose sheet"))),
  h("section", { class: "panel" }, h("h2", { style: "margin-bottom:12px" }, "Images"), picker));
}
