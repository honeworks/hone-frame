# Why hone-frame exists

> Define a project's characters, places and objects once. Generate, judge and pick their images
> unattended. Lay out sheets without another model call, and build scenes from exactly the references
> you chose, while watching the work happen.

## The problem

Making consistent pictures of the same character, room and props across many shots is still manual
work, even with good image models:

- **Every project re-writes the pipeline:** prompts, reference handling, retries, judging, picking and
  the sheet layout.
- **Sheets are drawn as one picture.** They cannot be re-laid out or relabelled, they cannot be reused
  piece by piece, and their text comes out garbled.
- **References pile up.** Everything available is attached to every call, the model gets confused or
  hits its limit, and nobody can say afterwards what a picture was made from.
- **Judging is a single blended score.** A beautiful image with the wrong face wins, and "the judge could
  not tell" turns into a number.
- **Long runs are opaque.** There is a spinner, an invented percentage, and no way to pause without
  losing work.

## Why existing tools fall short

- **Node-graph tools** (ComfyUI and its front ends) are excellent at one generation. They have no notion
  of a project, subject versions, judging rules, sheets as data or a honest run history.
- **Hosted image apps** keep the person in the loop for every pick, hide the model and its settings,
  and tie the work to one provider.
- **Hand-written pipelines** (the playground pipelines that came before hone-frame) proved the ideas
  but were rebuilt for every project and had no dashboard.

## Core ideas

1. **Images are the unit, sheets are compositions.** Every candidate is kept as its own file with a full
   record. A sheet is a saved layout over exact image ids, composed in Python, deterministic, with no
   model call.
2. **Versions, not overwrites.** Subjects, scenes and sheets change by new versions. Outputs keep what
   they were made from, and a flag shows when something newer exists.
3. **References have a purpose.** Each reference in a scene has a role (identity, outfit, object,
   pose...) and a precedence. Nothing unselected is attached, and the exact inputs are visible before
   generation.
4. **Required checks gate, preference ranks.** A judge answers per check with a verdict and a finding.
   A required failure is never outweighed by a high score, and "uncertain" is not "pass". Picking is
   hone-select's job, and "nothing passed" is a visible state.
5. **Honest runs.** Real stages, real counts, estimates only from observed durations, pause and resume
   at safe boundaries, nothing lost on a restart. hone-flow keeps every run as a run folder.
6. **One model layer.** Every model call (planner, generator, judge, upscaler) goes through
   hone-models, so profiles are just registry ids and local and hosted models are equal.

## What it deliberately does not do

No video or audio generation, rigging, 3D scene editing, layer extraction, model training,
drag-and-drop canvas, collaboration, accounts or billing. These are separate extensions. A preset never
chooses a paid model.

## What is in this folder

| File | What it holds |
|---|---|
| [`current.md`](current.md) | the design as it stands today: concepts, rules and the guarantees the tests check |
| [`changes/0001-initial-design.md`](changes/0001-initial-design.md) | the first design, from the owner's brief |
| [`changes/0002-prompt-dialects.md`](changes/0002-prompt-dialects.md) | prompts written per model, task and style |
| [`changes/0003-character-first.md`](changes/0003-character-first.md) | complete character packs, world and character assets, a dashboard that follows the work |
| [`history/`](history/) | the owner's product brief, kept in full |
| [`decisions.md`](decisions.md) | small implementation choices, and the items awaiting owner review |

A new design change starts as a record in `changes/` with status `proposed`; see
[CONTRIBUTING.md](../CONTRIBUTING.md#changing-the-design). How the package is built is described in the
[README](../README.md#how-this-was-built).
