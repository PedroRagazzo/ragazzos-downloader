import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from videodl.queue import DownloadQueue
from videodl.server import ApiServer

ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"


class FakeActions:
    def __init__(self):
        self.opened = 0
        self.info_error = None
        self.update_error = None

    def status(self):
        return {"ok": True, "version": "0.1.0", "ytdlp_version": "2026.09.01", "ffmpeg": True}

    def info(self, url):
        if self.info_error:
            raise self.info_error
        return {"title": "Um vídeo", "thumbnail": None, "site": "youtube"}

    def open_folder(self):
        self.opened += 1

    def update_ytdlp(self):
        if self.update_error:
            raise self.update_error
        return {"ok": True, "version": "2026.10.01", "restarting": False}


@pytest.fixture
def api(tmp_path):
    queue = DownloadQueue(tmp_path / "queue.json", downloader=lambda item, report, is_cancelled: "")
    actions = FakeActions()
    server = ApiServer(("127.0.0.1", 0), queue, actions, ORIGIN)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(method, path, body=None, origin=ORIGIN, raw=None, marker=True):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(base + path, data=data, method=method)
        if origin:
            req.add_header("Origin", origin)
        if marker and method != "OPTIONS":
            req.add_header("X-Video-Downloader", "1")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with opener.open(req, timeout=5) as res:
                payload = res.read()
                return res.status, (json.loads(payload) if payload else None), res.headers
        except urllib.error.HTTPError as err:
            payload = err.read()
            return err.code, (json.loads(payload) if payload else None), err.headers

    yield SimpleNamespace(call=call, queue=queue, actions=actions, server=server)
    server.shutdown()
    server.server_close()


def test_rejects_foreign_origin_even_with_marker(api):
    assert api.call("GET", "/status", origin="https://evil.example")[0] == 403
    assert api.call("POST", "/queue", {"urls": ["https://youtu.be/a"], "mode": "video", "quality": "best"},
                    origin="https://evil.example")[0] == 403
    assert api.queue.list() == []


def test_rejects_requests_without_extension_marker(api):
    # um site não consegue mandar cabeçalho próprio sem preflight, e o preflight exige a origem da extensão
    assert api.call("GET", "/status", origin=None, marker=False)[0] == 403
    assert api.call("GET", "/status", marker=False)[0] == 403
    assert api.call("POST", "/queue", {"urls": ["https://youtu.be/a"], "mode": "video", "quality": "best"},
                    origin=None, marker=False)[0] == 403
    assert api.queue.list() == []


def test_accepts_extension_get_without_origin(api):
    # o Brave não manda Origin nos GET de extensão com host_permissions
    status, body, _ = api.call("GET", "/status", origin=None)
    assert status == 200 and body["ok"] is True


def test_rejected_origin_is_logged(api, caplog):
    with caplog.at_level("WARNING", logger="videodl.server"):
        api.call("GET", "/status", origin="chrome-extension://outroid")
        api.call("OPTIONS", "/queue", origin=None)
    assert "chrome-extension://outroid" in caplog.text
    assert "OPTIONS /queue" in caplog.text


def test_preflight(api):
    status, _, headers = api.call("OPTIONS", "/queue")
    assert status == 204
    assert headers["Access-Control-Allow-Origin"] == ORIGIN
    assert "POST" in headers["Access-Control-Allow-Methods"]
    assert "X-Video-Downloader" in headers["Access-Control-Allow-Headers"]
    assert api.call("OPTIONS", "/queue", origin="https://evil.example")[0] == 403


def test_status_has_cors_header(api):
    status, body, headers = api.call("GET", "/status")
    assert status == 200 and body["ffmpeg"] is True
    assert headers["Access-Control-Allow-Origin"] == ORIGIN


def test_add_and_list_queue(api):
    status, body, _ = api.call("POST", "/queue", {"urls": ["https://youtu.be/a", "https://youtu.be/a"],
                                                   "mode": "video", "quality": "720"})
    assert status == 200 and len(body["added"]) == 1 and body["duplicates"] == 1
    status, body, _ = api.call("GET", "/queue")
    assert status == 200 and [i["url"] for i in body["items"]] == ["https://youtu.be/a"]


