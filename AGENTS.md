# AGENTS.md: hone-frame

A brief for AI coding tools (Claude Code, Codex, Cursor and others) helping with this repository.
People follow the same rules; they are in [CONTRIBUTING.md](CONTRIBUTING.md).

## What this is

`hone-frame` (import `hone_frame`) is Hone Frame, a project-based visual production workspace. You define
characters, environments and assets; generate, judge and pick their images unattended; compose sheets in
Python without model calls; build scenes from exactly the references chosen; and watch it all in a local
dashboard. Model calls go through hone-models, runs through hone-flow, picks through hone-select. Read
[design/current.md](design/current.md) before changing behaviour; it is the design as it stands, and its
§14 lists the guarantees the tests check. Why the design looks like this:
[design/changes/](design/changes/) and [design/decisions.md](design/decisions.md).

## Commands

```bash
uv sync --all-extras                 # install everything (dev included)
scripts/check.sh                     # all quality gates: lint, format, types, tests + coverage, build, wheel smoke test
uv run pytest                        # default suite (fast, offline, deterministic)
uv run pytest tests/e2e              # acceptance cases only
scripts/gpu-lock.sh uv run pytest -m gpu   # real-model tests, under the machine-wide GPU lock
uv run ruff check . && uv run ruff format .
uv run pyright                       # strict for src/
```

## Layout

```text
src/hone_frame/
  workspace.py  store.py  records.py     the workspace folder, project store, records (format_version "1")
  _files.py  _versions.py  _operations.py  atomic JSON and ids, versioned records, forwarded store methods
  presets.py  data/presets/*.toml        the preset catalogue
  profiles.py  requests.py               profiles, requests, plans
  recipes.py  recipes_subjects.py  recipes_scenes.py   request -> planned outputs
  references.py  planning.py  prompts.py reference roles and limits, plans, prompts
  judging.py  pick.py                    judging profiles and verdicts, hone-select picks
  engine.py  control.py  runs.py        the hone-flow workflow and Runner; submit / pause / resume / pick; run records
  produce.py  produce_refs.py  candidates.py  the rounds of one output, its references, one candidate
  events.py                              events, estimates, usage
  sheets.py  exports.py                  the Pillow compositor, zip exports
  ports.py  models.py                    the Models port; HoneModels (hone-models)
  dashboard.py  _dashboard_api.py  _dashboard_work.py  _dashboard_data.py  dashboard_page/   the local dashboard
  cli.py                                 the CLI (extra cli)
  testing/                               FakeModels, sample_workspace
tests/unit|contract|integration|e2e|gpu
docs/                  user docs; every Python block is run by the tests
examples/              one explained, runnable example per concept
design/                why and how: README, current.md, changes/, decisions.md, history/
```

A workspace folder (`HONE_FRAME_HOME`, default `~/hone-frame`) holds everything: projects as JSON files,
images as files, hone-flow run folders under `flows/`. There is no database.

## Rules

1. **Keep it simple**: the simplest code that passes the acceptance cases; no speculative abstractions;
   complexity at most 10 per function, about 40 lines per function and 300 per module.
2. **Built on its siblings, nothing else**: hone-flow, hone-models and hone-select are core dependencies
   (design/decisions.md D-001), from their git sources until they are on PyPI, never local paths. Every
   model call goes through the `Models` port (`ports.py`), whose default is hone-models; no other model
   client, no optional extra imported at import time.
3. **Explicit failure**: typed errors with messages that say what to do.
4. **Stored formats** are versioned and documented in `docs/`; old data opens or is refused with a
   message that says how to migrate.
5. **Records and secrets**: never record secrets anywhere.
6. **Determinism**: explicit seeds; `hashlib`, never `hash()`, for ids.
7. **Tests first** for public behaviour; each acceptance case has a `tests/e2e/test_ac<N>_*` test; docs and
   examples are executed by tests. Green means `scripts/check.sh` passes; never weaken a test to pass.
8. **Real models** only through `scripts/gpu-lock.sh`; unload what you load.
9. **Design changes** get a record in `design/changes/` first; small choices go into
   `design/decisions.md`; update `design/current.md` when behaviour changes.
10. **Git**: Conventional Commits, small commits; AI-written commits end with a `Co-Authored-By:` line.
    Push a branch and open a pull request only when the user asks ("push", "ship it"). Inside that pull
    request's flow, reviewing it on GitHub and pushing fixes the user asked for need no new request.
    Never push to `main`, tag or publish unless the maintainer asks.

## Workflow and tooling

One branch per task; a change record before a design change; tests first; the docs updated with the
code (the table in [`.claude/skills/sync-docs/SKILL.md`](.claude/skills/sync-docs/SKILL.md));
`scripts/check.sh` green; a pull request from
[`.github/pull_request_template.md`](.github/pull_request_template.md). Claude Code users get this flow
as skills, reviewer agents and hooks in [`.claude/`](.claude/); see [`CLAUDE.md`](CLAUDE.md). Other
tools: the skills are plain Markdown and can be followed as they are.
