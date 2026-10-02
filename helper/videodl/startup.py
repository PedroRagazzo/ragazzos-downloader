"""Atalhos do Windows: menu Iniciar e pasta Inicializar (abrir com o Windows)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

SHORTCUT_NAME = "Video Downloader.lnk"
HELPER_DIR = Path(__file__).resolve().parent.parent
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _programs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def startup_shortcut() -> Path:
    return _programs_dir() / "Startup" / SHORTCUT_NAME


def start_menu_shortcut() -> Path:
    return _programs_dir() / SHORTCUT_NAME


def _pythonw() -> Path:
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return candidate if candidate.exists() else exe


def _ps_quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def create_shortcut(link: Path, run: Callable = subprocess.run) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({_ps_quote(link)});"
        f"$s.TargetPath = {_ps_quote(_pythonw())};"
        "$s.Arguments = '-m videodl';"
        f"$s.WorkingDirectory = {_ps_quote(HELPER_DIR)};"
        "$s.Description = 'Vídeo Downloader';"
        "$s.Save()"
    )
    run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True, capture_output=True, creationflags=_NO_WINDOW)


def is_enabled() -> bool:
    return startup_shortcut().exists()


def enable(run: Callable = subprocess.run) -> None:
    create_shortcut(startup_shortcut(), run)


def disable() -> None:
    startup_shortcut().unlink(missing_ok=True)


def install_shortcuts(run: Callable = subprocess.run) -> None:
    create_shortcut(start_menu_shortcut(), run)
    enable(run)
