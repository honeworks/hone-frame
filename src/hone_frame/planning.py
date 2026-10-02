"""Plans (design §6.2): a request resolved into outputs, models, references, counts and warnings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter, ValidationError

from hone_frame.errors import HoneFrameError, InvalidRequest
from hone_frame.events import estimate_plan
from hone_frame.ports import ModelInfo
from hone_frame.profiles import resolve_profile, resolve_selection
from hone_frame.recipes import build
from hone_frame.references import reduce
from hone_frame.requests import Counts, Plan, PlannedOutput, Request, RequestBase, ResolvedProfile

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

REQUEST = TypeAdapter[Any](Request)


def as_request(request: RequestBase | dict[str, Any]) -> RequestBase:
    if isinstance(request, RequestBase):
        return request
    try:
        return REQUEST.validate_python(request)
    except ValidationError as exc:
        raise InvalidRequest(
            "the request is not valid", [e["msg"] + f" ({e['loc']})" for e in exc.errors()]
        ) from exc


def plan(store: ProjectStore, request: RequestBase | dict[str, Any]) -> Plan:
    """Resolve everything and write nothing (design §6.2). Problems are in `errors` / `warnings`."""
    request = as_request(request)
    profile = resolve_profile(store, request)
    selection = resolve_selection(store, request)
    errors: list[str] = []
    warnings: list[str] = []
    try:
        built = build(store, request)
    except HoneFrameError as exc:
        return Plan(
            kind=request.task,
            title=request.title or request.task,
            request=request.model_dump(mode="json"),
            outputs=[],
            profile=profile,
            selection=selection,
            errors=[str(exc)],
        )
    errors += built.errors
    warnings += built.warnings
    checker = ModelCheck(store, profile, errors, warnings)
    outputs = [checker.finish(o) for o in built.outputs]
    checker.judge(selection.auto_judge)
    if selection.auto_pick and not selection.auto_judge:
        errors.append("automatic pick needs automatic judging: turn the judge on, or pick by hand")
    if not outputs and not errors:
        errors.append("this request makes no outputs")
    result = Plan(
        kind=request.task,
        title=request.title or _title(store, request, outputs),
        request=request.model_dump(mode="json"),
        outputs=outputs,
        profile=profile,
        selection=selection,
        presets=_presets_used(store, built.choices.used, profile, outputs, request),
        counts=_counts(outputs, profile, selection),
        warnings=list(dict.fromkeys(warnings)),
        errors=list(dict.fromkeys(errors)),
        sheet_layout=built.sheet_layout,
    )
    result.estimate = estimate_plan(store.workspace, result)
    return result


class ModelCheck:
    """Chooses each output's model and checks what the chosen models can take (design §7, §10.2)."""

    def __init__(
        self, store: ProjectStore, profile: ResolvedProfile, errors: list[str], warnings: list[str]
    ) -> None:
        self.store, self.profile, self.errors, self.warnings = store, profile, errors, warnings
        self._info: dict[str, ModelInfo | None] = {}

    def info(self, model_id: str, role: str) -> ModelInfo | None:
        if model_id not in self._info:
            try:
                found = self.store.workspace.models.info(model_id)
            except HoneFrameError as exc:
                self.errors.append(f"the {role} model {model_id!r} cannot be used: {exc}")
                found = None
            if found is not None and not found.available:
                self.errors.append(
                    f"the {role} model {model_id} is not installed or is disabled: "
                    f"see `hone-models models install {model_id}`"
                )
            self._info[model_id] = found
        return self._info[model_id]

    def finish(self, out: PlannedOutput) -> PlannedOutput:
        model, role = self._model_for(out)
        if model is None:
            return out
        info = self.info(model, role)
        limit = None if info is None else info.max_references
        if out.mode == "upscale":
            return out.model_copy(update={"model": model, "size": self.profile.size})
        room = None if limit is None else max(limit - len(out.depends_on), 0)
        kept, words, warns = reduce(self.store, out.references, room, keep_order=out.kind == "promotion")
        self.warnings += [f"{out.label}: {w}" for w in warns]
        if (out.references or out.depends_on) and limit == 0:
            self.warnings.append(f"{out.label}: {model} takes no reference images; text only: weaker control")
        return out.model_copy(
            update={
                "model": model,
                "references": kept,
                "text_refs": out.text_refs + words,
                "size": self.profile.size,
            }
        )

    def _model_for(self, out: PlannedOutput) -> tuple[str | None, str]:
        if out.mode == "upscale":
            if self.profile.upscaler is None:
                self.errors.append(
                    f"no upscaler is available in the {self.profile.id} profile: "
                    "choose refine or regenerate, or set an upscaler model"
                )
            return self.profile.upscaler, "upscaler"
        if out.references or out.depends_on:
            if self.profile.editor is None:
                self.warnings.append(f"{out.label}: the {self.profile.id} profile has no editor; text only")
                return self.profile.generator, "generator"
            return self.profile.editor, "editor"
        return self.profile.generator, "generator"

    def judge(self, auto_judge: bool) -> None:
        if not auto_judge:
            return
        if self.profile.judge is None:
            self.errors.append(f"automatic judging needs a judge model in the {self.profile.id} profile")
            return
        info = self.info(self.profile.judge, "judge")
        if info is not None and info.vision is False:
            self.errors.append(f"the judge {self.profile.judge} cannot see images; choose a vision model")


def _presets_used(
    store: ProjectStore,
    used: dict[str, int],
    profile: ResolvedProfile,
    outputs: list[PlannedOutput],
    request: RequestBase,
) -> dict[str, int]:
    """Every preset the run depends on, with its version (design §5.2)."""
    catalog = store.workspace.presets
    found = dict(used)
    found[f"profile:{profile.id}"] = catalog.get("profile", profile.id).version
    for judging in {o.judging for o in outputs}:
        found[f"judging:{judging}"] = catalog.get("judging", judging).version
    if "selection" in request.presets:
        found[f"selection:{request.presets['selection']}"] = catalog.get(
            "selection", request.presets["selection"]
        ).version
    return dict(sorted(found.items()))


def _counts(outputs: list[PlannedOutput], profile: ResolvedProfile, selection: Any) -> Counts:
    per_output = selection.rounds * selection.candidates
    planner_rounds = selection.rounds if selection.strategy == "sequential" else 1
    return Counts(
        outputs=len(outputs),
        images=len(outputs) * per_output,
        judge_calls=len(outputs) * per_output if selection.auto_judge else 0,
        planner_calls=len(outputs) * planner_rounds if profile.planner else 0,
    )


def _title(store: ProjectStore, request: RequestBase, outputs: list[PlannedOutput]) -> str:
    for attr in ("subject_id", "character_id"):
        if subject_id := getattr(request, attr, None):
            return f"{store.subject(subject_id).name} {request.task.replace('_', ' ')}"
    if scene_id := getattr(request, "scene_id", None):
        return store.scene(scene_id).name
    if sequence_id := getattr(request, "sequence_id", None):
        return store.sequence(sequence_id).name
    return outputs[0].label if outputs else "Generation"
