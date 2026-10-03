# hone-frame: the design today (0.1.0, first product)

This is the design as it stands: what hone-frame does, the rules it follows and the behaviour it
guarantees. Why it looks like this is in [`changes/0001-initial-design.md`](changes/0001-initial-design.md).
The smaller choices are in [`decisions.md`](decisions.md), and the owner's brief is in
[`history/0000-first-product-brief.md`](history/0000-first-product-brief.md). Section numbers are stable,
and code comments refer to them (for example "design §8.3").

## 1. What hone-frame does

Hone Frame is a project-based visual production workspace. A person describes a project and creates its
characters, environments and assets (objects and props). hone-frame then:

- generates and judges their reference images unattended;
- composes sheets from those images in Python, without another model call;
- builds scenes from exactly the references chosen;
- explores cheap drafts and promotes the chosen ones to finals;
- exports focused reference packs for other image and video tools.

A local dashboard shows the work as it happens.

### Goals

- Every generated image is kept on its own and stays reusable. Sheets are compositions of images, never
  generated collages.
- Generation runs unattended for many outputs (rounds, judging, picking) and explains every selection.
  Unresolved quality failures stay visible and are never shown as accepted.
- A scene sees only what was selected for it, with a visible purpose (role), version and order for each
  reference.
- Progress, estimates and usage are real. When there is no evidence, the dashboard says so.
- Projects, images, runs and decisions are plain files in a workspace folder. They survive refreshes
  and restarts.

### Non-goals (0.1)

Video generation, audio, rigging, a 3D scene editor, layer extraction, model training, a drag-and-drop
scene canvas, several users, accounts and hosted billing.

### Responsibilities

hone-frame owns the visual domain:

- project definitions and their versions;
- the preset catalogue and the recipes;
- reference roles;
- the judging profiles;
- sheet composition and exports;
- the dashboard.

It delegates the rest:

- every model call to **hone-models**;
- run execution to **hone-flow**;
- picking to **hone-select**.

These three are core dependencies (D-001).

## 2. Public API

```text
import hone_frame as hf

ws = hf.Workspace(path=None, *, models=None)   # path: HONE_FRAME_HOME, else ~/hone-frame
                                               # models: a Models port (§7.2); default hf.HoneModels()
ws.presets -> hf.PresetCatalog                 # the built-in catalogue (§5), also hf.presets()
ws.projects() -> list[hf.Project]
ws.create_project(name, *, brief="", direction="", style_pack="cinematic-realism",
                  defaults=None) -> hf.ProjectStore
ws.project(project_id) -> hf.ProjectStore
ws.queue() -> list[hf.RunView]                 # every project's queued and running runs, oldest first
ws.settings -> hf.Settings;  ws.save_settings(settings)

p = ws.project("morning-at-home")              # a ProjectStore
p.info -> hf.Project;  p.update(**fields) -> hf.Project
p.add_subject(kind, name, *, description="", **fields) -> hf.Subject      # kind: character | environment | asset
p.edit_subject(subject_id, **changes) -> hf.Subject                      # a new version
p.subject(subject_id, version=None) -> hf.Subject;  p.subjects(kind=None) -> list[hf.Subject]
p.import_image(path, *, subject_id=None, label="") -> hf.ImageRecord
p.image(image_id) -> hf.ImageRecord;  p.image_path(image_id) -> Path
p.image_uses(image_id) -> list[str];  p.delete_image(image_id)            # refused while used (§4.3)
p.images(*, kind=None, subject_id=None, status=None, model=None, since=None) -> list[hf.ImageRecord]
p.save_scene(scene) -> hf.Scene;  p.scene(scene_id, version=None);  p.scenes()
p.save_sequence(sequence) -> hf.Sequence;  p.sequence(sequence_id, version=None);  p.sequences()
p.save_sheet(recipe, sheet_id=None) -> hf.Sheet;  p.sheet(sheet_id, version=None);  p.sheets()
p.compose_sheet(sheet_id, version=None) -> Path            # deterministic PNG, no model call (§11)
p.outdated() -> list[hf.OutdatedUse]                       # scenes / sheets on an older subject version

p.plan(request) -> hf.Plan                     # the expansion, references, counts and warnings; writes nothing
p.submit(request) -> hf.RunView                # validated, saved, Queued
p.runs() -> list[hf.RunView];  p.run_view(run_id) -> hf.RunView
p.pause(run_id);  p.cancel(run_id);  p.resume(run_id)      # resume: also after a pause or a crash
p.retry(run_id)                                # failed / waiting outputs of the same run
p.rerun(run_id, output_id) -> hf.RunView       # a new run for one output, linked to the old one
p.pick(run_id, output_id, image_id, *, note="") -> hf.OutputRecord     # a manual pick (§8.5)
p.export_sheet(sheet_id, out, *, sources=False) -> Path
p.export_pack(scene_id, out) -> Path;  p.export_sequence(sequence_id, out) -> Path
p.export_project(out) -> Path

hf.Runner(ws).run_next() -> hf.RunView | None  # execute the oldest queued run in this process
hf.Runner(ws).run_forever(stop_event)          # what the dashboard's runner thread does
hf.Runner(ws).recover() -> list[str]           # resume runs left running by a dead process

hone_frame.dashboard.serve(ws, host="127.0.0.1", port=8792, *, runner=True)   # §12; Dashboard(...).start() in tests

Requests (Pydantic, §6): hf.SubjectReferences, hf.SceneShot, hf.Coverage, hf.Interaction, hf.StatePair,
hf.SequenceFrames, hf.Variations, hf.Promote (a dict with "kind" works too); settings: hf.Selection and
a profile id.
Records: hf.Project, hf.Subject, hf.State, hf.ImageRecord, hf.Scene, hf.SceneRef, hf.Sequence, hf.Frame,
hf.Sheet, hf.SheetRecipe, hf.Plan, hf.PlannedOutput, hf.RunView, hf.OutputRecord, hf.Evaluation,
hf.CheckResult.
hf.Models (the port, §7.2), hf.HoneModels, hf.ModelInfo, hf.Generated, hf.ModelFailure
hf.errors: HoneFrameError, NotFound, InvalidRequest, CapabilityProblem, RunStateError
hone_frame.testing: FakeModels (scriptable images and verdicts), judge_answer(prompt, fail=...), sample_workspace(path)
```

Command line (extra `cli`): `hone-frame dashboard [--home DIR] [--port 8792] [--no-runner]`,
`hone-frame presets [--category C] [--json]`, `hone-frame projects`, `hone-frame run-queue [--once]`,
`hone-frame status RUN_ID`, `hone-frame export-pack PROJECT SCENE OUT`. Every command has `--json`. Exit
codes: 0 success, 1 failure, 2 usage error.

## 3. A worked example

This is the main acceptance flow (AC-3, AC-4 and AC-5, run with `hf.testing.FakeModels`).

```text
import hone_frame as hf
from hone_frame.testing import FakeModels

ws = hf.Workspace(tmp_path / "studio", models=FakeModels())
p = ws.create_project("Morning at home", brief="A quiet morning routine.",
                      direction="soft, natural, lived-in", style_pack="cinematic-realism")
woman = p.add_subject("character", "Woman", description="late twenties, black hair in a loose bun, cream knit sweater")
kitchen = p.add_subject("environment", "Kitchen", description="small bright kitchen, white tiles, wooden shelves")
cup = p.add_subject("asset", "Coffee cup", description="speckled cream ceramic mug, round handle")
p.add_subject("asset", "Toothbrush", description="bamboo toothbrush")

req = hf.SubjectReferences(subject_id=woman.id, presentation="turnaround", profile="draft",
                           selection=hf.Selection(rounds=3, candidates=1, auto_judge=True, auto_pick=True))
plan = p.plan(req)               # 5 outputs: hero, then front, three-quarter, side, back (each depends on the hero)
assert plan.counts.images == 15  # 5 outputs x 3 rounds x 1 candidate
run = p.submit(req)
hf.Runner(ws).run_next()         # executes the hone-flow run in this process
view = p.run_view(run.id)
assert view.status == "done" and all(o.status == "done" for o in view.outputs)
assert len(p.images(subject_id=woman.id)) == 15        # every candidate kept

sheet = p.save_sheet(hf.SheetRecipe(name="Woman turnaround", layout="four-view-turnaround",
                                    images=[o.selected for o in view.outputs[1:]],
                                    labels=["Front", "3/4", "Side", "Back"]))
png = p.compose_sheet(sheet.id)                        # no model call; same bytes every time

scene = p.save_scene(hf.Scene(name="Coffee scene", description="She holds the cup and smiles at the window.",
                              refs=[hf.SceneRef(subject_id=woman.id, role="identity"),
                                    hf.SceneRef(subject_id=kitchen.id, role="environment"),
                                    hf.SceneRef(subject_id=cup.id, role="object")],
                              camera="medium", expression="focused"))
shot = p.plan(hf.SceneShot(scene_id=scene.id, profile="draft"))
assert [r.subject_id for r in shot.outputs[0].references] == [woman.id, kitchen.id, cup.id]   # no toothbrush
```

## 4. Workspace and records

