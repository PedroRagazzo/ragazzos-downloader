import itertools
import json

import pytest

from videodl.formats import InvalidOptions
from videodl.queue import DownloadQueue


def make_queue(tmp_path, **kwargs):
    return DownloadQueue(tmp_path / "queue.json", downloader=lambda item, report, is_cancelled: "", **kwargs)


def test_add_creates_waiting_items(tmp_path):
    q = make_queue(tmp_path)
    added, dup = q.add(["https://youtu.be/a", "https://youtu.be/b"], "video", "720")
    assert len(added) == 2 and dup == 0
    items = q.list()
    assert [i["url"] for i in items] == ["https://youtu.be/a", "https://youtu.be/b"]
    assert all(i["status"] == "waiting" and i["mode"] == "video" and i["quality"] == "720" for i in items)


def test_duplicates_ignored_while_active(tmp_path):
    q = make_queue(tmp_path)
    q.add(["https://youtu.be/a"], "video", "720")
    added, dup = q.add(["https://youtu.be/a", "https://youtu.be/a", "https://youtu.be/b"], "video", "720")
    assert len(added) == 1 and dup == 2


def test_same_url_with_other_options_is_not_duplicate(tmp_path):
    q = make_queue(tmp_path)
    q.add(["https://youtu.be/a"], "video", "720")
    added, dup = q.add(["https://youtu.be/a"], "audio", "320")
    assert len(added) == 1 and dup == 0


def test_finished_item_does_not_block_readding(tmp_path):
    q = make_queue(tmp_path)
    [item_id], _ = q.add(["https://youtu.be/a"], "video", "best")
    q.cancel(item_id)
    added, dup = q.add(["https://youtu.be/a"], "video", "best")
    assert len(added) == 1 and dup == 0


def test_invalid_options_raise(tmp_path):
    with pytest.raises(InvalidOptions):
        make_queue(tmp_path).add(["https://youtu.be/a"], "video", "320")


def test_items_persist_between_instances(tmp_path):
    make_queue(tmp_path).add(["https://youtu.be/a"], "audio", "192")
    items = make_queue(tmp_path).list()
    assert [(i["url"], i["mode"], i["quality"]) for i in items] == [("https://youtu.be/a", "audio", "192")]


def test_running_items_resume_as_waiting(tmp_path):
    (tmp_path / "queue.json").write_text(json.dumps({"items": [{
        "id": "x1", "url": "https://youtu.be/a", "mode": "video", "quality": "best",
        "status": "downloading", "progress": 0.4, "created_at": 1.0,
    }]}), encoding="utf-8")
    [item] = make_queue(tmp_path).list()
    assert item["status"] == "waiting" and item["progress"] == 0.0


def test_corrupt_store_starts_empty_and_keeps_backup(tmp_path):
    (tmp_path / "queue.json").write_text("{nao é json", encoding="utf-8")
    assert make_queue(tmp_path).list() == []
    assert (tmp_path / "queue.json.bad").exists()


def test_empty_store_file_starts_empty(tmp_path):
    (tmp_path / "queue.json").write_text("", encoding="utf-8")
    assert make_queue(tmp_path).list() == []


def test_cancel_waiting_item(tmp_path):
    q = make_queue(tmp_path)
    [item_id], _ = q.add(["https://youtu.be/a"], "video", "best")
    item = q.cancel(item_id)
    assert item["status"] == "cancelled" and item["finished_at"] is not None


def test_cancel_unknown_raises_keyerror(tmp_path):
    with pytest.raises(KeyError):
        make_queue(tmp_path).cancel("nao-existe")


def test_retry_moves_to_end_as_waiting(tmp_path):
    q = make_queue(tmp_path)
    [a], _ = q.add(["https://youtu.be/a"], "video", "best")
    q.add(["https://youtu.be/b"], "video", "best")
    q.cancel(a)
    item = q.retry(a)
    assert item["status"] == "waiting" and item["finished_at"] is None and item["error_short"] is None
    assert [i["url"] for i in q.list()] == ["https://youtu.be/b", "https://youtu.be/a"]


def test_retry_only_finished_with_failure(tmp_path):
    q = make_queue(tmp_path)
    [item_id], _ = q.add(["https://youtu.be/a"], "video", "best")
    with pytest.raises(ValueError):
        q.retry(item_id)


def test_history_keeps_last_50_finished(tmp_path):
    counter = itertools.count(1)
    q = make_queue(tmp_path, clock=lambda: float(next(counter)))
    ids, _ = q.add([f"https://youtu.be/{n}" for n in range(55)], "video", "best")
    for item_id in ids:
        q.cancel(item_id)
    items = q.list()
    assert len(items) == 50
    assert items[0]["url"] == "https://youtu.be/5"


def test_active_count_ignores_waiting(tmp_path):
    q = make_queue(tmp_path)
    q.add(["https://youtu.be/a"], "video", "best")
    assert q.active_count() == 0
