"""`HoneModels`: the `Models` port over hone-models, the only way hone-frame reaches a model (§7.2)."""

from __future__ import annotations

import atexit
import os
import threading
from contextlib import ExitStack
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar

import hone_models as mk
from hone_models.errors import CapabilityError, ConfigError, HoneModelsError, ProviderError
from pydantic import BaseModel

from hone_frame.errors import NotFound
from hone_frame.ports import Generated, ModelFailure, ModelInfo

T = TypeVar("T", bound=BaseModel)
FRAME_REGISTRY = Path(str(resources.files("hone_frame"))) / "data" / "hone-models.toml"
# Workflows whose unused reference slots break the graph: hone-models removes an unused slot's LoadImage
# but not the nodes behind it (flux's VAEEncode then misses its pixels), so these get every slot filled,
# the last reference repeated (decisions D-017). Remove an entry once hone-models drops the whole chain.
FILL_SLOTS = {"flux.2-klein-4b"}
LOCAL_PROVIDERS = {"ollama", "comfyui", "command", "faster_whisper", "kokoro", "chatterbox", "jev_local"}


class HoneModels:
    """Every call goes through `mk.image` / `mk.text`; GPU leases and records are hone-models' (§7.2).

    A local server (Ollama, ComfyUI) that is not running is started on first use through
    `mk.session(provider)` and kept for the life of the process; one that was already running is left
    alone (decisions D-014).

    The registry is hone-models' catalog plus hone-frame's own entries (`data/hone-models.toml`: the
    reference-editing workflows), then `extra` files such as `<home>/hone-models.toml`, so model
    entries never depend on the folder hone-frame starts in (design §7.3, decisions D-016)."""

    def __init__(self, extra: list[Path] | None = None) -> None:
        self.paths = [FRAME_REGISTRY, *(extra or [])]
        os.environ.setdefault("HONE_FRAME_TOOLS_DIR", str(FRAME_REGISTRY.parent / "tools"))  # 0007's tools
        self._registry: Any = None
        self._servers = ExitStack()
        self._open: set[str] = set()
        self._lock = threading.Lock()
        atexit.register(self.close)

    def close(self) -> None:
        """Stop the servers this object started (models are freed after every call anyway)."""
        with self._lock:
            self._servers.close()
            self._open.clear()

    def _server(self, model_id: str) -> None:
        provider = self.registry.get(model_id).provider
        if provider not in ("ollama", "comfyui") or provider in self._open:
            return
        with self._lock:
            if provider not in self._open:
                self._servers.enter_context(mk.session(provider))
                self._open.add(provider)

    def generate(
        self,
        model_id: str,
        prompt: str,
        *,
        out: Path,
        seed: int,
        references: list[Path],
        inputs: dict[str, Any],
    ) -> Generated:
        try:
            self._server(model_id)
            client = mk.image(model_id, registry=self.registry)
            accepted = set(client.inputs)
            kwargs = {k: v for k, v in inputs.items() if k in accepted and v is not None}
            if references:
                kwargs["references"] = _filled(model_id, references, self.registry)
            result = client.generate(prompt, out=out, seed=seed, **kwargs)
        except (ConfigError, CapabilityError) as exc:
            raise ModelFailure(f"{model_id}: {exc}", transient=False) from exc
        except (ProviderError, HoneModelsError) as exc:  # ModelTimeout is a ProviderError
            raise ModelFailure(f"{model_id}: {exc}", transient=True) from exc
        return Generated(
            path=result.path,
            seed=result.seed,
            elapsed_s=result.elapsed_s,
            job_id=result.job_id,
            cost_usd=result.cost_usd,
            cost_estimated=bool(result.cost_estimated),
            error=result.error,
            error_kind=result.error_kind,
        )

    def ask(self, model_id: str, prompt: str, *, images: list[Path], schema: type[T], think: bool) -> T:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content += [{"type": "image", "path": str(p)} for p in images]
        try:
            self._server(model_id)
            result = mk.text(model_id, registry=self.registry).complete(
                [{"role": "user", "content": content}], schema=schema, think=think, temperature=0.2
            )
        except (ConfigError, CapabilityError) as exc:
            raise ModelFailure(f"{model_id}: {exc}", transient=False) from exc
        except HoneModelsError as exc:
            raise ModelFailure(f"{model_id}: {exc}", transient=True) from exc
        if result.error is not None or not isinstance(result.parsed, schema):
            raise ModelFailure(
                f"{model_id}: {result.error or 'the answer did not fit the schema'}", transient=True
            )
        return result.parsed

    def info(self, model_id: str) -> ModelInfo:
        try:
            cfg = self.registry.get(model_id)
        except ConfigError as exc:
            raise NotFound(f"no model {model_id!r} in the hone-models registry: {exc}") from exc
        return _info(cfg, self.registry)

    def available(self, kind: str) -> list[ModelInfo]:
        found = mk.select(kind=kind, registry=self.registry)  # pyright: ignore[reportArgumentType]
        return [_info(cfg, self.registry) for cfg in found]

    @property
    def registry(self) -> Any:
        """hone-models' registry with hone-frame's entries and the extra files, loaded once."""
        if self._registry is None:
            self._registry = mk.registry.load(paths=[str(p) for p in self.paths if p.is_file()])
        return self._registry


def _info(cfg: Any, registry: Any) -> ModelInfo:
    caps = cfg.capabilities
    installed = _installed(cfg)
    no_workflow = cfg.provider == "comfyui" and not cfg.workflow  # hone-models: "no workflow yet" when called
    guide = cfg.guide  # a hone-models Guide, or None
    return ModelInfo(
        id=cfg.id,
        kind=cfg.kind,
        local=cfg.provider in LOCAL_PROVIDERS,
        installed=installed,
        available=not cfg.disabled and installed != "no" and not no_workflow,
        max_references=caps.max_references,
        inputs=tuple(_inputs(cfg, registry)),
        features=tuple(caps.features or ()),
        sizes=tuple(caps.sizes or ()),
        vision=caps.vision,
        prompt_guide=str(getattr(guide, "prompt", None) or ""),
        note="no ComfyUI workflow in the registry yet"
        if no_workflow
        else str(getattr(guide, "summary", None) or ""),
    )


def _installed(cfg: Any) -> str:
    try:
        return mk.catalog.installed(cfg)
    except HoneModelsError:
        return "unknown"


def _inputs(cfg: Any, registry: Any) -> list[str]:
    if cfg.kind != "image":
        return []
    try:
        return list(mk.image(cfg.id, registry=registry).inputs)
    except HoneModelsError:
        return []


def _filled(model_id: str, references: list[Path], registry: Any) -> list[Path]:
    """`references`, with the last one repeated into the free slots of a FILL_SLOTS workflow."""
    slots = registry.get(model_id).capabilities.max_references
    if model_id not in FILL_SLOTS or not slots or not references or len(references) >= slots:
        return references
    return references + [references[-1]] * (slots - len(references))
