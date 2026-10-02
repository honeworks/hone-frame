"""The workspace records (design §4): Pydantic models stored as JSON with `format_version` "1"."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SubjectKind = Literal["character", "environment", "asset"]
StateKind = Literal["outfit", "expression", "condition", "lighting", "other"]
Role = Literal[
    "identity", "object", "environment", "outfit", "pose", "expression", "composition", "lighting", "style"
]
ROLE_ORDER: tuple[Role, ...] = (
    "identity",
    "object",
    "environment",
    "outfit",
    "pose",
    "expression",
    "composition",
    "lighting",
    "style",
)
ImageStatus = Literal[
    "candidate", "picked", "manual_pick", "best_available", "rejected", "uncertain", "imported"
]
Verdict = Literal["pass", "fail", "uncertain", "not_assessable"]
ID_PREFIX: dict[str, str] = {"character": "char", "environment": "env", "asset": "obj"}


class Record(BaseModel):
    """A stored record: unknown keys are ignored so newer files stay readable (design §4.1)."""

    model_config = ConfigDict(extra="ignore")


class Selection(Record):
    """How candidates are made and chosen (design §6.1, brief §4)."""

    strategy: Literal["batch", "sequential"] = "batch"
    rounds: int = Field(default=3, ge=1, le=10)
    candidates: int = Field(default=1, ge=1, le=8)
    auto_judge: bool = True
    auto_pick: bool = True
    stop: Literal["all_rounds", "stop_on_pass"] = "all_rounds"
    technical_retries: int = Field(default=2, ge=0, le=5)


class ProjectDefaults(Record):
    profile: str = "draft"
    selection: Selection = Field(default_factory=Selection)
    presets: dict[str, str] = Field(default_factory=dict[str, str])  # category -> preset id
    profiles: dict[str, dict[str, Any]] = Field(default_factory=dict[str, dict[str, Any]])  # overrides


class Project(Record):
    format_version: str = "1"
    id: str
    name: str
    brief: str = ""
    direction: str = ""
    style_pack: str = "cinematic-realism"
    defaults: ProjectDefaults = Field(default_factory=ProjectDefaults)
    created_at: str
    updated_at: str


class State(Record):
    name: str
    kind: StateKind = "other"
    description: str = ""


class Subject(Record):
    id: str
    kind: SubjectKind
    name: str
    description: str = ""
    version: int = 1
    fields: dict[str, Any] = Field(default_factory=dict[str, Any])
    states: list[State] = Field(default_factory=list[State])
    tags: list[str] = Field(default_factory=list[str])
    reference_images: list[str] = Field(default_factory=list[str])
    created_at: str = ""
    updated_at: str = ""

    def state(self, name: str | None) -> State | None:
        return next((s for s in self.states if s.name == name), None) if name else None


class SubjectLink(Record):
    subject_id: str
    version: int


class RefUse(Record):
    image_id: str
    role: str


class Generation(Record):
    model: str
    prompt: str
    negative: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict[str, Any])
    references: list[RefUse] = Field(default_factory=list[RefUse])
    seed: int | None = None
    job_id: str | None = None
    elapsed_s: float | None = None
    cost_usd: float | None = None
    cost_estimated: bool = False


class CheckResult(Record):
    name: str
    verdict: Verdict
    score: float | None = None
    finding: str = ""
    required: bool = True


class Evaluation(Record):
    description: str = ""
    checks: list[CheckResult] = Field(default_factory=list[CheckResult])
    overall: float = 0.0
    summary: str = ""
    judge: str = ""
    passed: bool = False
    uncertain: bool = False


class ImageRecord(Record):
    format_version: str = "1"
    id: str
    file: str
    width: int
    height: int
    sha256: str
    source: Literal["generated", "imported", "promoted"] = "generated"
    subjects: list[SubjectLink] = Field(default_factory=list[SubjectLink])
    label: str = ""
    run_id: str | None = None
    output_id: str | None = None
    round: int | None = None
    candidate: int | None = None
    parent: str | None = None
    generation: Generation | None = None
    evaluation: Evaluation | None = None
    status: ImageStatus = "candidate"
    profile: str | None = None
    tags: list[str] = Field(default_factory=list[str])
    created_at: str = ""

    @property
    def kind(self) -> str:
        """The image's subject kind ("scene" when it shows several subjects)."""
        if len(self.subjects) != 1:
            return "scene"
        prefix = self.subjects[0].subject_id.split("_")[0]
        return next((k for k, p in ID_PREFIX.items() if p == prefix), "scene")


class SceneRef(Record):
    subject_id: str
    version: int | None = None
    image_ids: list[str] = Field(default_factory=list[str])
    role: Role = "identity"
    state: str | None = None


class Scene(Record):
    id: str = ""
    version: int = 0
    name: str
    description: str = ""
    refs: list[SceneRef] = Field(default_factory=list[SceneRef])
    camera: str | None = None
    framing: str = ""
    pose: str | None = None
    expression: str | None = None
    lighting: str | None = None
    action: str = ""
    gaze: str = ""
    notes: str = ""
    overrides: dict[str, str] = Field(default_factory=dict[str, str])
    created_at: str = ""


class Frame(Record):
    id: str
    description: str = ""
    start_state: str = ""
    change: str = ""
    end_state: str = ""
    use_previous: bool = True


class Sequence(Record):
    id: str = ""
    version: int = 0
    name: str
    scene_id: str
    frames: list[Frame] = Field(default_factory=list[Frame])
    created_at: str = ""


class SheetRecipe(Record):
    name: str
    layout: str = "contact-grid"
    images: list[str] = Field(default_factory=list[str])
    labels: list[str] = Field(default_factory=list[str])
    columns: int | None = None
    page: str = "auto"
    fit: Literal["contain", "cover"] = "contain"
    background: str = "#FFFFFF"
    spacing: int = Field(default=24, ge=0, le=400)
    margin: int = Field(default=48, ge=0, le=800)
    heading: str | None = None
    palette: list[str] = Field(default_factory=list[str])
    notes: str = ""
    show_meta: bool = False


class Sheet(Record):
    id: str = ""
    version: int = 0
    recipe: SheetRecipe
    render: str | None = None  # the composed file of this version, relative to the project
    created_at: str = ""


class OutdatedUse(Record):
    kind: Literal["scene", "sequence", "sheet"]
    id: str
    version: int
    subject_id: str
    used_version: int
    current_version: int