@pytest.mark.parametrize("payload", [
    {"urls": ["ftp://x"], "mode": "video", "quality": "best"},
    {"urls": "https://youtu.be/a", "mode": "video", "quality": "best"},
    {"urls": [], "mode": "video", "quality": "best"},
    {"urls": ["https://youtu.be/a"], "mode": "video", "quality": "320"},
])
def test_add_rejects_bad_input(api, payload):
    status, body, _ = api.call("POST", "/queue", payload)
    assert status == 400 and body["error"]


def test_add_rejects_invalid_json(api):
    assert api.call("POST", "/queue", raw=b"{nao json")[0] == 400


def test_cancel_and_retry(api):
    [item_id], _ = api.queue.add(["https://youtu.be/a"], "video", "best")
    assert api.call("POST", f"/queue/{item_id}/retry")[0] == 409
    status, body, _ = api.call("POST", f"/queue/{item_id}/cancel")
    assert status == 200 and body["status"] == "cancelled"
    status, body, _ = api.call("POST", f"/queue/{item_id}/retry")
    assert status == 200 and body["status"] == "waiting"
    assert api.call("POST", "/queue/nao-existe/cancel")[0] == 404


def test_info(api):
    status, body, _ = api.call("GET", "/info?url=https%3A%2F%2Fyoutu.be%2Fa")
    assert status == 200 and body["title"] == "Um vídeo"
    assert api.call("GET", "/info")[0] == 400


def test_info_error_is_translated(api):
    api.actions.info_error = RuntimeError("ERROR: Unsupported URL: https://example.com")
    status, body, _ = api.call("GET", "/info?url=https%3A%2F%2Fexample.com")
    assert status == 422 and body["error"] == "Esse link não tem vídeo suportado"


def test_open_folder_and_update(api):
    assert api.call("POST", "/open-folder")[0] == 200
    assert api.actions.opened == 1
    status, body, _ = api.call("POST", "/update-ytdlp")
    assert status == 200 and body["version"] == "2026.10.01"


def test_update_failure_returns_message(api):
    api.actions.update_error = RuntimeError("sem internet")
    status, body, _ = api.call("POST", "/update-ytdlp")
    assert status == 502 and "sem internet" in body["error"]


def test_unknown_route(api):
    assert api.call("GET", "/nada")[0] == 404


def test_second_server_on_same_port_fails(api):
    port = api.server.server_address[1]
    with pytest.raises(OSError):
        ApiServer(("127.0.0.1", port), api.queue, api.actions, ORIGIN)


def test_clear_finished_endpoint(api):
    [done_like, waiting], _ = api.queue.add(["https://youtu.be/a", "https://youtu.be/b"], "video", "best")
    api.queue.cancel(done_like)
    status, body, _ = api.call("POST", "/queue/clear")
    assert status == 200 and body == {"removed": 1}
    assert [i["id"] for i in api.queue.list()] == [waiting]


def test_clear_finished_endpoint_rejects_requests_from_outside(api):
    [item_id], _ = api.queue.add(["https://youtu.be/a"], "video", "best")
    api.queue.cancel(item_id)
    assert api.call("POST", "/queue/clear", origin="https://evil.example")[0] == 403
    assert api.call("POST", "/queue/clear", origin=None, marker=False)[0] == 403
    assert len(api.queue.list()) == 1


def test_add_with_format(api):
    status, body, _ = api.call("POST", "/queue", {"urls": ["https://youtu.be/a"], "mode": "audio", "quality": "320", "ext": "flac"})
    assert status == 200 and len(body["added"]) == 1
    assert api.queue.list()[0]["ext"] == "flac"


def test_add_without_format_uses_default(api):
    api.call("POST", "/queue", {"urls": ["https://youtu.be/a"], "mode": "video", "quality": "best"})
    assert api.queue.list()[0]["ext"] == "mp4"


def test_add_rejects_invalid_format(api):
    status, body, _ = api.call("POST", "/queue", {"urls": ["https://youtu.be/a"], "mode": "video", "quality": "best", "ext": "exe"})
    assert status == 400 and body["error"]
    assert api.queue.list() == []
