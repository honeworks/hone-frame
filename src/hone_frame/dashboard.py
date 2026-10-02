"""The local dashboard (design §12): a standard-library HTTP server, a JSON API and static files."""

from __future__ import annotations

import json
import logging
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from pydantic import ValidationError

from hone_frame._dashboard_api import ApiError, route
from hone_frame.engine import Runner
from hone_frame.errors import HoneFrameError, InvalidRequest, NotFound, RunStateError
from hone_frame.workspace import Workspace

PAGE = resources.files("hone_frame") / "dashboard_page"
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}
PAGE_CSP = (  # inline styles carry no data; scripts only from the page itself (decisions D-012)
    "default-src 'self'; img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'"
)
LOG = logging.getLogger("hone_frame.dashboard")
MAX_BODY = 64 * 1024 * 1024


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    ws: Workspace


class Dashboard:
    """The server, its workspace and (optionally) the runner thread."""

    def __init__(
        self, ws: Workspace, host: str = "127.0.0.1", port: int = 8792, *, runner: bool = True
    ) -> None:
        self.ws = ws
        self.stop = threading.Event()
        self.server = _Server((host, port), Handler)
        self.server.ws = ws
        self.runner: threading.Thread | None = None
        if runner:
            self.runner = threading.Thread(target=self._run, name="hone-frame-runner", daemon=True)

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}/"

    def _run(self) -> None:
        runner = Runner(self.ws)
        runner.recover()
        runner.run_forever(self.stop)

    def start(self) -> Dashboard:
        """Serve in background threads (tests, notebooks)."""
        if self.runner is not None:
            self.runner.start()
        threading.Thread(target=self.server.serve_forever, name="hone-frame-http", daemon=True).start()
        return self

    def close(self) -> None:
        self.stop.set()
        self.server.shutdown()
        self.server.server_close()


def serve(ws: Workspace, host: str = "127.0.0.1", port: int = 8792, *, runner: bool = True) -> None:
    """Serve until interrupted (Ctrl-C). The runner thread executes queued runs one at a time."""
    dashboard = Dashboard(ws, host, port, runner=runner)
    if dashboard.runner is not None:
        dashboard.runner.start()
    print(f"Hone Frame dashboard: {dashboard.url}  (workspace {ws.root})", flush=True)
    try:
        dashboard.server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        dashboard.close()


class Handler(BaseHTTPRequestHandler):
    """One request: `/api/*` JSON, `/files/*` project images, `/downloads/*` exports, else the page."""

    server_version = "hone-frame"

    @property
    def ws(self) -> Workspace:
        server: _Server = self.server  # pyright: ignore[reportAssignmentType]
        return server.ws

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet: the dashboard polls every 2 s."""

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PATCH(self) -> None:
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        parts = urlsplit(self.path)
        path = unquote(parts.path)
        query = {k: v[-1] for k, v in parse_qs(parts.query).items()}
        try:
            if path.startswith("/api/"):
                self._api(method, path, query)
            elif method == "GET" and path.startswith("/files/"):
                self._file(path.removeprefix("/files/"))
            elif method == "GET" and path.startswith("/downloads/"):
                self._download(path.removeprefix("/downloads/"))
            elif method == "GET":
                self._static(path)
            else:
                self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _api(self, method: str, path: str, query: dict[str, str]) -> None:
        body = self._body()
        try:
            result = route(self.ws, method, path.removeprefix("/api"), query, body)
        except ApiError as exc:
            self._json(exc.status, {"error": str(exc)})
        except ValidationError as exc:  # a body that does not fit the record: say which field and why
            problems = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid input: " + "; ".join(problems), "problems": problems},
            )
        except InvalidRequest as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "problems": exc.problems})
        except NotFound as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except RunStateError as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except HoneFrameError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            LOG.exception("dashboard API %s %s failed", method, path)
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"internal error: {type(exc).__name__}: {exc}"}
            )
        else:
            self._json(HTTPStatus.OK, result)

    def _body(self) -> Any:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return None
        if length > MAX_BODY:
            raise ApiError("request too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        raw = self.rfile.read(length)
        if (self.headers.get("Content-Type") or "").startswith("application/json"):
            return json.loads(raw or b"null")
        return {"bytes": raw, "name": self.headers.get("X-File-Name") or "upload.png"}

    def _file(self, relative: str) -> None:
        """Images and sheet renders of a project, never anything else (design §12.1)."""
        root = (self.ws.root / "projects").resolve()
        target = (root / relative).resolve()
        ok = target.is_relative_to(root) and target.is_file() and target.suffix.lower() in IMAGE_TYPES
        if not ok or not {"images", "sheets"} & set(target.relative_to(root).parts[1:2]):
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        self._send(
            HTTPStatus.OK,
            target.read_bytes(),
            IMAGE_TYPES[target.suffix.lower()],
            {"Content-Security-Policy": "default-src 'none'; sandbox", "Cache-Control": "max-age=3600"},
        )

    def _download(self, name: str) -> None:
        """Exports made through the API, from `<home>/exports/` only."""
        folder = (self.ws.root / "exports").resolve()
        target = (folder / name).resolve()
        if not (target.is_relative_to(folder) and target.is_file() and target.suffix == ".zip"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        self._send(
            HTTPStatus.OK,
            target.read_bytes(),
            "application/zip",
            {"Content-Disposition": f'attachment; filename="{target.name}"'},
        )

    def _static(self, path: str) -> None:
        parts = [p for p in path.split("/") if p]
        name = "/".join(parts) or "index.html"
        node = PAGE.joinpath(*parts) if parts and ".." not in parts else PAGE / "index.html"
        if not node.is_file():
            node, name = PAGE / "index.html", "index.html"  # client-side routes
        kind = (
            STATIC_TYPES.get(Path(name).suffix) or mimetypes.guess_type(name)[0] or "application/octet-stream"
        )
        self._send(HTTPStatus.OK, node.read_bytes(), kind, {"Content-Security-Policy": PAGE_CSP})

    def _json(self, status: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self._send(status, body, "application/json; charset=utf-8", {"Cache-Control": "no-store"})

    def _send(self, status: int, body: bytes, kind: str, headers: dict[str, str]) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)
