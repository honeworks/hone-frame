# hone-frame examples

One runnable file per concept. Each opens with a docstring saying **what** it shows, **how** (the calls,
in order) and **why** (the problem it solves), then runs top to bottom with `FakeModels` and a temporary
folder (no network, no GPU), prints a few lines and asserts the key facts. `tests/e2e/test_examples.py`
runs every file here, so they always work with the current code.

```bash
uv run python examples/quickstart.py
```

| # | File | Concept | In one sentence | Design |
|---|---|---|---|---|
| 1 | [`quickstart.py`](quickstart.py) | projects, subjects, plans, runs, sheets | A turnaround runs unattended, keeps every candidate, explains each pick and becomes a sheet. | §2, §3 |
| 2 | [`scene_references.py`](scene_references.py) | scenes, roles, precedence | A scene sends exactly the references it selected, in a visible order. | §10 |
| 3 | [`sheets_and_exports.py`](sheets_and_exports.py) | the compositor, versions, exports | Sheets are deterministic layouts of saved images; packs hold only what a scene uses. | §11 |
| 4 | [`run_control.py`](run_control.py) | pause, resume, needs review, manual pick | Stop and continue without regenerating; unresolved outputs stay visible until a person picks. | §8.5, §9 |
| 5 | [`coverage_states_sequences.py`](coverage_states_sequences.py) | coverage, interactions, states, sequences, grids | Every advanced request reuses the project's subjects, one output per view, frame or cell. | §6.1 |
| 6 | [`project_file.py`](project_file.py) | project files: import, edit, import again | A whole project (characters, belongings, world, scenes) comes from one TOML or JSON file; only what changed gets a new version. | change 0004 |
