"""AC-13: the README and docs/ are complete and every code example in them runs as written.

- Relative links in README, docs/, design/, CONTRIBUTING, AGENTS, CHANGELOG and examples/README resolve.
- Every ```python block of README.md and docs/*.md runs. The blocks of one file run in order in one fresh
  module namespace, in a fresh temporary working folder, with the environment restored afterwards.
- The ```bash blocks of docs/cli.md are one shell session, run in a fresh temporary folder with this
  environment's `hone-frame` script on PATH. Other ```bash blocks are not run; ```text blocks never are.
"""

import linecache
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[2]
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
PAGES = {
    "index.md",
    "workspace.md",
    "presets.md",
    "generation.md",
    "scenes.md",
    "sheets.md",
    "runs.md",
    "models.md",
    "dashboard.md",
    "cli.md",
    "project-files.md",
    "variations.md",
}
NO_PYTHON = {"index.md", "dashboard.md", "cli.md"}
PROJECT_DOCS = [
    *(ROOT / name for name in ("CONTRIBUTING.md", "AGENTS.md", "CHANGELOG.md")),
    ROOT / "examples" / "README.md",
    *sorted((ROOT / "design").rglob("*.md")),
]
HOME_PATH = re.compile(r"/home/(?!me/)\w+")
WORKSPACE_ONLY = ("project-design", "FIRST-PRODUCT-BRIEF", "pipeline-demo/src")
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def blocks(doc: Path, language: str) -> list[str]:
    pattern = re.compile(rf"^```{language}\n(.*?)^```", re.S | re.M)
    return pattern.findall(doc.read_text(encoding="utf-8"))


def test_ac13_docs_pages_exist() -> None:
    assert {doc.name for doc in DOCS} >= PAGES
    for doc in DOCS:
        if doc.name in PAGES - NO_PYTHON:
            assert blocks(doc, "python"), f"{doc.name} has no runnable example"


def test_ac13_readme_quickstart_is_the_example() -> None:
    source = (ROOT / "examples" / "quickstart.py").read_text(encoding="utf-8")
    body = source.split('"""', 2)[2]
    assert blocks(ROOT / "README.md", "python")[0].strip() == body.strip()


def test_ac13_relative_links_resolve() -> None:
    for doc in [*DOCS, *PROJECT_DOCS]:
        for target in LINK.findall(doc.read_text(encoding="utf-8")):
            if "://" not in target and not target.startswith("mailto:"):
                assert (doc.parent / target).exists(), f"{doc.name} links to missing {target}"


def test_ac13_no_workspace_files_or_home_paths() -> None:
    for doc in [*DOCS, *PROJECT_DOCS]:
        text = doc.read_text(encoding="utf-8")
        for word in WORKSPACE_ONLY:
            assert word not in text, f"{doc.name} mentions {word}"
        assert not HOME_PATH.search(text), f"{doc.name} has a local home path"


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_ac13_python_blocks_run(doc: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    saved = dict(os.environ)
    monkeypatch.chdir(tmp_path)
    module = types.ModuleType(f"hone_frame_docs_{doc.stem.replace('-', '_').lower()}")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    names: list[str] = []
    try:
        for number, block in enumerate(blocks(doc, "python"), start=1):
            filename = f"<{doc.name} block {number}>"
            names.append(filename)
            linecache.cache[filename] = (len(block), None, block.splitlines(keepends=True), filename)
            exec(compile(block, filename, "exec"), module.__dict__)  # noqa: S102 - running our own docs
    finally:
        for filename in names:
            linecache.cache.pop(filename, None)
        os.environ.clear()
        os.environ.update(saved)


def test_ac13_cli_session_runs(tmp_path: Path) -> None:
    session = "\n".join(blocks(ROOT / "docs" / "cli.md", "bash"))
    assert "hone-frame presets" in session
    env = dict(os.environ)
    env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"
    bash = shutil.which("bash")
    assert bash, "the CLI session needs bash"
    result = subprocess.run(
        [bash, "-euo", "pipefail", "-c", session],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=110,
    )
    assert result.returncode == 0, result.stdout + result.stderr
