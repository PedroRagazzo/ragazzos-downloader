import threading
import time

from videodl.queue import Cancelled, DownloadQueue


def wait_for(predicate, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condição não atingida a tempo")


def item_of(q, item_id):
    return next(i for i in q.list() if i["id"] == item_id)


def test_downloads_item_until_done(tmp_path):
    def downloader(item, report, is_cancelled):
        report({"title": "Meu vídeo", "status": "downloading", "progress": 0.5, "speed": 1000.0})
        report({"status": "converting"})
        return "C:/videos/Meu vídeo [youtube].mp4"

    q = DownloadQueue(tmp_path / "queue.json", downloader)
    q.start()
    try:
        [item_id], _ = q.add(["https://youtu.be/a"], "video", "best")
        wait_for(lambda: item_of(q, item_id)["status"] == "done")
        item = item_of(q, item_id)
        assert item["title"] == "Meu vídeo"
        assert item["filename"] == "C:/videos/Meu vídeo [youtube].mp4"
        assert item["progress"] == 1.0 and item["speed"] is None
    finally:
        q.stop()


def test_runs_at_most_two_at_once(tmp_path):
    release = threading.Event()
    running = []

    def downloader(item, report, is_cancelled):
        running.append(item.url)
        release.wait(3)
        return "x.mp4"

    q = DownloadQueue(tmp_path / "queue.json", downloader)
    q.start()
    try:
        ids, _ = q.add(["https://a.com/1", "https://a.com/2", "https://a.com/3"], "video", "best")
        wait_for(lambda: len(running) == 2)
        time.sleep(0.1)
        assert len(running) == 2
        assert item_of(q, ids[2])["status"] == "waiting"
        assert q.active_count() == 2
        release.set()
        wait_for(lambda: all(i["status"] == "done" for i in q.list()))
    finally:
        release.set()
        q.stop()


def test_cancel_running_item(tmp_path):
    started = threading.Event()

    def downloader(item, report, is_cancelled):
        started.set()
        while not is_cancelled():
            time.sleep(0.01)
        raise Cancelled()

    q = DownloadQueue(tmp_path / "queue.json", downloader)
    q.start()
    try:
        [item_id], _ = q.add(["https://youtu.be/a"], "video", "best")
        assert started.wait(3)
        q.cancel(item_id)
        wait_for(lambda: item_of(q, item_id)["status"] == "cancelled")
    finally:
        q.stop()


def test_non_retryable_error_marks_item(tmp_path):
    sleeps = []

    def downloader(item, report, is_cancelled):
        raise RuntimeError("ERROR: Unsupported URL: https://example.com/")

    q = DownloadQueue(tmp_path / "queue.json", downloader, sleep=sleeps.append)
    q.start()
    try:
        [item_id], _ = q.add(["https://example.com/"], "video", "best")
        wait_for(lambda: item_of(q, item_id)["status"] == "error")
        item = item_of(q, item_id)
        assert item["error_code"] == "unsupported"
        assert item["error_short"] == "Esse link não tem vídeo suportado"
        assert "Unsupported URL" in item["error_detail"]
        assert sleeps == []
    finally:
        q.stop()


def test_network_error_retries_with_delays_then_succeeds(tmp_path):
    attempts = []
    sleeps = []

    def downloader(item, report, is_cancelled):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("ERROR: Read timed out.")
        return "ok.mp4"

    q = DownloadQueue(tmp_path / "queue.json", downloader, sleep=sleeps.append)
    q.start()
    try:
        [item_id], _ = q.add(["https://youtu.be/a"], "video", "best")
        wait_for(lambda: item_of(q, item_id)["status"] == "done")
        assert len(attempts) == 3
        assert sleeps == [5, 15]
        assert item_of(q, item_id)["error_short"] is None
    finally:
        q.stop()


def test_network_error_gives_up_after_two_retries(tmp_path):
    attempts = []
    sleeps = []

    def downloader(item, report, is_cancelled):
        attempts.append(1)
        raise RuntimeError("ERROR: Read timed out.")

    q = DownloadQueue(tmp_path / "queue.json", downloader, sleep=sleeps.append)
    q.start()
    try:
        [item_id], _ = q.add(["https://youtu.be/a"], "video", "best")
        wait_for(lambda: item_of(q, item_id)["status"] == "error")
        assert len(attempts) == 3
        assert sleeps == [5, 15]
        assert item_of(q, item_id)["error_code"] == "network"
    finally:
        q.stop()


def test_pause_stops_picking_new_items(tmp_path):
    calls = []
    q = DownloadQueue(tmp_path / "queue.json", lambda item, report, is_cancelled: calls.append(1) or "x.mp4")
    q.pause()
    q.start()
    try:
        [item_id], _ = q.add(["https://youtu.be/a"], "video", "best")
        time.sleep(0.2)
        assert calls == []
        assert item_of(q, item_id)["status"] == "waiting"
    finally:
        q.stop()


def test_stop_leaves_running_item_to_resume(tmp_path):
    started = threading.Event()

    def downloader(item, report, is_cancelled):
        started.set()
        while not is_cancelled():
            time.sleep(0.01)
        raise Cancelled()

    q = DownloadQueue(tmp_path / "queue.json", downloader)
    q.start()
    [item_id], _ = q.add(["https://youtu.be/a"], "video", "best")
    assert started.wait(3)
    q.stop()
    reopened = DownloadQueue(tmp_path / "queue.json", downloader)
    assert item_of(reopened, item_id)["status"] == "waiting"
