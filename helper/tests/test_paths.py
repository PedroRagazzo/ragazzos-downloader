from pathlib import Path

import pytest

from videodl import paths
from videodl.extension_key import extension_id_from_der, manifest_key_from_der


def test_extension_id_matches_chrome_algorithm():
    assert extension_id_from_der(b"abc") == "lkhibglpipabmpokebebeanofnkocccd"


def test_manifest_key_is_base64():
    assert manifest_key_from_der(b"abc") == "YWJj"


def test_app_dir_uses_localappdata(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert paths.app_dir() == tmp_path / "VideoDownloader"


def test_download_dir_is_in_user_downloads():
    assert paths.download_dir() == Path.home() / "Downloads" / "Video Downloader"


def test_extension_origin_reads_id(tmp_path):
    f = tmp_path / "extension_id.txt"
    f.write_text("lkhibglpipabmpokebebeanofnkocccd\n", encoding="utf-8")
    assert paths.extension_origin(f) == "chrome-extension://lkhibglpipabmpokebebeanofnkocccd"


@pytest.mark.parametrize("content", ["", "xyz", "LKHIBGLPIPABMPOKEBEBEANOFNKOCCCD"])
def test_extension_origin_rejects_invalid(tmp_path, content):
    f = tmp_path / "extension_id.txt"
    f.write_text(content, encoding="utf-8")
    with pytest.raises(RuntimeError, match="gen_extension_key"):
        paths.extension_origin(f)


def test_extension_origin_missing_file(tmp_path):
    with pytest.raises(RuntimeError, match="gen_extension_key"):
        paths.extension_origin(tmp_path / "nao-existe.txt")
