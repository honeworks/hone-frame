// Queue: the run table, and the run page of mockup 1 (stages, current task, evaluation, live activity).
import { api, clock, duration, empty, failure, field, h, icon, img, pill, presetOptions, progressBar, range, replace, select, state, toast, words } from "../core.js";

const LIVE = new Set(["running", "pausing", "queued"]);

export async function render(main, [project, runId]) {
  if (project && runId) return runPage(main, project, runId);
  return runTable(main);
}

async function runTable(main) {
  let scope = "project";
  const body = h("div");
  const head = h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Queue"),
    h("p", { class: "muted" }, "Every run with its stage, progress and time. Open one to watch it.")),
  scopeSelect());
  replace(main, head, body);

  function scopeSelect() {
    const control = h("select", { class: "input", "aria-label": "Scope", style: "width:auto" },
      h("option", { value: "project" }, "This project"), h("option", { value: "all" }, "All projects"));
    control.addEventListener("change", () => { scope = control.value; refresh(); });
    return control;
  }

  async function refresh() {
    const path = scope === "all" ? "/runs?scope=all" : `/runs?project=${state.project}`;
    const rows = await api(path);
    if (!rows.length) {
      replace(body, empty("No runs yet", "Open a character and press Generate assets, or generate a scene.", h("a", { class: "btn primary", href: "#/characters" }, "Characters")));
      return rows;
    }
    replace(body, h("div", { class: "panel" }, h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Output / job", "Model · profile", "Size", "Round", "Status", "Progress", "Elapsed · remaining", ""].map((t, i) => h("th", { class: i === 7 ? "num" : null }, t)))),
      h("tbody", {}, rows.map(runRow))))));
    return rows;
  }

  let timer = null;
  const tick = async () => {
    try {
      const rows = await refresh();
      if (body.isConnected && rows.some((r) => LIVE.has(r.status))) timer = setTimeout(tick, 2000);
    } catch (error) { failure(error); }
  };
  await tick();
  return () => clearTimeout(timer);
}

function runRow(r) {
  const open = () => { location.hash = `#/queue/${r.project}/${r.id}`; };
  const live = r.status === "running" || r.status === "pausing";
  return h("tr", { class: "link", tabindex: 0, onclick: open, onkeydown: (e) => { if (e.key === "Enter") open(); } },
    h("td", {}, h("div", { style: "font-weight:600" }, r.title), h("div", { class: "caption mono" }, r.id)),
    h("td", {}, h("div", {}, r.model || "—"), h("div", { class: "caption" }, r.profile)),
    h("td", { class: "mono" }, r.size || "—"),
    h("td", { class: "num" }, r.round ? `${r.round} of ${r.rounds}` : "—"),
    h("td", {}, pill(r.status)),
    h("td", {}, h("div", { class: "row" }, progressBar(r.progress, live), h("span", { class: "caption" }, `${r.accepted}/${r.outputs}`))),
    h("td", {}, duration(r.elapsed_s), h("span", { class: "muted" }, ` · ${live || r.status === "queued" ? range(r.estimate) : "—"}`)),
    h("td", { class: "num" }, icon("arrow")));
}

