# Implementation decisions

Choices too small for a change record: places where the design was silent or ambiguous and the
implementation had to pick. They are numbered in the order they were made, and code comments refer to
them by number. Entries marked **awaiting owner review** are in effect but not yet confirmed by the
owner.

## Awaiting owner review

These entries are in effect but not yet confirmed by the owner. When the owner decides, the entry's
**Status:** line records the outcome.

| Entry | Question for the owner |
|---|---|
| [D-005](#d-005-the-mockups-show-the-look-the-brief-decides-the-content--2026-10-02) | Accept dropping the mockups' "Professional Plan" label and sample scores, and moving the project selector into the sidebar footer? |
| [D-006](#d-006-the-shipped-profiles-name-local-models--2026-10-02) | Accept the default models of the Draft, Standard and Final profiles? |

## D-001: hone-flow, hone-models and hone-select are core dependencies  (2026-10-02)

- **Question:** The family rule says a package's core never imports another honeworks package (AGENTS.md
  rule 2 in the siblings). hone-frame is a product whose runs, model calls and picks are those packages.
- **Options:**
  - (a) Ports and optional extras, as in the siblings. hone-frame would be useless without them, and each
    would be a copy of the sibling's API.
  - (b) Core dependencies.
- **Choice:** (b), by the owner's instruction ("The base of this project should use hone-flow,
  hone-models"). hone-select is added because brief §13 gives selection to it. The published metadata
  says `hone-flow>=0.1`, `hone-models>=0.1` and `hone-select>=0.1`. For development, `[tool.uv.sources]`
  takes them from their GitHub repositories (`branch = "main"`), the same as the siblings do, until they
  are on PyPI. Model calls still go through one small port (`Models`, design §7.2), so tests run without
  models.
- **Reason:** the owner's instruction, and there is nothing to gain from an abstraction layer over
  sibling packages that are always installed.

## D-002: the wheel smoke test installs the siblings from GitHub first  (2026-10-02)

- **Question:** `scripts/check.sh` and CI install the built wheel into a clean environment. pip cannot
  find `hone-flow` on PyPI yet.
- **Choice:** before installing the wheel, both install every `[tool.uv.sources]` git source as
  `<name> @ git+<url>`. Once the siblings are on PyPI, the sources go and the step does nothing.
- **Reason:** the smoke test still checks what users get: the wheel plus its dependencies, nothing from
  the working tree.

## D-003: a workspace of JSON files with readable sequential ids  (2026-10-02)

- **Question:** The brief's mockups show ids like `char_001` and `env_001`. Should the store be a
  database?
- **Choice:**
  - JSON files and image files under the workspace folder, written atomically. There is no database,
    like hone-flow.
  - Ids are `<prefix>_<n>`, numbered per project and kind (`char`, `env`, `obj`, `scn`, `seq`, `sht`,
    `img`), and the next number comes from the existing files.
  - Run ids use hone-flow's time-sortable form.
- **Reason:** a project can be read, copied and backed up without the package. Sequential ids are what
  people see in the mockups, and they are deterministic in tests.

## D-004: one writer per project, with a lock  (2026-10-02)

- **Question:** The dashboard's request threads and the runner thread write the same project files.
- **Choice:** every write takes a per-project lock: a `threading.RLock` within the process, plus an
  `fcntl` lock on `projects/<id>/.lock` across processes. Reads take no lock, and readers always see a
  whole file (writes use `os.replace`).
- **Reason:** the simplest thing that prevents lost updates for the sizes involved (a person and one
  runner).

## D-005: the mockups show the look, the brief decides the content  (2026-10-02)

- **Question:** The two mockups show a "Professional Plan" account label, a plan-style avatar and sample
  scores and thresholds. The brief says the dashboard implies no hosted billing system and shows no
  invented numbers.
- **Choice:**
  - The layout, spacing and components follow the mockups.
  - The sidebar footer shows the current project (as in the second mockup) instead of an account plan.
  - Scores appear only from real evaluations, with the verdict word and the finding beside each. The
    mockup's "Threshold" column is left out: a verdict is the judge's per check (a profile's `min_score`
    turns a low-scoring pass into a fail), so a threshold column would suggest a rule that is not there.
  - In the run page's current task, one card per round (and candidate) shows its picture and verdict,
    as in the mockup.
- **Reason:** the brief is the specification. The mockups illustrate it.
- **Status:** **awaiting owner review**.

## D-006: the shipped profiles name local models  (2026-10-02)

- **Question:** Which hone-models ids do Draft, Standard and Final use?
- **Choice:**
  - **Draft:** `z-image-turbo` without references and `flux.2-klein-4b` with references.
  - **Standard:** `flux.2-klein-4b`.
  - **Final:** `qwen-image-edit-2511`.
  - **Planner and judge (all three):** `gemma4-12b` as the planner and `qwen2.5vl-7b` as the judge, both
    with thinking off.

  All are local and in hone-models' catalogue. A missing or uninstalled model shows as unavailable in
  Models, and the plan says which role cannot run.
- **Reason:** no preset may force a paid provider (brief §12). These are the models the playground
  pipelines proved on the 8 GB GPU. Thinking stays off for planners and judges, because a thinking
  planner kept the first picture waiting for ten minutes.
- **Status:** **awaiting owner review**. The 7B judge is known to be lenient. A stronger judge
  (`qwen3.8-27b`) can be set per project.

## D-007: pause and cancel stop at a model-call boundary through hone-flow's failure path  (2026-10-02)

- **Question:** hone-flow has no pause or cancel.
- **Choice:**
  - `produce` checks `control.json` before every model call and raises `StopRequested`. hone-flow
    records that item as failed with the message, and the other items stop at their first boundary the
    same way.
  - hone-frame derives `paused` or `canceled` from the control file, so the hone-flow status `failed` is
    never shown for a stop.
  - Resume is hone-flow's `resume()`, and stored candidates are skipped (design §8.2).
- **Reason:** it uses hone-flow's own resume semantics, and a stop never discards committed work.

## D-008: dependencies wait through a failed item, not a gate  (2026-10-02)

- **Question:** An output that needs an accepted reference (a view needs the hero) can be reached before
  that reference is accepted (the hero needs review).
- **Options:**
  - (a) A hone-flow gate. It stops the whole run, and gates review a step's output, not another item's.
  - (b) Raise `WaitingForReference`, so hone-flow marks the item failed and hone-frame shows `waiting`.
- **Choice:** (b). Items run in plan order (dependencies first) in hone-flow's breadth-first order. A
  later `retry` reruns the waiting items.
- **Reason:** unrelated outputs continue, as the brief asks, and the mechanism is the same as the stop
  in D-007.

## D-009: estimates need 3 observations per model and size  (2026-10-02)

- **Choice:**
  - Durations come from `generated` and `judged` events workspace-wide, using the last 50 per
    `(model, size)`.
  - The range is the 25th to 75th percentile times the remaining units.
  - With fewer than 3 durations for a needed key, the estimate is `null` ("Estimating").
- **Reason:** an interquartile range is honest about variance and stable with few samples. Below 3
  samples, a percentile is a guess.

## D-010: the dashboard is the standard-library server and static files  (2026-10-02)

- **Choice:** `ThreadingHTTPServer` with a JSON API and hand-written HTML, CSS and JavaScript modules.
  There is no framework and no build step. This is the approach of hone-select's rebuilt dashboard
  (hone-select 0013), and it includes that work's fixes:
  - views render from data;
  - live updates change parts in place;
  - paths are percent-decoded and confined to the workspace;
  - user files are never served as script.
- **Reason:** a local, single-user page needs no framework, and the package stays installable with pip
  alone.

## D-011: a rerun of one output is a new run  (2026-10-02)

- **Question:** hone-flow's resume never reruns a `done` item, and a fork makes a new run id anyway.
- **Choice:** `rerun(run, output)` submits a new run with that output's planned definition and
  `rerun_of`. The old run and its images are unchanged.
- **Reason:** every run stays a faithful record of what it did, and the new candidates are easy to
  compare with the old ones.

## D-012: style-src allows inline styles in the dashboard  (2026-10-02)

- **Question:** the page sets a few inline `style` attributes (progress widths, layout tweaks); a strict
  `style-src 'self'` blocks them.
- **Choice:** `style-src 'self' 'unsafe-inline'` plus Google Fonts; `script-src 'self'` stays strict, and
  user files are served with `default-src 'none'; sandbox`.
- **Reason:** inline styles carry no data from the workspace (text goes through text nodes), so the risk
  that matters, script, stays closed.

## D-013: subject tabs show the subject's own images; scenes are in Images and Scenes  (2026-10-02)

- **Choice:** a subject's section in the Library lists images whose only subject it is; images of several
  subjects (scenes, interactions) are under Images (kind "scene") and on their scene.
- **Reason:** a scene shot is not a reference image of each character in it.

## D-014: HoneModels starts a local server that is not running and keeps it  (2026-10-02)

- **Question:** hone-models' ComfyUI provider requires a running server (`mk.session("comfyui")` starts
  one from `HONE_COMFYUI_START`); a run makes many image calls.
