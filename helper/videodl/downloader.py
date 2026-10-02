"""Integração com o yt-dlp: baixa um item da fila e busca informações de um link."""

from __future__ import annotations

import glob
import logging
import threading
from pathlib import Path
from typing import Callable

from .filenames import build_base_name, site_tag, unique_base
from .formats import build_format_opts, final_extension
from .queue import Cancelled, Item

log = logging.getLogger(__name__)


class _YtLogger:
    """Manda as mensagens do yt-dlp para o log (pythonw não tem console)."""

    def __init__(self) -> None:
        self._log = logging.getLogger("yt-dlp")

    def debug(self, msg: str) -> None:
        self._log.debug(msg)

    def info(self, msg: str) -> None:
        self._log.info(msg)

    def warning(self, msg: str) -> None:
        self._log.warning(msg)

    def error(self, msg: str) -> None:
        self._log.error(msg)


def _default_factory(params: dict):
    import yt_dlp  # import tardio: a versão nova vale após reiniciar o programa

    return yt_dlp.YoutubeDL(params)


def _single_entry(info: dict) -> dict:
    if info.get("_type") in ("playlist", "multi_video"):
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise RuntimeError("No video formats found: a lista não tem vídeos")
        return entries[0]
    return info


def _site_of(info: dict) -> str:
    return info.get("extractor_key") or info.get("extractor") or "web"


class YtDlpDownloader:
    def __init__(self, download_dir: Path, *, js_runtime: str | None = "node",
                 ydl_factory: Callable[[dict], object] = _default_factory):
        self._dir = Path(download_dir)
        self._js_runtime = js_runtime
        self._factory = ydl_factory
        self._lock = threading.Lock()
        self._reserved: set[str] = set()

    def _base_opts(self) -> dict:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "playlist_items": "1",
            "logger": _YtLogger(),
        }
        if self._js_runtime:
            opts["js_runtimes"] = {self._js_runtime: {}}
        return opts

    def get_info(self, url: str) -> dict:
        with self._factory(self._base_opts()) as ydl:
            info = _single_entry(ydl.extract_info(url, download=False))
        return {"title": info.get("title") or url, "thumbnail": info.get("thumbnail"), "site": site_tag(_site_of(info))}

    def __call__(self, item: Item, report: Callable[[dict], None], is_cancelled: Callable[[], bool]) -> str:
        self._dir.mkdir(parents=True, exist_ok=True)
        with self._factory(self._base_opts()) as ydl:
            info = _single_entry(ydl.extract_info(item.url, download=False))
        if is_cancelled():
            raise Cancelled()
        report({"title": info.get("title") or item.url})

        base = self._reserve(build_base_name(info.get("title"), _site_of(info)))
        target = self._dir / f"{base}.{final_extension(item.mode)}"

        def progress_hook(d: dict) -> None:
            if is_cancelled():
                raise Cancelled()
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                done = d.get("downloaded_bytes") or 0
                progress = min(done / total, 0.99) if total else 0.0
                report({"status": "downloading", "progress": progress, "speed": d.get("speed")})

        def postprocessor_hook(d: dict) -> None:
            if is_cancelled():
                raise Cancelled()
            if d.get("status") == "started":
                report({"status": "converting"})

        opts = {
            **self._base_opts(),
            **build_format_opts(item.mode, item.quality),
            "outtmpl": {"default": str(self._dir / base).replace("%", "%%") + ".%(ext)s"},
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
        }
        try:
            with self._factory(opts) as ydl:
                ydl.process_ie_result(info, download=True)
            if not target.exists():
                raise RuntimeError(f"arquivo final não encontrado: {target.name}")
            return str(target)
        except BaseException:
            self._cleanup(base)
            if is_cancelled():
                raise Cancelled() from None
            raise
        finally:
            self._release(base)

    def _reserve(self, wanted: str) -> str:
        with self._lock:
            base = unique_base(self._dir, wanted, taken=self._reserved)
            self._reserved.add(base)
            return base

    def _release(self, base: str) -> None:
        with self._lock:
            self._reserved.discard(base)

    def _cleanup(self, base: str) -> None:
        for path in self._dir.glob(glob.escape(base) + ".*"):
            try:
                path.unlink()
            except OSError:
                log.warning("não consegui apagar o arquivo parcial %s", path)
