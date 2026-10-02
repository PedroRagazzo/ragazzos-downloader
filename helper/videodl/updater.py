"""Atualiza o yt-dlp via pip, no máximo uma vez por dia."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class UpdateError(Exception):
    """pip falhou ao atualizar o yt-dlp."""


def _console_python() -> str:
    exe = Path(sys.executable)
    candidate = exe.with_name("python.exe")
    return str(candidate if candidate.exists() else exe)


class Updater:
    INTERVAL = 24 * 3600

    def __init__(self, state_path: Path, *, python: str | None = None,
                 run: Callable = subprocess.run, clock: Callable[[], float] = time.time):
        self._state_path = Path(state_path)
        self._python = python or _console_python()
        self._run = run
        self._clock = clock

    def due(self) -> bool:
        try:
            last = float(json.loads(self._state_path.read_text(encoding="utf-8"))["last_update"])
        except (FileNotFoundError, ValueError, KeyError, TypeError):
            return True
        return self._clock() - last >= self.INTERVAL

    def installed_version(self) -> str:
        result = self._run(
            [self._python, "-c", "import yt_dlp.version as v; print(v.__version__)"],
            capture_output=True, text=True, timeout=60, creationflags=_NO_WINDOW,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def update(self) -> tuple[bool, str]:
        before = self.installed_version()
        try:
            result = self._run(
                [self._python, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "yt-dlp[default]"],
                capture_output=True, text=True, timeout=600, creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            raise UpdateError("o pip demorou demais") from None
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "").strip()[-500:]
            raise UpdateError(message or f"pip saiu com código {result.returncode}")
        after = self.installed_version()
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps({"last_update": self._clock(), "version": after}), encoding="utf-8")
        return after != before, after