- **Choice:** on the first call to an Ollama or ComfyUI model, `HoneModels` enters `mk.session(provider)`
  and keeps it until the process ends (`close()`, or at exit). A server that was already running is used
  and never stopped. Models are still freed after every call by hone-models.
- **Reason:** starting ComfyUI once per call would cost tens of seconds per image; the dashboard is a
  long-running process anyway.

## D-015: Pillow is a core dependency  (2026-10-02)

- **Question:** sheets, reference reduction, image import (size, format) and the fakes need an image
  library; should it be an extra?
- **Options:** (a) an extra `sheets`; (b) a core dependency.
- **Choice:** (b) `pillow>=10.1` (10.1 brings `ImageFont.load_default(size)`, the bundled font that makes
  composed sheets byte-identical across machines, design §11.2).
- **Reason:** every project imports images and every scene reduces its references; without Pillow the
  package could not open a single image, so an extra would only move the error later. Pillow ships
  wheels for every supported platform and has no native dependency to install.

## D-016: hone-frame ships its own hone-models entries  (2026-10-02)

- **Question:** the reference-editing models (flux.2-klein-4b, qwen-image-edit-2511) are in hone-models'
  catalog without a ComfyUI workflow; their proven workflows lived only in another project's
  `hone-models.toml`, so hone-frame worked only when started in that project's folder.
