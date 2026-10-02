# hone-frame

[![CI](https://github.com/honeworks/hone-frame/actions/workflows/ci.yml/badge.svg)](https://github.com/honeworks/hone-frame/actions/workflows/ci.yml)

**Hone Frame.** Purpose: to be defined in [design/changes/0001](design/changes/0001-initial-design.md).

Part of **[honeworks](https://github.com/honeworks)**: small, standalone tools for reliable generative-AI
workflows. Works on its own; works better with its siblings.

This repository is a working skeleton: packaging, tests, CI and the design process are in place; the
package has no features yet.

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
