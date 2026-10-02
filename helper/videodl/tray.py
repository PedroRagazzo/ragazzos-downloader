"""Ícone na bandeja do Windows."""

from __future__ import annotations

from typing import Callable

import pystray

from . import startup
from .icon import draw_icon


def build_icon(actions, on_quit: Callable[[], None], on_update: Callable[[], None]) -> pystray.Icon:
    def toggle_startup(icon, item) -> None:
        if startup.is_enabled():
            startup.disable()
        else:
            startup.enable()

    menu = pystray.Menu(
        pystray.MenuItem("Abrir pasta", lambda icon, item: actions.open_folder(), default=True),
        pystray.MenuItem("Atualizar yt-dlp", lambda icon, item: on_update()),
        pystray.MenuItem("Iniciar com o Windows", toggle_startup, checked=lambda item: startup.is_enabled()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", lambda icon, item: on_quit()),
    )
    return pystray.Icon("video-downloader", draw_icon(64), "Ragazzo's Downloader", menu)
