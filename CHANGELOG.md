# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Why the design changed is recorded in
[design/changes/](design/changes/).

## [Unreleased]

### Added
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
