"""Fila de downloads: estado, persistência em JSON e workers."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Callable

from .errors import ErrorInfo, classify_error
from .formats import final_extension, validate

log = logging.getLogger(__name__)

WAITING = "waiting"
DOWNLOADING = "downloading"
CONVERTING = "converting"
DONE = "done"
ERROR = "error"
CANCELLED = "cancelled"
RUNNING = (DOWNLOADING, CONVERTING)
ACTIVE = (WAITING, *RUNNING)


class Cancelled(Exception):
    """Levantada pelo downloader quando o item foi cancelado."""


@dataclass
class Item:
    id: str
    url: str
    mode: str
    quality: str
    status: str = WAITING
    title: str | None = None
    progress: float = 0.0
    speed: float | None = None
    filename: str | None = None
    error_code: str | None = None
    error_short: str | None = None
    error_detail: str | None = None
    created_at: float = 0.0
    finished_at: float | None = None
    base: str | None = None  # nome do arquivo sem extensão; permite retomar o .part após reiniciar
    ext: str | None = None  # formato do arquivo final (mp4, mkv, mov, mp3, wav, flac)

    def to_dict(self) -> dict:
        return asdict(self)


_FIELDS = {f.name for f in fields(Item)}

_IO_RETRIES = 5
_IO_DELAY = 0.1


def _with_retries(action: Callable[[], object]):
    # no Windows, antivírus e backup seguram arquivos por instantes (PermissionError)
    for attempt in range(_IO_RETRIES):
        try:
            return action()
        except PermissionError:
            if attempt == _IO_RETRIES - 1:
                raise
            time.sleep(_IO_DELAY)

Report = Callable[[dict], None]
Downloader = Callable[[Item, Report, Callable[[], bool]], str]


class DownloadQueue:
    def __init__(
        self,
        store_path: Path,
        downloader: Downloader,
        *,
        max_workers: int = 2,
        history_limit: int = 50,
        retry_delays: tuple[float, ...] = (5, 15),
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ):
        self._store_path = Path(store_path)
        self._downloader = downloader
        self._max_workers = max_workers
        self._history_limit = history_limit
        self._retry_delays = tuple(retry_delays)
        self._sleep = sleep
        self._clock = clock
        self._cond = threading.Condition()
        self._cancel_requested: set[str] = set()
        self._stopping = False
        self._paused = False
        self._workers: list[threading.Thread] = []
        self._items: list[Item] = self._load()

    # ---- API pública ----

    def add(self, urls: list[str], mode: str, quality: str, ext: str | None = None) -> tuple[list[str], int]:
        validate(mode, quality, ext)
        ext = final_extension(mode, ext)
        added: list[str] = []
        duplicates = 0
        with self._cond:
            for url in urls:
                if self._has_active_duplicate(url, mode, quality, ext):
                    duplicates += 1
                    continue
                item = Item(id=uuid.uuid4().hex[:12], url=url, mode=mode, quality=quality, ext=ext,
                            created_at=self._clock())
                self._items.append(item)
                added.append(item.id)
            if added:
                self._save()
                self._cond.notify_all()
        return added, duplicates

    def list(self) -> list[dict]:
        with self._cond:
            return [item.to_dict() for item in self._items]

    def cancel(self, item_id: str) -> dict:
        with self._cond:
            item = self._find(item_id)
            if item.status == WAITING:
                self._finish(item, CANCELLED)
            elif item.status in RUNNING:
                self._cancel_requested.add(item_id)
            return item.to_dict()

    def retry(self, item_id: str) -> dict:
        with self._cond:
            item = self._find(item_id)
            if item.status not in (ERROR, CANCELLED):
                raise ValueError("só dá para tentar de novo itens com erro ou cancelados")
            self._items.remove(item)
            self._items.append(item)
            item.status = WAITING
            item.progress = 0.0
            item.speed = None
            item.filename = None
            item.base = None  # parciais já foram apagados no erro/cancelamento
            item.error_code = item.error_short = item.error_detail = None
            item.finished_at = None
            item.created_at = self._clock()
            self._save()
            self._cond.notify_all()
            return item.to_dict()

    def clear_finished(self) -> int:
        """Tira da lista os itens concluídos, com erro ou cancelados. Não apaga arquivos baixados."""
        with self._cond:
            before = len(self._items)
            self._items = [i for i in self._items if i.status in ACTIVE]
            removed = before - len(self._items)
            if removed:
                self._save()
            return removed

    def active_count(self) -> int:
        with self._cond:
            return sum(1 for item in self._items if item.status in RUNNING)

    # ---- internos (chamar com self._cond adquirido) ----

    def _find(self, item_id: str) -> Item:
        for item in self._items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    def _has_active_duplicate(self, url: str, mode: str, quality: str, ext: str) -> bool:
        return any(
            i.url == url and i.mode == mode and i.quality == quality and i.ext == ext and i.status in ACTIVE
            for i in self._items
        )

    def _finish(self, item: Item, status: str) -> None:
        item.status = status
        item.speed = None
        item.finished_at = self._clock()
        self._trim_history()
        self._save()
        self._cond.notify_all()

    def _trim_history(self) -> None:
        finished = [i for i in self._items if i.status not in ACTIVE]
        excess = len(finished) - self._history_limit
        if excess > 0:
            oldest = sorted(finished, key=lambda i: i.finished_at or 0.0)[:excess]
            drop = {i.id for i in oldest}
            self._items = [i for i in self._items if i.id not in drop]

    def _load(self) -> list[Item]:
        try:
            raw = json.loads(_with_retries(lambda: self._store_path.read_text(encoding="utf-8")))
            items = [Item(**{k: v for k, v in d.items() if k in _FIELDS}) for d in raw["items"]]
        except FileNotFoundError:
            return []
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            log.warning("queue.json inválido, começando com fila vazia: %s", exc)
            backup = self._store_path.with_name(self._store_path.name + ".bad")
            try:
                os.replace(self._store_path, backup)
            except OSError:
                log.exception("não consegui guardar o queue.json inválido")
            return []
        for item in items:
            item.ext = item.ext or final_extension(item.mode)  # itens de antes da escolha de formato
            if item.status in RUNNING:
                item.status = WAITING
                item.progress = 0.0
                item.speed = None
        return items

    def _save(self) -> None:
        # falhar ao gravar não pode parar os downloads: o estado continua em memória e vai no próximo save
        payload = {"items": [item.to_dict() for item in self._items]}
        tmp = self._store_path.with_name(self._store_path.name + ".tmp")
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            _with_retries(lambda: tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"))
            _with_retries(lambda: os.replace(tmp, self._store_path))
        except OSError:
            log.exception("não consegui gravar %s", self._store_path)

    # ---- workers ----

    def start(self) -> None:
        with self._cond:
            self._stopping = False
        for n in range(self._max_workers):
            worker = threading.Thread(target=self._worker, name=f"download-{n + 1}", daemon=True)
            worker.start()
            self._workers.append(worker)

    def stop(self, timeout: float = 5.0) -> None:
        with self._cond:
            self._stopping = True
            self._cond.notify_all()
        for worker in self._workers:
            worker.join(timeout)
        self._workers.clear()

    def pause(self) -> None:
        with self._cond:
            self._paused = True

    def _next_waiting(self) -> Item | None:
        if self._paused or self._stopping:
            return None
        return next((i for i in self._items if i.status == WAITING), None)

    def _worker(self) -> None:
        while True:
            with self._cond:
                item = self._next_waiting()
                while item is None:
                    if self._stopping:
                        return
                    self._cond.wait()
                    item = self._next_waiting()
                item.status = DOWNLOADING
                item.progress = 0.0
                item.error_short = None
                self._save()
            try:
                self._run(item)
            except Exception:
                log.exception("falha interna ao processar %s", item.url)
                self._on_internal_error(item)

    def _on_internal_error(self, item: Item) -> None:
        # nunca deixar um item preso como "baixando": isso travaria a fila e o reinício pós-atualização
        with self._cond:
            self._cancel_requested.discard(item.id)
            if item.status in RUNNING:
                item.status = ERROR
                item.speed = None
                item.error_code = "unknown"
                item.error_short = classify_error("").short
                item.error_detail = "erro interno do programa — veja o log"
                item.finished_at = self._clock()
            self._cond.notify_all()

    def _run(self, item: Item) -> None:
        attempts = 0
        while True:
            try:
                path = self._downloader(
                    replace(item),
                    lambda update: self._report(item, update),
                    lambda: self._is_cancelled(item.id),
                )
            except Cancelled:
                self._on_cancelled(item)
                return
            except Exception as exc:  # qualquer falha do download vira erro do item
                if self._is_cancelled(item.id):
                    self._on_cancelled(item)
                    return
                info = classify_error(str(exc))
                if info.retryable and attempts < len(self._retry_delays):
                    with self._cond:
                        item.error_short = info.short
                    self._sleep(self._retry_delays[attempts])
                    attempts += 1
                    if self._is_cancelled(item.id):
                        self._on_cancelled(item)
                        return
                    continue
                log.warning("download falhou (%s): %s", item.url, exc)
                self._on_error(item, info, str(exc))
                return
            self._on_done(item, path)
            return

    def _report(self, item: Item, update: dict) -> None:
        with self._cond:
            if item.status not in RUNNING:
                return
            changed = False
            status = update.get("status")
            if status in RUNNING and status != item.status:
                item.status = status
                changed = True
            title = update.get("title")
            if title and title != item.title:
                item.title = title
                changed = True
            base = update.get("base")
            if base and base != item.base:
                item.base = base
                changed = True
            if "progress" in update:
                item.progress = max(0.0, min(1.0, float(update["progress"] or 0.0)))
            if "speed" in update:
                item.speed = update["speed"]
            if changed:
                self._save()

    def _is_cancelled(self, item_id: str) -> bool:
        with self._cond:
            return item_id in self._cancel_requested or self._stopping

    def _on_cancelled(self, item: Item) -> None:
        with self._cond:
            requested = item.id in self._cancel_requested
            self._cancel_requested.discard(item.id)
            if self._stopping and not requested:
                return  # o programa está fechando: o item volta como "aguardando" na próxima abertura
            self._finish(item, CANCELLED)

    def _on_error(self, item: Item, info: ErrorInfo, detail: str) -> None:
        with self._cond:
            item.error_code = info.code
            item.error_short = info.short
            item.error_detail = detail
            self._finish(item, ERROR)

    def _on_done(self, item: Item, path: str) -> None:
        with self._cond:
            self._cancel_requested.discard(item.id)
            item.filename = path
            item.progress = 1.0
            item.error_code = item.error_short = item.error_detail = None
            self._finish(item, DONE)
