import copy
from pathlib import Path

import pytest

from videodl.downloader import YtDlpDownloader
from videodl.queue import Cancelled, Item

INFO = {"id": "a", "title": "Meu vídeo", "extractor_key": "Youtube", "thumbnail": "https://i.ytimg.com/x.jpg"}
PLAYLIST = {
    "_type": "playlist",
    "title": "Lista",
    "entries": [
        {"id": "1", "title": "Primeiro", "extractor_key": "Youtube"},
        {"id": "2", "title": "Segundo", "extractor_key": "Youtube"},
    ],
}


def make_factory(info, *, fail_on_download=None):
    calls = []

    class FakeYDL:
        def __init__(self, params):
            self.params = params
            calls.append(params)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            if isinstance(info, Exception):
                raise info
            if download:
                self._fake_download()
            return copy.deepcopy(info)

        def process_ie_result(self, entry, download=True):
            # como no yt-dlp real: links resolvidos em outra instância dão 403 ao baixar
            raise RuntimeError("ERROR: unable to download video data: HTTP Error 403: Forbidden")

        def _fake_download(self):
            template = self.params["outtmpl"]["default"]
            assert template.endswith(".%(ext)s")
            base = template[: -len(".%(ext)s")].replace("%%", "%")
            part = Path(base + ".f1.mp4.part")
            part.write_bytes(b"partial")
            if fail_on_download:
                raise fail_on_download
            for hook in self.params["progress_hooks"]:
                hook({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100, "speed": 2048.0})
            for hook in self.params["postprocessor_hooks"]:
                hook({"status": "started"})
            part.unlink()
            # como o yt-dlp: áudio sai no codec pedido, vídeo no contêiner de saída
            extract = [pp for pp in self.params.get("postprocessors", []) if pp["key"] == "FFmpegExtractAudio"]
            ext = extract[0]["preferredcodec"] if extract else self.params["merge_output_format"]
            Path(base + "." + ext).write_bytes(b"media")

    return FakeYDL, calls


def make_item(mode="video", quality="720", ext=None):
    return Item(id="i1", url="https://youtu.be/a", mode=mode, quality=quality, ext=ext)


def test_downloads_video_with_readable_name(tmp_path):
    factory, calls = make_factory(INFO)
    reports = []
    path = YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item(), reports.append, lambda: False)
    assert Path(path) == tmp_path / "Meu vídeo [youtube].mp4"
    assert Path(path).read_bytes() == b"media"
    assert {"title": "Meu vídeo"} in reports
    assert {"status": "downloading", "progress": 0.5, "speed": 2048.0} in reports
    assert {"status": "converting"} in reports
    assert calls[1]["format_sort"][0] == "res:720"


def test_downloads_audio_as_mp3(tmp_path):
    factory, calls = make_factory(INFO)
    path = YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item("audio", "192"), lambda u: None, lambda: False)
    assert Path(path) == tmp_path / "Meu vídeo [youtube].mp3"
    assert calls[1]["postprocessors"][0]["preferredquality"] == "192"


def test_name_conflict_gets_number(tmp_path):
    (tmp_path / "Meu vídeo [youtube].mp4").write_bytes(b"old")
    factory, _ = make_factory(INFO)
    path = YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item(), lambda u: None, lambda: False)
    assert Path(path).name == "Meu vídeo [youtube] (2).mp4"
    assert (tmp_path / "Meu vídeo [youtube].mp4").read_bytes() == b"old"


def test_percent_in_title_is_escaped(tmp_path):
    factory, _ = make_factory({**INFO, "title": "100% real"})
    path = YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item(), lambda u: None, lambda: False)
    assert Path(path).name == "100% real [youtube].mp4"


def test_playlist_downloads_only_first_entry(tmp_path):
    factory, calls = make_factory(PLAYLIST)
    path = YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item(), lambda u: None, lambda: False)
    assert Path(path).name == "Primeiro [youtube].mp4"
    assert calls[0]["playlist_items"] == "1"
    assert calls[0]["noplaylist"] is True


