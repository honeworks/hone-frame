# 0001: Initial design: Hone Frame, the first product (v0.1)

## Status

`accepted` 2026-10-02. The owner gave the product brief (kept in full in
[`../history/0000-first-product-brief.md`](../history/0000-first-product-brief.md)) with two dashboard
mockups. They said "First step is the design doc... Don't wait on me, write the docs, and start
developing. The base of this project should use hone-flow, hone-models." This record turns the brief into
a design, and it is accepted in advance by that instruction. Implementation is in milestones (M1 to M6
below). The smaller choices are in [`../decisions.md`](../decisions.md), and the ones that need the
owner's eyes are flagged there.

## Context

The honeworks libraries already cover the building blocks of a picture pipeline:

- **hone-models** calls image models (ComfyUI workflows such as `z-image-turbo`, `flux.2-klein-4b` and
  `qwen-image-edit-2511`, and hosted ones such as `gpt-image-1.5`) and vision LLMs through one registry,
  with GPU leases, call records, fakes for tests and per-model guides
  ([hone-models 0015](https://github.com/honeworks/hone-models/blob/main/design/changes/0015-generation-models.md)).
- **hone-flow** runs steps as self-contained run folders with resume after a crash, per-item failure
  isolation and progress events.
- **hone-select** picks a winner from candidates. It keeps gates apart from scores and never treats
  "could not score" as zero.

A first attempt at the product built a character model sheet and placed the character in scenes. It was
written as two hand-made pipelines in a local playground (`pipeline-demo`: `sheets`, `scenes`, `fishing`),
and it taught most of what this design keeps or avoids:

- **Collages are a trap.** A sheet drawn as one picture cannot be re-laid out, relabelled or reused piece
  by piece, and drawn text is wrong. The pipeline ended up drawing each panel separately and typesetting
  the sheet in Python.
- **Identity comes from references, not words.** A text-only model (`z-image-turbo`) drifted the hair
  colour between frames. Reference-taking models (Qwen-Image-Edit 2511, FLUX.2 klein) kept the character.
- **Judges are weak and must explain themselves.** A 7B vision judge scored almost everything 0.9 to 1.0.
  A describe-first answer and required checks that must pass (not one blended score) made the verdicts
  useful.
- **Reference lists grow silently.** Attaching "everything we have" to every call hit model limits and
  confused the models. References have to be chosen and given a purpose.
- **Waiting without information is the worst part.** A planner with thinking on ran for ten minutes with
  nothing on screen (the owner keeps thinking off for planners and judges).
- **hone-flow cannot fan out again after a select step.** The playground had to hold whole stages in one
  step.

## Problem

There is no product that lets a person run a visual project end to end: define characters, places and
objects once; generate and judge their reference images unattended; lay out sheets without another model
call; build scenes from exactly the references chosen; and see honestly what is happening while it runs.
Each new project re-wrote the pipeline, the judging, the sheet layout and the progress display.

## Options

1. **Keep writing pipelines per project** in a playground. Fast for one demo, but the work is redone every
   time and there is no dashboard.
2. **A ComfyUI front end** (custom nodes and a web UI). It ties everything to one backend and has no place
   for projects, versions, judging or sheets as data.
3. **A product package on the honeworks libraries.** It owns the visual domain (projects, subjects,
   presets, recipes, judging rules, sheets, the dashboard) and delegates model calls to hone-models, run
   execution to hone-flow and picking to hone-select.

## Decision

Option 3: **hone-frame**, a Python package with a local dashboard. The design in full is in
[`../current.md`](../current.md). In short:

### What it owns and what it delegates (brief §13)

- **hone-frame owns** project definitions and their versions, the preset catalogue, production recipes
  (which outputs a request expands into), reference roles and their precedence, the judging profiles,
  deterministic sheet composition, exports and the dashboard.
- **hone-models** handles every model call: image generation, vision judging, planning and upscaling.
  There is no model client of hone-frame's own. Profiles name hone-models registry ids.
- **hone-flow** runs every generation request as a run folder. Each requested output is one item. The
  `produce` step runs that output's rounds and the final step composes and exports.
- **hone-select** picks each output's winner. Required checks are gates, the judge's preference is the
  score, and "none passed" is a flagged result, never a silent winner.
- Unlike its siblings, hone-frame depends on these three packages in its core: it is a product built on
  them, by the owner's instruction (D-001). They come from their GitHub repositories until they are on
  PyPI.

### Data: a workspace of plain files (brief §3, §17)

- A **workspace** folder (default `./hone-frame`, or `HONE_FRAME_HOME`) holds projects as JSON files and
  images as files, with no database. Runs are hone-flow run folders inside it.
- **Project → characters, environments, assets** (the three subject kinds), plus scenes, sheets,
  sequences and runs. Subjects carry **states** (outfit, expression, wet/dry, open/closed...).
- **Versions:** changing a subject, scene or sheet writes a new version. Images are immutable and every
  image records the subject versions it was made from. Scenes and sheets point at exact versions, and an
  "update available" flag shows when a newer subject version exists. Updating is the user's action.
- **Every candidate image is kept.** A selection points at an image and never overwrites one. Status
  (draft, final, rejected, picked, uncertain, needs review) is data on the image and on the output.

### Generation: requests, outputs, rounds (brief §4, §5)

- A **request** (task type, subjects, scene, presets, profile, selection settings) expands into
  **outputs**: one per view, expression, interaction, scene shot or sequence frame. The plan is shown
  before launch with counts. Twelve outputs × 3 rounds × 1 candidate is 36 planned images; judging work
  and technical retries are counted separately.
- **Profiles** (Draft, Standard, Final, Custom) name the planner, generator, judge and upscaler models and
  their settings. The **selection settings** are separate: strategy (`batch`: generate the round's
  candidates and judge them; `sequential`: each round's prompt uses the previous findings), rounds
  (default 3), candidates per round (default 1), auto judge, auto pick (needs auto judge), stopping rule
  (`all_rounds` or `stop_on_pass`) and the technical retry limit (default 2).
- **Judging** is one vision-LLM call per candidate through hone-models. Its answer has a short
  description, per-check verdicts (`pass`, `fail`, `uncertain`, `not_assessable`) with a score and a
  finding, and an overall preference. A judging profile lists the checks per output kind, and only
  meaningful checks run (an isolated cup has no anatomy check). Required checks gate, so a high overall
  score never hides a required failure.
- **Picking:** across all completed rounds the best eligible candidate wins, so a later candidate never
  replaces a better earlier one. With none eligible, the output is **Needs review** and keeps its best
  candidate as "best available", not accepted. A manual pick records an override and keeps the findings.
- **Dependencies:** an output that needs an accepted reference (a view needs the accepted hero, a frame
  the accepted previous frame) waits. Unrelated outputs continue. A dependency that ends in Needs review
  leaves the dependents **Waiting for reference** until someone picks. Then a retry continues them.

### Scenes and the advanced features (brief §7 to §11)

- A **scene** names its subjects explicitly, each with a version, the images to use and a **role**
  (identity, outfit, environment, object, pose, expression, composition, lighting, style). Nothing
  unselected is attached. The plan shows the exact references, their order, any reduction forced by the
  model's `max_references` (lowest-precedence roles go first), and whether the model takes references at
  all ("text only: weaker control").
- **Coverage** (one output per camera), **interactions** (a character with an asset and an action),
  **state pairs** (before/after with shared framing and seed), **sequences** (ordered frames, each with
  start state, change and end state. Every frame keeps the stable identity references and may add the
  previous frame for continuity) and **variation grids** (the cartesian product of chosen axes) are all
  recipes that expand a request into outputs. Every output gets its own candidates and verdicts.
- **Promotion** of a chosen draft: `upscale` (needs a model with the `upscale` feature, shown as
  unavailable otherwise), `refine` (the draft plus its original references go to the Final model) or
  `regenerate` (the saved scene definition with the Final profile). Results link to their parent, and a
  failed promotion never replaces the draft.

### Sheets and exports (brief §6, §17)

- The **sheet composer** is deterministic Python (Pillow). A sheet is a saved layout recipe (layout
  preset, image order, crop or fit, columns, page size, background, spacing, labels, heading, palette,
  notes) plus exact image ids, in versions. The same recipe and images always give the same PNG bytes.
  Recomposing never calls a model. A larger canvas never invents detail.
- **Exports** are zip files: a sheet (PNG, optionally the source images and `sheet.json`), a **reference
  pack** (only the subjects and views a scene selected, with `pack.json`), a sequence (numbered frames
  and `sequence.json`) or the whole project. Secrets never enter an export.

### Presets before any project (brief §12)

The package ships a populated **catalogue**: 10 style packs and the camera, lighting, expression, pose,
interaction, state, presentation, sheet layout, profile, selection and judging categories. Each preset
has an id, a version, a description, prompt fragments, supported subject kinds and capability needs.
Presets never name a paid model, so profiles stay the only place models are chosen. Runs record the
preset versions they used. The default pack is Cinematic realism with neutral studio lighting and the
four-view turnaround.

### Runs you can watch and trust (brief §15)

- Statuses: Queued, Running, Pausing, Paused, Done, Needs review, Failed, Canceled. "Done" means every
  output was accepted. Calls finishing is not the same as checks passing.
- The `produce` step writes **events** (`events.jsonl`) as it goes: stage, round, candidate, model,
  durations, findings and previews. The dashboard reads them, so "Generating kitchen profile, round 2 of
  3" is visible while it happens.
- **Progress** counts completed planned units (image calls and judge calls), and early stopping shrinks
  the plan. The current generation is indeterminate unless the backend reports steps.
- **Estimates** are a range (25th to 75th percentile) from observed durations of the same model and size,
  times the remaining calls, plus the queue ahead. Without evidence they say "Estimating".
- **Pause** and **cancel** take effect at the next safe boundary (between model calls). The UI says "will
  stop after the current call". **Resume** and **retry** continue the same hone-flow run. `produce` skips
  every candidate already stored, so nothing accepted or generated is redone. A restart of the dashboard
  resumes interrupted runs (hone-flow takes over the dead lease).
- **Usage** shows render seconds, GPU seconds for local models, and cost only when the provider reports
  or the registry prices it (marked estimated). Local work never gets a dollar price.

### The dashboard (brief §14, §16)

A local web page served by the package (`hone-frame dashboard`). It uses the standard-library HTTP
server with a JSON API and static HTML, CSS and JavaScript, and has no build step, the same approach as
hone-select's dashboard. It includes:

- the **Studio Minimal** look: tokens, type scale, layout and components as in the brief, with light as
  the primary theme and dark available;
- a sidebar with Overview, Create, Library, Scenes, Sheets, Queue, Presets, Models and Settings, and a
  project selector;
- one primary action per view;
- a **runner** thread that executes the queue one run at a time (a local GPU does one job at a time).

The page shows only real data. The mockups' "Professional Plan" label and sample scores are not product
features (D-005).

### Milestones

| Milestone | Scope | Acceptance cases |
|---|---|---|
| M1 | workspace, projects, subjects and versions, images and import, the preset catalogue | AC-1, AC-2 |
| M2 | sheet composer and exports | AC-5, AC-10 |
| M3 | requests and plans, profiles, the `produce` step (rounds, judging, picking, retries), runs, control, events, estimates | AC-3, AC-8, AC-9, AC-11 |
| M4 | scenes and roles, coverage, interactions, state pairs, sequences, variation grids, promotion | AC-4, AC-6, AC-7 |
| M5 | the dashboard and its API | AC-12 |
| M6 | docs and examples, the real-model case | AC-13, AC-14 |

## Consequences

- hone-frame needs hone-flow, hone-models and hone-select installed. The wheel smoke test installs them
  from GitHub first (D-002).
- Everything a person sees is a file in the workspace, so a project can be copied, backed up or read
  without the package.
- Judging quality is bounded by the judge model. The design makes verdicts visible and overridable
  rather than trusting them.
- A remote generation that was in flight when the process died cannot be looked up again: hone-models
  has no "fetch job by id" yet. Such an attempt is recorded as `unknown` and generated again, visibly
  (§10 of current.md; a hone-models change can close this gap).
- Out of scope (brief §18): video, audio, rigging, 3D editing, layer extraction, training, a
  drag-and-drop canvas, several users and hosted billing.

## Migration and compatibility

None: nothing has been released. The workspace format starts at `format_version: "1"`.
