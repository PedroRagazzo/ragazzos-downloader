"""Converte mensagens de erro do yt-dlp em mensagens curtas em português."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorInfo:
    code: str
    short: str
    retryable: bool


# A ordem importa: a primeira regra com um trecho presente na mensagem vence.
_RULES = (
    ("ffmpeg", ("ffmpeg is not installed", "ffmpeg not found", "ffprobe and ffmpeg not found"),
     "ffmpeg não encontrado — rode o instalador", False),
    ("disk", ("no space left", "errno 28", "permission denied", "errno 13", "access is denied", "winerror 5", "winerror 112"),
     "Não consegui salvar o arquivo", False),
    ("unavailable", ("video unavailable", "this video is unavailable", "has been removed", "no longer available",
                     "not available in your country", "geo restriction", "geo-restricted", "http error 404",
                     "http error 410", "video has been deleted", "ip address is blocked"),
     "Vídeo indisponível", False),
    ("unsupported", ("unsupported url", "no video formats found", "no video could be found", "not a valid url",
                     "there is no video in this post"),
     "Esse link não tem vídeo suportado", False),
    ("network", ("timed out", "timeout", "connection reset", "connection aborted", "connection refused",
                 "getaddrinfo failed", "name resolution", "network is unreachable", "remote end closed",
                 "urlopen error", "incompleteread", "winerror 10054", "winerror 10060"),
     "Falha de conexão, tentando de novo…", True),
    ("extractor", ("not a bot", "unable to extract", "signature", "nsig",
                   "unable to download api page", "unable to download webpage", "jsinterp", "http error 403"),
     "O site mudou — clique em Atualizar", False),
    ("private", ("private", "login required", "log in", "login", "sign in", "requires authentication",
                 "--cookies", "age-restricted", "confirm your age"),
     "Conteúdo privado — por enquanto só baixo vídeos públicos", False),
    # o yt-dlp põe "please report this issue" no fim de vários erros; só vale se nada acima explicou
    ("extractor", ("please report this issue",),
     "O site mudou — clique em Atualizar", False),
)

_UNKNOWN = ErrorInfo("unknown", "Erro inesperado — veja os detalhes", False)


def classify_error(message: str) -> ErrorInfo:
    text = (message or "").lower()
    for code, needles, short, retryable in _RULES:
        if any(needle in text for needle in needles):
            return ErrorInfo(code, short, retryable)
    return _UNKNOWN
