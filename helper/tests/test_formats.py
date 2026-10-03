import pytest

from videodl.formats import InvalidOptions, build_format_opts, final_extension


def test_video_quality_limits_height_and_prefers_h264():
    opts = build_format_opts("video", "720")
    assert opts["format"] == "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b"
    assert opts["format_sort"] == ["res:720", "vcodec:h264", "acodec:aac"]
    assert opts["merge_output_format"] == "mp4"
    assert opts["postprocessors"] == [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]


def test_video_best_has_no_height_limit():
    opts = build_format_opts("video", "best")
    assert opts["format"] == "bv*+ba/b"
    assert opts["format_sort"] == ["res", "vcodec:h264", "acodec:aac"]


def test_audio_extracts_mp3_with_bitrate():
    opts = build_format_opts("audio", "192")
    assert opts["format"] == "ba/b"
    assert opts["postprocessors"] == [
        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
    ]
    assert "merge_output_format" not in opts


@pytest.mark.parametrize(
    "mode,quality",
    [("video", "320"), ("audio", "720"), ("audio", "best"), ("gif", "best"), ("video", "")],
)
def test_invalid_combinations_raise(mode, quality):
    with pytest.raises(InvalidOptions):
        build_format_opts(mode, quality)


@pytest.mark.parametrize("mode,quality", [("video", "best"), ("audio", "128")])
def test_never_downloads_whole_playlist(mode, quality):
    assert build_format_opts(mode, quality)["noplaylist"] is True


def test_final_extension():
    assert final_extension("video") == "mp4"
    assert final_extension("audio") == "mp3"


def test_default_ext_keeps_old_behavior():
    assert build_format_opts("video", "720") == build_format_opts("video", "720", "mp4")
    assert build_format_opts("audio", "192") == build_format_opts("audio", "192", "mp3")


def test_mov_uses_h264_like_mp4():
    opts = build_format_opts("video", "1080", "mov")
    assert opts["format_sort"] == ["res:1080", "vcodec:h264", "acodec:aac"]
    assert opts["merge_output_format"] == "mov"
    assert opts["postprocessors"] == [{"key": "FFmpegVideoRemuxer", "preferedformat": "mov"}]


def test_mkv_keeps_original_codecs():
    opts = build_format_opts("video", "720", "mkv")
    assert opts["format"] == "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b"
    assert opts["format_sort"] == ["res:720"]
    assert opts["merge_output_format"] == "mkv"
    assert opts["postprocessors"] == [{"key": "FFmpegVideoRemuxer", "preferedformat": "mkv"}]
    assert build_format_opts("video", "best", "mkv")["format_sort"] == ["res"]


@pytest.mark.parametrize("ext", ["wav", "flac"])
def test_lossless_audio_has_no_bitrate(ext):
    opts = build_format_opts("audio", "320", ext)
    assert opts["format"] == "ba/b"
    assert opts["postprocessors"] == [{"key": "FFmpegExtractAudio", "preferredcodec": ext}]


@pytest.mark.parametrize("mode,ext", [("video", "mp3"), ("audio", "mkv"), ("video", "webm"), ("audio", "ogg"), ("video", "")])
def test_invalid_ext_raises(mode, ext):
    quality = "best" if mode == "video" else "320"
    with pytest.raises(InvalidOptions):
        build_format_opts(mode, quality, ext)


def test_final_extension_follows_chosen_format():
    assert final_extension("video", "mkv") == "mkv"
    assert final_extension("video", "mov") == "mov"
    assert final_extension("audio", "flac") == "flac"
    assert final_extension("audio", None) == "mp3"
