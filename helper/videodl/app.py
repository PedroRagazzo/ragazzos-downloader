"""Ponto de entrada: sobe a fila, a API e o ícone da bandeja."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, TypeVar

from . import __version__, paths
from .downloader import YtDlpDownloader
from .queue import DownloadQueue
from .server import ApiServer
from .updater import Updater

PORT = 47321
HELPER_DIR = Path(__file__).resolve().parent.parent
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
log = logging.getLogger("videodl")
T = TypeVar("T")


def start_server_with_retry(factory: Callable[[], T], attempts: int, delay: float = 0.5,
                            sleep: Callable[[float], None] = time.sleep) -> T | None:
    for n in range(attempts):
        try:
            return factory()
        except OSError as exc:
            log.info("porta %d ocupada (%s), tentativa %d/%d", PORT, exc, n + 1, attempts)
            if n + 1 < attempts:
                sleep(delay)
    return None


def update_when_idle(queue, updater, *, sleep: Callable[[float], None] = time.sleep,
                     poll: float = 0.5) -> tuple[bool, str]:
    """Atualiza o yt-dlp sem downloads rodando: o pip trocar arquivos no meio de um download o quebraria.

    Se a versão mudou, a fila fica pausada (o programa vai reiniciar); senão, volta ao normal.
    """
    queue.pause()
    try:
        while queue.active_count() > 0:
            sleep(poll)
        changed, version = updater.update()
    except BaseException:
        queue.resume()
        raise
    if not changed:
        queue.resume()
    return changed, version


UPDATE_CHECK_INTERVAL = 3600  # confere de hora em hora se já passaram 24 h (funciona mesmo após hibernar)


def auto_update_once(updater, queue, update: Callable[[], object]) -> bool:
    """Atualiza se já deu o prazo e não há download rodando (para não pausar a fila no meio do uso).

    Devolve True se tentou atualizar. Falhas só vão para o log: tenta de novo na próxima checagem.
    """
    if not updater.due() or queue.active_count() > 0:
        return False
    try:
        update()
    except Exception:
        log.exception("atualização periódica do yt-dlp falhou")
    return True


def auto_update_loop(check: Callable[[], object], stop, interval: float = UPDATE_CHECK_INTERVAL) -> None:
    while not stop.wait(interval):
        check()


RESTART_FAILED = ("Não consegui reiniciar depois de atualizar o yt-dlp. "
                  "A versão nova vale na próxima vez que o programa abrir.")


def restart_when_idle(queue, spawn: Callable[[], None], shutdown: Callable[[], None],
                      on_failure: Callable[[], None], *, sleep: Callable[[float], None] = time.sleep,
                      poll: float = 2.0) -> bool:
    """Espera a fila parar, abre a cópia nova e encerra esta. Se não conseguir abrir, segue rodando com a fila solta."""
    while queue.active_count() > 0:
        sleep(poll)
    log.info("reiniciando para carregar a nova versão do yt-dlp")
    try:
        spawn()
    except Exception:
        log.exception("não consegui reiniciar o programa; seguindo com a versão atual")
        queue.resume()  # sem isso a fila ficaria pausada para sempre
        on_failure()
        return False
    shutdown()
    return True


def _ytdlp_version() -> str | None:
    try:
        from yt_dlp.version import __version__ as version
    except Exception:
        return None
    return version


class AppActions:
    def __init__(self, downloader, updater, download_dir: Path, request_restart: Callable[[], None], queue=None):
        self._downloader = downloader
        self._updater = updater
        self._dir = Path(download_dir)
        self._request_restart = request_restart
        self._queue = queue
        self._update_lock = threading.Lock()  # automática, popup e bandeja nunca rodam o pip ao mesmo tempo

    def status(self) -> dict:
        return {
            "ok": True,
            "version": __version__,
            "ytdlp_version": _ytdlp_version(),
            "ffmpeg": shutil.which("ffmpeg") is not None,
        }

    def info(self, url: str) -> dict:
        return self._downloader.get_info(url)

    def open_folder(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self._dir)  # type: ignore[attr-defined]  # só existe no Windows

    def update_ytdlp(self) -> dict:
        with self._update_lock:
            if self._queue is not None:
                changed, version = update_when_idle(self._queue, self._updater)
            else:
                changed, version = self._updater.update()
        if changed:
            self._request_restart()
        return {"ok": True, "version": version, "restarting": changed}


class App:
    def __init__(self, wait_for_port: bool):
        self._wait_for_port = wait_for_port
        self._restarting = threading.Event()
        self._stopping = threading.Event()
        self.icon = None

    def run(self) -> int:
        app_dir = paths.app_dir()
        app_dir.mkdir(parents=True, exist_ok=True)
        download_dir = paths.download_dir()
        node = "node" if shutil.which("node") else None
        if node is None:
            log.warning("Node não encontrado: downloads do YouTube podem falhar")
        downloader = YtDlpDownloader(download_dir, js_runtime=node)
        self.queue = DownloadQueue(app_dir / "queue.json", downloader)
        self.updater = Updater(app_dir / "update.json")
        self.actions = AppActions(downloader, self.updater, download_dir, self.request_restart, queue=self.queue)
        origin = paths.extension_origin()

        self.server = start_server_with_retry(
            lambda: ApiServer(("127.0.0.1", PORT), self.queue, self.actions, origin),
            attempts=20 if self._wait_for_port else 1,
        )
        if self.server is None:
            log.info("outra instância já está rodando; saindo")
            return 0

        self.queue.start()
        threading.Thread(target=self.server.serve_forever, name="api", daemon=True).start()
        threading.Thread(target=self._auto_update, name="auto-update", daemon=True).start()
        threading.Thread(target=auto_update_loop, args=(self._periodic_update, self._stopping),
                         name="auto-update-loop", daemon=True).start()
        log.info("Ragazzo's Downloader %s ouvindo em 127.0.0.1:%d", __version__, PORT)

        from .tray import build_icon  # import tardio: pystray só é necessário aqui

        self.icon = build_icon(self.actions, on_quit=self.shutdown, on_update=self._tray_update)
        self.icon.run()
        return 0

    def shutdown(self) -> None:
        log.info("encerrando")
        self._stopping.set()
        self.server.shutdown()
        self.server.server_close()
        self.queue.stop()
        if self.icon is not None:
            self.icon.stop()

    def request_restart(self) -> None:
        if self._restarting.is_set():
            return
        self._restarting.set()
        self.queue.pause()
        threading.Thread(target=self._restart_when_idle, name="restart", daemon=True).start()

    def _restart_when_idle(self) -> None:
        def spawn() -> None:
            subprocess.Popen([sys.executable, "-m", "videodl", "--wait-for-port"],
                             cwd=HELPER_DIR, creationflags=_NO_WINDOW)

        def failed() -> None:
            self._restarting.clear()  # deixa tentar de novo numa próxima atualização
            if self.icon is not None:
                self.icon.notify(RESTART_FAILED, "Ragazzo's Downloader")

        restart_when_idle(self.queue, spawn, self.shutdown, failed)

    def _auto_update(self) -> None:
        if not self.updater.due():
            return
        try:
            result = self.actions.update_ytdlp()  # espera a fila ficar parada e pede reinício se mudou
        except Exception:
            log.exception("atualização automática do yt-dlp falhou")
            return
        log.info("yt-dlp verificado: %s (mudou: %s)", result["version"], result["restarting"])

    def _periodic_update(self) -> None:
        if self._restarting.is_set():
            return
        auto_update_once(self.updater, self.queue, self._log_update)

    def _log_update(self) -> None:
        result = self.actions.update_ytdlp()
        log.info("yt-dlp verificado (periódico): %s (mudou: %s)", result["version"], result["restarting"])

    def _tray_update(self) -> None:
        def work() -> None:
            try:
                result = self.actions.update_ytdlp()
                message = f"yt-dlp {result['version']}" + (" — reiniciando" if result["restarting"] else " — já está atualizado")
            except Exception as exc:
                message = f"Falha ao atualizar: {exc}"
            if self.icon is not None:
                self.icon.notify(message, "Ragazzo's Downloader")

        threading.Thread(target=work, name="tray-update", daemon=True).start()


def _fix_std_streams() -> None:
    # pythonw não tem console: sys.stdout/stderr são None
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _setup_logging(app_dir: Path) -> None:
    app_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(app_dir / "log.txt", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videodl")
    parser.add_argument("--wait-for-port", action="store_true", help="espera a porta liberar (usado ao reiniciar)")
    args = parser.parse_args(argv)
    _fix_std_streams()
    _setup_logging(paths.app_dir())
    try:
        return App(args.wait_for_port).run()
    except Exception:
        log.exception("falha fatal")
        return 1
