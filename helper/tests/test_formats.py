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
