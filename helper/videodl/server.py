"""API HTTP local usada pela extensão. Só aceita a origem da própria extensão."""

from __future__ import annotations

import json
import logging
import re
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from .errors import classify_error
from .formats import InvalidOptions
from .queue import DownloadQueue

log = logging.getLogger(__name__)

MAX_BODY = 1_000_000
MAX_URLS = 200
MARKER_HEADER = "X-Video-Downloader"
_ITEM_ACTION = re.compile(r"/queue/([\w-]+)/(cancel|retry)")


class Actions(Protocol):
    def status(self) -> dict: ...
    def info(self, url: str) -> dict: ...
    def open_folder(self) -> None: ...
    def update_ytdlp(self) -> dict: ...


class ApiError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _require_http_url(url: object) -> str:
    if not isinstance(url, str):
        raise ApiError(400, "link inválido")
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ApiError(400, f"link inválido: {url[:100]}")
    return url


class ApiServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # no Windows, reuse permitiria duas instâncias na mesma porta

    def __init__(self, address: tuple[str, int], queue: DownloadQueue, actions: Actions, allowed_origin: str):
        self.queue = queue
        self.actions = actions
        self.allowed_origin = allowed_origin
        super().__init__(address, ApiHandler)

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class ApiHandler(BaseHTTPRequestHandler):
    server: ApiServer

    def log_message(self, fmt: str, *args) -> None:
        log.debug("%s - %s", self.address_string(), fmt % args)

    def _origin_ok(self) -> bool:
        return self.headers.get("Origin") == self.server.allowed_origin

    def _request_ok(self) -> bool:
        # A extensão sempre manda MARKER_HEADER. Um site não consegue mandar cabeçalho próprio sem
        # preflight, e o preflight exige a origem da extensão. O Origin pode faltar: o Brave não o
        # envia nos GET de extensão com host_permissions; quando vier, tem de ser o da extensão.
        origin = self.headers.get("Origin")
        return self.headers.get(MARKER_HEADER) == "1" and origin in (None, self.server.allowed_origin)

    def _reject_origin(self) -> None:
        log.warning("pedido recusado: Origin=%r %s=%r em %s %s (esperada %s)",
                    self.headers.get("Origin"), MARKER_HEADER, self.headers.get(MARKER_HEADER),
                    self.command, self.path, self.server.allowed_origin)
        self._send(403, {"error": "origem não permitida"})

    def _cors_headers(self) -> None:
        if self._origin_ok():
            self.send_header("Access-Control-Allow-Origin", self.server.allowed_origin)
            self.send_header("Vary", "Origin")

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        if not self._origin_ok():
            self._reject_origin()
            return
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", f"Content-Type, {MARKER_HEADER}")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        if not self._request_ok():
            self._reject_origin()
            return
        parts = urlsplit(self.path)
        try:
            code, payload = self._route(method, parts.path, parse_qs(parts.query))
        except ApiError as exc:
            code, payload = exc.code, {"error": exc.message}
        except Exception:
            log.exception("erro inesperado em %s %s", method, self.path)
            code, payload = 500, {"error": "erro interno do programa"}
        self._send(code, payload)

    def _route(self, method: str, path: str, query: dict) -> tuple[int, dict]:
        queue, actions = self.server.queue, self.server.actions

        if method == "GET" and path == "/status":
            return 200, actions.status()

        if method == "GET" and path == "/info":
            url = _require_http_url((query.get("url") or [""])[0])
            try:
                return 200, actions.info(url)
            except Exception as exc:
                log.info("info falhou para %s: %s", url, exc)
                raise ApiError(422, classify_error(str(exc)).short) from None

        if path == "/queue" and method == "GET":
            return 200, {"items": queue.list()}

        if path == "/queue" and method == "POST":
            body = self._json_body()
            urls = body.get("urls")
            if not isinstance(urls, list) or not urls:
                raise ApiError(400, "envie ao menos um link")
            if len(urls) > MAX_URLS:
                raise ApiError(400, f"no máximo {MAX_URLS} links por vez")
            clean = [_require_http_url(u) for u in urls]
            try:
                added, duplicates = queue.add(clean, body.get("mode"), body.get("quality"))
            except InvalidOptions as exc:
                raise ApiError(400, str(exc)) from None
            return 200, {"added": added, "duplicates": duplicates}

        if path == "/queue/clear" and method == "POST":
            return 200, {"removed": queue.clear_finished()}

        match = _ITEM_ACTION.fullmatch(path)
        if method == "POST" and match:
            item_id, action = match.groups()
            try:
                item = queue.cancel(item_id) if action == "cancel" else queue.retry(item_id)
            except KeyError:
                raise ApiError(404, "item não encontrado") from None
            except ValueError as exc:
                raise ApiError(409, str(exc)) from None
            return 200, item

        if method == "POST" and path == "/open-folder":
            actions.open_folder()
            return 200, {"ok": True}

        if method == "POST" and path == "/update-ytdlp":
            try:
                return 200, actions.update_ytdlp()
            except Exception as exc:
                log.warning("atualização falhou: %s", exc)
                raise ApiError(502, f"Falha ao atualizar: {exc}") from None

        raise ApiError(404, "rota não encontrada")

    def _json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "corpo inválido") from None
        if length > MAX_BODY:
            raise ApiError(413, "corpo grande demais")
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError):
            raise ApiError(400, "JSON inválido") from None
        if not isinstance(data, dict):
            raise ApiError(400, "JSON inválido")
        return data
