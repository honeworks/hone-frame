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

