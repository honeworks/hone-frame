// Shared helpers: the API, safe DOM building (never innerHTML with data), icons and formatting.

export const state = { project: null, projects: [], presets: null, settings: null };

export async function api(path, { method = "GET", body, raw } = {}) {
  const init = { method, headers: {} };
  if (raw) {
    init.body = raw.body;
    init.headers["Content-Type"] = raw.type || "application/octet-stream";
    init.headers["X-File-Name"] = raw.name || "upload.png";
  } else if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`/api${path}`, init);
  const data = await response.json().catch(() => ({ error: response.statusText }));
  if (!response.ok) {
    const error = new Error(data.error || response.statusText);
    error.problems = data.problems || [];
    error.status = response.status;
    throw error;
  }
  return data;
}

// h("div", {class: "x", onclick: fn}, child, "text", [children]) -> Element
export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "value") node.value = value;
    else if (key === "checked") node.checked = Boolean(value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function replace(node, ...children) {
  node.replaceChildren();
  append(node, children);
  return node;
}

const SVG = "http://www.w3.org/2000/svg";
const ICONS = {
  overview: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  create: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 8v8M8 12h8",
  library: "M5 4h10a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2zM17 6h2v14M9 8h4",
  scenes: "M3 6h18v12H3zM3 10h18M7 6l2 4M12 6l2 4M17 6l2 4",
  sheets: "M4 4h16v16H4zM4 12h16M12 4v16",
  queue: "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
  presets: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M16 4v4M10 10v4M18 16v4",
  models: "M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12v9M12 12 4 7.5",
  settings: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  check: "M5 12l5 5L20 7",
  close: "M6 6l12 12M18 6 6 18",
  pause: "M8 5v14M16 5v14",
  play: "M7 4l13 8-13 8z",
  arrow: "M5 12h14M13 6l6 6-6 6",
  plus: "M12 5v14M5 12h14",
  download: "M12 4v12M6 10l6 6 6-6M4 20h16",
};

export function icon(name, label) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon");
  if (label) { svg.setAttribute("role", "img"); svg.setAttribute("aria-label", label); }
  else svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", ICONS[name] || ICONS.more);
  svg.append(path);
  return svg;
}

const WORDS = {
  queued: "Queued", running: "Running", pausing: "Pausing", paused: "Paused", done: "Done",
  needs_review: "Needs review", failed: "Failed", canceled: "Canceled", waiting: "Waiting",
  candidate: "Candidate", picked: "Picked", manual_pick: "Picked by you", best_available: "Best available",
  rejected: "Rejected", uncertain: "Uncertain", imported: "Imported", pass: "Pass", fail: "Fail",
  not_assessable: "Not assessable",
};

export function pill(status) {
  return h("span", { class: `pill ${status}` }, WORDS[status] || status);
}

export function words(status) { return WORDS[status] || status; }

export function progressBar(progress, live) {
  if (!progress || !progress.planned) return h("div", { class: `progress${live ? " indeterminate" : ""}` }, h("span"));
  const pct = Math.round((progress.fraction || 0) * 100);
  return h("div", { class: "progress", role: "progressbar", "aria-valuenow": pct, "aria-valuemin": 0,
    "aria-valuemax": 100 }, h("span", { style: `width:${pct}%` }));
}

export function duration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
}

export function range(estimate) {
  if (!estimate) return "Estimating";
  const low = Math.max(1, Math.round(estimate.low_s / 60));
  const high = Math.max(low, Math.round(estimate.high_s / 60));
  if (estimate.high_s < 90) {
    const [a, b] = [Math.round(estimate.low_s), Math.round(estimate.high_s)];
    return a === b ? `${a}s` : `${a}–${b}s`;
  }
  return low === high ? `${low}m` : `${low}–${high}m`;
}

export function clock(stamp) {
  if (!stamp) return "";
  const date = new Date(stamp);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

export function when(stamp) {
  if (!stamp) return "";
  const date = new Date(stamp);
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function toast(message, error = false) {
  const node = document.getElementById("toast");
  replace(node, message);
  node.className = `toast${error ? " error" : ""}`;
  node.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.hidden = true; }, error ? 7000 : 3500);
}

export function failure(error) {
  const problems = (error.problems || []).filter((p) => p && p !== error.message);
  toast(problems.length ? `${error.message}` : error.message, true);
}

export function img(card, alt) {
  if (!card) return h("span", { class: "placeholder-img" }, "No image yet");
  return h("img", { src: card.url, alt: alt || card.label || card.id, loading: "lazy", width: card.width, height: card.height });
}

export function empty(title, text, action) {
  return h("div", { class: "empty" }, h("h2", {}, title), h("p", {}, text), action || null);
}

export function field(label, control, hint) {
  const id = control.id || `f-${Math.random().toString(36).slice(2, 8)}`;
  control.id = id;
  return h("div", { class: "field" }, h("label", { for: id }, label), control, hint ? h("div", { class: "hint" }, hint) : null);
}

export function select(options, value, attrs = {}) {
  return h("select", { class: "input", ...attrs },
    options.map(([v, text]) => h("option", { value: v, selected: v === value ? true : null }, text)));
}

export function toggle(checked, attrs = {}) {
  const input = h("input", { type: "checkbox", role: "switch", checked, ...attrs });
  return { input, node: h("span", { class: "switch" }, input, h("span")) };
}

export function presetOptions(category, { kind, blank } = {}) {
  const rows = (state.presets?.[category] || []).filter((p) => !kind || !p.subject_kinds.length || p.subject_kinds.includes(kind));
  return [...(blank ? [["", blank]] : []), ...rows.map((p) => [p.id, p.name])];
}

export function projectPath(rest = "") { return `/projects/${state.project}${rest}`; }
