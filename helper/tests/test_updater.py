import json
from types import SimpleNamespace

import pytest

from videodl.updater import UpdateError, Updater


class FakeRun:
    def __init__(self, versions, pip_rc=0, pip_err=""):
        self.versions = list(versions)
        self.pip_rc = pip_rc
        self.pip_err = pip_err
        self.commands = []

    def __call__(self, cmd, **kwargs):
        self.commands.append(cmd)
        if "-c" in cmd:
            return SimpleNamespace(returncode=0, stdout=self.versions.pop(0) + "\n", stderr="")
        return SimpleNamespace(returncode=self.pip_rc, stdout="", stderr=self.pip_err)


def make(tmp_path, run, now=1_000_000.0):
    return Updater(tmp_path / "update.json", python="py", run=run, clock=lambda: now)


def test_due_without_state(tmp_path):
    assert make(tmp_path, FakeRun([])).due() is True


def test_not_due_right_after_update_and_due_a_day_later(tmp_path):
    make(tmp_path, FakeRun(["2026.09.01", "2026.10.01"])).update()
    assert make(tmp_path, FakeRun([]), now=1_000_000.0 + 3600).due() is False
    assert make(tmp_path, FakeRun([]), now=1_000_000.0 + 86400).due() is True


def test_corrupt_state_is_due(tmp_path):
    (tmp_path / "update.json").write_text("lixo", encoding="utf-8")
    assert make(tmp_path, FakeRun([])).due() is True


def test_update_reports_change_and_calls_pip(tmp_path):
    run = FakeRun(["2026.09.01", "2026.10.01"])
    assert make(tmp_path, run).update() == (True, "2026.10.01")
    assert ["py", "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "yt-dlp[default]"] in run.commands
    assert json.loads((tmp_path / "update.json").read_text(encoding="utf-8"))["version"] == "2026.10.01"


def test_update_without_change(tmp_path):
    assert make(tmp_path, FakeRun(["2026.10.01", "2026.10.01"])).update() == (False, "2026.10.01")


def test_pip_failure_raises_and_stays_due(tmp_path):
    updater = make(tmp_path, FakeRun(["2026.09.01"], pip_rc=1, pip_err="ERROR: sem internet"))
    with pytest.raises(UpdateError, match="sem internet"):
        updater.update()
    assert updater.due() is True
