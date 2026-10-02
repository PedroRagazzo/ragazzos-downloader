from videodl.filenames import build_base_name, sanitize_title, site_tag, unique_base


def test_removes_windows_invalid_characters():
    assert sanitize_title('a<b>c:d"e/f\\g|h?i*j') == "a b c d e f g h i j"


def test_collapses_whitespace_and_strips():
    assert sanitize_title("  olá   mundo \n") == "olá mundo"


def test_keeps_emoji_accents_and_percent():
    assert sanitize_title("Férias 🏖️ 2026") == "Férias 🏖️ 2026"
    assert sanitize_title("100% real") == "100% real"


def test_empty_or_only_invalid_becomes_video():
    for title in ("", None, "???", "...", "   "):
        assert sanitize_title(title) == "video"


def test_trailing_dots_removed():
    assert sanitize_title("fim...") == "fim"


def test_limits_length():
    assert len(sanitize_title("a" * 300)) == 150


def test_reserved_names_prefixed():
    assert sanitize_title("CON") == "_CON"
    assert sanitize_title("nul.txt") == "_nul.txt"


def test_site_tag():
    assert site_tag("Youtube") == "youtube"
    assert site_tag("TikTok") == "tiktok"
    assert site_tag(None) == "web"
    assert site_tag("!!!") == "web"


def test_build_base_name():
    assert build_base_name("Meu vídeo", "Youtube") == "Meu vídeo [youtube]"


def test_unique_base_free_name(tmp_path):
    assert unique_base(tmp_path, "X [youtube]") == "X [youtube]"


def test_unique_base_counts_up(tmp_path):
    (tmp_path / "X [youtube].mp4").write_bytes(b"")
    (tmp_path / "X [youtube] (2).mp3").write_bytes(b"")
    assert unique_base(tmp_path, "X [youtube]") == "X [youtube] (3)"


def test_unique_base_any_extension_counts(tmp_path):
    # protege arquivos do usuário: a limpeza de parciais apaga "base.*"
    (tmp_path / "X [youtube].mp3").write_bytes(b"")
    assert unique_base(tmp_path, "X [youtube]") == "X [youtube] (2)"


def test_unique_base_respects_taken(tmp_path):
    assert unique_base(tmp_path, "X [youtube]", taken={"X [youtube]"}) == "X [youtube] (2)"