def test_cancel_removes_partial_files_but_keeps_others(tmp_path):
    (tmp_path / "Outro [youtube].mp4").write_bytes(b"keep")
    factory, _ = make_factory(INFO)
    state = {"cancel": False}

    def report(update):
        if "progress" in update:
            state["cancel"] = True

    with pytest.raises(Cancelled):
        YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item(), report, lambda: state["cancel"])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Outro [youtube].mp4"]


def test_download_error_cleans_up_and_propagates(tmp_path):
    factory, _ = make_factory(INFO, fail_on_download=RuntimeError("ERROR: boom"))
    with pytest.raises(RuntimeError, match="boom"):
        YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item(), lambda u: None, lambda: False)
    assert list(tmp_path.iterdir()) == []


def test_extract_error_propagates(tmp_path):
    factory, _ = make_factory(RuntimeError("ERROR: Unsupported URL: x"))
    with pytest.raises(RuntimeError, match="Unsupported URL"):
        YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item(), lambda u: None, lambda: False)


def test_js_runtime_option(tmp_path):
    factory, calls = make_factory(INFO)
    YtDlpDownloader(tmp_path, js_runtime="node", ydl_factory=factory).get_info("https://youtu.be/a")
    YtDlpDownloader(tmp_path, js_runtime=None, ydl_factory=factory).get_info("https://youtu.be/a")
    assert calls[0]["js_runtimes"] == {"node": {}}
    assert "js_runtimes" not in calls[1]


def test_reports_reserved_base_name(tmp_path):
    factory, _ = make_factory(INFO)
    reports = []
    YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item(), reports.append, lambda: False)
    assert {"base": "Meu vídeo [youtube]"} in reports


def test_resumes_interrupted_download_with_same_name(tmp_path):
    # PC desligou no meio: sobrou o .part e o item voltou para a fila lembrando o nome
    (tmp_path / "Meu vídeo [youtube].f1.mp4.part").write_bytes(b"meio baixado")
    factory, _ = make_factory(INFO)
    item = make_item()
    item.base = "Meu vídeo [youtube]"
    path = YtDlpDownloader(tmp_path, ydl_factory=factory)(item, lambda u: None, lambda: False)
    assert Path(path).name == "Meu vídeo [youtube].mp4"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Meu vídeo [youtube].mp4"]


def test_saved_base_is_not_reused_when_final_file_exists(tmp_path):
    (tmp_path / "Meu vídeo [youtube].mp4").write_bytes(b"old")
    factory, _ = make_factory(INFO)
    item = make_item()
    item.base = "Meu vídeo [youtube]"
    path = YtDlpDownloader(tmp_path, ydl_factory=factory)(item, lambda u: None, lambda: False)
    assert Path(path).name == "Meu vídeo [youtube] (2).mp4"
    assert (tmp_path / "Meu vídeo [youtube].mp4").read_bytes() == b"old"


def test_get_info(tmp_path):
    factory, _ = make_factory(INFO)
    info = YtDlpDownloader(tmp_path, ydl_factory=factory).get_info("https://youtu.be/a")
    assert info == {"title": "Meu vídeo", "thumbnail": "https://i.ytimg.com/x.jpg", "site": "youtube"}


@pytest.mark.parametrize("mode,quality,ext", [
    ("video", "720", "mkv"), ("video", "best", "mov"), ("audio", "320", "wav"), ("audio", "128", "flac"),
])
def test_downloads_in_chosen_format(tmp_path, mode, quality, ext):
    factory, calls = make_factory(INFO)
    path = YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item(mode, quality, ext), lambda u: None, lambda: False)
    assert Path(path) == tmp_path / f"Meu vídeo [youtube].{ext}"
    assert Path(path).read_bytes() == b"media"


def test_item_without_format_still_downloads_mp4(tmp_path):
    factory, _ = make_factory(INFO)
    path = YtDlpDownloader(tmp_path, ydl_factory=factory)(make_item(ext=None), lambda u: None, lambda: False)
    assert Path(path).suffix == ".mp4"
