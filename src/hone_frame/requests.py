"""Generation requests and plans (design §6). A request expands into planned outputs (`recipes.py`)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from hone_frame.records import Record, Role, Selection, SubjectLink


class RequestBase(Record):
    """Fields every request has; each request type adds its own and a `kind` literal."""

    profile: str = ""  # a profile id; empty: the project's default
    selection: Selection | None = None  # None: the project's default
    presets: dict[str, str] = Field(default_factory=dict[str, str])  # category -> preset id overrides
    note: str = ""
    title: str = ""
    variation: str = ""  # a variation id (change 0005); empty: the project's active one
    approval: Literal["auto", "base", "each"] = "auto"  # when the run waits for the person (0006)
    judge_mode: Literal["default", "strong_base", "strong_all"] = "default"  # the stronger judge (0006)

    @property
    def task(self) -> str:
        """The request's `kind` ("scene", "coverage"...)."""
        return str(self.__dict__.get("kind", "request"))


class SubjectReferences(RequestBase):
    """A subject's reference images: a hero, then the presentation's views (design §6.1)."""

    kind: Literal["subject_references"] = "subject_references"
    subject_id: str
    presentation: str | None = None  # a <kind>_presentation preset id
    expressions: list[str] = Field(default_factory=list[str])
    poses: list[str] = Field(default_factory=list[str])
    states: list[str] = Field(default_factory=list[str])
    hero_image: str | None = None  # an existing image to use as the hero instead of generating one
    sheet_layout: str | None = None  # compose a sheet of the views once all are accepted


class SceneShot(RequestBase):
    kind: Literal["scene"] = "scene"
    scene_id: str
    scene_version: int | None = None


class Coverage(RequestBase):
    kind: Literal["coverage"] = "coverage"
    scene_id: str
    cameras: list[str] = Field(min_length=1)


class Interaction(RequestBase):
    kind: Literal["interaction"] = "interaction"
    character_id: str
    asset_id: str
    action: str  # an interaction preset id, or free text
    pose: str | None = None
    pose_image: str | None = None
    environment_id: str | None = None


class StatePair(RequestBase):
    kind: Literal["state_pair"] = "state_pair"
    subject_id: str | None = None
    scene_id: str | None = None
    state: str  # a state preset id (before/after)
    same_framing: bool = True


class SequenceFrames(RequestBase):
    kind: Literal["sequence"] = "sequence"
    sequence_id: str


class Variations(RequestBase):
    """The cartesian product of `axes` over one base output (design §6.1, brief §11)."""

    kind: Literal["variations"] = "variations"
    scene_id: str | None = None
    subject_id: str | None = None
    axes: dict[str, list[str]] = Field(
        min_length=1
    )  # outfit, expression, lighting, camera, state, style, pose


class CharacterPacks(RequestBase):
    """A character's references, pack by pack, from one hero (change 0003). The hero is drawn when the
    character has no accepted hero, or when `redraw_hero` is set; otherwise the accepted one is reused."""

    kind: Literal["character_packs"] = "character_packs"
    subject_id: str
    packs: list[str] = Field(default_factory=list[str])  # empty: every pack
    custom: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])  # pack -> extra items
    redraw_hero: bool = False  # draw a new hero even when one is accepted
    only_custom: bool = False  # make only the `custom` items ("add to a pack"), not the packs' defaults
    casting: int = Field(default=0, ge=0, le=8)  # hero candidates from distinct readings (change 0006)


class Promote(RequestBase):
    kind: Literal["promote"] = "promote"
    image_id: str
    operation: Literal["upscale", "refine", "regenerate"]
    profile: str = "final"


Request = Annotated[
    SubjectReferences
    | SceneShot
    | Coverage
    | Interaction
    | StatePair
    | SequenceFrames
    | Variations
    | Promote
    | CharacterPacks,
    Field(discriminator="kind"),
]
OutputMode = Literal["generate", "upscale"]


class PlannedRef(Record):
    image_id: str
    subject_id: str | None = None
    version: int | None = None
    role: Role = "identity"


class Dependency(Record):
    output: str
    role: Role = "identity"


class PlannedOutput(Record):
    id: str
    label: str
    kind: str  # character | environment | asset | interaction | scene | sequence_frame | promotion
    subjects: list[SubjectLink] = Field(default_factory=list[SubjectLink])
    references: list[PlannedRef] = Field(default_factory=list[PlannedRef])
    text_refs: list[str] = Field(default_factory=list[str])  # references described in words instead
    depends_on: list[Dependency] = Field(default_factory=list[Dependency])
    prompt_inputs: dict[str, Any] = Field(default_factory=dict[str, Any])
    judging: str = "scene-fidelity"
    conditions: list[str] = Field(default_factory=list[str])
    size: str = "1024x1024"
    model: str = ""
    mode: OutputMode = "generate"
    seed_group: str | None = None
    parent: str | None = None
    pack: str | None = None  # a character pack and its item (change 0003)
    item: str | None = None


class ResolvedProfile(Record):
    id: str
    planner: str | None = None
    generator: str
    editor: str | None = None
    judge: str | None = None
    upscaler: str | None = None
    size: str = "1024x1024"
    settings: dict[str, Any] = Field(default_factory=dict[str, Any])
    planner_think: bool = False
    judge_think: bool = False


class Counts(Record):
    outputs: int = 0
    images: int = 0
    judge_calls: int = 0
    planner_calls: int = 0


class Plan(Record):
    kind: str
    title: str
    request: dict[str, Any]
    outputs: list[PlannedOutput]
    profile: ResolvedProfile
    selection: Selection
    presets: dict[str, int] = Field(default_factory=dict[str, int])
    counts: Counts = Field(default_factory=Counts)
    estimate: dict[str, float] | None = None
    warnings: list[str] = Field(default_factory=list[str])
    errors: list[str] = Field(default_factory=list[str])
    sheet_layout: str | None = None
    variation: str = ""  # the variation every image of this plan belongs to (change 0005)
    checkpoints: list[str] = Field(default_factory=list[str])  # outputs after which the run waits (0006)
    approval: str = "auto"
    judge_mode: str = "default"
