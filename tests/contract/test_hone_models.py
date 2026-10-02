"""`HoneModels`, the default `Models` port, against hone-models' own fakes (design §7.2)."""

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from hone_models.errors import ProviderError
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
    monkeypatch.setattr(models_module.mk, "image", lambda _model_id, **_: fake)
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
    for model_id, refs in (("flux.2-klein-4b", 2), ("qwen-image-edit-2511", 3), ("flux.2-klein-4b-text", 0)):
        info = port.info(model_id)  # from hone-frame's own registry file, in any working folder
        assert info.max_references == refs and info.note != "no ComfyUI workflow in the registry yet"
        assert ("references" in info.inputs) is (refs > 0)
    assert {m.id for m in port.available("image")} >= {"z-image-turbo"}
    with pytest.raises(NotFound):
        port.info("no-such-model")


class Sessions:
    """Counts `mk.session(provider)` entries and exits (decisions D-014)."""

    def __init__(self, delay_s: float = 0.0) -> None:
        self.entered: list[str] = []
        self.exited: list[str] = []
        self.delay_s = delay_s

    @contextmanager
    def __call__(self, provider: str) -> Iterator[str]:
        time.sleep(self.delay_s)
        self.entered.append(provider)
        try:
            yield f"http://fake/{provider}"
        finally:
            self.exited.append(provider)


def _patched(monkeypatch: pytest.MonkeyPatch, sessions: Sessions) -> HoneModels:
    monkeypatch.setattr(models_module.mk, "session", sessions)
    monkeypatch.setattr(models_module.mk, "image", FakeMedia.like)
    return HoneModels()


def test_a_local_server_is_entered_once_and_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sessions = Sessions()
    port = _patched(monkeypatch, sessions)
    for n in range(2):
        port.generate("z-image-turbo", "a cup", out=tmp_path / f"{n}.png", seed=n, references=[], inputs={})
    assert sessions.entered == ["comfyui"] and sessions.exited == []
    port.generate("gpt-image-1.5", "a cup", out=tmp_path / "h.png", seed=3, references=[], inputs={})
    assert sessions.entered == ["comfyui"]  # a hosted model needs no local server
    port.close()
    assert sessions.exited == ["comfyui"]
    port.generate("z-image-turbo", "a cup", out=tmp_path / "again.png", seed=4, references=[], inputs={})
    assert sessions.entered == ["comfyui", "comfyui"]  # entered again after close()
    port.close()


def test_concurrent_calls_enter_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sessions = Sessions(delay_s=0.05)
    port = _patched(monkeypatch, sessions)

    def call(n: int) -> None:
        port.generate("z-image-turbo", "a cup", out=tmp_path / f"t{n}.png", seed=n, references=[], inputs={})

    threads = [threading.Thread(target=call, args=(n,)) for n in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sessions.entered == ["comfyui"]
    port.close()


def test_a_server_that_fails_to_start_is_tried_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sessions = Sessions()
    calls = {"n": 0}

    @contextmanager
    def flaky(provider: str) -> Iterator[str]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise ProviderError(
                "no ComfyUI server at http://127.0.0.1:8188 and HONE_COMFYUI_START is not set"
            )
        with sessions(provider) as url:
            yield url

    port = _patched(monkeypatch, sessions)
    monkeypatch.setattr(models_module.mk, "session", flaky)
    with pytest.raises(ModelFailure, match="HONE_COMFYUI_START") as raised:
        port.generate("z-image-turbo", "a cup", out=tmp_path / "a.png", seed=1, references=[], inputs={})
    assert raised.value.transient is True
    port.generate("z-image-turbo", "a cup", out=tmp_path / "b.png", seed=2, references=[], inputs={})
    assert sessions.entered == ["comfyui"]  # the failed start was not remembered as open
    port.close()


def test_a_workspace_registry_file_wins(tmp_path: Path) -> None:
    import hone_frame as hf

    home = tmp_path / "studio"
    home.mkdir()
    (home / "hone-models.toml").write_text(
        '[models."flux.2-klein-4b"]\ncapabilities = { max_references = 1 }\n'
    )
    assert hf.Workspace(home).models.info("flux.2-klein-4b").max_references == 1
    assert hf.Workspace(tmp_path / "other").models.info("flux.2-klein-4b").max_references == 2


def test_flux_reference_slots_are_filled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeMedia.like("flux.2-klein-4b", registry=HoneModels().registry)
    monkeypatch.setattr(models_module.mk, "image", lambda _model_id, **_: fake)
    port = HoneModels()
    monkeypatch.setattr(port, "_server", lambda _model_id: None)
    Image.new("RGB", (8, 8)).save(tmp_path / "hero.png")
    port.generate(
        "flux.2-klein-4b",
        "a view",
        out=tmp_path / "v.png",
        seed=1,
        references=[tmp_path / "hero.png"],
        inputs={},
    )
    sent = fake.calls[-1][1]["references"]
    assert [Path(p).name for p in sent] == ["hero.png", "hero.png"]
