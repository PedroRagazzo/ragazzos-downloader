import pytest

from videodl.errors import classify_error


@pytest.mark.parametrize(
    "message,code",
    [
        ("ERROR: Postprocessing: ffprobe and ffmpeg not found. Please install or provide the path using --ffmpeg-location", "ffmpeg"),
        ("ERROR: unable to write data: [Errno 28] No space left on device", "disk"),
        ("ERROR: unable to open for writing: [WinError 5] Access is denied", "disk"),
        ("ERROR: [youtube] abc: Video unavailable. This video has been removed by the uploader", "unavailable"),
        ("ERROR: [Instagram] xyz: Unable to download webpage: HTTP Error 404: Not Found", "unavailable"),
        ("ERROR: Unsupported URL: https://example.com/", "unsupported"),
        ("ERROR: [Pinterest] 123: No video formats found!", "unsupported"),
        ("ERROR: [youtube] abc: Unable to download webpage: <urlopen error [Errno 11001] getaddrinfo failed>", "network"),
        ("ERROR: Read timed out.", "network"),
        ("ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies-from-browser", "extractor"),
        ("ERROR: [TikTok] 123: Unable to extract webpage video data; please report this issue on https://github.com/yt-dlp/yt-dlp/issues", "extractor"),
        ("ERROR: unable to download video data: HTTP Error 403: Forbidden", "extractor"),
        ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access to this video", "private"),
        ("ERROR: [Instagram] xyz: Requested content is not available, rate-limit reached or login required", "private"),
        ("algo totalmente diferente", "unknown"),
    ],
)
def test_classifies_yt_dlp_messages(message, code):
    assert classify_error(message).code == code


def test_short_messages_in_portuguese():
    assert classify_error("ERROR: Unsupported URL: x").short == "Esse link não tem vídeo suportado"
    assert classify_error("ERROR: Private video").short == "Conteúdo privado — por enquanto só baixo vídeos públicos"
    assert classify_error("ERROR: Video unavailable").short == "Vídeo indisponível"
    assert classify_error("ERROR: Read timed out.").short == "Falha de conexão, tentando de novo…"
    assert classify_error("ERROR: Unable to extract data").short == "O site mudou — clique em Atualizar"
    assert classify_error("[Errno 28] No space left on device").short == "Não consegui salvar o arquivo"
    assert classify_error("???").short == "Erro inesperado — veja os detalhes"


def test_only_network_is_retryable():
    assert classify_error("ERROR: Read timed out.").retryable is True
    assert classify_error("ERROR: Unsupported URL: x").retryable is False
    assert classify_error("???").retryable is False
