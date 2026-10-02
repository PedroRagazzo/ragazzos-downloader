import pytest

from videodl.app import AppActions, start_server_with_retry
from videodl.icon import draw_icon
from videodl.updater import UpdateError


def test_retry_returns_server_when_port_frees():
    attempts = []

    def factory():
        attempts.append(1)
        if len(attempts) < 3:
            raise OSError("porta ocupada")
        return "server"

    assert start_server_with_retry(factory, attempts=5, sleep=lambda s: None) == "server"
    assert len(attempts) == 3


def test_retry_gives_up_when_another_instance_holds_port():
    attempts = []

    def factory():
        attempts.append(1)
        raise OSError("porta ocupada")

    assert start_server_with_retry(factory, attempts=1, sleep=lambda s: None) is None
    assert len(attempts) == 1


class FakeUpdater:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def update(self):
        if self.error:
            raise self.error
        return self.result


def test_status_reports_missing_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr("videodl.app.shutil.which", lambda name: None)
    status = AppActions(None, FakeUpdater(), tmp_path, lambda: None).status()
    assert status["ok"] is True and status["ffmpeg"] is False and status["version"] == "0.1.0"


def test_update_requests_restart_when_version_changes(tmp_path):
    restarts = []
    actions = AppActions(None, FakeUpdater((True, "2026.10.01")), tmp_path, lambda: restarts.append(1))
    assert actions.update_ytdlp() == {"ok": True, "version": "2026.10.01", "restarting": True}
    assert restarts == [1]


def test_update_without_change_does_not_restart(tmp_path):
    restarts = []
    actions = AppActions(None, FakeUpdater((False, "2026.10.01")), tmp_path, lambda: restarts.append(1))
    assert actions.update_ytdlp()["restarting"] is False
    assert restarts == []


def test_update_failure_propagates(tmp_path):
    actions = AppActions(None, FakeUpdater(error=UpdateError("sem internet")), tmp_path, lambda: None)
    with pytest.raises(UpdateError):
        actions.update_ytdlp()


def test_icon_has_requested_size():
    image = draw_icon(16)
    assert image.size == (16, 16) and image.mode == "RGBA"