### 4.1 Layout (`format_version: "1"`)

```text
<home>/
  workspace.json                     {"format_version": "1", "created_at": ...}
  settings.json                      dashboard and default settings (§12.6); never secrets
  projects/<project id>/
    project.json                     the project and its defaults
    subjects/<subject id>.json       the subject's versions, newest last
    images/<image id>.<ext>          the original file, never modified
    images/<image id>.json           its record
    scenes/<scene id>.json           versions
    sequences/<sequence id>.json     versions
    sheets/<sheet id>.json           versions;  sheets/<sheet id>/v<n>.png the composed renders
    runs/<run id>/
      run.json                       request, plan, effective settings, preset versions, flow run id, state
      control.json                   {"action": "pause" | "cancel" | null, "at"} (only while asked)
      events.jsonl                   progress events (§9.3)
      outputs/<output id>.json       the output record (§8.6)
      work/                          reduced reference copies (§10.3); removed when the run finishes
  flows/<project id>/runs/<flow run id>/   hone-flow run folders (one per run)
  exports/                           default export target
```

- **Ids** are readable and sequential per project and kind: `char_001`, `env_001`, `obj_001`,
  `scn_001`, `seq_001`, `sht_001`, `img_0001`. A project id is the name's slug (`morning-at-home`, with
  `-2`, `-3` added on a clash). Run ids follow hone-flow's form (`<UTC %Y%m%dT%H%M%SZ>-<6 hex>`).
- Every JSON file has `format_version: "1"` and is written atomically (a temporary file, then
  `os.replace`). Readers ignore unknown keys. A `format_version` they do not know raises
  `HoneFrameError` saying "upgrade hone-frame". Records are Pydantic models in `records.py`.
- One process writes at a time per project (D-004). The dashboard's handlers and the runner thread take
  a per-project lock for every write.

### 4.2 Projects and subjects

- `Project`: `id`, `name`, `brief`, `direction`, `style_pack` (preset id), `look` (the world's look
  guide, change 0005), `variations` and `variation` (the active one; §4.5), `defaults` (profile names per
  role, a `Selection`, preset choices per category), `created_at`, `updated_at`.
- `Subject`: `id`, `kind` (`character` | `environment` | `asset`), `name`, `description`, `version`,
  `fields` (by kind: character: `appearance`, `proportions`, `features`, `outfits`; environment:
  `anchors`, `materials`, `viewpoints`, `recurring_objects`; asset: `scale`, `materials`, `colours`,
  `details`), `states` (a `State(name, kind, description)` each, kind `outfit`, `expression`,
  `condition`, `lighting` or `other`), `tags`, `reference_images` (image ids the person chose as the
  subject's references, in order), `owner` (a belonging's character, 0003), and `must` / `never` (what
  every image of it always or never shows, 0005).
- **Versions.** `edit_subject` writes a new version with the changed fields. Older versions stay readable
  (`p.subject(id, version=1)`), and a version's content never changes.

### 4.5 Variations (change 0005)

A project is a world; a **variation** is one way of drawing it: `Variation(id, name, style_pack,
direction)`. The world (subjects, scenes, the look guide) is shared; every generated image belongs to one
variation (`ImageRecord.variation`; a plan's `variation`; a request may name one, else the project's
active one). Accepted heroes, references, the character page, model sheets and world assets are looked up
per variation, so each variation has its own hero of each character. A project without variations has
one, `main`, from its style pack; images without a variation belong to the first one. A project made
before this change uses its `direction` as its look guide. `add_variation`, `edit_variation` and
`use_variation` on the project store.

### 4.3 Images

`ImageRecord`:

| Group | Fields |
|---|---|
| What it is | `id`, `file`, `width`, `height`, `sha256`, `source` (`generated` \| `imported` \| `promoted`) |
| Subject links | `subjects` (`[{"subject_id", "version"}]`), `label` (`front`, `smile`, `scene`...) |
| Where it came from | `run_id`, `output_id`, `round`, `candidate`, `parent` (the image it was promoted or refined from) |
| How it was made | `generation` (`model`, `prompt`, `inputs` without file paths, `references` (`[{"image_id", "role"}]` in order), `seed`, `job_id`, `elapsed_s`, `cost_usd`, `cost_estimated`) |
| Quality | `evaluation` (§8.3, or `null`), `status` |
| Bookkeeping | `profile`, `created_at` |

- `status` is one of `candidate`, `picked` (chosen automatically), `manual_pick` (a person chose it),
  `best_available` (best of an output that needs review), `rejected` (failed a required check),
  `uncertain` (the judge could not decide a required check) or `imported`. Status and verdict are
  separate fields: a manual pick of a failed image keeps its evaluation.
- Image files are never changed or deleted by a run. Deleting an image someone uses is refused, and the
  dashboard lists the uses first (§12.4).

### 4.4 Scenes, sequences and sheets

