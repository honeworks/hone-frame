# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Why the design changed is recorded in
[design/changes/](design/changes/).

## [Unreleased]

### Added
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
