#!/usr/bin/env python3
"""Print one `name @ git+url@ref` line per [tool.uv.sources] git source (design/decisions.md D-002)."""

import tomllib
from pathlib import Path

sources = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())["tool"]["uv"][
    "sources"
]
for name, source in sources.items():
    if "git" in source:
        ref = source.get("rev") or source.get("tag") or source.get("branch")
        print(f"{name} @ git+{source['git']}" + (f"@{ref}" if ref else ""))
