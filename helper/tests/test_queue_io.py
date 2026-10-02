"""Arquivo da fila travado por antivírus/backup (PermissionError no Windows) não pode travar a fila."""

import os
import pathlib
import threading
import time

import pytest

from videodl import queue as queue_module
from videodl.queue import DownloadQueue

REAL_REPLACE = os.replace
REAL_READ_TEXT = pathlib.Path.read_text


@pytest.fixture(autouse=True)
def no_io_delay(monkeypatch):
    monkeypatch.setattr(queue_module, "_IO_DELAY", 0, raising=False)


def wait_for(predicate, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condição não atingida a tempo")


def test_transient_lock_on_save_is_retried(tmp_path, monkeypatch):
    failures = {"left": 2}

    def flaky_replace(src, dst):
        if failures["left"]:
            failures["left"] -= 1
            raise PermissionError(13, "Access is denied")
        return REAL_REPLACE(src, dst)

    monkeypatch.setattr(queue_module.os, "replace", flaky_replace)
    q = DownloadQueue(tmp_path / "queue.json", lambda item, report, is_cancelled: "x.mp4")
    q.add(["https://youtu.be/a"], "video", "best")
    monkeypatch.setattr(queue_module.os, "replace", REAL_REPLACE)
    assert [i["url"] for i in DownloadQueue(tmp_path / "queue.json", lambda *a: "").list()] == ["https://youtu.be/a"]


def test_permanent_lock_on_save_does_not_stop_downloads(tmp_path, monkeypatch):
    def locked_replace(src, dst):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(queue_module.os, "replace", locked_replace)
    q = DownloadQueue(tmp_path / "queue.json", lambda item, report, is_cancelled: "x.mp4")
    q.start()
    try:
        ids, _ = q.add(["https://youtu.be/a", "https://youtu.be/b", "https://youtu.be/c"], "video", "best")
        assert len(ids) == 3
        wait_for(lambda: all(i["status"] == "done" for i in q.list()))
        assert q.active_count() == 0
    finally:
        q.stop()


def test_internal_failure_after_download_does_not_kill_worker(tmp_path, monkeypatch):
    q = DownloadQueue(tmp_path / "queue.json", lambda item, report, is_cancelled: "x.mp4", max_workers=1)
    real_trim = q._trim_history
    calls = {"n": 0}

    def trim_failing_once():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("falha interna simulada")
        real_trim()

    monkeypatch.setattr(q, "_trim_history", trim_failing_once)
    q.start()
    try:
        ids, _ = q.add(["https://youtu.be/a", "https://youtu.be/b"], "video", "best")
        wait_for(lambda: {i["id"]: i["status"] for i in q.list()}.get(ids[1]) == "done")
        assert q.active_count() == 0
    finally:
        q.stop()


def test_internal_failure_while_running_marks_item_as_error(tmp_path, monkeypatch):
    q = DownloadQueue(tmp_path / "queue.json", lambda item, report, is_cancelled: "x.mp4", max_workers=1)
    real_on_done = q._on_done
    calls = {"n": 0}

    def on_done_failing_once(item, path):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("falha interna simulada")
        real_on_done(item, path)

    monkeypatch.setattr(q, "_on_done", on_done_failing_once)
    q.start()
    try:
        ids, _ = q.add(["https://youtu.be/a", "https://youtu.be/b"], "video", "best")
        wait_for(lambda: {i["id"]: i["status"] for i in q.list()}.get(ids[1]) == "done")
        first = next(i for i in q.list() if i["id"] == ids[0])
        assert first["status"] == "error" and first["error_code"] == "unknown"
    finally:
        q.stop()


def test_transient_lock_on_startup_read_is_retried(tmp_path, monkeypatch):
    DownloadQueue(tmp_path / "queue.json", lambda *a: "").add(["https://youtu.be/a"], "video", "best")
    failures = {"left": 2}
    store = tmp_path / "queue.json"

    def flaky_read_text(self, *args, **kwargs):
        if self == store and failures["left"]:
            failures["left"] -= 1
            raise PermissionError(13, "Access is denied")
        return REAL_READ_TEXT(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", flaky_read_text)
    assert [i["url"] for i in DownloadQueue(store, lambda *a: "").list()] == ["https://youtu.be/a"]
    assert not (tmp_path / "queue.json.bad").exists()
