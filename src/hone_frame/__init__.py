"""Hone Frame: a project-based visual production workspace (design/current.md)."""

from hone_frame import errors
from hone_frame.engine import Runner
from hone_frame.models import HoneModels
from hone_frame.ports import Generated, ModelFailure, ModelInfo, Models
from hone_frame.presets import Preset, PresetCatalog, presets
from hone_frame.records import (
    CheckResult,
    Evaluation,
    Frame,
    ImageRecord,
    OutdatedUse,
    Project,
    ProjectDefaults,
    Scene,
    SceneRef,
    Selection,
    Sequence,
    Sheet,
    SheetRecipe,
    State,
    Subject,
)
from hone_frame.requests import (
    CharacterPacks,
    Coverage,
    Interaction,
    Plan,
    PlannedOutput,
    Promote,
    SceneShot,
    SequenceFrames,
    StatePair,
    SubjectReferences,
    Variations,
)
from hone_frame.runs import OutputRecord, RunView
from hone_frame.store import ProjectStore
from hone_frame.workspace import Settings, Workspace

__version__ = "0.0.0"

__all__ = [
    "CharacterPacks",
    "CheckResult",
    "Coverage",
    "Evaluation",
    "Frame",
    "Generated",
    "HoneModels",
    "ImageRecord",
    "Interaction",
    "ModelFailure",
    "ModelInfo",
    "Models",
    "OutdatedUse",
    "OutputRecord",
    "Plan",
    "PlannedOutput",
    "Preset",
    "PresetCatalog",
    "Project",
    "ProjectDefaults",
    "ProjectStore",
    "Promote",
    "RunView",
    "Runner",
    "Scene",
    "SceneRef",
    "SceneShot",
    "Selection",
    "Sequence",
    "SequenceFrames",
    "Settings",
    "Sheet",
    "SheetRecipe",
    "State",
    "StatePair",
    "Subject",
    "SubjectReferences",
    "Variations",
    "Workspace",
    "__version__",
    "errors",
    "presets",
]