async function runPage(main, project, runId) {
  let since = 0;
  let timer = null;
  const parts = {
    head: h("div", { class: "run-head" }), pipeline: h("div"), activity: h("ul", { class: "activity", "aria-live": "polite" }),
    actions: h("div", { class: "row" }), outputs: h("div"), notice: h("div"),
  };
  replace(main,
    h("div", { class: "crumbs caption" }, h("a", { href: "#/queue" }, "Queue"), " / ", runId),
    parts.head, parts.notice,
    h("div", { class: "run-layout" },
      h("section", { class: "panel", "aria-label": "Generation pipeline" }, h("div", { class: "panel-head" }, h("h2", {}, "Generation pipeline")), parts.pipeline),
      h("section", { class: "panel", "aria-label": "Live activity" }, h("div", { class: "panel-head" }, h("h2", {}, "Live activity")), parts.activity, h("hr", { class: "divider" }), parts.actions)),
    h("section", { class: "panel", style: "margin-top:24px", "aria-label": "Completed outputs" }, parts.outputs));

  let misses = 0;
  async function tick() {
    try {
      const data = await api(`/runs/${project}/${runId}?since=${since}`);
      if (!main.isConnected) return;  // the person left this page
      since = data.next;
      misses = 0;
      draw(data);
      if (LIVE.has(data.run.status)) timer = setTimeout(tick, 2000);
    } catch (error) {
      misses += 1;  // a dropped poll is retried; a run of failures is shown once
      if (misses === 3 || error.status === 404) failure(error);
      if (error.status !== 404 && main.isConnected) timer = setTimeout(tick, Math.min(2000 * misses, 10000));
    }
  }

  function draw(data) {
    const run = data.run;
    const live = run.status === "running" || run.status === "pausing";
    replace(parts.head,
      h("div", {}, h("h1", { class: "display", style: "font-size:28px;line-height:36px" }, live ? `Generating ${run.title.toLowerCase()}` : run.title),
        h("div", { class: "caption" }, `${run.outputs.length} outputs · ${run.profile.id} profile · ${run.selection.rounds} rounds × ${run.selection.candidates}`)),
      h("div", { class: "run-stats" },
        stat("Status", pill(run.status)),
        stat("Progress", h("div", { class: "row" }, h("span", { class: "big" }, `${Math.round((run.progress.fraction || 0) * 100)}%`), progressBar(run.progress, false))),
        stat("Elapsed", h("span", { class: "big" }, duration(run.elapsed_s))),
        stat("Estimated remaining", h("span", { class: "big" }, live || run.status === "queued" ? range(run.estimate) : "—"))));
    replace(parts.notice, run.reason ? h("div", { class: `notice ${run.status === "failed" ? "danger" : "warning"}`, style: "margin-bottom:24px" }, run.reason) : null);
    replace(parts.pipeline, h("div", { class: "pipeline" }, stagesList(data.stages), currentTask(data)));
    for (const row of data.activity) parts.activity.prepend(activityRow(row));
    replace(parts.actions, actions(project, run));
    replace(parts.outputs, completed(project, data));
  }

  await tick();
  return () => clearTimeout(timer);
}

function stat(label, value) {
  return h("div", {}, h("span", { class: "caption" }, label), value);
}

function stagesList(stages) {
  return h("ol", { class: "stages", "aria-label": "Stages" }, stages.map((s) => h("li", { class: s.state },
    h("span", { class: "stage-dot" }, s.state === "done" ? icon("check") : null),
    h("div", {}, h("div", { style: "font-weight:600" }, s.name[0].toUpperCase() + s.name.slice(1)),
      h("div", { class: "caption" }, s.state === "running" ? "Running" : s.state === "done" ? "Done" : "Waiting"),
      h("div", { class: "caption" }, s.seconds ? duration(s.seconds) : "")))));
}

function currentTask(data) {
  const cur = data.current;
  if (!cur) return h("div", { class: "muted" }, data.run.status === "queued" ? "Waiting for its turn in the queue." : "Nothing is being worked on.");
  const imgs = cur.images.map((id) => data.images[id]).filter(Boolean);
  const live = data.run.status === "running" || data.run.status === "pausing";
  const judged = imgs.filter((i) => i.evaluation).pop();
  const now = cur.now || {};
  const slot = (s) => {
    const card = imgs.find((i) => i.round === s.round && i.candidate === s.candidate) || null;
    const isNow = live && now.round === s.round && now.candidate === s.candidate;
    return candidate(card, isNow && (!card || now.event === "judging"), cur.candidates > 1 ? `R${s.round} · C${s.candidate}` : `Round ${s.round}`);
  };
  return h("div", { class: "stack" },
    h("div", { class: "panel", style: "padding:16px" },
      h("div", { class: "row" }, h("div", {}, h("div", { class: "caption" }, "Current task"),
        h("h2", {}, `${cur.label} · Round ${cur.round} of ${cur.rounds}`)), h("span", { class: "spacer" }),
        h("div", { class: "caption mono", style: "text-align:right" }, `Output ${cur.output}`, h("br"), cur.model || "")),
      h("div", { class: "candidates", style: "margin-top:12px" }, cur.slots.map(slot))),
    judged ? evaluationTable(judged) : h("div", { class: "caption" }, "No evaluation yet for this output."));
}

