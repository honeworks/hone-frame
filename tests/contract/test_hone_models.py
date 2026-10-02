"""`HoneModels`, the default `Models` port, against hone-models' own fakes (design §7.2)."""

import json
from pathlib import Path

import pytest
from hone_models.testing import FakeMedia, FakeOllama
from PIL import Image

import hone_frame.models as models_module
from hone_frame.errors import NotFound
from hone_frame.judging import JudgeAnswer
from hone_frame.models import HoneModels
from hone_frame.ports import ModelFailure


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # hone-models reads ./hone-models.toml and writes its records here
    monkeypatch.setenv("HOME", str(tmp_path))


def test_generate_maps_results_and_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeMedia.like("z-image-turbo")
    monkeypatch.setattr(models_module.mk, "image", lambda _model_id: fake)
    port = HoneModels()
    monkeypatch.setattr(port, "_server", lambda _model_id: None)  # no ComfyUI server in tests
    done = port.generate(
        "z-image-turbo",
        "a cup",
        out=tmp_path / "a.png",
        seed=7,
        references=[],
        inputs={"size": "64x64", "camera_angle": "front", "steps": None},
    )
    assert done.path is not None and done.path.is_file() and done.seed == 7 and done.error is None
    assert fake.calls[-1][1] == {"size": "64x64", "steps": 8}  # camera_angle left out; steps is the default
    fake.fail_next("CUDA out of memory")
    failed = port.generate("z-image-turbo", "a cup", out=tmp_path / "b.png", seed=8, references=[], inputs={})
    assert failed.path is None and failed.error_kind == "out_of_memory"
    with pytest.raises(ModelFailure) as raised:
        port.generate(
            "z-image-turbo",
            "a cup",
            out=tmp_path / "c.png",
            seed=9,
            references=[tmp_path / "x.png"],
            inputs={},
        )
    assert raised.value.transient is False  # z-image-turbo takes no references: a capability error


def test_ask_parses_the_judge_answer(tmp_path: Path) -> None:
    Image.new("RGB", (8, 8)).save(tmp_path / "c.png")
    answer = {
        "description": "a cup",
        "checks": [{"name": "shape", "verdict": "pass", "score": 0.9, "finding": "ok"}],
        "overall": 0.7,
        "summary": "fine",
    }
    with FakeOllama() as server:
        server.queue("/api/chat", {"message": {"role": "assistant", "content": json.dumps(answer)}})
        parsed = HoneModels().ask(
            "qwen2.5vl-7b", "Judge it.", images=[tmp_path / "c.png"], schema=JudgeAnswer, think=False
        )
        assert parsed.overall == 0.7 and parsed.checks[0].name == "shape"
        server.queue("/api/chat", 500, 500, 500)
        with pytest.raises(ModelFailure) as raised:
            HoneModels().ask("qwen2.5vl-7b", "Judge it.", images=[], schema=JudgeAnswer, think=False)
        assert raised.value.transient is True
    chat = next(q["body"] for q in server.requests if q["path"] == "/api/chat")
    assert chat["think"] is False and any("images" in m for m in chat["messages"])


def test_info_and_available() -> None:
    port = HoneModels()
    image = port.info("z-image-turbo")
    assert (image.kind, image.local, image.max_references) == ("image", True, 0)
    assert "size" in image.inputs and image.prompt_guide
    judge = port.info("qwen2.5vl-7b")
    assert judge.kind == "chat" and judge.vision is True
    assert not port.info("flux.2-klein-4b").available or port.info("flux.2-klein-4b").note  # no workflow yet
    assert {m.id for m in port.available("image")} >= {"z-image-turbo"}
    with pytest.raises(NotFound):
        port.info("no-such-model")
