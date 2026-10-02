"""`HoneModels`: the `Models` port over hone-models, the only way hone-frame reaches a model (§7.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import hone_models as mk
from hone_models.errors import CapabilityError, ConfigError, HoneModelsError, ProviderError
from pydantic import BaseModel

from hone_frame.errors import NotFound
from hone_frame.ports import Generated, ModelFailure, ModelInfo

T = TypeVar("T", bound=BaseModel)
LOCAL_PROVIDERS = {"ollama", "comfyui", "command", "faster_whisper", "kokoro", "chatterbox", "jev_local"}


class HoneModels:
    """Every call goes through `mk.image` / `mk.text`; GPU leases and records are hone-models' (§7.2)."""

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
            client = mk.image(model_id)
            accepted = set(client.inputs)
            kwargs = {k: v for k, v in inputs.items() if k in accepted and v is not None}
            if references:
                kwargs["references"] = references
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
            result = mk.text(model_id).complete(
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
            cfg = mk.registry.load().get(model_id)
        except ConfigError as exc:
            raise NotFound(f"no model {model_id!r} in the hone-models registry: {exc}") from exc
        return _info(cfg)

    def available(self, kind: str) -> list[ModelInfo]:
        return [_info(cfg) for cfg in mk.select(kind=kind)]  # pyright: ignore[reportArgumentType]


def _info(cfg: Any) -> ModelInfo:
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
        inputs=tuple(_inputs(cfg)),
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


def _inputs(cfg: Any) -> list[str]:
    if cfg.kind != "image":
        return []
    try:
        return list(mk.image(cfg.id).inputs)
    except HoneModelsError:
        return []