function candidate(card, current, label) {
  if (!card) {
    return h("div", { class: `cand${current ? " current" : ""}` }, h("div", { class: "thumb" }, h("span", { class: "caption" }, current ? "Generating…" : "Queued")),
      h("div", { class: "foot" }, h("span", { class: "caption" }, current ? "Current" : label), h("span", { class: "caption" }, "—")));
  }
  const passed = card.passed === true;
  const verdict = card.passed === null ? h("span", { class: "caption" }, current ? "Judging…" : "Not judged")
    : pill(passed ? "pass" : (card.evaluation?.uncertain ? "uncertain" : "fail"));
  return h("div", { class: `cand${current ? " current" : ""}` }, h("div", { class: "thumb" }, img(card)),
    h("div", { class: `foot${passed ? " pass" : ""}` }, verdict, h("span", { class: "mono" }, card.overall !== null ? card.overall.toFixed(2) : label)));
}

function evaluationTable(card) {
  const ev = card.evaluation;
  return h("div", { class: "panel", style: "padding:16px" },
    h("div", { class: "row" }, h("h3", {}, "Evaluation"), h("span", { class: "caption" }, `${card.id} · judge ${ev.judge}`)),
    h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Check"), h("th", {}, "Score"), h("th", {}, "Verdict"), h("th", {}, "Finding"))),
      h("tbody", {}, ev.checks.map((c) => h("tr", {},
        h("td", {}, c.name.replace(/_/g, " "), c.required ? null : h("span", { class: "caption" }, " (preference)")),
        h("td", {}, c.score === null ? "—" : h("div", { class: "row" }, h("div", { class: "bar" }, h("span", { style: `width:${Math.round(c.score * 100)}%` })), h("span", { class: "mono" }, c.score.toFixed(2)))),
        h("td", {}, pill(c.verdict === "pass" ? "pass" : c.verdict === "fail" ? "fail" : "uncertain")),
        h("td", { style: "white-space:normal;min-width:200px" }, c.finding)))))),
    ev.summary ? h("p", { class: "caption" }, ev.summary) : null);
}

function activityRow(row) {
  return h("li", {}, h("span", { class: "t" }, clock(row.at)), h("span", { class: `dot ${row.tone}` }),
    h("div", {}, h("div", { class: "mono", style: "font-size:13px" }, row.title), row.detail ? h("div", { class: "d" }, row.detail) : null));
}

function actions(project, run) {
  const act = (action, body) => async () => {
    try {
      await api(`/runs/${project}/${run.id}/${action}`, { method: "POST", body: body || {} });
      toast(action === "pause" ? "Will stop after the current call." : `${words(action) || action}: done.`);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    } catch (error) { failure(error); }
  };
  const buttons = [];
  if (["running", "queued"].includes(run.status)) buttons.push(h("button", { class: "btn primary", onclick: act("pause") }, icon("pause"), "Pause after current"));
  if (["running", "pausing", "queued", "paused"].includes(run.status)) buttons.push(h("button", { class: "btn", onclick: act("cancel") }, "Cancel"));
  if (run.status === "paused") buttons.push(h("button", { class: "btn primary", onclick: act("resume") }, icon("play"), "Resume"));
  if (["failed", "needs_review"].includes(run.status) && run.outputs.some((o) => ["failed", "waiting", "paused"].includes(o.status))) {
    buttons.push(h("button", { class: "btn primary", onclick: act("retry") }, "Retry"));
  }
  buttons.push(h("details", { class: "advanced" }, h("summary", {}, "View settings"),
    h("pre", { class: "mono caption", style: "white-space:pre-wrap" }, JSON.stringify({ profile: run.profile, selection: run.selection, presets: run.presets }, null, 2))));
  return buttons;
}

function completed(project, data) {
  const run = data.run;
  const accepted = run.outputs.filter((o) => o.selected);
  const open = run.outputs.filter((o) => !o.selected);
  return [
    h("div", { class: "panel-head" }, h("div", {}, h("h2", {}, "Outputs"), h("div", { class: "caption" }, `${accepted.length} accepted · ${open.length} not accepted`)),
      h("a", { href: "#/library/images" }, "View all in library ", icon("arrow"))),
    h("div", { class: "outputs-strip" }, run.outputs.map((o) => outputCard(project, run, o, data.images))),
  ];
}

