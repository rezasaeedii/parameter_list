"""The little web server behind the GUI.

Only the Python standard library is used, so nothing has to be installed.  The
server binds to ``127.0.0.1`` - the loopback interface, which is the machine
talking to itself - so the editor is not reachable from the network at all, and
it never reaches out either: the pages in ``web/`` reference no external file.

It serves the files in ``web/`` and answers the JSON calls of
:class:`~pl_gui.api.Api` under ``/api/<name>``.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from pl_codegen.errors import CodeGeneratorError
from pl_codegen.logging_utils import get_logger

from .api import Api
from .browser import app_window_command, find_browser
from .workspace import Workspace

WEB_DIRECTORY = Path(__file__).resolve().parent / "web"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class GuiServer:
    """Serves the GUI on ``http://127.0.0.1:<port>``."""

    def __init__(self, project: Optional[Path] = None, host: str = "127.0.0.1",
                 port: int = 8765) -> None:
        """*project* is the project file to open at startup, or ``None``.

        None is a normal state, not a failure: the editor starts on its start
        screen, offering the recent projects and the two buttons that make or
        open one.  That is what a machine with a freshly copied app has.
        """
        self.host = host
        self.port = port
        self.workspace = Workspace()
        if project is not None:
            self.workspace.open(project)
        self.api = Api(self.workspace)
        self._httpd: Optional[ThreadingHTTPServer] = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def serve_forever(self, open_browser: bool = True, app_window: bool = True) -> None:
        handler = _make_handler(self.api)
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)

        logger = get_logger()
        logger.info("GUI running at %s (loopback only - no network access)", self.url)
        if self.workspace.is_open:
            config = self.workspace.require().config
            logger.info("project: %s  (%s)", config.project.name, config.path)
        else:
            logger.info("no project open - choose one in the editor")
        logger.info("press Ctrl+C to stop")

        profile = None
        if open_browser:
            profile = tempfile.TemporaryDirectory(prefix="pl_editor_")
            threading.Timer(0.6, lambda: self._open(app_window, profile.name)).start()
        try:
            self._httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("stopping")
        finally:
            self._httpd.server_close()
            if profile is not None:
                profile.cleanup()

    def _open(self, app_window: bool, profile_directory: str) -> None:
        """Show the editor: as its own window if possible, else as a browser tab."""
        logger = get_logger()

        if app_window and self._open_app_window(profile_directory):
            return

        # webbrowser.open says whether it started anything.  Ignoring that made a
        # machine with no browser at all - no desktop, WSL - say "opened in the
        # default browser" and then sit there with nothing on the screen and
        # nothing to say what to do instead.
        if webbrowser.open(self.url):
            logger.info("opened in the default browser")
            return
        logger.warning("no browser could be started on this machine - open %s "
                       "in a browser yourself", self.url)

    def _open_app_window(self, profile_directory: str) -> bool:
        """Try the borderless window.  ``False`` means "use the normal browser"."""
        logger = get_logger()
        browser = find_browser()
        if browser is None:
            return False

        command = app_window_command(browser, self.url, profile_directory)
        # The browser's error output goes to a FILE, not a pipe.  Nothing reads
        # it once the window is up, and a pipe nobody reads fills up - 64 KB on
        # Linux, where Chrome writes to stderr freely - after which the browser
        # blocks on its next write and the editor's window hangs with it.  A file
        # never fills; it is read only when the browser dies at once, to say why.
        # Closing it here is fine: the browser keeps a handle of its own.
        with tempfile.TemporaryFile() as errors:
            try:
                process = subprocess.Popen(command,
                                           stdout=subprocess.DEVNULL,
                                           stderr=errors)
            except OSError as error:
                logger.warning("could not start %s (%s)", Path(browser).name, error)
                return False

            # A browser that refuses to start does so immediately; give it a
            # moment and fall back to the default browser if it is already gone.
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                logger.info("opened in a separate window (%s)", Path(browser).name)
                return True

            errors.seek(0)
            reason = errors.read().decode("utf-8", "replace").strip()
        logger.warning("%s exited straight away%s", Path(browser).name,
                       f": {reason.splitlines()[-1]}" if reason else "")
        return False

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()


def _make_handler(api: Api):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # -- GET: the static files -------------------------------------
        def do_GET(self) -> None:  # noqa: N802 - required by the base class
            name = self.path.split("?", 1)[0].lstrip("/") or "index.html"
            target = (WEB_DIRECTORY / name).resolve()

            if WEB_DIRECTORY not in target.parents or not target.is_file():
                self._send(404, b"not found", "text/plain; charset=utf-8")
                return

            content_type = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
            self._send(200, target.read_bytes(), content_type)

        # -- POST: the JSON api -----------------------------------------
        def do_POST(self) -> None:  # noqa: N802 - required by the base class
            if not self.path.startswith("/api/"):
                self._send(404, b"not found", "text/plain; charset=utf-8")
                return

            action = self.path[len("/api/"):].strip("/")
            handler = api.handlers().get(action)
            if handler is None:
                self._json(404, {"ok": False, "message": f"Unknown action '{action}'."})
                return

            length = int(self.headers.get("Content-Length") or 0)
            try:
                request = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError as error:
                self._json(400, {"ok": False, "message": f"Bad request: {error}"})
                return

            try:
                response = handler(request)
            except Exception as error:  # noqa: BLE001 - never kill the server
                get_logger().exception("api '%s' failed", action)
                # CodeGeneratorError is the tool's own way of saying something
                # a person is meant to read - "'x.xml' is not a valid XML file:
                # mismatched tag: line 5, column 4".  Its class name in front
                # of that adds nothing.  Any other exception is a fault rather
                # than a message, and there the type is the first clue.
                message = (str(error) if isinstance(error, CodeGeneratorError)
                           else f"{type(error).__name__}: {error}")
                self._json(500, {"ok": False, "message": message})
                return

            self._json(200, response)

        # -- helpers ------------------------------------------------------
        def _json(self, status: int, payload: dict) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:  # keep the console clean
            pass

    return Handler
