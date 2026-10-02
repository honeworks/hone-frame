# AGENTS.md: hone-frame

A brief for AI coding tools (Claude Code, Codex, Cursor and others) helping with this repository.
People follow the same rules; they are in [CONTRIBUTING.md](CONTRIBUTING.md).

## What this is

`hone-frame` (import `hone_frame`) is a honeworks package. Purpose: to be defined in
[design/changes/0001](design/changes/0001-initial-design.md); until that record is accepted, the
repository is a working skeleton with no features. Read [design/current.md](design/current.md) before
changing behaviour; it is the design as it stands, and its §5 lists the guarantees the tests check. Why
the design looks like this: [design/changes/](design/changes/) and [design/decisions.md](design/decisions.md).

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
  __init__.py          the version; the public API, once there is one
tests/unit|contract|integration|e2e|gpu
docs/                  user docs
design/                why and how: README, current.md, changes/, decisions.md, history/
```

## Rules

1. **Keep it simple**: the simplest code that passes the acceptance cases; no speculative abstractions;
   complexity at most 10 per function, about 40 lines per function and 300 per module.
2. **The core is useful alone**: it never imports another honeworks package or an optional extra at import
   time; integrations go through ports (small Protocols owned by hone-frame) and lazily imported adapters.
   If another honeworks package is ever needed, it is an optional extra from its git source or PyPI,
   never a local path.
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
