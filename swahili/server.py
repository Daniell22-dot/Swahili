"""Seva — a small synchronous HTTP server built on the standard library.

The `seva` module exposes this to Kiswahili programs. Everything here is
deliberately single-threaded: handlers run one at a time inside the
interpreter, so shared globals cannot race.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from .errors import KiswahiliError
from .runtime import display

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_MAX_BODY = 1_048_576
DEFAULT_MAX_RESPONSE = 10_000_000

ANY_METHOD = "*"
_PARAM = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def compile_path(template: str) -> re.Pattern[str]:
    """Turn `/watumiaji/{id}` into a regex with a named group."""
    if not template.startswith("/"):
        raise ValueError("njia lazima ianze na '/' / path must start with '/'")
    parts = _PARAM.split(template)
    out = ["^"]
    for index, part in enumerate(parts):
        if index % 2 == 0:
            out.append(re.escape(part))
        else:
            out.append(f"(?P<{part}>[^/]+)")
    out.append("$")
    return re.compile("".join(out))


def jibu(msimbo: int = 200, mwili: Any = "", vichwa: dict | None = None) -> dict:
    """Build the dict a handler returns."""
    return {
        "msimbo": int(msimbo),
        "mwili": mwili,
        "vichwa": dict(vichwa or {}),
    }


def json_response(msimbo: int, thamani: Any) -> dict:
    body = json.dumps(thamani, ensure_ascii=False, separators=(",", ":"))
    return jibu(msimbo, body,
                {"Content-Type": "application/json; charset=utf-8"})


@dataclass
class Route:
    method: str
    pattern: re.Pattern[str]
    handler: Any


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    params: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "mbinu": self.method,
            "njia": self.path,
            "hoja": dict(self.query),
            "vichwa": dict(self.headers),
            "mwili": self.body,
            "vigezo": dict(self.params),
        }


def _text_headers() -> dict:
    return {"Content-Type": "text/plain; charset=utf-8"}


def normalize_response(result: Any, max_response: int) -> dict:
    if result is None:
        status, headers, body = 200, {}, ""
    elif isinstance(result, dict):
        status = result.get("msimbo", result.get("hali", 200))
        headers = result.get("vichwa") or {}
        body = result.get("mwili", "")
    elif isinstance(result, str):
        status, headers, body = 200, {}, result
    else:
        status, headers, body = 200, {}, display(result)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 500
    if not isinstance(headers, dict):
        headers = {}
    headers = {str(key): str(value) for key, value in headers.items()}
    headers.setdefault("Content-Type", "text/plain; charset=utf-8")
    if not isinstance(body, str):
        body = display(body)
    if len(body.encode("utf-8")) > max_response:
        return jibu(500, "Jibu ni kubwa mno", _text_headers())
    return {"msimbo": status, "mwili": body, "vichwa": headers}


class ServerApp:
    def __init__(self, interp, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 max_body: int = DEFAULT_MAX_BODY,
                 max_response: int = DEFAULT_MAX_RESPONSE):
        self.interp = interp
        self.host = host
        self.port = int(port)
        self.max_body = int(max_body)
        self.max_response = int(max_response)
        self.routes: list[Route] = []

    def add_route(self, method: str, path: str, handler: Any) -> None:
        method = str(method).upper()
        if method != ANY_METHOD and not method.isalpha():
            raise ValueError("mbinu si sahihi / invalid method")
        self.routes.append(Route(method, compile_path(str(path)), handler))

    def _find(self, method: str, path: str):
        for route in self.routes:
            if route.method not in (ANY_METHOD, method):
                continue
            match = route.pattern.fullmatch(path)
            if match:
                return route, match.groupdict()
        return None, {}

    def dispatch(self, method: str, path: str, query: dict | None = None,
                 headers: dict | None = None, body: str = "") -> dict:
        method = method.upper()
        route, params = self._find(method, path)
        if route is None:
            return jibu(404, "Haijapatikana", _text_headers())
        self.interp.reset_budgets()
        request = Request(method, path, dict(query or {}), dict(headers or {}),
                          body, params)
        result = self.interp.call(route.handler, request.as_dict())
        return normalize_response(result, self.max_response)

    def log_exception(self, exc: BaseException) -> None:
        if isinstance(exc, KiswahiliError):
            message = exc.render()
        else:
            message = f"{type(exc).__name__}: {exc}"
        sys.stderr.write(f"[seva] {message}\n")


class _Handler(BaseHTTPRequestHandler):
    server_version = "KiswahiliSeva/0.1"

    def _dispatch(self) -> None:
        app: ServerApp = self.server.app  # type: ignore[attr-defined]
        parsed = urlsplit(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            length = 0
        if length < 0 or length > app.max_body:
            self._send(jibu(413, "Ombi ni kubwa mno", _text_headers()))
            self.close_connection = True
            return
        body = ""
        if length:
            body = self.rfile.read(length).decode("utf-8", "replace")
        headers = {key: value for key, value in self.headers.items()}
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        try:
            response = app.dispatch(self.command, parsed.path, query, headers, body)
        except BaseException as exc:  # a handler must never kill the server
            app.log_exception(exc)
            response = jibu(500, "Hitilafu ya ndani", _text_headers())
        self._send(response)

    def _send(self, response: dict) -> None:
        body = response.get("mwili", "")
        data = body.encode("utf-8") if isinstance(body, str) else str(body).encode("utf-8")
        self.send_response(int(response.get("msimbo", 200)))
        for key, value in (response.get("vichwa") or {}).items():
            self.send_header(str(key), str(value))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_PUT(self) -> None:
        self._dispatch()

    def do_PATCH(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()

    def do_HEAD(self) -> None:
        self._dispatch()

    def do_OPTIONS(self) -> None:
        self._dispatch()

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("[seva] " + (format % args) + "\n")


def make_server(app: ServerApp) -> HTTPServer:
    server = HTTPServer((app.host, app.port), _Handler)
    server.app = app  # type: ignore[attr-defined]
    app.port = server.server_address[1]
    return server


def serve(app: ServerApp) -> None:
    server = make_server(app)
    sys.stderr.write(f"[seva] inasikiliza http://{app.host}:{app.port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
