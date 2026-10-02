// The shell: navigation, the project selector, hash routing. Each view renders into <main>.
import { api, h, icon, replace, state, failure } from "./core.js";
import * as overview from "./views/overview.js";
import * as create from "./views/create.js";
import * as library from "./views/library.js";
import * as scenes from "./views/scenes.js";
import * as sheets from "./views/sheets.js";
import * as queue from "./views/queue.js";
import * as presets from "./views/presets.js";
import * as models from "./views/models.js";
import * as settings from "./views/settings.js";
import * as projects from "./views/projects.js";

const NAV = [
  ["overview", "Overview", overview], ["create", "Create", create], ["library", "Library", library],
  ["scenes", "Scenes", scenes], ["sheets", "Sheets", sheets], ["queue", "Queue", queue],
  ["presets", "Presets", presets], ["models", "Models", models], ["settings", "Settings", settings],
];
const MOBILE = ["overview", "create", "library", "queue"];
const MORE = { render(main) {
  replace(main, h("h1", { style: "margin-bottom:16px" }, "More"), h("div", { class: "stack" },
    [...NAV.filter(([id]) => !MOBILE.includes(id)), ["projects", "Projects"]].map(([id, label]) =>
      h("a", { class: "panel row", href: `#/${id}`, style: "color:inherit" }, icon(id), h("span", {}, label)))));
} };
const VIEWS = Object.fromEntries([...NAV.map(([id, , view]) => [id, view]), ["projects", projects], ["more", MORE]]);
const NEEDS_PROJECT = new Set(["overview", "create", "library", "scenes", "sheets", "settings"]);
let dispose = null;

function navLink([id, label], mobile = false) {
  return h("a", { href: `#/${id}`, dataset: { nav: id } }, icon(id), h("span", { class: "label" }, label));
}

function buildNav() {
  replace(document.getElementById("nav"), NAV.map((item) => h("li", {}, navLink(item))));
  const more = h("a", { href: "#/more", dataset: { nav: "more" } }, icon("more"), h("span", {}, "More"));
  replace(document.getElementById("bottombar"), NAV.filter(([id]) => MOBILE.includes(id)).map((i) => navLink(i, true)), more);
}

async function loadWorkspace() {
  const ws = await api("/workspace");
  state.projects = ws.projects;
  state.settings = ws.settings;
  const saved = (() => { try { return localStorage.getItem("hf.project"); } catch { return null; } })();
  const ids = ws.projects.map((p) => p.id);
  state.project = ids.includes(state.project) ? state.project : (ids.includes(saved) ? saved : ids[0] || null);
  const selector = document.getElementById("project-select");
  replace(selector, ws.projects.map((p) => h("option", { value: p.id, selected: p.id === state.project ? true : null }, p.name)),
    h("option", { value: "__all__" }, "All projects…"));
  applyTheme(ws.settings.theme);
}

export function applyTheme(theme) {
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}

export function setProject(id) {
  state.project = id;
  try { localStorage.setItem("hf.project", id); } catch { /* private mode: fine */ }
}

async function route() {
  if (dispose) { dispose(); dispose = null; }
  const parts = (location.hash.replace(/^#\/?/, "") || "overview").split("/").map(decodeURIComponent);
  let [name, ...rest] = parts;
  if (!VIEWS[name]) name = "overview";
  if (NEEDS_PROJECT.has(name) && !state.project) name = "projects";
  for (const link of document.querySelectorAll("[data-nav]")) {
    link.toggleAttribute("aria-current", link.dataset.nav === name);
    if (link.dataset.nav === name) link.setAttribute("aria-current", "page");
  }
  const main = document.getElementById("main");
  const title = document.getElementById("topbar-title");
  replace(title, state.projects.find((p) => p.id === state.project)?.name || "Hone Frame");
  replace(main);
  try {
    dispose = (await VIEWS[name].render(main, rest)) || null;
  } catch (error) {
    failure(error);
    replace(main, h("div", { class: "empty" }, h("h2", {}, "This page could not load"), h("p", {}, error.message)));
  }
}

async function start() {
  buildNav();
  try {
    [state.presets] = await Promise.all([api("/presets"), loadWorkspace()]);
  } catch (error) {
    failure(error);
  }
  document.getElementById("project-select").addEventListener("change", (event) => {
    if (event.target.value === "__all__") { location.hash = "#/projects"; return; }
    setProject(event.target.value);
    route();
  });
  document.getElementById("search").addEventListener("submit", (event) => {
    event.preventDefault();
    const q = document.getElementById("search-input").value.trim();
    location.hash = `#/library/search/${encodeURIComponent(q)}`;
  });
  window.addEventListener("hashchange", route);
  window.addEventListener("hf:projects", async () => { await loadWorkspace(); route(); });
  route();
}

start();
