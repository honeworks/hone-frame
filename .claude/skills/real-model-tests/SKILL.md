---
name: real-model-tests
description: Run or write real-model tests (tests/gpu, marker gpu) safely on a shared GPU - the machine-wide lock, model names from environment variables, skips with reasons, unloading models. Use before running or changing anything under tests/gpu or code that drives a real model.
---

# Real-model tests

Details: CONTRIBUTING.md, "Real-model tests and `scripts/gpu-lock.sh`". hone-frame has no real-model
tests yet.

**Run**
- Only through the lock: `scripts/gpu-lock.sh uv run pytest -m gpu -q`. It waits for the machine-wide
  lock (`$HONE_GPU_LOCK`), so runs from several projects never share a small GPU.
- Models come from the environment (`HONE_TEST_*` variables, listed in CONTRIBUTING.md once there are
  any). Set them for your machine in `.claude/settings.local.json` under `env` (not committed).
- Never start or stop model services and never delete models.

**Write**
- Put the test in `tests/gpu/` with `@pytest.mark.gpu` (plus `ollama`, `comfyui` or `hosted`), using the
  `gpu_lock` fixture from `tests/conftest.py`.
- Check the service and model are available first; if not, `pytest.skip` with a precise reason.
- Few calls, small outputs; assert types, ranges and clear-cut order, never exact model text.
- Unload what you loaded (Ollama: `keep_alive: 0`).

**Report** what ran and what was skipped, with reasons, in the PR's "How it was tested".
