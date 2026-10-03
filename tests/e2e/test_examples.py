"""AC-13: every example runs, explains itself (What / How / Why) and is listed in examples/README.md."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

EXAMPLES = Path(__file__).parents[2] / "examples"
FILES = sorted(EXAMPLES.glob("*.py"))


def test_ac13_examples_are_the_set() -> None:
    assert {p.stem for p in FILES} == {
        "quickstart",
        "scene_references",
        "sheets_and_exports",
        "run_control",
        "coverage_states_sequences",
        "project_file",
    }


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_ac13_examples_explain_themselves(path: Path) -> None:
    docstring = ast.get_docstring(ast.parse(path.read_text())) or ""
    paragraphs = [p.strip() for p in docstring.split("\n\n")]
    for word in ("What:", "How:", "Why:"):
        assert any(p.startswith(word) for p in paragraphs), f"a '{word}' paragraph"
    assert f"[`{path.name}`]({path.name})" in (EXAMPLES / "README.md").read_text(), "listed in the README"


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_ac13_examples_run(path: Path, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(path)], cwd=tmp_path, capture_output=True, text=True, timeout=90
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "prints what it shows"
