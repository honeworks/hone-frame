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

- Model ids are hone-models registry ids (`hone-models models list`). A project's own
  `hone-models.toml`, in the folder where you start hone-frame, adds or overrides entries. A ComfyUI
  model without a workflow in the registry shows as unavailable, and the plan says which role cannot run.
- Thinking is off for planners and judges (`planner_think`, `judge_think` in a profile).
- `hf.testing.FakeModels` writes small PNGs, scripts judge verdicts (`judge=`), failures
  (`fail_generate`, `fail_ask`) and model capabilities (`infos=`). Tests and examples use it.
