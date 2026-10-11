"""Integração com o yt-dlp: baixa um item da fila e busca informações de um link."""

from __future__ import annotations

import glob
import logging
import os
import re
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


_PARTIAL = re.compile(r"\.(f[\w-]+\.\w+|\w+\.part|part|ytdl|temp\.\w+)(\.part.*|\.ytdl)?$|\.part-Frag\d+")


def _is_partial(name: str, base: str) -> bool:
    """Arquivo temporário do yt-dlp (fragmento, .part, .ytdl, .temp), não um arquivo pronto."""
    return bool(_PARTIAL.search(name[len(base):]))


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
            # consulta leve: título e miniatura sem resolver os formatos do vídeo
            info = ydl.extract_info(url, download=False, process=False)
            if info.get("_type", "video") != "video" or not info.get("title"):
                # link curto/redirecionamento ou lista: só a consulta completa traz o vídeo de fato
                info = _single_entry(ydl.extract_info(url, download=False))
        return {"title": info.get("title") or url, "thumbnail": info.get("thumbnail"), "site": site_tag(_site_of(info))}

    def __call__(self, item: Item, report: Callable[[dict], None], is_cancelled: Callable[[], bool]) -> str:
        self._dir.mkdir(parents=True, exist_ok=True)
        ext = final_extension(item.mode, item.ext)

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
            **build_format_opts(item.mode, item.quality, item.ext),
            # o nome só se conhece depois de extrair: vai no campo vdl_base do próprio info
            "outtmpl": {"default": os.path.join(str(self._dir).replace("%", "%%"), "%(vdl_base)s.%(ext)s")},
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
        }
        # Uma só instância e uma só consulta ao site: extrair aqui e baixar em outra instância dá 403 no YouTube.
        with self._factory(opts) as ydl:
            info = _single_entry(ydl.extract_info(item.url, download=False))
            if is_cancelled():
                raise Cancelled()
            report({"title": info.get("title") or item.url})

            resuming = bool(item.base) and not (self._dir / f"{item.base}.{ext}").exists()
            if resuming:
                base = self._reserve_saved(item.base, ext)  # retomada: mesmo nome, o yt-dlp continua o .part
            else:
                base = self._reserve(build_base_name(info.get("title"), _site_of(info)), ext)
            # o que já existia com esse nome não é deste download e nunca é apagado na limpeza;
            # na retomada, os parciais da vez anterior são deste item e podem ir embora
            existing = {p for p in self._files_named(base) if not (resuming and _is_partial(p.name, base))}
            report({"base": base})
            target = self._dir / f"{base}.{ext}"
            try:
                info["vdl_base"] = base
                ydl.process_ie_result(info, download=True)
                if not target.exists():
                    raise RuntimeError(f"arquivo final não encontrado: {target.name}")
                return str(target)
            except BaseException:
                self._cleanup(base, existing)
                if is_cancelled():
                    raise Cancelled() from None
                raise
            finally:
                self._release(base)

    def _reserve(self, wanted: str, ext: str) -> str:
        with self._lock:
            base = unique_base(self._dir, wanted, ext, taken=self._reserved)
            self._reserved.add(base)
            return base

    def _reserve_saved(self, saved: str, ext: str) -> str:
        with self._lock:
            if saved in self._reserved:  # outro download ativo já usa esse nome
                saved = unique_base(self._dir, saved, ext, taken=self._reserved)
            self._reserved.add(saved)
            return saved

    def _release(self, base: str) -> None:
        with self._lock:
            self._reserved.discard(base)

    def _files_named(self, base: str) -> set[Path]:
        return set(self._dir.glob(glob.escape(base) + ".*"))

    def _cleanup(self, base: str, existing: set[Path]) -> None:
        # apaga só o que este download criou (ex.: "X.mp3" já existente fica ao cancelar o "X.mp4")
        for path in self._files_named(base) - existing:
            try:
                path.unlink()
            except OSError:
                log.warning("não consegui apagar o arquivo parcial %s", path)
