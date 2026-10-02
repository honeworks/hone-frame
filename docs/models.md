# Models

hone-frame calls models only through one small port, `Models` (`hone_frame.ports`): `generate`, `ask`,
`info` and `available`. The default implementation is `hf.HoneModels()`, which is
[hone-models](https://github.com/honeworks/hone-models). Every image, planner and judge call goes
through hone-models' registry, GPU leases and call records.

```python
import hone_frame as hf
from hone_frame.testing import FakeModels

fake = FakeModels()
info = fake.info("flux.2-klein-4b")
print(info.kind, info.max_references, info.local)
```

- Model ids are hone-models registry ids (`hone-models models list`). hone-frame ships its own entries
  for the reference-editing models (`flux.2-klein-4b`, `flux.2-klein-4b-text`, `qwen-image-edit-2511`,
  with their ComfyUI workflows), so it works from any folder. The files merge in this order, later
  ones winning: hone-models' catalog, `~/.config/hone/models.toml`, `./hone-models.toml` (the folder
  you start in, as before), hone-frame's entries, then `<home>/hone-models.toml`, so a workspace's own
  file is the place to change a model for that workspace.
  A ComfyUI model without a workflow shows as unavailable, and the plan says which role cannot run.
- Local servers start by themselves: Ollama, and ComfyUI from `HONE_COMFYUI_START`, on first use.
- Thinking is off for planners and judges (`planner_think`, `judge_think` in a profile).
- `hf.testing.FakeModels` writes small PNGs, scripts judge verdicts (`judge=`), failures
  (`fail_generate`, `fail_ask`) and model capabilities (`infos=`). Tests and examples use it.