- **Choice:** `src/hone_frame/data/hone-models.toml` and `data/workflows/` hold those entries (plus
  `flux.2-klein-4b-text`). `HoneModels` loads hone-models' registry with this file and then
  `<home>/hone-models.toml` (when it exists) as explicit paths, so the entries do not depend on the
  working folder, and a workspace can still override any of them. Every call passes that registry to
  `mk.image` / `mk.text`. They are still hone-models entries, called only through hone-models.
- **Reason:** the owner wants hone-frame fully independent of other projects. The entries move into
  hone-models' catalog once it ships these workflows; then this file shrinks to nothing.

## D-017: flux.2-klein-4b gets every reference slot filled  (2026-10-02)

- **Question:** the flux.2-klein-4b workflow has two reference slots. With one reference, hone-models
  removes the second `LoadImage` and its links, but the `VAEEncode` behind it stays without pixels and
  ComfyUI refuses the graph (seen on the real model: "node 14 (VAEEncode), input 'pixels': Required input
  is missing").
- **Choice:** `HoneModels` repeats the last reference into the free slots for the models in
  `models.FILL_SLOTS` (only flux.2-klein-4b). The same picture twice is a stronger hint for that
  reference and changes nothing else; the record still lists the references that were chosen.
- **Reason:** the real fix belongs to hone-models (drop an unused slot's whole chain up to an optional
  input); until then this keeps the editor usable with one reference.

## D-018: the default workspace is `~/hone-frame`  (2026-10-02)

- **Question:** the first default was `./hone-frame`, relative to the folder the process starts in, so the
  dashboard started from another folder showed an empty workspace, and one started inside the repository
  wrote images into it.
- **Choice:** `HONE_FRAME_HOME` when set, else `~/hone-frame`, by the owner's choice. `--home` and
  `hf.Workspace(path)` still pick any folder.
- **Reason:** one place for a person's work, whatever folder a command runs in.

## D-019: "Generate again" replaces one output with a new run  (2026-10-02)

- **Question:** when every candidate of one output is bad (a back view drawn from the front), a person
  needs to ask for that output again, with a reason, without redoing the rest of the run.
- **Choice:** the run page's "Generate again" (also offered from "Choose a candidate" as "None of
  these") calls `rerun(run, output, note=, profile=, selection=)`. The note is added to the output's
  prompt; a different profile picks that profile's model for the output (Final's Qwen-Image-Edit has the
  camera-angle LoRA, the better choice for side and back views). The old output gets the new status
  `replaced` with `replaced_by`, so its run no longer waits for review, while its candidates and their
  findings stay in the library.
- **Reason:** the rest of the run is fine and stays accepted; each attempt is still its own faithful
  record (D-011).

## D-020: the judge answers one named field per check; rear views are judged from behind  (2026-10-02)

