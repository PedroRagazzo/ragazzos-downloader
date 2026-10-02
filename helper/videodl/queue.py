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
from .formats import validate

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

    def to_dict(self) -> dict:
        return asdict(self)


_FIELDS = {f.name for f in fields(Item)}

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

    def add(self, urls: list[str], mode: str, quality: str) -> tuple[list[str], int]:
        validate(mode, quality)
        added: list[str] = []
        duplicates = 0
        with self._cond:
            for url in urls:
                if self._has_active_duplicate(url, mode, quality):
                    duplicates += 1
                    continue
                item = Item(id=uuid.uuid4().hex[:12], url=url, mode=mode, quality=quality, created_at=self._clock())
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
            item.error_code = item.error_short = item.error_detail = None
            item.finished_at = None
            item.created_at = self._clock()
            self._save()
            self._cond.notify_all()
            return item.to_dict()

    def active_count(self) -> int:
        with self._cond:
            return sum(1 for item in self._items if item.status in RUNNING)

    # ---- internos (chamar com self._cond adquirido) ----

    def _find(self, item_id: str) -> Item:
        for item in self._items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    def _has_active_duplicate(self, url: str, mode: str, quality: str) -> bool:
        return any(
            i.url == url and i.mode == mode and i.quality == quality and i.status in ACTIVE
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
            raw = json.loads(self._store_path.read_text(encoding="utf-8"))
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
            if item.status in RUNNING:
                item.status = WAITING
                item.progress = 0.0
                item.speed = None
        return items

    def _save(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._store_path.with_name(self._store_path.name + ".tmp")
        payload = {"items": [item.to_dict() for item in self._items]}
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._store_path)
