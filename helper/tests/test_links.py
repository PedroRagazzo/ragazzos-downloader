import pytest

from videodl.links import normalize_url

YT = "https://www.youtube.com/watch?v=abc123DEF_-"


@pytest.mark.parametrize("url", [
    "https://youtu.be/abc123DEF_-",
    "https://youtu.be/abc123DEF_-?si=XyZ123",
    "https://www.youtube.com/watch?v=abc123DEF_-&si=XyZ&feature=share",
    "https://m.youtube.com/watch?v=abc123DEF_-",
    "https://youtube.com/watch?v=abc123DEF_-&list=PL123&index=2",
    "https://www.youtube.com/shorts/abc123DEF_-?feature=share",
    "https://www.youtube.com/watch?feature=youtu.be&v=abc123DEF_-",
    "https://music.youtube.com/watch?v=abc123DEF_-&si=1",
    "https://www.youtube.com/embed/abc123DEF_-",
    "https://www.youtube.com/live/abc123DEF_-?si=1",
    "HTTPS://WWW.YOUTUBE.COM/watch?v=abc123DEF_-#t=10",
])
def test_youtube_variants_become_the_same_link(url):
    assert normalize_url(url) == YT


@pytest.mark.parametrize("url,expected", [
    ("https://www.instagram.com/reel/Cxyz/?igsh=MWQ1ZGUxMzBkMA==", "https://www.instagram.com/reel/Cxyz/"),
    ("https://www.instagram.com/p/Cxyz/?utm_source=ig_web_copy_link&igshid=abc", "https://www.instagram.com/p/Cxyz/"),
    ("https://www.tiktok.com/@a/video/123?is_from_webapp=1&sender_device=pc&_r=1&_t=8abc",
     "https://www.tiktok.com/@a/video/123"),
    ("https://br.pinterest.com/pin/123/?utm_medium=share&fbclid=x", "https://br.pinterest.com/pin/123/"),
])
def test_tracking_params_are_removed(url, expected):
    assert normalize_url(url) == expected


def test_meaningful_params_are_kept():
    assert normalize_url("https://example.com/video?id=7&utm_source=x") == "https://example.com/video?id=7"


def test_youtube_link_without_video_is_left_alone():
    assert normalize_url("https://www.youtube.com/@canal") == "https://www.youtube.com/@canal"


def test_not_a_url_is_returned_trimmed():
    assert normalize_url("  qualquer coisa  ") == "qualquer coisa"
