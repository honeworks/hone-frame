"""The command line (extra `cli`, design §2): the dashboard, presets, projects, the queue, exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from hone_frame.engine import Runner
from hone_frame.errors import HoneFrameError
from hone_frame.workspace import Workspace

app = typer.Typer(help="Hone Frame: a project-based visual production workspace.", no_args_is_help=True)
Home = Annotated[
    Path | None,
    typer.Option("--home", help="The workspace folder (default $HONE_FRAME_HOME or ./hone-frame)."),
]
Json = Annotated[bool, typer.Option("--json", help="Print JSON.")]


def _print(data: Any, as_json: bool, lines: list[str]) -> None:
    typer.echo(json.dumps(data, indent=2, default=str) if as_json else "\n".join(lines))


@app.command()
def dashboard(
    home: Home = None,
    port: Annotated[int, typer.Option(help="The port to serve on.")] = 8792,
    host: Annotated[str, typer.Option(help="The address to bind; keep it local.")] = "127.0.0.1",
    no_runner: Annotated[
        bool, typer.Option("--no-runner", help="Serve without executing queued runs.")
    ] = False,
) -> None:
    """Serve the dashboard; its runner executes queued runs one at a time."""
    from hone_frame.dashboard import serve  # noqa: PLC0415 - the server loads only for this command

    serve(Workspace(home), host, port, runner=not no_runner)


@app.command()
def presets(
    category: Annotated[str | None, typer.Option(help="Only this category.")] = None,
    home: Home = None,
    as_json: Json = False,
) -> None:
    """List the preset catalogue (usable before any project exists)."""
    catalog = Workspace(home).presets
    cats = [category] if category else catalog.categories()
    data = {c: [p.model_dump() for p in catalog.list(c)] for c in cats}
    lines = [f"{c}: " + ", ".join(p["id"] for p in rows) for c, rows in data.items()]
    _print(data, as_json, lines)


@app.command()
def projects(home: Home = None, as_json: Json = False) -> None:
    """List the projects of the workspace."""
    found = Workspace(home).projects()
    _print([p.model_dump(mode="json") for p in found], as_json, [f"{p.id}\t{p.name}" for p in found])


@app.command("run-queue")
def run_queue(
    home: Home = None,
    once: Annotated[bool, typer.Option("--once", help="Run only the oldest queued run.")] = False,
) -> None:
    """Execute queued runs in this process (resuming any a dead process left running)."""
    runner = Runner(Workspace(home))
    for run_id in runner.recover():
        typer.echo(f"recovered {run_id}")
    while (done := runner.run_next()) is not None:
        typer.echo(f"{done.id}\t{done.status}\t{done.title}")
        if once:
            break


@app.command()
def status(project: str, run_id: str, home: Home = None, as_json: Json = False) -> None:
    """Show one run: status, progress, outputs."""
    view = Workspace(home).project(project).run_view(run_id)
    lines = [
        f"{view.title}: {view.status} {view.reason}".rstrip(),
        f"progress {view.progress['done']}/{view.progress['planned']}",
    ]
    lines += [f"  {o.id} {o.label}: {o.status} {o.selected or ''} {o.reason}".rstrip() for o in view.outputs]
    _print(view.model_dump(mode="json"), as_json, lines)


@app.command("export-pack")
def export_pack(project: str, scene_id: str, out: Path, home: Home = None) -> None:
    """Export a scene's reference pack (only its selected references) as a zip file."""
    typer.echo(str(Workspace(home).project(project).export_pack(scene_id, out)))


def main() -> None:
    try:
        app()
    except HoneFrameError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from exc