function outputCard(project, run, o, images) {
  const card = images[o.selected || o.best_available] || images[o.candidates[o.candidates.length - 1]];
  const pickable = o.status === "needs_review" && o.candidates.length;
  const redoable = ["done", "needs_review", "failed"].includes(o.status) && !LIVE.has(run.status);
  return h("div", { class: "cand" }, h("div", { class: "thumb" }, card ? img(card) : h("span", { class: "caption" }, words(o.status))),
    h("div", { class: "stack", style: "padding:8px 12px;gap:4px" },
      h("div", { class: "row" }, h("strong", {}, o.label), h("span", { class: "spacer" }), pill(o.status)),
      card ? h("span", { class: "caption mono" }, `${card.width} × ${card.height}`) : null,
      o.reason ? h("span", { class: "caption", style: "white-space:normal" }, o.reason) : null,
      o.replaced_by ? h("a", { class: "caption", href: `#/queue/${project}/${o.replaced_by.run}` }, "Open the new attempt") : null,
      h("div", { class: "row", style: "gap:6px" },
        pickable ? h("button", { class: "btn small", onclick: () => pickDialog(project, run, o, images) }, "Choose a candidate") : null,
        redoable ? h("button", { class: "btn small", onclick: () => redoDialog(project, run, o) }, "Generate again") : null)));
}

function pickDialog(project, run, o, images) {
  const note = h("input", { class: "input", placeholder: "Why this one (optional)" });
  const dialog = h("dialog", { "aria-label": `Choose a candidate for ${o.label}` },
    h("h2", {}, `Choose a candidate for ${o.label}`),
    h("p", { class: "caption" }, "Your choice is recorded as a manual pick; the judge's findings stay with the image."),
    h("div", { class: "candidates", style: "margin:12px 0" }, o.candidates.map((id) => {
      const card = images[id];
      return h("button", { class: "cand", style: "padding:0;cursor:pointer;text-align:left", onclick: async () => {
        try {
          await api(`/runs/${project}/${run.id}/pick`, { method: "POST", body: { output: o.id, image: id, note: note.value } });
          dialog.close(); toast(`${o.label}: ${id} picked.`);
          window.dispatchEvent(new HashChangeEvent("hashchange"));
        } catch (error) { failure(error); }
      } }, h("div", { class: "thumb" }, img(card)), h("div", { class: "foot" }, h("span", { class: "mono caption" }, id),
        card?.overall !== null && card ? h("span", { class: "mono" }, card.overall.toFixed(2)) : null));
    })),
    note,
    h("div", { class: "row", style: "margin-top:12px" },
      h("button", { class: "btn", onclick: () => { dialog.close(); redoDialog(project, run, o); } }, "None of these: generate again"),
      h("span", { class: "spacer" }), h("button", { class: "btn", onclick: () => dialog.close() }, "Close")));
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
}

function redoDialog(project, run, o) {
  const note = h("textarea", { class: "input", placeholder: "What was wrong and what you want instead, e.g. seen from directly behind, no face visible, both hands empty" });
  const profile = select(presetOptions("profile"), run.profile.id, { "aria-label": "Profile" });
  const rounds = h("input", { class: "input", type: "number", min: 1, max: 10, value: run.selection.rounds, "aria-label": "Rounds" });
  const dialog = h("dialog", { "aria-label": `Generate ${o.label} again` },
    h("form", { class: "stack", onsubmit: async (event) => {
      event.preventDefault();
      try {
        const redo = await api(`/runs/${project}/${run.id}/rerun`, { method: "POST",
          body: { output: o.id, note: note.value, profile: profile.value, rounds: Number(rounds.value) } });
        dialog.close();
        toast(`${o.label}: a new attempt is queued.`);
        location.hash = `#/queue/${redo.project}/${redo.id}`;
      } catch (error) { failure(error); }
    } },
    h("h2", {}, `Generate ${o.label} again`),
    h("p", { class: "caption", style: "margin:0" }, "A new run for this one output, with the same subject and references. The current candidates stay in the library with their findings."),
    field("What should change", note, "Added to the prompt."),
    h("div", { class: "row", style: "flex-wrap:nowrap" }, field("Profile", profile, "Final uses Qwen-Image-Edit, which has camera-angle control (good for side and back views)."), field("Rounds", rounds)),
    h("div", { class: "row" }, h("span", { class: "spacer" }), h("button", { class: "btn", type: "button", onclick: () => dialog.close() }, "Cancel"),
      h("button", { class: "btn primary", type: "submit" }, "Generate again"))));
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
}
