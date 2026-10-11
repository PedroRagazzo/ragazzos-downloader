import pytest

from videodl.app import AppActions, start_server_with_retry, update_when_idle
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


class FakeQueue:
    def __init__(self, active_counts):
        self.active_counts = list(active_counts)
        self.events = []

    def pause(self):
        self.events.append("pause")

    def resume(self):
        self.events.append("resume")

    def active_count(self):
        count = self.active_counts.pop(0) if self.active_counts else 0
        self.events.append(f"active={count}")
        return count


class RecordingUpdater(FakeUpdater):
    def __init__(self, queue, **kwargs):
        super().__init__(**kwargs)
        self.queue = queue

    def update(self):
        self.queue.events.append("pip")
        return super().update()


def test_update_waits_for_running_downloads_then_resumes():
    queue = FakeQueue([2, 1, 0])
    updater = RecordingUpdater(queue, result=(False, "2026.10.01"))
    assert update_when_idle(queue, updater, sleep=lambda s: None) == (False, "2026.10.01")
    assert queue.events == ["pause", "active=2", "active=1", "active=0", "pip", "resume"]


def test_update_that_changes_version_stays_paused_for_restart():
    queue = FakeQueue([0])
    updater = RecordingUpdater(queue, result=(True, "2026.10.01"))
    update_when_idle(queue, updater, sleep=lambda s: None)
    assert queue.events == ["pause", "active=0", "pip"]


def test_failed_update_resumes_queue():
    queue = FakeQueue([0])
    updater = RecordingUpdater(queue, error=UpdateError("sem internet"))
    with pytest.raises(UpdateError):
        update_when_idle(queue, updater, sleep=lambda s: None)
    assert queue.events[-1] == "resume"


def test_app_actions_update_goes_through_the_queue(tmp_path):
    queue = FakeQueue([0])
    actions = AppActions(None, RecordingUpdater(queue, result=(False, "v")), tmp_path, lambda: None, queue=queue)
    actions.update_ytdlp()
    assert queue.events == ["pause", "active=0", "pip", "resume"]