- `Scene`: `id`, `version`, `name`, `description`, `refs` (a `SceneRef` each: `subject_id`, `version`
  (pinned when saved; the latest when omitted), `image_ids` (which of the subject's images to use; the
  subject's accepted references when empty), `role`, `state` (a state name or `null`)), `camera`,
  `framing`, `pose`, `expression`, `lighting`, `action`, `gaze`, `notes`, `overrides` (preset choices
  that win over the project's defaults).
- `Sequence`: `id`, `version`, `scene_id`, `frames` (a `Frame(id, start_state, change, end_state,
  description, use_previous=True)` each, in order).
- `Sheet`: `id`, `version`, `recipe` (`SheetRecipe`, §11.1), `renders` (`{version: file}`).
- **Outdated uses.** `p.outdated()` lists every scene, sequence and sheet whose pinned subject version, or
  whose images' subject version, is older than the subject's current version. The dashboard shows an
  "Update available" flag. Updating saves a new scene or sheet version and never changes the old one.

## 5. Presets

### 5.1 The catalogue

The package ships `hone_frame/data/presets/<category>.toml`. `ws.presets` merges them with the user's
own packs (`<home>/presets/*.toml`, optional). Categories and the shipped presets:

| Category (`id`) | Presets |
|---|---|
| `style_pack` | cinematic-realism, illustrated-storybook, clean-2d-animation, cel-shaded-animation, inked-comic, painterly-fantasy, stylised-3d, miniature-stop-motion, historical-epic, product-studio |
| `character_presentation` | neutral-full-body, portrait-detail, turnaround, expression-study, pose-study, outfit-comparison |
| `environment_presentation` | interior-coverage, exterior-coverage, establishing-detail, day-night, material-landmark |
| `asset_presentation` | four-views, top-detail, isolated-studio, scale-comparison, state-comparison, interaction-study |
| `camera` | establishing, wide, medium, close-up, extreme-close-up, detail, front, profile, rear, three-quarter, overhead, low-angle, reverse, pov |
| `lighting` | neutral-studio, soft-daylight, overcast, dawn, golden-hour, moonlight, candlelight, practical-interior, dramatic-side |
| `expression` | neutral, happy, sad, angry, afraid, surprised, tired, focused, doubtful, determined |
| `pose` | neutral-standing, seated, walking, reaching, pointing, looking-back, holding, carrying, gripping, pushing, pulling |
| `interaction` | hold-cup, grip-tool, wear-backpack, sit-on-chair, open-door, operate-appliance |
| `state` | clean-dirty, dry-wet, intact-damaged, open-closed, empty-full, on-off, day-night, tidy-disordered |
| `sheet_layout` | four-view-turnaround, expression-grid, pose-grid, object-detail-board, environment-board, before-after, sequence-strip, contact-grid |
| `profile` | draft, standard, final, custom |
| `selection` | batch-then-judge, sequential-judge-refine, all-rounds, stop-on-pass, manual-pick |
| `judging` | character-identity, environment-continuity, object-fidelity, interaction-plausibility, scene-fidelity, sequence-continuity |

### 5.2 A preset

Each preset has these fields:

- `id`, `category`, `version` (an integer), `name`, `description` (plain words that are useful without
  an image);
- `subject_kinds` (which kinds it applies to; empty means all);
- `prompt` (fragments: `prefix`, `suffix`, `negative`);
- `values` (category-specific defaults: a style pack's choices per category, a presentation's outputs, a
  layout's grid, a profile's roles, a selection's settings, a judging profile's checks);
- `needs` (capabilities it requires, such as `references`, `pose_conditioning` or `upscale`);
- `example` (an optional image path inside the package; none ship in 0.1).

- **Presets never name a model.** Models are chosen only by profiles, and the shipped profiles name local
  models (§7.1), so no preset forces a paid provider. A test checks every shipped preset.
- **Independent categories.** A style pack sets defaults for other categories, and a choice in one
  category (a camera) never replaces another (the subject's identity, the project's style).
- **Unsupported combinations** are explained or disabled. `Plan.warnings` names any preset whose `needs`
  the profile's models do not meet, and the dashboard disables those choices with that reason.
- **Versions are recorded.** A run records `{preset id: version}` for every preset it used. Changing the
  catalogue never changes a saved project. The project stores preset ids, and a run resolves them once,
  when it is submitted.
- Defaults: the style pack is `cinematic-realism` (with `neutral-studio` lighting and the
  `four-view-turnaround` layout), the profile is `draft` and the selection is `all-rounds` (3 rounds, 1
  candidate, auto judge and auto pick on).

## 6. Requests, recipes and plans

### 6.1 Requests

Every request has these fields:

- `profile` (a profile id or a `Profile`);
- `selection` (`Selection` or `null` for the project default);
- `presets` (choices per category that override the project's);
- `note` (free text that goes into prompts).

The request kinds, each with its recipe (`recipes.py`):

| Request | Outputs |
|---|---|
| `SubjectReferences(subject_id, presentation, states=[], expressions=[], poses=[])` | a **hero** first (no references, or the subject's chosen reference images), then one output per view, expression, pose or state of the presentation. Each depends on the hero and takes the accepted hero as its identity reference |
| `SceneShot(scene_id)` | one output: the scene with its references |
| `Coverage(scene_id, cameras)` | one output per camera, sharing the scene's references, states and seed base |
| `Interaction(character_id, asset_id, action, pose=None, pose_image=None)` | one output linked to both subjects |
| `StatePair(subject_id or scene_id, state_before, state_after, same_framing=True)` | two outputs, before and after. With `same_framing` they share the seed and framing, and the after output also takes the accepted before image as its `composition` reference |
| `SequenceFrames(sequence_id)` | one output per frame, in order. Each depends on the previous frame when `use_previous` is set |
| `Variations(base, axes)` | the cartesian product of `axes` (`{"outfit": [...], "expression": [...], "lighting": [...], "camera": [...], "state": [...], "style": [...]}`) over a `base` request (a `SceneShot` or `SubjectReferences` hero). Each cell is one output, labelled by its axis values |
| `Promote(image_id, operation)` | `upscale`, `refine` or `regenerate` (§10.5) |
| `CharacterPacks(subject_id, packs=[], custom={}, redraw_hero=False, only_custom=False)` | a character's packs (§6.3, change 0003): the hero once, then every chosen pack's items from it |

### 6.3 Character packs (change 0003)

A character's references are made pack by pack (`data/character_packs.toml`, `recipes_packs.py`), in
this order: `hero` (front, full figure, neutral pose), `turnaround` (Front, 3/4, Side, Back),
`expressions` (eight face close-ups), `poses` (six full-figure poses), `outfits` (one per outfit state),
`states` (one per condition, lighting or other state), `assets` (each **belonging**: an asset whose
`owner` is the character) and `actions` (the character holding and using each belonging).

- `packs` empty means every pack; `custom` adds a person's own items to a pack (its keys must be among
  the chosen packs, else the request is refused): an expression, a pose,
  an outfit, a state, an action or a view, as the pack's `custom` says; `only_custom` makes only those.
- **The hero is drawn once.** When the character has an accepted hero (an accepted image with pack
  `hero`, or an older one labelled "Hero") it is every item's identity reference; otherwise the hero is
  the first output and the others depend on it (§8.7). `redraw_hero` draws a new one.
- An action takes the belonging's accepted image as its `object` reference; a belonging without one is
  made first in the same request and the action depends on it (change 0004).
- A character whose features or outfit put an object in its hands (a weapon, "holding"...) gets a plan
  warning (`carried_objects`): reference images are drawn with empty hands, and the object belongs in
  Belongings.
- **Reference look.** Every item of a character or object reference (packs and `SubjectReferences`) is
  written on `a plain pure white background` and, for characters except actions, with **empty hands**
  (the `props` section); the outputs carry the conditions `clean_background` and `no_props`, which the
  judge checks (§8.3). Places keep their own background.
- Planned outputs and images record `pack` and `item`. The character page (§12.4) shows per item the
  latest accepted image and the newest output with its candidates.
- **World assets** are places and objects without an `owner`; `world_requests` makes one request per
  chosen world asset (a place: `SubjectReferences`; an object: its object packs), by default those
  without an accepted hero.
- **Object packs** (change 0005, `data/object_packs.toml`, `recipes_objects.py`): an object (a belonging
  or a world object) gets a `hero` (three-quarter, from slightly above) and `views` (front, side, back,
  top, and a close-up of its distinctive detail) made from it; `CharacterPacks` on an object makes them.
  A character's request makes each belonging without an accepted hero first (hero and views); its
  actions take the belonging's hero as their `object` reference. The character page shows each
  belonging as a section, like a pack.
- **The pose library** (change 0005, `pose_library.py`): every pose item but standing takes a plain
  wooden mannequin in its pose as its `pose` reference; the mannequin is drawn first in the same request
  (fixed wording, judged by `pose-reference`) unless the project already has an accepted one, and is
  reused by every character (mannequins belong to no variation).
- **Plan warnings:** objects in a character's hands (0004) and small marks that drift between images
  (beauty marks, moles, freckles, tattoos, scars: give an exact place and size, or remove them; 0005).
- **When to check** (change 0006): a request's `approval` is `auto`, `base` (the run waits after the
  outputs others are made from: hero, belongings' heroes, pose mannequins, planned first) or `each` (also
  after every pack). The plan's `checkpoints` name them; after one the run stops with "Waiting for your
  approval: …" (control action `approve`) and resuming it is the approval.
- **Hero casting** (change 0006, `casting.py`): `CharacterPacks.casting` = n draws the hero's n candidates
  from n distinct readings the planner writes (varying only what the description leaves open); seeds only
  without a planner or when it fails.
- **Standard issues** (change 0006, `issues.py`, `data/issues.toml`): `rerun(..., issues=[ids])` adds
  each issue's fix to the new attempt's prompt and its check to the judging.
- **Judge options** (change 0006): `judge_mode` `default`, `strong_base` or `strong_all` uses the
  workspace's `strong_judge` for the base images or for every image; a plan without one set has an error.
- **Clean-up** (change 0006, `cleanup.py`): delete unchosen candidates of finished outputs, or a
  variation's images (not the active or only one). `unchosen` keeps and counts images in use; deleting a
  variation is refused (`InvalidRequest`, naming the uses) while any of its images is in use.
- **Whole-world runs** (change 0005, `world_runs.py`): `p.world_plan(variation)` lists the runs of every
  place and object without an image and every character, with an estimate (measured median seconds per
  image, or 70 s before any measurement); `p.generate_world(variation)` queues them in that order and
  gives the last run its scenes as follow-up requests (`RunRecord.then`), queued when it finishes.

### 6.2 Plans

`p.plan(request)` resolves everything and writes nothing. `p.submit(request)` saves the same plan in
`run.json`. A `Plan` has:

- `outputs`: a `PlannedOutput(id, label, kind, subjects, references, depends_on, prompt_inputs,
  judging, size)` each. `references` is the exact ordered list `[{image_id, subject_id, version, role}]`
  after precedence and reduction (§10.2). `prompt_inputs` holds the preset fragments and the scene
  fields the prompt is built from.
- `profile`: the resolved models and settings (§7.1). `selection` is the effective `Selection`.
- `presets`: `{id: version}`.
- `counts`: `outputs`, `images` (= outputs × rounds × candidates, the most it can take), `judge_calls`
  (the same when auto judge is on, else 0), `planner_calls`.
- `estimate`: `{"low_s", "high_s"}` or `null` ("Estimating", §9.4).
- `warnings`: references reduced, a model without reference input ("text only: weaker control"), a
  preset whose needs are not met, an unaccepted dependency.
- `errors`: things that block submission. Examples: auto pick without auto judge, a scene ref to a
  subject with no usable image, an unknown preset or model. `submit` raises `InvalidRequest` with them.

## 7. Profiles and models

### 7.1 Profiles

A profile names a model id (a hone-models registry id) for each role, plus settings:

- `planner`: a chat model that writes the image prompt, or `null` for the template prompt;
- `generator`: an image model for outputs without references;
- `editor`: an image model that takes references, used when an output has references (`null`: the
  generator is used and the references are described in text);
- `judge`: a vision chat model;
- `upscaler`: an image model whose guide lists the feature `upscale`, or `null`;
- `size` (`"1024x1024"` or per output kind), `settings` (the generation inputs the models take: `steps`,
  `cfg`, `negative`...), `planner_think` (default `false`), `judge_think` (default `false`).

| Profile | planner | generator | editor | judge |
|---|---|---|---|---|
| draft | `gemma4-12b` | `z-image-turbo` | `flux.2-klein-4b` | `qwen2.5vl-7b` |
| standard | `gemma4-12b` | `flux.2-klein-4b` | `flux.2-klein-4b` | `qwen2.5vl-7b` |
| final | `gemma4-12b` | `qwen-image-edit-2511` | `qwen-image-edit-2511` | `qwen2.5vl-7b` |
| custom | the user's choices, saved in the project (`defaults.custom_profile`) | | | |

Profiles are presets (category `profile`). A project may override any role (`defaults.profiles`), and so
may a request. The effective models are in the plan, the run and every image record. "Draft" means a
cheaper intent, not a promise that the model is fast (brief §4).

### 7.2 The `Models` port

hone-frame calls models only through this small Protocol (`ports.py`). The default implementation,
`HoneModels`, is hone-models (`mk.image`, `mk.text`, `mk.guide`, `mk.registry`). Tests use
`hf.testing.FakeModels`.

```python
class Models(Protocol):
    def generate(self, model_id: str, prompt: str, *, out: Path, seed: int,
                 references: list[Path], inputs: dict[str, Any]) -> Generated: ...
    def ask(self, model_id: str, prompt: str, *, images: list[Path], schema: type[T],
            think: bool) -> T: ...            # raises ModelFailure with the reason
    def info(self, model_id: str) -> ModelInfo: ...   # kind, max_references, inputs, features, local,
                                                      # installed, available, sizes
    def available(self, kind: str) -> list[ModelInfo]: ...
```

`Generated` holds `path`, `seed`, `elapsed_s`, `job_id`, `cost_usd`, `cost_estimated`, `error` and
`error_kind` (hone-models' `MediaResult` fields). `HoneModels.generate` passes `references` only when
there are some, and `inputs` only when the model takes them (`info.inputs`). Model calls lease the GPU
themselves (hone-models §7), so hone-frame's steps hold no GPU lease of their own.

### 7.3 hone-frame's model entries

`src/hone_frame/data/hone-models.toml` (with its `data/workflows/`) holds the hone-models entries that
hone-models' catalog does not ship yet: the proven ComfyUI workflows of `flux.2-klein-4b` (two reference
slots), `flux.2-klein-4b-text` and `qwen-image-edit-2511` (three slots), each with `vram_gb` near the
whole card so the GPU scheduler unloads the chat models first. `HoneModels` loads hone-models' registry
with this file and then `<home>/hone-models.toml` (when it exists), after hone-models' own user and
working-folder files, so hone-frame works from any folder
and a workspace can override any entry (decisions D-016). `flux.2-klein-4b` gets every reference slot
filled, the last reference repeated, because an empty slot breaks its graph (D-017).

## 8. Producing an output

### 8.1 The workflow

Each project has one hone-flow workflow, `hone_frame.engine.build(store)`: name = the project id, storage
= `<home>/flows`, version `"1"`. Its items are the plan's outputs, in plan order (dependencies first). It
has two steps:

- `produce` (item step, `deterministic=False`): runs §8.2 for one output and returns its `OutputRecord`.
- `compose` (final step): when the request asked for a sheet (`SubjectReferences` with a sheet layout)
  and every output is accepted, it saves and composes that sheet. Otherwise it records why it did
  nothing. An output asked again in another run (`replaced`) is not accepted in this run, so its
  sheet is composed from the Sheets view once the new attempt is accepted.

The run's seed is derived from the run id, so `ctx.seed` differs per output and stays stable across
resume. A candidate's seed is `int(sha256(f"{ctx.seed}:{round}:{candidate}")[:8], 16)`, except that the
outputs of a `StatePair` with `same_framing` share their seed.

### 8.2 Rounds

```text
plan the prompt (planner model, else the template)                          stage "planning"
for round in 1..rounds:
    for candidate in 1..candidates:                                          stage "generating"
        skip it if its image is already stored for (run, output, round, candidate)   (resume)
        generate with technical retries (§8.4); store the image (status "candidate")
        if auto_judge: evaluate it (§8.3), store the evaluation                stage "judging"
    if stop_on_pass and some candidate of this round passed: stop
    if strategy == "sequential": re-plan the prompt with this round's findings
pick (§8.5)                                                                  stage "selecting"
```

- The **prompt** is composed for the generating model's **dialect**, the output's **mode** and the
  style (§8.8, change 0002). The **planner** gets the dialect's rules for that mode, the word budget and
  the composed draft, and returns `{"prompt": str, "negative": str | null}`. Its answer is used only if
  it passes the dialect's checks (§8.8); otherwise the composed draft is used and a `planner_rejected`
  event says why. If the planner fails after its technical retries, the composed draft is used and a
  `planner_failed` event says so.
- **Sequential strategy:** the next round's prompt gets the latest findings ("fix: the cup handle is
  missing; keep: identity"). The stable identity references are always attached, and a candidate image
  is never used as the identity reference.

### 8.3 Judging

One `Models.ask` call per candidate. The images are the candidate first, then the output's identity and
object references (at most 3). The prompt describes the requested output and lists the checks of the
judging profile chosen for the output kind:

| Output kind | Judging profile | Checks (required unless marked) |
|---|---|---|
| hero, view, expression, pose of a character | character-identity | identity (not for the hero), view, expression, outfit_state, framing, anatomy, style (preference) |
| environment output | environment-continuity | viewpoint, anchors, recurring_objects (when listed), materials, lighting, style (preference) |
| asset output | object-fidelity | shape, details, material, view_state, object_alone (object packs, 0006), scale_cues (preference), style (preference) |
| interaction | interaction-plausibility | identity, contact, hand_placement, object_orientation, scale, anatomy, style (preference) |
| scene, coverage, state | scene-fidelity | subject_presence, identity, action, reference_roles, composition, camera, state, style (preference) |
| sequence frame | sequence-continuity | the scene-fidelity checks plus continuity and state_progression |

Reference outputs of characters and objects (change 0003) also carry `clean_background` (the
character-identity, object-fidelity and interaction-plausibility profiles ask whether the background is
plain white) and, for characters with empty hands, `no_props` (character-identity asks whether the hands
are empty). An object pack's images (change 0006) carry `object_alone`: the prompt has the required
`alone` section ("The object alone: no person, no hands, nobody holding, wearing or riding it") and
object-fidelity asks whether anyone is in the picture.

**What was asked** (change 0004): the judge prompt lists the request from the plan, not only the prompt
that was sent: `Requested view`, framing, pose, facial expression, clothing, state, action, background
and empty hands, so a rewritten or shortened prompt cannot redefine what passes. `view` asks only about
the requested view; a back view (`rear`) also gets `faces_away`. `anatomy` names hands and feet (fingers,
missing, merged or twisted feet, feet that point a way the body could not stand).

The answer schema:

```python
class CheckResult(BaseModel):
    name: str
    verdict: Literal["pass", "fail", "uncertain", "not_assessable"]
    score: float | None  # 0..1, a comparative signal, not a probability
    finding: str  # one concrete sentence

class Evaluation(BaseModel):  # what hone-frame stores
    description: str  # what the judge sees, written first
    checks: list[CheckResult]
    overall: float  # 0..1 preference among acceptable candidates
    summary: str
```

- **The judge's schema names every check.** The schema sent to the judge (`answer_schema(checks)`)
  makes `checks` an object with one required key per check name (any name: fields are aliased), each
  `{finding, verdict, score}` in that order, so a judge cannot mislabel or skip a check (D-020) and
  writes what it sees before it decides (change 0004: with the verdict first, the 7B judge wrote "not
  kneeling" and answered pass). `finding` is required in the schema sent and tolerated empty when read.
- **Rear views** (camera `rear`, in subject references and scenes) replace `identity` with
  `identity_from_behind`: build, hair, clothing
  and distinguishing features against the reference, no face expected (D-020).
- **Only meaningful checks.** A check whose condition does not hold is left out of the prompt. Examples:
  `identity` without an identity reference, `anatomy` for an isolated object, `state` without a
  requested state.
- **Verdicts.** A check may carry `min_score` in its profile. A `pass` below it becomes `fail` with the
  finding "score below the threshold". An output passes when every required check is `pass`. `uncertain`
  or `not_assessable` on a required check does not pass, and the image status becomes `uncertain` (not
  `rejected`).
- A judge answer that is not a valid `Evaluation` after hone-models' own retries is a technical failure
  of the judge call (§8.4). If the judge still fails after the retries, the candidate's evaluation is
  `null` with the reason in an event, and the output cannot be auto-picked from that candidate.

### 8.4 Technical retries

A model call that raises (`ProviderError`, `ModelTimeout`) or returns `error_kind` `out_of_memory`,
`failed` or `no_output` is retried up to `selection.technical_retries` times (default 2). Each retry is a
`retry` event and is counted apart from creative rounds. `refused` and `invalid_input` are not retried:
the candidate is recorded as failed with the reason. When the retries run out, the whole output fails
(`failed`, technical) with the last error, and the images made so far stay stored.

### 8.5 Picking

`pick.py` builds a hone-select `Engine` per output:

- one gate per required check (`passed` = the check's verdict is `pass`);
- one scorer `overall` (the judge's preference);
- the policy `argmax` and the fallback `none`.

The engine runs over every candidate of every completed round. Ties are broken by the earlier candidate,
so a later candidate never replaces a better earlier one.

- A winner is an accepted output. Its image status becomes `picked` and the losers become `candidate` or
  `rejected`.
- With no winner (or no auto pick), the output is `needs_review`. The best candidate by `overall` among
  the uncertain, then the rejected, is marked `best_available` and is not accepted.
- `p.pick(run, output, image, note=)` sets `selected` to that image with `manual: true`, the actor (the
  OS user), the time and the note. The image status becomes `manual_pick`, its evaluation is kept, and
  the output becomes `done` (accepted by a person). Dependent outputs that were waiting can then be
  continued with `p.retry(run)`.

### 8.6 The output record

`runs/<run>/outputs/<output id>.json`, written by `produce` as it goes and on every pick:

- `id`, `label`, `kind`, `status`, `rounds_done`;
- `candidates` (image ids, in order), `selected` (image id or `null`), `best_available`, `manual`;
- `reason` (why this pick, or why none: "no candidate passed identity; best available img_0012");
- `retries`, `error`, `prompt` (the last prompt used), `started_at`, `ended_at`.

Output statuses:

| Status | Meaning |
|---|---|
| `queued` | not started |
| `running` | being produced |
| `done` | accepted, automatically or by a person |
| `needs_review` | no candidate passed, or manual pick mode |
| `waiting` | it needs an accepted reference that does not exist yet |
| `failed` | a technical failure after its retries |
| `paused` | stopped by a pause before it finished |
| `canceled` | stopped by a cancel before it finished |
| `replaced` | a person asked for it again in a new run (`replaced_by`); its candidates stay |

### 8.7 Dependencies

`produce` for an output with `depends_on` reads the dependencies' output records:

- When every dependency is `done`, their selected images become this output's references, with the
  roles the recipe gives them.
- Otherwise `produce` records `waiting` ("waiting for an accepted Woman hero") and raises
  `WaitingForReference`, so hone-flow marks that item `failed`. Other outputs continue.
- `p.retry(run)` resumes the hone-flow run, which reruns the failed items. Outputs that are `done` are
  never produced again.

### 8.8 Prompt dialects (change 0002)

- **Mode**, from what the model receives: `generate` (no reference image), `view` (the same character,
  place or object again from its reference: other views, expressions, poses, states), `compose`
  (references combined into a scene, interaction or sequence frame). Promotions keep their own wording.
- **Dialect** (`data/prompting.toml`, plus `<home>/prompting.toml`, whose dialects win by name): the
  models it serves (ids or `*` patterns; `generic` last), an optional `camera_phrase` template, and per
  mode the ordered `sections`, `max_words`, the style form (`full` or `short`) and the planner's
  `rules`. Shipped: `z-image` (long and structured, up to 250 words), `flux-klein` (subject first, up to
  120; a view is an edit instruction), `qwen-edit` (the Multiple-Angles camera phrase first, keep and
  change, up to 110 for a view), `generic`.
- **Sections** (`prompt_sections.py`): `camera_phrase`, `shot`, `view`, `subject`, `outfit`, `features`,
  `keep`, `scene`, `roles`, `action`, `expression`, `pose`, `gaze`, `state`, `frame`, `background`,
  `props`, `lighting`, `style_lead`, `style_close`, `text_refs`, `note`, `fixes`. A view whose camera preset has
  `faces_away` leaves the face out everywhere and says it is not visible; a full-figure output asks for
  the whole figure and uses `wide shot` in the camera phrase; a reference output (`reference`) uses the
  style pack's `short` form, never its scene and mood wording.
- **Budget** (change 0004): over `max_words`, `keep` first becomes compact ("the same clothes, armour
  and colours", since the reference image shows them), then optional sections are dropped, least
  important first (`style_close`, `text_refs`, `frame`, `features`, `lighting`, `roles`...). Never
  dropped: what was **asked** (`pose`, `expression`, `outfit`, `state`, `action`, `gaze`, a person's
  `note`), the framing and style (`shot`, `style_lead`) and `camera_phrase`, `view`, `keep`, `subject`,
  `scene`, `background`, `props`, `fixes`. A prompt that still does not fit is sent whole and a
  `prompt_long` event says so.
- An outfit item (`outfit` input) replaces the clothes: `keep` no longer lists the default outfit and
  `outfit` says what is worn instead; a view's `framing` is appended to its `view` sentence.
- **Style packs** carry `short` and optional `dialects.<name>.prefix / suffix` (clean 2D animation opens
  and closes a z-image prompt with its 2D wording). **Camera presets** carry `view`, `faces_away`,
  `azimuth`, `elevation` and `distance`.
- **Planner check:** the planner is told what the image exists to show. A rewrite is refused when it is
  longer than 125% of `max_words` (or 110% of a draft that is already longer), loses the camera phrase,
  no longer names `image 1` when the draft did, or loses most of the words of what was asked.
- **The look guide and must lists** (change 0005): sections `look` (after the shot; in every mode except
  an edit of the same subject, unless the item's pack has `context = "full"`, like outfits and states)
  and `must` ("Always visible: …"); both are never dropped. The variation's `direction` follows the style
  words in `style_lead`. A subject's `never` list goes into the negative of models that take one.
- When the dialect writes the camera phrase, `camera_angle` is not also sent as an input. The `planned`
  event and each image's `generation` record the `dialect` and `mode`.

## 9. Runs

### 9.1 Run statuses

A run's status is derived from `run.json`, the control file, the hone-flow lease and the output records.
The first match wins:

| Status | When |
|---|---|
| `queued` | submitted, no hone-flow run yet |
| `pausing` | a pause or cancel was asked while the run is live |
| `running` | its hone-flow run's lease is live |
| `paused` | stopped by a pause, or left by a dead process (`reason: "interrupted"`) |
| `canceled` | stopped by a cancel |
| `failed` | some output `failed` |
| `needs_review` | some output `needs_review` or `waiting` |
| `done` | every output `done` |

`RunView` holds:

- `id`, `project`, `title` (from the request: "Generating coffee scene"), `kind`, `status`, `reason`;
- `stage` (the latest stage event), `current` (the output, round, candidate and model being worked on);
- `outputs` (`OutputRecord`s), `accepted` and `unresolved` (output ids);
- `progress` (§9.3), `estimate` (§9.4), `usage` (§9.5);
- `created_at`, `started_at`, `ended_at`, `elapsed_s`;
- `profile`, `selection`, `presets`, `flow_run_id`, `rerun_of`.

### 9.2 Control

- `pause(run)` and `cancel(run)` write `control.json`. `produce` checks it before every model call and
  raises `StopRequested` at that boundary, so a model call in flight finishes first (the dashboard says
  "Will stop after the current call"). `run_next` returns and the run becomes `paused` or `canceled`.
  Outputs that had not finished become `paused` or `canceled`. A queued run is paused or canceled at
  once.
- `resume(run)` clears `control.json` and queues the run again. The runner calls hone-flow's `resume()`,
  which reruns the failed (stopped, waiting) and interrupted items. Candidates already stored are
  skipped (§8.2), so a resume never regenerates an image.
- `retry(run)` is a resume of a finished run with `failed` or `waiting` outputs. `rerun(run, output, note=, profile=, selection=)`
  is a new run with that one output's planned definition (`rerun_of` set): the person's note is added to
  its prompt, and another profile or selection may be chosen (the model is chosen again for that
  profile). The old output becomes `replaced` (with `replaced_by`), keeps its images and findings, and no
  longer counts as unresolved (D-019).
- Calling these in the wrong state raises `RunStateError` with what is allowed (a canceled run cannot be
  resumed; `rerun` it).
- **Restart.** `Runner.recover()` (run when the dashboard starts) finds runs whose `run.json` says
  `running` but whose hone-flow lease is not live and queues them for resume. hone-flow takes over the
  dead lease and marks the running item `interrupted`.

### 9.3 Events and progress

`events.jsonl` has one JSON object per line: `at`, `event`, `output`, `round`, `candidate`, `model`,
`image`, `duration_s`, `message`, plus event fields. The events:

- `run_started`, `run_finished`;
- `stage` (`planning`, `generating`, `judging`, `selecting`, `refining`, `composing`, `exporting`);
- `output_started`, `output_finished`;
- `planned` (the prompt);
- `generated`, `judged` (verdict, overall, findings);
- `retry`, `planner_failed`, `judge_failed`, `candidate_failed`, `waiting`, `picked`, `stopped`,
  `stopped_early`;
- `model_info_unavailable` (the port could not describe a model, so its prompt guide and local flag are
  left out);
- `prompt_long`, `planner_rejected` (change 0004);
- `follow_up` (a follow-up request queued, or why not) and `follow_up_skipped` (the run ended failed,
  canceled or paused, so its follow-ups were not queued) (change 0005).

Events are written by the process doing the work. The dashboard tails the file.

**Progress** counts units, where a unit is one image call or one judge call. `planned` starts at
`counts.images + counts.judge_calls`. Early stopping lowers it by the units of the rounds skipped, so the
denominator moves visibly. `done` counts finished units (failed calls included). `fraction = done /
planned`. The current generation is reported as `indeterminate`, because hone-models reports no step
progress for image jobs.

### 9.4 Estimates

- **Evidence.** The duration of each `generated` and `judged` event, keyed by `(model, size)` (size
  `null` for judges), from every run of the workspace. The last 50 events per key count.
- **Range.** With at least 3 durations for every key the remaining work needs, the remaining time is
  `remaining units per key × (25th, 75th percentile of that key)`, summed. The queue ahead adds its own
  estimates.
- **No evidence.** If any key has fewer than 3 durations, the estimate is `null` and the dashboard shows
  "Estimating". It never counts down a made-up figure.

### 9.5 Usage

Per run and per project:

- `render_s`: the sum of the generation `elapsed_s`.
- `gpu_s`: the same sum over local models only (`ModelInfo.local`). It is `null` when there were none.
- `cost_usd`: the sum of `cost_usd` where the provider or registry gave one, with `cost_estimated` when
  any part was estimated. It is `null` when there was none, and never 0 for local work.
- `images`, `judge_calls`, `retries`.

Provider balances appear only if a model provider reports them. None does in 0.1, so the dashboard shows
none.

## 10. Scenes and references

### 10.1 Roles

The roles are `identity`, `outfit`, `environment`, `object`, `pose`, `expression`, `composition`,
`lighting` and `style`. A `SceneRef` gives one subject one role. Several refs may name the same subject
with different images and roles (a face for `identity`, an outfit image for `outfit`). A ref's images
are `image_ids` when given, else the subject's chosen reference images, else its accepted hero, else the
first accepted image of that subject (§4.4). A scene ref with no usable image is a plan error.

**Belongings in scenes** (change 0003). Saved with `suggest`, a scene's characters' belongings not yet in
it are listed for the profile's planner with the scene's description and action; those it names are added
as `object` refs with `suggested: true`. A suggested ref is replaced on the next suggestion; without a
planner, or when it fails, nothing is added and the reason is returned.

### 10.2 Precedence, order and reduction

- References are ordered by role precedence: identity, object, environment, outfit, pose, expression,
  composition, lighting, style. Within a role they keep the scene's order.
- When the editor's `max_references` is smaller than the list, the lowest-precedence references are
  dropped. `Plan.warnings` names each dropped reference, and the dropped ones are written into the prompt
  as text.
- With an editor that takes no references (or `editor: null` and a text-only generator), every
  reference becomes text (the subject's description). The plan warns "text only: weaker control".
- Explicit scene fields (`camera`, `lighting`...) win over the project defaults. A subject's `state`
  changes only what the state describes, and identity stays. The prompt says so.

### 10.3 Size limits

References larger than `settings.max_reference_px` (default 1536 px on the long side) are reduced into
`runs/<run>/work/` before submission. The original image is never changed.

### 10.4 Pose, camera and interactions

- Camera, pose, expression, gaze and orientation come from presets plus free text.
- A model whose guide lists a `camera_angle` input (Qwen-Image-Edit's Multiple-Angles LoRA) receives the
  matching choice. Other models get the camera in words.
- Pose or skeleton conditioning is used only when the model's info lists the feature `pose`, and the plan
  says when it is not available.
- An interaction output links to both subjects. Its judging adds `contact`, `hand_placement` and
  `object_orientation`.

### 10.5 Promotion

`Promote(image_id, operation, profile="final")` is a run with one output:

| Operation | What happens | Without a capable model |
|---|---|---|
| `upscale` | the profile's `upscaler` gets the image as its `image` input | a plan error ("no upscaler is available") |
| `refine` | the profile's `editor` gets the draft first, then the draft's original references, with the draft's prompt and "keep the composition, improve detail" | a plan error |
| `regenerate` | the draft's scene or output definition with the profile's models | (always possible) |

- The new image records `parent` and `source: "promoted"`. The draft keeps its status.
- Judging checks the requested subject consistency, plus `preserved_composition` for `refine` and
  `upscale`.
- A failed promotion (`needs_review` or `failed`) never changes the draft.

## 11. Sheets and exports

### 11.1 The sheet recipe

`SheetRecipe` fields:

| Field | Default and meaning |
|---|---|
| `name` | the sheet's name |
| `layout` | a `sheet_layout` preset id |
| `images` | image ids, in order |
| `labels` | one per image, or empty |
| `columns` | `null`: from the layout |
| `page` | `"auto"`, or `"WxH"` px |
| `fit` | `contain` or `cover` |
| `background` | a hex colour; default `#FFFFFF` |
| `spacing` | 24 px |
| `margin` | 48 px |
| `heading` | `null`: the name |
| `palette` | hex colours drawn as swatches |
| `notes` | free text |
| `show_meta` | print each image's id and size under its label |

Layouts set the defaults for `columns`, the cell aspect ratio and the label style. Each layout is one
of:

- `four-view-turnaround` (4 columns, tall cells);
- `expression-grid` (4 columns, square);
- `pose-grid` (3, tall);
- `object-detail-board` (one large cell and a grid);
- `environment-board` (2, wide);
- `before-after` (2);
- `sequence-strip` (one row with numbers);
- `contact-grid` (`ceil(sqrt(n))`).

### 11.2 Composition (`sheets.py`)

- Pillow only, no model call. Cells are laid out on the grid. Each image is resized with `LANCZOS` into
  its cell (`contain` letterboxes on the background, `cover` crops the centre).
- Labels, the heading, notes and swatches with their hex codes are typeset with Pillow's bundled font
  (`ImageFont.load_default(size)`), so the result does not depend on the system's fonts.
- **Determinism:** the PNG is saved with no metadata and fixed settings. The same recipe and the same
  image files give byte-identical output (AC-5).
- `page` larger than the images' natural size makes a larger canvas, and the images are not upscaled
  past 1:1 (the brief: a canvas never invents detail). `contain` centres them at their natural size.
- `compose_sheet` saves `sheets/<id>/v<version>.png`. Recomposing a saved version gives the same file.
- **`character-model-sheet`** (change 0003): the first `columns` images are full figures in one row (the
  hero and the turnaround), the rest face close-ups below, four to a row, then the notes (description,
  appearance, build, distinguishing features, outfit). `characters.model_sheet_recipe` builds it from the
  character's accepted pack images.

### 11.3 Exports (`exports.py`)

Each export is a zip file:

- `export_sheet`: `sheet.png`, `sheet.json` (the recipe and the image records), and with `sources=True`
  the source images under `images/`.
- `export_pack(scene)`: the scene's references after resolution (§10.1), only those, as
  `images/<nn>-<subject>-<role>.<ext>`, plus `pack.json` (the scene, the subjects at their versions, each
  image's record and role, in order).
- `export_sequence`: `frames/<nn>.<ext>` (each frame's selected image) and `sequence.json` (frame order,
  descriptions, states, references).
- `export_project`: the project folder's JSON files and images, without `runs/*/work/` or `control.json`.

Records hold no secrets (API keys live in the environment, and hone-models reads them). An export test
plants a key in the environment and checks every exported file (AC-10).

## 12. The dashboard

### 12.1 Server

`hf.dashboard.serve(ws, host="127.0.0.1", port=8792, runner=True)` serves the dashboard with the
standard library (`ThreadingHTTPServer`).

- **Files.** `dashboard_page/` holds the static files (`index.html`, `app.css`, one `.js` per view) under
  `/`, and `/api/*` is JSON. Image files are served from `/files/<project>/images/<file>` and composed
  sheets from `/files/<project>/sheets/...`. Only `.png`, `.jpg`, `.jpeg` and `.webp` are served, with
  their image MIME type, `X-Content-Type-Options: nosniff` and a `Content-Security-Policy` that allows
  no script from files.
- **Paths.** Paths are percent-decoded and must resolve inside the workspace (404 otherwise).
- **Runner.** With `runner=True` a thread runs `Runner.recover()` once, then `run_forever`: the oldest
  queued run, one at a time.
- **Writes.** Every write goes through the `ProjectStore` methods under the project lock.
- **Binding.** The server binds to localhost only by default, and has no accounts.

### 12.2 API

| Method | Path | What |
|---|---|---|
| GET | `/api/workspace` | projects, settings, queue summary |
| GET | `/api/presets` | the catalogue (§5) |
| GET | `/api/models` | `Models.available` per kind, with installed state and observed latency |
| GET, POST | `/api/projects` | list, create |
| GET, PATCH | `/api/projects/{p}` | the project, its defaults |
| GET | `/api/projects/{p}/overview` | §12.5 |
| GET, POST | `/api/projects/{p}/subjects` | list (`?kind=`), add |
| GET, PATCH | `/api/projects/{p}/subjects/{id}` | the subject with its versions and images, edit |
| GET, POST | `/api/projects/{p}/images` | list with filters, import (multipart) |
| GET | `/api/projects/{p}/images/{id}` | the record and its uses |
| GET, POST | `/api/projects/{p}/scenes` | list, save (`"suggest": true`: the planner first adds the belongings the scene uses, §10.1) |
| GET, POST | `/api/projects/{p}/sequences` | list, save |
| GET, POST | `/api/projects/{p}/sheets` | list, save |
| POST | `/api/projects/{p}/sheets/{id}/compose` | compose, return the render URL |
| POST | `/api/projects/{p}/plan` | a plan for a request (no write) |
| POST | `/api/projects/{p}/runs` | submit |
| GET | `/api/runs?project=&scope=all` | runs, newest first |
| GET | `/api/runs/{project}/{run}` | `RunView` plus the latest events (`?since=<n>` for new lines only) |
| POST | `/api/runs/{project}/{run}/{action}` | `pause`, `cancel`, `resume`, `retry`, `rerun` (`{"output"}`), `pick` (`{"output", "image", "note"}`) |
| GET | `/api/projects/{p}/home` | the project page: the overview plus characters, world and scenes (change 0003) |
| GET | `/api/projects/{p}/characters` | characters with their hero and how many pack items are ready |
| GET | `/api/projects/{p}/characters/{id}` | the character page: packs, items (accepted image, status, run, output, candidates with evaluations), belongings, model sheet |
| POST | `/api/projects/{p}/characters/{id}/generate` | a `CharacterPacks` request (`packs`, `custom`, `redraw_hero`, `only_custom`, `profile`, `selection`) |
| POST | `/api/projects/{p}/characters/{id}/sheet` | compose (again) the character model sheet |
| GET | `/api/projects/{p}/world` | places and objects without an owner |
| POST | `/api/projects/{p}/world/generate` | `{"subject_ids"}` (default: those without an accepted hero) → one run each |
| POST | `/api/import` | `{"text", "format": "toml" \| "json"}`: create or update a project from a project file (change 0004) |
| GET | `/api/projects/{p}/file` | the project as a project file |
| GET, POST | `/api/projects/{p}/variations` | the variations and the active one; add one (`name`, `style_pack`, `direction`, `active`) |
| PATCH | `/api/projects/{p}/variations/{id}` | rename, restyle |
| POST | `/api/projects/{p}/variations/{id}/use` | make it the active variation |
| POST | `/api/projects/{p}/world/plan` | what Generate everything would make, with the estimate |
| POST | `/api/projects/{p}/world/generate-all` | queue it (`profile`, `rounds`) |
| GET | `/api/projects/{p}/objects/{id}` | an object's hero and views as a page section |
| GET | `/api/projects/{p}/subjects/{id}/compare` | its hero in every variation |
| POST | `/api/projects/{p}/cleanup` | `{"what": "unchosen" \| "variation", "variation", "dry_run"}` (change 0006) |
| GET | `/api/issues` | the standard issues for Generate again (change 0006) |
| POST | `/api/projects/{p}/exports` | `{"kind": "sheet" \| "pack" \| "sequence" \| "project", "id"}` → a download URL |

Errors are `{"error": message}` with 400 (an invalid request, with the plan errors), 404 or 409 (a run in
the wrong state).

### 12.3 Look: Studio Minimal

The tokens, type scale, layout grid, spacing, radii, borders, focus ring, breakpoints (a 72 px icon rail
below 1024 px, a bottom bar with "More" below 640 px), components and copy rules are exactly those of
the brief §16. They are written once as CSS custom properties in `app.css`, with a light theme and a
dark theme (`prefers-color-scheme` plus a manual switch in Settings). The fonts are Plus Jakarta Sans
and JetBrains Mono, loaded from Google Fonts when online, with system sans-serif and monospace as
fallbacks. Icons are inline SVG line icons, 20 px with a 1.5 px stroke. There is no emoji, gradient or
heavy shadow, and motion respects `prefers-reduced-motion`.

### 12.4 Views

- **Sidebar** (change 0003). Project, Characters, World, Scenes, Queue; then Presets, Models and
  Settings; a project selector. Create, Library ("All images") and Sheets stay reachable from the
  project page but leave the main path.
- **Top bar.** The current page's title and search over the project's subjects, images and scenes.

| View | Contents |
|---|---|
| Projects | list, search, create |
| Project | the brief (edit), the **variation switcher** (choose, add, edit; the top bar shows the active variation on every page), the **look guide** (edit), **Generate assets** (the world's places and objects), **Generate everything** (the whole world of the variation, with the estimate), the next step, the characters with their hero and progress, the world, the scenes, the activity |
| Characters | the characters' tiles; the **character page**: the hero beside the details (edit), **Generate assets** (every pack ticked, custom items per pack, quality and attempts), one section per pack with its item tiles ("Not made yet", "Queued", "Generating…", "Waiting for the hero", "Needs your choice", "Ready"), **Regenerate** and **Add** per pack, **Draw a new hero**; an item opens its candidates with their failed checks, **Use this one** and **Generate again** with a note; each belonging as a section with its hero and views (change 0005), the belongings list (add), the hero in every variation side by side, the model sheet (compose, export). The page refreshes while items are being made |
| World | places and shared objects: add, edit, **Generate assets** |
| Create | a settings column (task, description, subjects and references, presets, profile, auto judge and pick, rounds, candidates, stopping rule; an "Advanced" disclosure for model settings and the raw prompt) and a larger results area: the plan preview with counts and warnings before launch, then the live output grid. Primary action: Generate |
| Library | tabs Characters, Environments, Assets, Images (Images has filters for kind, subject, status, model and date). Tiles show the image, name, id, size and state. Selecting an item opens a side panel (description, references, states, results, history). Multi-select reveals Export, Tag and Delete, and Delete lists the uses first. This is the second mockup, whose scene builder panel is the Scenes view's side panel |
| Scenes | list; the scene definition (references show characters, places, objects and belongings, and which the planner suggested; **Suggest belongings** asks again) with its references and roles (exactly the inputs, in order), camera, pose, expression and state controls; drafts and finals side by side; actions Generate scene, Coverage, State pair, Sequence, Promote |
| Sheets | saved sheets, and a composer: source picker, layout, columns, labels, palette, page size and a live preview made by the server. Primary action: Compose sheet |
| Queue | a table (output or job, model and profile, size, round, status, progress, elapsed and estimate, actions) and the **run page**. The run page is the first mockup: the header (status, progress bar, elapsed, estimate range), the stage list (only applicable stages, with times), the current task (round x of y, candidates with their verdicts, job id and seed), the evaluation table of the current candidate (checks with scores, verdicts and findings), live activity (the events), the actions (Pause after current, Cancel, View settings) and completed outputs |
| Presets | categories with descriptions, usable before any project exists |
| Models | each role's available models: id, kind, local or hosted, installed, max references, features, observed latency (median, from events) |
| Settings | project defaults (profiles, selection, presets), connections (read-only: the hone-models registry files and environment variable names, never values), appearance (theme), usage |

### 12.5 Overview metrics

The four metrics are: images generated today, queued · running runs, the median render time today
(over the `generated` events), and GPU time today. A metric with no data shows "—" and a short reason,
never 0 when nothing was measured. Trend charts appear only with at least 7 days of real events.
Charts use real character, environment, asset and scene work only.

### 12.6 Live behaviour

- **Polling.** The page polls the run endpoint every 2 s while a run is live, and requests only new
  events (`since`). It updates the parts that changed in place, so open panels, scroll position and
  focus stay where they are.
- **Reloads.** A refresh or a server restart loses nothing, because the state is in the workspace.
- **Pages** (change 0004) render into their own container; a request or poll of a page the person left
  finds its container detached and stops, so it can never redraw over the current page.
- **Magnifier:** every image has a magnifier button that opens it in a full-window viewer (fit, or 1:1 on
  click) with a link to the file.

## 13. Modules

| Module | Responsibility |
|---|---|
| `workspace.py` | `Workspace`: paths, settings, the project list, the queue |
| `store.py` | `ProjectStore`: projects, subjects and versions, images, scenes, sequences, sheets |
| `_operations.py` | the `ProjectStore` methods that forward to the modules below (plans, runs, sheets, exports) |
| `_versions.py` | versioned records and the outdated-use check |
| `_files.py` | atomic JSON, `format_version` checks, sequential ids, the project lock |
| `records.py` | Pydantic records |
| `presets.py` + `data/presets/*.toml` | the catalogue, user packs, validation, versions |
| `profiles.py` | profiles, selection settings, the effective preset of each category |
| `requests.py` | request models, planned outputs, plans |
| `recipes.py`, `recipes_subjects.py`, `recipes_scenes.py`, `recipes_packs.py` + `data/character_packs.toml` | request → planned outputs: the shared parts; subject references and interactions; state pairs, sequences, grids and promotion; character packs |
| `project_file.py` | project files: parse, import by name, write back (change 0004) |
| `run_options.py`, `casting.py`, `issues.py` + `data/issues.toml`, `cleanup.py`, `produce_prompt.py` | approval checkpoints and the stronger judge; hero casting; standard issues; clean-up; how a producer writes a prompt (change 0006) |
| `variations.py`, `world_runs.py`, `recipes_objects.py` + `data/object_packs.toml`, `pose_library.py`, `_dashboard_world.py` | variations; whole-world runs and follow-ups; object packs; the pose library; their API routes (change 0005) |
| `characters.py` | the character page and cards, the world, world requests, the model sheet recipe, scene belonging suggestions |
| `references.py` | reference resolution, precedence, reduction, size limits |
| `planning.py` | `plan()`: models per output, counts, warnings, errors, preset versions, the estimate |
| `prompts.py`, `prompt_sections.py`, `dialects.py`, `data/prompting.toml` | prompts composed per dialect, mode and style; the planner prompt and its check (§8.8) |
| `judging.py` | judging profiles' checks, the judge prompt, verdict rules |
| `pick.py` | hone-select selection per output, and the output's resulting status |
| `produce.py`, `produce_refs.py`, `candidates.py` | §8.2: rounds, retries, stored candidates, events; an output's references at run time; one candidate's seed, inputs, result check and record |
| `engine.py` | the hone-flow workflow, `Runner`, `recover`, the requested sheet |
| `control.py` | submit, pause, cancel, resume, retry, rerun, manual pick |
| `runs.py` | run and output records, statuses, `RunView` |
| `events.py` | `events.jsonl`, estimates, usage |
| `sheets.py`, `sheets_model.py` | the compositor; the `character-model-sheet` layout |
| `exports.py` | zip exports |
| `ports.py` | the `Models` Protocol and its result types |
| `models.py` | `HoneModels` (hone-models) |
| `dashboard.py`, `_dashboard_api.py`, `_dashboard_work.py`, `_dashboard_data.py`, `_dashboard_characters.py`, `dashboard_page/` | server; API routes (workspace, projects, library; scenes, sheets, runs, exports; project home, characters, world); view data; the static page |
| `cli.py` | the CLI (extra `cli`) |
| `testing/` | `FakeModels`, `judge_answer`, `sample_workspace` |

Dependencies: pydantic, Pillow, hone-flow, hone-models and hone-select. The `cli` extra adds typer.

## 14. Guarantees (acceptance cases)

Each case has a test in `tests/e2e/` named `test_ac<N>_*`. AC-14 is in `tests/gpu/` and needs real
models.

| AC | Scenario | Expected |
|---|---|---|
| AC-1 | Fresh install, no project | `hf.presets()` lists all 14 categories with the shipped presets; every preset has a description, version and `subject_kinds`; no preset names a model; the defaults are cinematic-realism, neutral-studio and four-view-turnaround; a user pack is merged; a run records the preset versions; editing the catalogue after submission changes no saved project or run |
| AC-2 | Workspace and versions | create a project with 2 characters, an environment and 2 assets; edit a subject: version 2, version 1 still readable; ids `char_001`...; an imported image records its subject link; filters by kind, subject, status and model; a scene and a sheet on version 1 appear in `outdated()` after the edit; a new workspace object on the same folder reads the same data; an unknown `format_version` raises |
| AC-3 | Three-round automatic generation | `SubjectReferences` turnaround (5 outputs), 3 rounds × 1 candidate: plan counts 15 images and 15 judge calls; the run is `done`; 15 images kept; each output's `reason` explains the pick; 12 outputs × 3 × 2 plans 72; `stop_on_pass` stops early and the planned units shrink; a round-1 winner is not replaced by a weaker round-3 pass; a high-`overall` candidate failing a required check is not picked; no pass → `needs_review` with `best_available`; the batch and sequential strategies (sequential prompts carry the findings) |
| AC-4 | Scene references | a scene with Woman (identity), Kitchen (environment) and Cup (object) in a project that also has a Toothbrush: the plan's references are exactly those 3, ordered by precedence, with their versions; the fake model received exactly those files in that order; an editor with `max_references=2` drops the lowest role with a warning; a text-only editor warns "text only"; an oversize reference is reduced into `work/` and the original is unchanged |
| AC-5 | Sheets without models | compose four-view, expression grid, environment board and before-after sheets from stored images: zero model calls; byte-identical output on recomposition and in a new process; a revised recipe makes version 2 and leaves v1.png unchanged; labels, palette and heading render; a large page does not upscale images |
| AC-6 | Promotion | `refine` a draft: the editor received the draft first, then its references; the new image has `parent`; `regenerate` uses the scene definition; `upscale` without an upscaler is a plan error; a failed refine leaves the draft's status and record unchanged |
| AC-7 | Coverage, interactions, states, sequences, grids | coverage of 3 cameras gives 3 outputs with their own candidates and verdicts; an interaction links both subjects and is judged with contact checks; a state pair shares the seed and the after output takes the before image; a 4-frame sequence: every frame has the identity references and frames 2 to 4 also the previous frame, and retrying frame 2 leaves frame 1 alone; 3 outfits × 4 expressions × 2 lightings = 24 outputs, 72 planned images |
| AC-8 | Control, restart, progress and estimates | pause during round 2: the call in flight finishes, the run is `paused`; resume regenerates nothing already stored and completes; cancel → `canceled`, and resume raises `RunStateError`; a run whose process was killed (subprocess, SIGKILL) is recovered by `Runner.recover()` and completes without duplicate images; progress goes 0 → 1 and its denominator shrinks with `stop_on_pass`; the estimate is `null` before 3 observations and a range after |
| AC-9 | Unresolved failures stay visible | of 3 outputs, one never passes: the run is `needs_review`, `accepted` and `unresolved` are separate, the image is `best_available`, not picked; a hero in `needs_review` leaves its views `waiting` while an unrelated output completes; a manual pick → the output is `done` with `manual`, the image keeps its failing evaluation; `retry` then completes the views |
| AC-10 | Exports | a scene reference pack holds only the scene's references with `pack.json`; a sheet export holds the PNG, recipe and (with sources) originals; a sequence export holds numbered frames in order; a planted API key in the environment appears in no exported file |
| AC-11 | Technical retries | 2 transient failures, then success: the output succeeds, 2 `retry` events, no extra round; failures beyond the limit fail the output (`failed`, the error kept) while other outputs complete; `refused` is not retried; a judge that fails is recorded and blocks the auto pick for that candidate |
| AC-12 | Dashboard | the server on a free port: the page and its scripts load; every GET endpoint returns the documented shape for the sample workspace; submit, pause, resume, pick and compose through the API change the workspace; a path outside the workspace and a non-image file → 404; image responses carry `nosniff` and the CSP; the overview shows "—" metrics on an empty workspace, not 0 |
| AC-13 | Docs and examples | every `examples/*.py` runs and has the What / How / Why docstring and an entry in `examples/README.md`; every Python block in the README and `docs/` runs |
| AC-15 | Character packs | one `CharacterPacks` request makes the hero first and every other item from it; with the hero accepted, a second request draws none; packs left out stay out; custom items join their pack; every output and image records its pack and item |
| AC-16 | Reference look | every pack item is written on a white background, with empty hands except actions and objects; expressions are face close-ups; the judge asks `clean_background` and `no_props` |
| AC-17 | Belongings and world | an asset with an owner is listed with its character and becomes an action item; world assets have no owner; the world request covers those without an accepted image |
| AC-18 | Scene belongings | saving a scene with `suggest` asks the planner which belongings appear and adds them as suggested `object` references; a failing planner adds none |
| AC-19 | Model sheet | the character model sheet is composed from the accepted hero, turnaround and expressions with no model call; without them it is refused |
| AC-20 | Character API | the project home, the character page and its actions: generate, add an item, choose another candidate on an accepted item, compose the model sheet; scene save with suggestions |
| AC-21 | Prompts keep what was asked | in runs for several styles and every profile, every image of a whole character keeps its pose, expression, outfit, state or action, its white background and its empty hands (the full matrix over every style is a unit test) |
| AC-22 | Judge told what was asked | in a run, the judge prompt lists the request from the plan; back views get `faces_away`; other views carry no back-view wording; anatomy names hands and feet |
| AC-23 | Belongings first | actions wait for their belongings, made first in the same request when they have no image |
| AC-24 | Project files | `ws.import_file` creates a project with characters, belongings, world and scenes; importing again versions only what changed and keeps what the file leaves out; bad files are refused with the place of the error; CLI import and export |
| AC-25 | Variations | a new variation draws a new hero in its style; images stay in their variation; switching back plans no new hero |
| AC-26 | Look guide, must, never | the look guide is in heroes and outfits, not expressions; must and never reach prompts, judge and negatives; small marks are warned about |
| AC-27 | Pose library | pose images depend on a mannequin made first; another character reuses it |
| AC-28 | Object packs | an object's hero and five views; belongings before actions, shown as character-page sections |
| AC-29 | Whole-world runs | an estimate; one run per subject; scenes queued after the last character |
| AC-30 | Approvals | `base` waits after the base group and continues on approval; `each` after each pack; `auto` never |
| AC-31 | Hero casting | candidates from distinct readings; seeds only when the planner fails |
| AC-32 | Standard issues | fixes in the prompt, checks in the judging; unknown issues refused |
| AC-33 | Judge options | the stronger judge where asked; a plan error without one |
| AC-34 | Clean-up | unchosen candidates deleted, those in use kept and counted; a variation deleted only when none of its images is in use; the active variation refused |
| AC-14 (real model) | One `SubjectReferences` hero with the draft profile on the GPU (`scripts/gpu-lock.sh`) | an image is generated and judged by the real models; the run completes as `done` or `needs_review`; the models are unloaded afterwards |

## 15. Known limits (0.1.0)

- A remote job in flight when the process died cannot be reattached: hone-models has no "fetch job by
  id". The attempt is recorded as `unknown` in the events and generated again. Closing this needs a
  hone-models change.
- One process writes to a project at a time (the dashboard, or a script, not both while a run is
  running). A second writer is detected by the hone-flow run lease for runs, not for project edits.
- The judge is a single vision LLM. Its scores are comparative signals, and verdicts from small local
  judges are weak, which is why every verdict is shown and can be overridden.
- Image generation progress is indeterminate (no step progress from hone-models).
- No preset ships with an example image.
