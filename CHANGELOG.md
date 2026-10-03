# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Why the design changed is recorded in
[design/changes/](design/changes/).

## [Unreleased]

### Added
- Choices when generation starts (change 0006): run automatically, approve the base images first, or
  approve each step; a stronger judge for base images or for everything; hero candidates that really
  differ (drawn from distinct readings of the description).
- "Generate again" offers 20 standard issues to tick (wrong pose, malformed feet, wrong culture or period,
  background not white...), each fixing the next prompt and judged.
- Desktop notifications when a run waits for approval, needs a choice or is done; a Clean up action for
  unchosen candidates and dropped variations.
- Variations (change 0005): one world, several styles; every image belongs to a variation, each with its
  own heroes; a switcher on the project page; compare a character's hero across variations.
- The world's look guide (culture, period, costume, materials in plain sentences) in every prompt that
  draws something new; per-subject Always shown / Never shown lists checked by the judge.
- Poses from a pose library: a wooden mannequin in each pose, drawn once per project, as the pose
  reference (kneeling, running and sitting now come out right).
- Belongings and world objects get a hero and five views; belongings are made before the actions that
  use them and appear as sections of the character page.
- Generate everything: the whole world of a variation in one go, with an estimate; scenes follow.
- A warning for small marks (beauty marks, moles, tattoos) that drift between images.
- Project files (change 0004): a whole project (characters with states and belongings, places, objects,
  scenes) in one TOML or JSON file, imported from the dashboard or `hone-frame import`, again after edits
  (only what changed gets a new version), and downloaded back with **Download as file** /
  `hone-frame export-file`. Example: `examples/projects/rostam-and-sohrab.toml`.
- A magnifier on every image in the dashboard.

### Fixed
- The Z-Image planner no longer copies "the whole figure from head to feet" into place and object
  prompts from its rules' example (D-041).
- A view of a place or an object no longer asks to keep a face, hair and clothes, which put a man into
  a fortress's detail view; "faces away" is said only of characters (D-040).
- Places came out full of people and objects with a warrior holding them when the look guide described
  costumes; places are now empty, heroes alone, objects alone, and the judge checks each. A queued run
  that is canceled now shows as canceled.
- Pose, expression, outfit, state, action, gaze and "Generate again" notes were cut from prompts to fit a
  model's word budget (most poses came out standing); they are now never dropped, and neither are the
  framing and the style. The planner's rewrite must keep them, and the judge is told what was asked.
- The judge failed good front views with "not from the back"; back views now have their own check, and
  the anatomy check names hands and feet. Side views ask for the feet to turn with the body.
- Actions were drawn before (or without) their belongings; belongings are now made first.
- Opening another page while a character was generating jumped back to the character a few seconds
  later.
- Character first (change 0003): one **Generate assets** makes a whole character from one hero: the
  turnaround, eight face close-ups, six poses, outfits, states, its belongings and actions with them,
  each on a plain white background with empty hands (checked by the judge); any pack can be made again
  or added to, and any candidate chosen. Belongings (assets with an `owner`) and world assets; scenes
  get the belongings they need from the planner; the character model sheet. The dashboard now follows
  the work: Project, Characters, World, Scenes, Queue.
- Prompts are written per model (dialects: z-image, FLUX.2 klein, Qwen-Image-Edit, generic), per task
  (a new picture, another view of the same subject, a composed scene) and per style; the planner's
  rewrite is checked against the dialect's rules (change 0002).
- "Generate again" for one output on the run page (also "None of these" when choosing a candidate):
  a new run for that output with a note added to its prompt and, optionally, another profile and number
  of rounds; the old output becomes "Replaced" and keeps its images.
- The repository skeleton: packaging, quality gates (`scripts/check.sh`), CI, the design folder and the
  contributor workflow.
- The first-product design: [0001](design/changes/0001-initial-design.md), `design/current.md`, the
  owner's brief in `design/history/`.
- The workspace: projects, versioned characters, environments and assets, images with full records,
  scenes, sequences and sheets as versioned JSON files.
- The preset catalogue (14 categories), usable before any project, with user packs.
- Requests and plans: subject references, scene shots, coverage, interactions, state pairs, sequences,
  variation grids and promotion, with the exact references, models and counts before launch.
- Generation on hone-flow runs: rounds of candidates, vision judging with required checks, picks through
  hone-select, technical retries, dependencies on accepted references, pause / cancel / resume / retry /
  rerun / manual pick, recovery after a crash, events, progress, estimates from observed durations, usage.
- The deterministic sheet compositor and zip exports (sheets, reference packs, sequences, projects).
- The Studio Minimal dashboard (`hone-frame dashboard`) and the CLI (extra `cli`).
- `hone_frame.testing.FakeModels` and `sample_workspace`; docs and runnable examples.
- hone-frame's own hone-models entries for the reference-editing models (flux.2-klein-4b,
  qwen-image-edit-2511) with their workflows, and `<home>/hone-models.toml` per workspace: hone-frame no
  longer depends on the folder it starts in.
- The default workspace is `~/hone-frame` (was `./hone-frame`), so the dashboard and the CLI find the
  same work from any folder; `HONE_FRAME_HOME` or `--home` still choose another. Work made under the old
  default: move the `./hone-frame` folder to `~/hone-frame`, or point `HONE_FRAME_HOME` at it.

### Fixed
- Judged candidates ended in "Needs review" with "the judge did not answer this check": the judge named
  every check "JudgeCheck". The judge's answer now has one named field per check. Back views are judged
  on build, hair and outfit (`identity_from_behind`) instead of a face they cannot show.
- Reference images use neutral studio light on a plain background, whatever the style pack's mood
  lighting, unless a lighting is chosen.
- The run page of a run that has not started a stage yet no longer drops the connection (the browser
  showed "NetworkError" right after Generate); any unexpected API error is now a JSON 500 with its
  message, and the run page retries a failed poll instead of stopping.
- Editing a subject's states with an unknown kind dropped the connection ("network error"); invalid input
  is now a 400 that names the field. The subject editor has the kind's fields (appearance, build,
  distinguishing features, default outfit for a character; anchors, materials... for places and objects)
  and one row per state with its name, kind and description. A list field is edited one item per line;
  a field left untouched keeps its stored value and type.
