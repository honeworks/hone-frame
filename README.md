# hone-frame

[![CI](https://github.com/honeworks/hone-frame/actions/workflows/ci.yml/badge.svg)](https://github.com/honeworks/hone-frame/actions/workflows/ci.yml)

**Hone Frame: a project-based visual production workspace.** Define a project's characters,
environments and assets once; generate, judge and pick their images unattended; compose reference sheets
in Python without another model call; build scenes from exactly the references you chose; and watch it
all happen in a local dashboard.

Part of **[honeworks](https://github.com/honeworks)**: small, standalone tools for reliable generative-AI
workflows. Works on its own; works better with its siblings.

- **Images are the unit, sheets are compositions.** Every candidate is kept with a full record; a sheet
  is a saved layout over exact image ids, composed deterministically.
- **References with a purpose.** A scene names its subjects and gives each reference a role (identity,
  outfit, object, pose...); nothing unselected is attached, and the exact inputs are shown first.
- **Unattended rounds, honest verdicts.** Rounds of generation, a vision judge with required checks, and a
  pick by [hone-select](https://github.com/honeworks/hone-select); "nothing passed" stays visible.
- **Runs you can trust.** Real stages, counts and estimates; pause, resume and restart without losing
  work; every run is a [hone-flow](https://github.com/honeworks/hone-flow) run folder.
- **One model layer.** Every model call goes through [hone-models](https://github.com/honeworks/hone-models):
  local ComfyUI and Ollama models and hosted APIs as equals.

The design is in [design/current.md](design/current.md); the first product is being built in milestones
(see [0001](design/changes/0001-initial-design.md)).

## Install

Not on PyPI yet. From GitHub:

```bash
uv add "hone-frame @ git+https://github.com/honeworks/hone-frame"
```

## Documentation

User docs: [docs/](docs/index.md). The design and its history: [design/](design/README.md).

## Design and contributing

How the package is designed and why: [design/](design/README.md). How to set up, the rules the code
follows and how the design changes: [CONTRIBUTING.md](CONTRIBUTING.md).

## How this was built

hone-frame is specified by a human and built by AI coding agents (Claude) working against written
specifications and acceptance tests; a human reviews the decisions they make, and commits written with
AI carry a `Co-Authored-By` line. Every design change, with what was found, what was decided and why, is
in [design/changes/](https://github.com/honeworks/hone-frame/tree/main/design/changes/); the smaller
implementation choices are in [design/decisions.md](https://github.com/honeworks/hone-frame/blob/main/design/decisions.md).

## Status

Planning, version 0.0.0 (unreleased). Nothing is public API yet; changes are listed in the
[CHANGELOG](https://github.com/honeworks/hone-frame/blob/main/CHANGELOG.md).

## License

Apache-2.0 ([LICENSE](https://github.com/honeworks/hone-frame/blob/main/LICENSE)). Copyright 2026 Bahman Shadmehr.
