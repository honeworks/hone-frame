"""The core imports its three sibling packages (decisions D-001) and nothing optional: not the CLI's
typer, not the other honeworks packages."""

import subprocess
import sys

BLOCKED = ("hone_taste", "hone_lens", "typer")


def test_core_imports_without_optional_packages() -> None:
    code = (
        "import sys, importlib.abc\n"
        f"blocked = {BLOCKED!r}\n"
        "class Block(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in blocked: raise ImportError('blocked ' + name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "import hone_frame, hone_frame.testing, hone_frame.dashboard\n"
        "print('ok')\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"