- **Question:** on the owner's first character, every Back candidate ended in "Needs review" with "the
  judge did not answer this check" for almost every check. The call records show qwen2.5vl-7b named
  every check "JudgeCheck" (the title of the list item's schema), so no answer matched a check, although
  it had passed them all. The identity check also asked for a face that a back view does not show.
- **Choice:** the schema sent to the judge has `checks` as an object with one required key per check
  name (`judging.answer_schema`); with Ollama's constrained output the judge cannot rename or drop one.
  Outputs whose camera is `rear` get the flag `rear`; the `character-identity` profile (version 2) then
  asks `identity_from_behind` instead of `identity`, and its `view` question says what a rear view must
  show.
- **Reason:** the failure was in reading the answer, not in the images. Re-judged with the new schema,
  three of the four real Back candidates pass every check, and the one that shows a face does not.
- **Note:** the same re-judge passed `view` for the candidate that faces the camera; the 7B judge is
  still lenient (D-006).

## D-021: reference images use neutral studio light  (2026-10-02)

- **Choice:** subject reference outputs use the `neutral-studio` lighting (even light, plain grey
  background), not the style pack's mood lighting, unless the request or the project chose a lighting.
  Scenes keep the pack's lighting.
- **Reason:** brief §12 ("neutral reference lighting"); the owner's first Rostam turnaround was drawn
  in a colonnaded hall with dramatic light because the Historical epic pack sets `dramatic-side`.

## D-022: camera presets and style packs moved to version 2  (2026-10-02)

- **Choice:** the data added by change 0002 (camera `view`, `faces_away`, `azimuth`, `elevation`,
  `distance`; style `short` and per-dialect wording) bumps every camera preset and style pack to version
  2, so runs record that their prompts were written with the new data.

## D-023: the model's prompt guide is shown, not sent to the planner  (2026-10-02)

- **Choice:** since change 0002 the planner gets the dialect's rules instead of the one-line prompt guide
  from hone-models' registry. `ModelInfo.prompt_guide` stays: the Models view shows it beside each model,
  and it is where a person reads what a new model wants before writing a dialect for it.

## D-024: a white background is its own prompt piece, not the lighting  (2026-10-02)

- **Choice:** change 0003's white background is the `background` input (`recipes.WHITE`) and a required
  prompt section, set for character and object references only; `neutral-studio` (version 2) says only
  "even soft neutral studio lighting, no cast shadows". Empty hands are the required `props` section.
- **Reason:** the lighting preset also lit places, which must keep their scenery, and a lighting choice
  could otherwise silently remove the white background.

## D-025: older images join packs by their label  (2026-10-02)

- **Choice:** an image or output without `pack` is placed in the pack whose default item has the same
  label ("Hero", "Front", "Back", "Happy"...); the latest accepted one wins.
- **Reason:** characters made before 0003 (Rostam) keep their accepted hero and turnaround, so a new
  `CharacterPacks` request reuses that hero instead of drawing another.

## D-026: belongings are suggested when a scene is created or when asked  (2026-10-02)

- **Choice:** the dashboard sends `suggest` when a scene is saved for the first time and from **Suggest
  belongings**; later saves keep the references as they are.
- **Reason:** suggesting on every save would put back a belonging the person removed.

## D-027: "Add" makes only the new item  (2026-10-02)

- **Choice:** `CharacterPacks.only_custom` plans only the `custom` items (plus the hero when none is
  accepted); the hero is drawn only when none is accepted or `redraw_hero` is set, even if `packs`
  names `hero`.
- **Reason:** "give me the hero in party clothing" must not remake the pack's other images, and ticking
  every pack must never replace an accepted hero by accident.

## D-028: own items for a pack that was not chosen are refused  (2026-10-02)

- **Choice:** a `CharacterPacks` request whose `custom` names a pack missing from `packs` is an
  `InvalidRequest` naming those packs, instead of dropping the items.
- **Reason:** silently making nothing for text the person typed is worse than asking them to tick the
  pack (the dashboard adds the pack itself when its box has text).

## D-029: the judge stays Qwen2.5-VL 7B  (2026-10-03)

- **Choice:** the draft, standard and final profiles keep `qwen2.5vl-7b` as the judge. Qwen3-VL 8B was
  tried on the owner's Rostam side view (one foot turned backwards): with a whole-image question, a
  feet-only question and a crop of the feet, both models passed it; Qwen3-VL also answered with thinking
  text only on some calls. Gemma 4 and Qwen 3.6 builds here take no images.
- **Reason:** no local vision model that fits the 8 GB GPU detects foot direction reliably. The defence is
  prevention in the prompt (side and three-quarter views ask for the feet to turn with the body), a
  judge told what was asked, and the person's eye (the magnifier, **Use this one**, **Generate again**).
  A hosted judge (for example `gpt-4.1-mini`, with `OPENAI_API_KEY`) can be set per project.

## D-030: project files are imported by name and never delete  (2026-10-03)

- **Choice:** a project file matches the project, subjects (by kind and name) and scenes by name;
  missing ones are created, changed ones get a new version, the rest are left alone, and nothing absent
  from the file is deleted. Write-back is JSON (`project_file`), since the standard library reads TOML
  but does not write it.
- **Reason:** the owner tests by editing one file and importing it again; deleting what a file leaves out
  would lose images and runs made since.

## D-031: variations hold images, the world holds what things are  (2026-10-03)

- **Choice:** subjects, scenes and the look guide belong to the project; style, style notes and every
  generated image belong to a variation. A project made before change 0005 has one implicit variation,
  `main`, and its visual direction becomes its look guide.
- **Reason:** the owner wants to try styles before choosing one, without typing the world again; a
  Sasanian warrior is Sasanian in every style.

## D-032: mannequins as pose references, drawn once per project  (2026-10-03)

- **Choice:** pose items take a plain wooden mannequin in the pose as a `pose` reference. Mannequins are
  made with one fixed wording (no planner), judged by `pose-reference`, belong to no variation and are
  reused by every character of the project.
- **Reason:** with the mannequin FLUX.2 klein drew kneeling, running and sitting correctly in a realistic
  and a 2D style; with text alone it kept the standing pose of the hero.

## D-033: belongings are made before actions, as whole objects  (2026-10-03)

- **Choice:** a belonging without an accepted hero is made (hero and five views) in the character's
  request before its actions; it is shown as a section of the character page, not on a page of its own.
  World objects use the same object packs and show their sections on the World page.
- **Reason:** the owner never saw the spear before the action that used it, and wants belongings handled
  like the character's own packs.

## D-034: "never" goes to the judge and the negative, not the prompt  (2026-10-03)

- **Choice:** a subject's never list becomes a required judge check and part of the negative prompt of
  models that take one; it is never written into the positive prompt.
- **Reason:** "no cape" in a positive prompt tends to draw a cape; z-image and FLUX.2 have no negative,
  so the judge is what enforces it there.

## D-035: FLUX.2 klein text-to-image budget 150 words  (2026-10-03)

- **Choice:** the FLUX.2 klein `generate` budget rises from 120 to 150 words.
- **Reason:** a hero drawn from words now carries the look guide as well as the description; the model's
  text encoder reads long prompts, and the guides' range is 50 to 150 words.

## D-036: approval is a planned pause  (2026-10-03)

- **Choice:** an approval mode is a list of checkpoint outputs in the plan; after one the producer sets
  the run's control to `approve` with a message, so the run stops before the next output exactly as a
  pause does; approving is resuming. Base outputs are planned first so `base` asks once.
- **Reason:** it reuses the tested pause and resume path and keeps every image; nothing new runs while
  the person looks.

## D-037: casting varies what the description leaves open  (2026-10-03)

- **Choice:** hero candidates come from planner-written readings that keep every stated fact and vary
  only what is unstated; the readings are stored on the output so a resumed run uses the same ones.
- **Reason:** z-image-turbo is distilled and gives near-copies for one prompt whatever the seed.

## D-038: no final pass and no grouping by model yet  (2026-10-03)

- **Choice:** both are documented in 0006 and not built: no upscaler is installed (SeedVR2 3B is 3.9 GB
  with ~15 GB free), and grouping by model needs the base group made and judged first, which approvals
  now provide.
- **Reason:** the owner asked for them as options, not defaults; neither may slow down development work.

## D-039: nobody else in a reference image; the look guide only where people are drawn  (2026-10-03)

- **Choice:** a place's reference images are asked to be empty (`empty_place`, judged `no_people`), a
  character's hero shows only that character (`solo`, judged where the prompt asks it: heroes and other
  pictures drawn anew, not edits of the same person), and every object reference (object packs and
  `SubjectReferences` of an object) stays alone (`object_alone`); and the look guide goes only into prompts that draw people (characters, scenes),
  not into a place's or an object's own images.
- **Reason:** in the first overnight run, a look guide that describes warriors' costumes turned the White
  Fortress and the palace hall into crowds of warriors and nobles, which the judge passed. With these
  changes the same places came out empty, and the hero alone on white.

