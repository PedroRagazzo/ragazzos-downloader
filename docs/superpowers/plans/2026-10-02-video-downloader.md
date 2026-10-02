# Vídeo Downloader — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extensão Chromium + programa local em Python que baixam vídeo (MP4) ou áudio (MP3) de YouTube, TikTok, Instagram e Pinterest, com fila de downloads.

**Architecture:** O helper Python (`helper/videodl`) roda em segundo plano no Windows, expõe uma API JSON em `127.0.0.1:47321` (só aceita a origem da extensão), mantém a fila persistente e baixa com `yt-dlp` + `ffmpeg`. A extensão (`extension/`, Manifest V3, ES modules puros) é só interface: lê a aba atual, aceita links colados e mostra a fila consultando a API a cada 1 s.

**Tech Stack:** Python 3.14 (stdlib `http.server`, `threading`), yt-dlp[default], ffmpeg (winget), Node 24 (runtime JS do yt-dlp e `node --test`), pystray + Pillow, pytest, JavaScript ES modules sem bundler.

**Spec:** `docs/superpowers/specs/2026-10-02-video-downloader-design.md`

## Global Constraints

- Windows 11; Python 3.14 em venv `helper\.venv`; Node 24 já instalado.
- Comandos deste plano são para **PowerShell**, executados a partir da raiz do repositório (`D:\Projetos e trabalhos\Programação\Vídeo Downloader`).
- Helper escuta **somente** em `127.0.0.1:47321`.
- Toda requisição à API precisa de `Origin: chrome-extension://<ID>` com o ID salvo em `helper/videodl/extension_id.txt`; qualquer outra origem → `403`.
- Pasta de downloads: `%USERPROFILE%\Downloads\Video Downloader\`. Dados do app: `%LOCALAPPDATA%\VideoDownloader\` (`queue.json`, `update.json`, `log.txt`).
- Qualidades válidas — vídeo: `best`, `1080`, `720`, `480`, `360`; áudio: `320`, `192`, `128` (kbps).
- No máximo **2** downloads simultâneos; histórico de **50** itens finalizados; erros de rede tentam de novo após **5 s** e **15 s**.
- Nome de arquivo: `Título [site].ext`, título com no máximo **150** caracteres; conflito → `Título [site] (2).ext`, `(3)`…
- Log rotativo: 1 MB × 3 arquivos.
- Texto visível ao usuário em **português (pt-BR)**; identificadores de código em inglês.
- Dependências de runtime: apenas `yt-dlp[default]`, `pystray`, `Pillow`. Servidor HTTP só com a biblioteca padrão. Extensão sem framework nem bundler.
- Toda mensagem de commit termina com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (use um segundo `-m`).

## Review Focus

1. **Link de playlist** (`youtube.com/watch?v=X&list=Y`, carrossel do Instagram, link de lista) → baixa **um** vídeo (o primeiro/o do `v=`), nunca a lista inteira. Testes: Task 1 (`noplaylist`) e Task 6 (`playlist_items: "1"` + playlist → primeiro item).
2. **Texto colado "sujo"** (mensagem do WhatsApp com texto, pontuação colada no link, links repetidos, CRLF) → extrai só os links, sem pontuação final e sem repetidos. Teste: Task 11 (`parseLinks`).
3. **Títulos estranhos** (emoji, `%`, só caracteres inválidos, 300 caracteres, terminando em ponto, `CON`) → nome de arquivo válido no Windows. Testes: Task 2 e Task 6 (`%` no outtmpl).
4. **`queue.json` corrompido ou vazio** (PC desligou durante a gravação) → helper abre com fila vazia e guarda o arquivo ruim como `queue.json.bad`, sem travar. Teste: Task 4.
5. **Helper aberto duas vezes** (início automático + clique no menu Iniciar) → a segunda cópia não consegue a porta e sai em silêncio; a primeira continua. Testes: Task 7 (bind exclusivo) e Task 10 (`start_server_with_retry`).

---

## Estrutura de arquivos

```
Vídeo Downloader/
├── .gitignore
├── package.json                      # só para `node --test` da extensão
├── README.md
├── docs/smoke-test.md                # checklist manual
├── scripts/
│   ├── install.ps1                   # venv, deps, ffmpeg, atalhos, inicia helper
│   ├── gen_extension_key.py          # gera "key" do manifest + extension_id.txt
│   └── make_icons.py                 # gera extension/icons/*.png
├── helper/
│   ├── pyproject.toml                # config do pytest
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── videodl/
│   │   ├── __init__.py               # __version__
│   │   ├── __main__.py               # python -m videodl
│   │   ├── formats.py                # modo/qualidade → opções do yt-dlp
│   │   ├── filenames.py              # sanitização e nomes únicos
│   │   ├── errors.py                 # mensagem do yt-dlp → ErrorInfo em pt-BR
│   │   ├── queue.py                  # fila: estado, persistência, workers
│   │   ├── downloader.py             # YtDlpDownloader (download + get_info)
│   │   ├── server.py                 # API HTTP + validação de origem
│   │   ├── updater.py                # atualização diária do yt-dlp
│   │   ├── startup.py                # atalhos (Inicializar / menu Iniciar)
│   │   ├── paths.py                  # pastas e origem da extensão
│   │   ├── extension_key.py          # cálculo do ID da extensão
│   │   ├── extension_id.txt          # gerado pelo script
│   │   ├── icon.py                   # desenho do ícone (Pillow)
│   │   ├── tray.py                   # ícone da bandeja (pystray)
│   │   └── app.py                    # junta tudo; main()
│   └── tests/ (test_<módulo>.py)
└── extension/
    ├── manifest.json
    ├── popup.html / popup.css / popup.js
    ├── icons/icon16.png … icon128.png
    ├── lib/links.js, format.js, prefs.js, api.js
    └── tests/*.test.js
```

---

### Task 1: Base do helper + mapeamento de formatos

**Files:**
- Create: `.gitignore`, `helper/pyproject.toml`, `helper/requirements.txt`, `helper/requirements-dev.txt`, `helper/videodl/__init__.py`, `helper/videodl/formats.py`
- Test: `helper/tests/test_formats.py`

**Interfaces:**
- Produces:
  - `videodl.__version__: str = "0.1.0"`
  - `formats.VIDEO_QUALITIES: tuple[str, ...]`, `formats.AUDIO_QUALITIES: tuple[str, ...]`
  - `class formats.InvalidOptions(ValueError)`
  - `formats.validate(mode: str, quality: str) -> None` (levanta `InvalidOptions`)
  - `formats.build_format_opts(mode: str, quality: str) -> dict` (parâmetros do `YoutubeDL`)
  - `formats.final_extension(mode: str) -> str` (`"mp4"` ou `"mp3"`)

- [ ] **Step 1: Criar arquivos de base**

`.gitignore`:
```gitignore
helper/.venv/
__pycache__/
*.pyc
.pytest_cache/
node_modules/
```

`helper/pyproject.toml`:
```toml
[project]
name = "videodl"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`helper/requirements.txt`:
```text
yt-dlp[default]
pystray>=0.19.5
Pillow>=11.3
```

`helper/requirements-dev.txt`:
```text
-r requirements.txt
pytest>=8
```

`helper/videodl/__init__.py`:
```python
"""Vídeo Downloader — programa local que baixa vídeos e áudios com yt-dlp."""

__version__ = "0.1.0"
```

- [ ] **Step 2: Criar o venv e instalar dependências**

Run:
```powershell
python -m venv helper\.venv
helper\.venv\Scripts\python -m pip install --upgrade pip
helper\.venv\Scripts\python -m pip install -r helper\requirements-dev.txt
```
Expected: termina com `Successfully installed ... yt-dlp-... pystray-... pytest-...`.

- [ ] **Step 3: Escrever os testes que falham**

`helper/tests/test_formats.py`:
```python
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
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_formats.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'videodl.formats'`.

- [ ] **Step 5: Implementar**

`helper/videodl/formats.py`:
```python
"""Traduz modo/qualidade escolhidos na extensão em parâmetros do yt-dlp."""

from __future__ import annotations

VIDEO_QUALITIES = ("best", "1080", "720", "480", "360")
AUDIO_QUALITIES = ("320", "192", "128")


class InvalidOptions(ValueError):
    """Combinação de modo e qualidade que não existe."""


def validate(mode: str, quality: str) -> None:
    if mode == "video" and quality in VIDEO_QUALITIES:
        return
    if mode == "audio" and quality in AUDIO_QUALITIES:
        return
    raise InvalidOptions(f"combinação inválida: {mode}/{quality}")


def final_extension(mode: str) -> str:
    return "mp3" if mode == "audio" else "mp4"


def build_format_opts(mode: str, quality: str) -> dict:
    validate(mode, quality)
    if mode == "audio":
        return {
            "format": "ba/b",
            "noplaylist": True,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": quality}
            ],
        }
    if quality == "best":
        fmt = "bv*+ba/b"
        sort = ["res", "vcodec:h264", "acodec:aac"]
    else:
        fmt = f"bv*[height<={quality}]+ba/b[height<={quality}]/bv*+ba/b"
        sort = [f"res:{quality}", "vcodec:h264", "acodec:aac"]
    return {
        "format": fmt,
        "format_sort": sort,
        "merge_output_format": "mp4",
        "noplaylist": True,
        # garante .mp4 mesmo quando o melhor formato único vem em outro contêiner
        "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
    }
```

- [ ] **Step 6: Rodar e ver passar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_formats.py -v`
Expected: todos PASS.

- [ ] **Step 7: Commit**

```powershell
git add .gitignore helper
git commit -m "feat(helper): base do projeto e mapeamento de formatos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Nomes de arquivo

**Files:**
- Create: `helper/videodl/filenames.py`
- Test: `helper/tests/test_filenames.py`

**Interfaces:**
- Produces:
  - `filenames.MAX_TITLE = 150`
  - `filenames.sanitize_title(title: str | None) -> str`
  - `filenames.site_tag(name: str | None) -> str` (minúsculas, só `[a-z0-9]`, padrão `"web"`)
  - `filenames.build_base_name(title: str | None, site: str | None) -> str` → `"Título [site]"`
  - `filenames.unique_base(folder: Path, base: str, taken: Collection[str] = frozenset()) -> str` — devolve um nome-base sem **nenhum** arquivo `base.*` existente na pasta e fora de `taken`.

- [ ] **Step 1: Escrever os testes que falham**

`helper/tests/test_filenames.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_filenames.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'videodl.filenames'`.

- [ ] **Step 3: Implementar**

`helper/videodl/filenames.py`:
```python
"""Nomes de arquivo seguros para o Windows e sem conflito."""

from __future__ import annotations

import glob
import re
import unicodedata
from collections.abc import Collection
from pathlib import Path

MAX_TITLE = 150
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def sanitize_title(title: str | None) -> str:
    text = unicodedata.normalize("NFC", title or "")
    text = _INVALID.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip().rstrip(". ")
    text = text[:MAX_TITLE].rstrip(". ")
    if not text:
        return "video"
    if text.split(".")[0].upper() in _RESERVED:
        text = f"_{text}"
    return text


def site_tag(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower()) or "web"


def build_base_name(title: str | None, site: str | None) -> str:
    return f"{sanitize_title(title)} [{site_tag(site)}]"


def _in_use(folder: Path, base: str, taken: Collection[str]) -> bool:
    return base in taken or any(folder.glob(glob.escape(base) + ".*"))


def unique_base(folder: Path, base: str, taken: Collection[str] = frozenset()) -> str:
    candidate, n = base, 2
    while _in_use(folder, candidate, taken):
        candidate = f"{base} ({n})"
        n += 1
    return candidate
```

- [ ] **Step 4: Rodar e ver passar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_filenames.py -v`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```powershell
git add helper/videodl/filenames.py helper/tests/test_filenames.py
git commit -m "feat(helper): nomes de arquivo seguros e únicos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Tradução de erros

**Files:**
- Create: `helper/videodl/errors.py`
- Test: `helper/tests/test_errors.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class errors.ErrorInfo: code: str; short: str; retryable: bool`
  - `errors.classify_error(message: str) -> ErrorInfo`
  - Códigos: `ffmpeg`, `disk`, `unavailable`, `unsupported`, `network`, `extractor`, `private`, `unknown`. Só `network` tem `retryable=True`.

- [ ] **Step 1: Escrever os testes que falham**

`helper/tests/test_errors.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_errors.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'videodl.errors'`.

- [ ] **Step 3: Implementar**

`helper/videodl/errors.py`:
```python
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
                     "http error 410", "video has been deleted"),
     "Vídeo indisponível", False),
    ("unsupported", ("unsupported url", "no video formats found", "no video could be found", "not a valid url",
                     "there is no video in this post"),
     "Esse link não tem vídeo suportado", False),
    ("network", ("timed out", "timeout", "connection reset", "connection aborted", "connection refused",
                 "getaddrinfo failed", "name resolution", "network is unreachable", "remote end closed",
                 "urlopen error", "incompleteread", "winerror 10054", "winerror 10060"),
     "Falha de conexão, tentando de novo…", True),
    ("extractor", ("not a bot", "unable to extract", "please report this issue", "signature", "nsig",
                   "unable to download api page", "unable to download webpage", "jsinterp"),
     "O site mudou — clique em Atualizar", False),
    ("private", ("private", "login required", "log in", "login", "sign in", "requires authentication",
                 "--cookies", "age-restricted", "confirm your age"),
     "Conteúdo privado — por enquanto só baixo vídeos públicos", False),
)

_UNKNOWN = ErrorInfo("unknown", "Erro inesperado — veja os detalhes", False)


def classify_error(message: str) -> ErrorInfo:
    text = (message or "").lower()
    for code, needles, short, retryable in _RULES:
        if any(needle in text for needle in needles):
            return ErrorInfo(code, short, retryable)
    return _UNKNOWN
```

- [ ] **Step 4: Rodar e ver passar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_errors.py -v`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```powershell
git add helper/videodl/errors.py helper/tests/test_errors.py
git commit -m "feat(helper): tradução de erros do yt-dlp" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Fila — estado e persistência

**Files:**
- Create: `helper/videodl/queue.py`
- Test: `helper/tests/test_queue_state.py`

**Interfaces:**
- Consumes: `formats.validate`, `formats.InvalidOptions` (Task 1); `errors.classify_error` (Task 3, usado na Task 5).
- Produces:
  - Constantes de status: `WAITING`, `DOWNLOADING`, `CONVERTING`, `DONE`, `ERROR`, `CANCELLED`; `RUNNING = (DOWNLOADING, CONVERTING)`; `ACTIVE = (WAITING, DOWNLOADING, CONVERTING)`.
  - `class Cancelled(Exception)` — o downloader levanta quando o item foi cancelado.
  - `@dataclass class Item` com campos: `id, url, mode, quality, status, title, progress, speed, filename, error_code, error_short, error_detail, created_at, finished_at`; `Item.to_dict() -> dict`.
  - Tipo `Downloader = Callable[[Item, Callable[[dict], None], Callable[[], bool]], str]` — recebe uma **cópia** do item, uma função `report(update)` e `is_cancelled()`; devolve o caminho do arquivo final.
  - `class DownloadQueue(store_path: Path, downloader: Downloader, *, max_workers=2, history_limit=50, retry_delays=(5, 15), sleep=time.sleep, clock=time.time)`:
    - `add(urls: list[str], mode: str, quality: str) -> tuple[list[str], int]` (ids adicionados, duplicatas)
    - `list() -> list[dict]`
    - `cancel(item_id: str) -> dict` (`KeyError` se não existe)
    - `retry(item_id: str) -> dict` (`KeyError`; `ValueError` se não está em erro/cancelado)
    - `active_count() -> int` (itens baixando/convertendo)
    - (Task 5 acrescenta `start()`, `stop()`, `pause()`)

- [ ] **Step 1: Escrever os testes que falham**

`helper/tests/test_queue_state.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_queue_state.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'videodl.queue'`.

- [ ] **Step 3: Implementar**

`helper/videodl/queue.py`:
```python
"""Fila de downloads: estado, persistência em JSON e workers."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Callable

from .errors import ErrorInfo, classify_error
from .formats import validate

log = logging.getLogger(__name__)

WAITING = "waiting"
DOWNLOADING = "downloading"
CONVERTING = "converting"
DONE = "done"
ERROR = "error"
CANCELLED = "cancelled"
RUNNING = (DOWNLOADING, CONVERTING)
ACTIVE = (WAITING, *RUNNING)


class Cancelled(Exception):
    """Levantada pelo downloader quando o item foi cancelado."""


@dataclass
class Item:
    id: str
    url: str
    mode: str
    quality: str
    status: str = WAITING
    title: str | None = None
    progress: float = 0.0
    speed: float | None = None
    filename: str | None = None
    error_code: str | None = None
    error_short: str | None = None
    error_detail: str | None = None
    created_at: float = 0.0
    finished_at: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


_FIELDS = {f.name for f in fields(Item)}

Report = Callable[[dict], None]
Downloader = Callable[[Item, Report, Callable[[], bool]], str]


class DownloadQueue:
    def __init__(
        self,
        store_path: Path,
        downloader: Downloader,
        *,
        max_workers: int = 2,
        history_limit: int = 50,
        retry_delays: tuple[float, ...] = (5, 15),
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ):
        self._store_path = Path(store_path)
        self._downloader = downloader
        self._max_workers = max_workers
        self._history_limit = history_limit
        self._retry_delays = tuple(retry_delays)
        self._sleep = sleep
        self._clock = clock
        self._cond = threading.Condition()
        self._cancel_requested: set[str] = set()
        self._stopping = False
        self._paused = False
        self._workers: list[threading.Thread] = []
        self._items: list[Item] = self._load()

    # ---- API pública ----

    def add(self, urls: list[str], mode: str, quality: str) -> tuple[list[str], int]:
        validate(mode, quality)
        added: list[str] = []
        duplicates = 0
        with self._cond:
            for url in urls:
                if self._has_active_duplicate(url, mode, quality):
                    duplicates += 1
                    continue
                item = Item(id=uuid.uuid4().hex[:12], url=url, mode=mode, quality=quality, created_at=self._clock())
                self._items.append(item)
                added.append(item.id)
            if added:
                self._save()
                self._cond.notify_all()
        return added, duplicates

    def list(self) -> list[dict]:
        with self._cond:
            return [item.to_dict() for item in self._items]

    def cancel(self, item_id: str) -> dict:
        with self._cond:
            item = self._find(item_id)
            if item.status == WAITING:
                self._finish(item, CANCELLED)
            elif item.status in RUNNING:
                self._cancel_requested.add(item_id)
            return item.to_dict()

    def retry(self, item_id: str) -> dict:
        with self._cond:
            item = self._find(item_id)
            if item.status not in (ERROR, CANCELLED):
                raise ValueError("só dá para tentar de novo itens com erro ou cancelados")
            self._items.remove(item)
            self._items.append(item)
            item.status = WAITING
            item.progress = 0.0
            item.speed = None
            item.filename = None
            item.error_code = item.error_short = item.error_detail = None
            item.finished_at = None
            item.created_at = self._clock()
            self._save()
            self._cond.notify_all()
            return item.to_dict()

    def active_count(self) -> int:
        with self._cond:
            return sum(1 for item in self._items if item.status in RUNNING)

    # ---- internos (chamar com self._cond adquirido) ----

    def _find(self, item_id: str) -> Item:
        for item in self._items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    def _has_active_duplicate(self, url: str, mode: str, quality: str) -> bool:
        return any(
            i.url == url and i.mode == mode and i.quality == quality and i.status in ACTIVE
            for i in self._items
        )

    def _finish(self, item: Item, status: str) -> None:
        item.status = status
        item.speed = None
        item.finished_at = self._clock()
        self._trim_history()
        self._save()
        self._cond.notify_all()

    def _trim_history(self) -> None:
        finished = [i for i in self._items if i.status not in ACTIVE]
        excess = len(finished) - self._history_limit
        if excess > 0:
            oldest = sorted(finished, key=lambda i: i.finished_at or 0.0)[:excess]
            drop = {i.id for i in oldest}
            self._items = [i for i in self._items if i.id not in drop]

    def _load(self) -> list[Item]:
        try:
            raw = json.loads(self._store_path.read_text(encoding="utf-8"))
            items = [Item(**{k: v for k, v in d.items() if k in _FIELDS}) for d in raw["items"]]
        except FileNotFoundError:
            return []
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            log.warning("queue.json inválido, começando com fila vazia: %s", exc)
            backup = self._store_path.with_name(self._store_path.name + ".bad")
            try:
                os.replace(self._store_path, backup)
            except OSError:
                log.exception("não consegui guardar o queue.json inválido")
            return []
        for item in items:
            if item.status in RUNNING:
                item.status = WAITING
                item.progress = 0.0
                item.speed = None
        return items

    def _save(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._store_path.with_name(self._store_path.name + ".tmp")
        payload = {"items": [item.to_dict() for item in self._items]}
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._store_path)
```

> `replace`, `ErrorInfo` e `classify_error` são usados na Task 5; deixar os imports agora evita editar o cabeçalho depois.

- [ ] **Step 4: Rodar e ver passar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_queue_state.py -v`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```powershell
git add helper/videodl/queue.py helper/tests/test_queue_state.py
git commit -m "feat(helper): estado e persistência da fila" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Fila — workers, cancelamento e novas tentativas

**Files:**
- Modify: `helper/videodl/queue.py` (acrescentar métodos ao final da classe `DownloadQueue`)
- Test: `helper/tests/test_queue_workers.py`

**Interfaces:**
- Consumes: tudo da Task 4; `errors.classify_error` / `ErrorInfo`.
- Produces (novos métodos de `DownloadQueue`):
  - `start() -> None` — inicia `max_workers` threads.
  - `stop(timeout: float = 5.0) -> None` — pede parada; itens em andamento ficam como `downloading` no disco e voltam a `waiting` na próxima abertura.
  - `pause() -> None` — workers não pegam itens novos (usado antes de reiniciar após atualização).
  - Contrato do `report(update)`: chaves opcionais `title: str`, `status: "downloading" | "converting"`, `progress: float (0–1)`, `speed: float | None`.

- [ ] **Step 1: Escrever os testes que falham**

`helper/tests/test_queue_workers.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_queue_workers.py -v`
Expected: FAIL com `AttributeError: 'DownloadQueue' object has no attribute 'start'`.

- [ ] **Step 3: Implementar** — acrescentar ao final da classe `DownloadQueue` em `helper/videodl/queue.py`:

```python
    # ---- workers ----

    def start(self) -> None:
        with self._cond:
            self._stopping = False
        for n in range(self._max_workers):
            worker = threading.Thread(target=self._worker, name=f"download-{n + 1}", daemon=True)
            worker.start()
            self._workers.append(worker)

    def stop(self, timeout: float = 5.0) -> None:
        with self._cond:
            self._stopping = True
            self._cond.notify_all()
        for worker in self._workers:
            worker.join(timeout)
        self._workers.clear()

    def pause(self) -> None:
        with self._cond:
            self._paused = True

    def _next_waiting(self) -> Item | None:
        if self._paused or self._stopping:
            return None
        return next((i for i in self._items if i.status == WAITING), None)

    def _worker(self) -> None:
        while True:
            with self._cond:
                item = self._next_waiting()
                while item is None:
                    if self._stopping:
                        return
                    self._cond.wait()
                    item = self._next_waiting()
                item.status = DOWNLOADING
                item.progress = 0.0
                item.error_short = None
                self._save()
            self._run(item)

    def _run(self, item: Item) -> None:
        attempts = 0
        while True:
            try:
                path = self._downloader(
                    replace(item),
                    lambda update: self._report(item, update),
                    lambda: self._is_cancelled(item.id),
                )
            except Cancelled:
                self._on_cancelled(item)
                return
            except Exception as exc:  # qualquer falha do download vira erro do item
                if self._is_cancelled(item.id):
                    self._on_cancelled(item)
                    return
                info = classify_error(str(exc))
                if info.retryable and attempts < len(self._retry_delays):
                    with self._cond:
                        item.error_short = info.short
                    self._sleep(self._retry_delays[attempts])
                    attempts += 1
                    if self._is_cancelled(item.id):
                        self._on_cancelled(item)
                        return
                    continue
                log.warning("download falhou (%s): %s", item.url, exc)
                self._on_error(item, info, str(exc))
                return
            self._on_done(item, path)
            return

    def _report(self, item: Item, update: dict) -> None:
        with self._cond:
            if item.status not in RUNNING:
                return
            changed = False
            status = update.get("status")
            if status in RUNNING and status != item.status:
                item.status = status
                changed = True
            title = update.get("title")
            if title and title != item.title:
                item.title = title
                changed = True
            if "progress" in update:
                item.progress = max(0.0, min(1.0, float(update["progress"] or 0.0)))
            if "speed" in update:
                item.speed = update["speed"]
            if changed:
                self._save()

    def _is_cancelled(self, item_id: str) -> bool:
        with self._cond:
            return item_id in self._cancel_requested or self._stopping

    def _on_cancelled(self, item: Item) -> None:
        with self._cond:
            requested = item.id in self._cancel_requested
            self._cancel_requested.discard(item.id)
            if self._stopping and not requested:
                return  # o programa está fechando: o item volta como "aguardando" na próxima abertura
            self._finish(item, CANCELLED)

    def _on_error(self, item: Item, info: ErrorInfo, detail: str) -> None:
        with self._cond:
            item.error_code = info.code
            item.error_short = info.short
            item.error_detail = detail
            self._finish(item, ERROR)

    def _on_done(self, item: Item, path: str) -> None:
        with self._cond:
            self._cancel_requested.discard(item.id)
            item.filename = path
            item.progress = 1.0
            item.error_code = item.error_short = item.error_detail = None
            self._finish(item, DONE)
```

- [ ] **Step 4: Rodar e ver passar (fila inteira)**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_queue_state.py helper\tests\test_queue_workers.py -v`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```powershell
git add helper/videodl/queue.py helper/tests/test_queue_workers.py
git commit -m "feat(helper): workers da fila com cancelamento e novas tentativas" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Downloader com yt-dlp

**Files:**
- Create: `helper/videodl/downloader.py`
- Test: `helper/tests/test_downloader.py`

**Interfaces:**
- Consumes: `formats.build_format_opts`, `formats.final_extension` (Task 1); `filenames.build_base_name`, `filenames.site_tag`, `filenames.unique_base` (Task 2); `queue.Item`, `queue.Cancelled` (Task 4).
- Produces:
  - `class YtDlpDownloader(download_dir: Path, *, js_runtime: str | None = "node", ydl_factory=...)`
    - `__call__(item: Item, report, is_cancelled) -> str` — cumpre o contrato `Downloader`; devolve o caminho absoluto do arquivo final.
    - `get_info(url: str) -> dict` → `{"title": str, "thumbnail": str | None, "site": str}`
  - `ydl_factory(params: dict)` devolve um objeto usável como context manager com `extract_info(url, download=False)` e `process_ie_result(info, download=True)` (a interface do `yt_dlp.YoutubeDL`).

- [ ] **Step 1: Escrever os testes que falham**

`helper/tests/test_downloader.py`:
```python
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
            return copy.deepcopy(info)

        def process_ie_result(self, entry, download=True):
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
            audio = any(pp["key"] == "FFmpegExtractAudio" for pp in self.params.get("postprocessors", []))
            Path(base + (".mp3" if audio else ".mp4")).write_bytes(b"media")
            return entry

    return FakeYDL, calls


def make_item(mode="video", quality="720"):
    return Item(id="i1", url="https://youtu.be/a", mode=mode, quality=quality)


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


def test_get_info(tmp_path):
    factory, _ = make_factory(INFO)
    info = YtDlpDownloader(tmp_path, ydl_factory=factory).get_info("https://youtu.be/a")
    assert info == {"title": "Meu vídeo", "thumbnail": "https://i.ytimg.com/x.jpg", "site": "youtube"}
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_downloader.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'videodl.downloader'`.

- [ ] **Step 3: Implementar**

`helper/videodl/downloader.py`:
```python
"""Integração com o yt-dlp: baixa um item da fila e busca informações de um link."""

from __future__ import annotations

import glob
import logging
import threading
from pathlib import Path
from typing import Callable

from .filenames import build_base_name, site_tag, unique_base
from .formats import build_format_opts, final_extension
from .queue import Cancelled, Item

log = logging.getLogger(__name__)


class _YtLogger:
    """Manda as mensagens do yt-dlp para o log (pythonw não tem console)."""

    def __init__(self) -> None:
        self._log = logging.getLogger("yt-dlp")

    def debug(self, msg: str) -> None:
        self._log.debug(msg)

    def info(self, msg: str) -> None:
        self._log.info(msg)

    def warning(self, msg: str) -> None:
        self._log.warning(msg)

    def error(self, msg: str) -> None:
        self._log.error(msg)


def _default_factory(params: dict):
    import yt_dlp  # import tardio: a versão nova vale após reiniciar o programa

    return yt_dlp.YoutubeDL(params)


def _single_entry(info: dict) -> dict:
    if info.get("_type") in ("playlist", "multi_video"):
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise RuntimeError("No video formats found: a lista não tem vídeos")
        return entries[0]
    return info


def _site_of(info: dict) -> str:
    return info.get("extractor_key") or info.get("extractor") or "web"


class YtDlpDownloader:
    def __init__(self, download_dir: Path, *, js_runtime: str | None = "node",
                 ydl_factory: Callable[[dict], object] = _default_factory):
        self._dir = Path(download_dir)
        self._js_runtime = js_runtime
        self._factory = ydl_factory
        self._lock = threading.Lock()
        self._reserved: set[str] = set()

    def _base_opts(self) -> dict:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "playlist_items": "1",
            "logger": _YtLogger(),
        }
        if self._js_runtime:
            opts["js_runtimes"] = {self._js_runtime: {}}
        return opts

    def get_info(self, url: str) -> dict:
        with self._factory(self._base_opts()) as ydl:
            info = _single_entry(ydl.extract_info(url, download=False))
        return {"title": info.get("title") or url, "thumbnail": info.get("thumbnail"), "site": site_tag(_site_of(info))}

    def __call__(self, item: Item, report: Callable[[dict], None], is_cancelled: Callable[[], bool]) -> str:
        self._dir.mkdir(parents=True, exist_ok=True)
        with self._factory(self._base_opts()) as ydl:
            info = _single_entry(ydl.extract_info(item.url, download=False))
        if is_cancelled():
            raise Cancelled()
        report({"title": info.get("title") or item.url})

        base = self._reserve(build_base_name(info.get("title"), _site_of(info)))
        target = self._dir / f"{base}.{final_extension(item.mode)}"

        def progress_hook(d: dict) -> None:
            if is_cancelled():
                raise Cancelled()
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                done = d.get("downloaded_bytes") or 0
                progress = min(done / total, 0.99) if total else 0.0
                report({"status": "downloading", "progress": progress, "speed": d.get("speed")})

        def postprocessor_hook(d: dict) -> None:
            if is_cancelled():
                raise Cancelled()
            if d.get("status") == "started":
                report({"status": "converting"})

        opts = {
            **self._base_opts(),
            **build_format_opts(item.mode, item.quality),
            "outtmpl": {"default": str(self._dir / base).replace("%", "%%") + ".%(ext)s"},
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
        }
        try:
            with self._factory(opts) as ydl:
                ydl.process_ie_result(info, download=True)
            if not target.exists():
                raise RuntimeError(f"arquivo final não encontrado: {target.name}")
            return str(target)
        except BaseException:
            self._cleanup(base)
            if is_cancelled():
                raise Cancelled() from None
            raise
        finally:
            self._release(base)

    def _reserve(self, wanted: str) -> str:
        with self._lock:
            base = unique_base(self._dir, wanted, taken=self._reserved)
            self._reserved.add(base)
            return base

    def _release(self, base: str) -> None:
        with self._lock:
            self._reserved.discard(base)

    def _cleanup(self, base: str) -> None:
        for path in self._dir.glob(glob.escape(base) + ".*"):
            try:
                path.unlink()
            except OSError:
                log.warning("não consegui apagar o arquivo parcial %s", path)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_downloader.py -v`
Expected: todos PASS.

- [ ] **Step 5: Verificar a API real do yt-dlp (sem rede)**

Run:
```powershell
helper\.venv\Scripts\python -c "import yt_dlp, inspect; src = inspect.getsource(yt_dlp.YoutubeDL); print('js_runtimes' in src, 'postprocessor_hooks' in src, 'process_ie_result' in src)"
```
Expected: `True True True`. Se `js_runtimes` vier `False`, a versão instalada é antiga: rode `helper\.venv\Scripts\python -m pip install -U "yt-dlp[default]"` e repita.

- [ ] **Step 6: Commit**

```powershell
git add helper/videodl/downloader.py helper/tests/test_downloader.py
git commit -m "feat(helper): downloader com yt-dlp, nomes únicos e limpeza de parciais" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: API HTTP

**Files:**
- Create: `helper/videodl/server.py`
- Test: `helper/tests/test_server.py`

**Interfaces:**
- Consumes: `DownloadQueue` (Tasks 4–5: `add`, `list`, `cancel`, `retry`); `formats.InvalidOptions`; `errors.classify_error`.
- Produces:
  - `class server.Actions(Protocol)`: `status() -> dict`, `info(url: str) -> dict`, `open_folder() -> None`, `update_ytdlp() -> dict`
  - `class server.ApiServer(address: tuple[str, int], queue: DownloadQueue, actions: Actions, allowed_origin: str)` — subclasse de `ThreadingHTTPServer` com bind **exclusivo** (segunda instância na mesma porta → `OSError`).
  - Rotas conforme a tabela da spec. Erros: `{"error": "<mensagem pt-BR>"}` com status 400/403/404/409/413/422/500/502.

- [ ] **Step 1: Escrever os testes que falham**

`helper/tests/test_server.py`:
```python
import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from videodl.queue import DownloadQueue
from videodl.server import ApiServer

ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"


class FakeActions:
    def __init__(self):
        self.opened = 0
        self.info_error = None
        self.update_error = None

    def status(self):
        return {"ok": True, "version": "0.1.0", "ytdlp_version": "2026.09.01", "ffmpeg": True}

    def info(self, url):
        if self.info_error:
            raise self.info_error
        return {"title": "Um vídeo", "thumbnail": None, "site": "youtube"}

    def open_folder(self):
        self.opened += 1

    def update_ytdlp(self):
        if self.update_error:
            raise self.update_error
        return {"ok": True, "version": "2026.10.01", "restarting": False}


@pytest.fixture
def api(tmp_path):
    queue = DownloadQueue(tmp_path / "queue.json", downloader=lambda item, report, is_cancelled: "")
    actions = FakeActions()
    server = ApiServer(("127.0.0.1", 0), queue, actions, ORIGIN)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(method, path, body=None, origin=ORIGIN, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(base + path, data=data, method=method)
        if origin:
            req.add_header("Origin", origin)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with opener.open(req, timeout=5) as res:
                payload = res.read()
                return res.status, (json.loads(payload) if payload else None), res.headers
        except urllib.error.HTTPError as err:
            payload = err.read()
            return err.code, (json.loads(payload) if payload else None), err.headers

    yield SimpleNamespace(call=call, queue=queue, actions=actions, server=server)
    server.shutdown()
    server.server_close()


def test_rejects_missing_or_foreign_origin(api):
    assert api.call("GET", "/status", origin=None)[0] == 403
    assert api.call("GET", "/status", origin="https://evil.example")[0] == 403
    assert api.call("POST", "/queue", {"urls": ["https://youtu.be/a"], "mode": "video", "quality": "best"},
                    origin="https://evil.example")[0] == 403
    assert api.queue.list() == []


def test_preflight(api):
    status, _, headers = api.call("OPTIONS", "/queue")
    assert status == 204
    assert headers["Access-Control-Allow-Origin"] == ORIGIN
    assert "POST" in headers["Access-Control-Allow-Methods"]
    assert api.call("OPTIONS", "/queue", origin="https://evil.example")[0] == 403


def test_status_has_cors_header(api):
    status, body, headers = api.call("GET", "/status")
    assert status == 200 and body["ffmpeg"] is True
    assert headers["Access-Control-Allow-Origin"] == ORIGIN


def test_add_and_list_queue(api):
    status, body, _ = api.call("POST", "/queue", {"urls": ["https://youtu.be/a", "https://youtu.be/a"],
                                                   "mode": "video", "quality": "720"})
    assert status == 200 and len(body["added"]) == 1 and body["duplicates"] == 1
    status, body, _ = api.call("GET", "/queue")
    assert status == 200 and [i["url"] for i in body["items"]] == ["https://youtu.be/a"]


@pytest.mark.parametrize("payload", [
    {"urls": ["ftp://x"], "mode": "video", "quality": "best"},
    {"urls": "https://youtu.be/a", "mode": "video", "quality": "best"},
    {"urls": [], "mode": "video", "quality": "best"},
    {"urls": ["https://youtu.be/a"], "mode": "video", "quality": "320"},
])
def test_add_rejects_bad_input(api, payload):
    status, body, _ = api.call("POST", "/queue", payload)
    assert status == 400 and body["error"]


def test_add_rejects_invalid_json(api):
    assert api.call("POST", "/queue", raw=b"{nao json")[0] == 400


def test_cancel_and_retry(api):
    [item_id], _ = api.queue.add(["https://youtu.be/a"], "video", "best")
    assert api.call("POST", f"/queue/{item_id}/retry")[0] == 409
    status, body, _ = api.call("POST", f"/queue/{item_id}/cancel")
    assert status == 200 and body["status"] == "cancelled"
    status, body, _ = api.call("POST", f"/queue/{item_id}/retry")
    assert status == 200 and body["status"] == "waiting"
    assert api.call("POST", "/queue/nao-existe/cancel")[0] == 404


def test_info(api):
    status, body, _ = api.call("GET", "/info?url=https%3A%2F%2Fyoutu.be%2Fa")
    assert status == 200 and body["title"] == "Um vídeo"
    assert api.call("GET", "/info")[0] == 400


def test_info_error_is_translated(api):
    api.actions.info_error = RuntimeError("ERROR: Unsupported URL: https://example.com")
    status, body, _ = api.call("GET", "/info?url=https%3A%2F%2Fexample.com")
    assert status == 422 and body["error"] == "Esse link não tem vídeo suportado"


def test_open_folder_and_update(api):
    assert api.call("POST", "/open-folder")[0] == 200
    assert api.actions.opened == 1
    status, body, _ = api.call("POST", "/update-ytdlp")
    assert status == 200 and body["version"] == "2026.10.01"


def test_update_failure_returns_message(api):
    api.actions.update_error = RuntimeError("sem internet")
    status, body, _ = api.call("POST", "/update-ytdlp")
    assert status == 502 and "sem internet" in body["error"]


def test_unknown_route(api):
    assert api.call("GET", "/nada")[0] == 404


def test_second_server_on_same_port_fails(api):
    port = api.server.server_address[1]
    with pytest.raises(OSError):
        ApiServer(("127.0.0.1", port), api.queue, api.actions, ORIGIN)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_server.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'videodl.server'`.

- [ ] **Step 3: Implementar**

`helper/videodl/server.py`:
```python
"""API HTTP local usada pela extensão. Só aceita a origem da própria extensão."""

from __future__ import annotations

import json
import logging
import re
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from .errors import classify_error
from .formats import InvalidOptions
from .queue import DownloadQueue

log = logging.getLogger(__name__)

MAX_BODY = 1_000_000
MAX_URLS = 200
_ITEM_ACTION = re.compile(r"/queue/([\w-]+)/(cancel|retry)")


class Actions(Protocol):
    def status(self) -> dict: ...
    def info(self, url: str) -> dict: ...
    def open_folder(self) -> None: ...
    def update_ytdlp(self) -> dict: ...


class ApiError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _require_http_url(url: object) -> str:
    if not isinstance(url, str):
        raise ApiError(400, "link inválido")
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ApiError(400, f"link inválido: {url[:100]}")
    return url


class ApiServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # no Windows, reuse permitiria duas instâncias na mesma porta

    def __init__(self, address: tuple[str, int], queue: DownloadQueue, actions: Actions, allowed_origin: str):
        self.queue = queue
        self.actions = actions
        self.allowed_origin = allowed_origin
        super().__init__(address, ApiHandler)

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class ApiHandler(BaseHTTPRequestHandler):
    server: ApiServer

    def log_message(self, fmt: str, *args) -> None:
        log.debug("%s - %s", self.address_string(), fmt % args)

    def _origin_ok(self) -> bool:
        return self.headers.get("Origin") == self.server.allowed_origin

    def _cors_headers(self) -> None:
        if self._origin_ok():
            self.send_header("Access-Control-Allow-Origin", self.server.allowed_origin)
            self.send_header("Vary", "Origin")

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        if not self._origin_ok():
            self._send(403, {"error": "origem não permitida"})
            return
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        if not self._origin_ok():
            self._send(403, {"error": "origem não permitida"})
            return
        parts = urlsplit(self.path)
        try:
            code, payload = self._route(method, parts.path, parse_qs(parts.query))
        except ApiError as exc:
            code, payload = exc.code, {"error": exc.message}
        except Exception:
            log.exception("erro inesperado em %s %s", method, self.path)
            code, payload = 500, {"error": "erro interno do programa"}
        self._send(code, payload)

    def _route(self, method: str, path: str, query: dict) -> tuple[int, dict]:
        queue, actions = self.server.queue, self.server.actions

        if method == "GET" and path == "/status":
            return 200, actions.status()

        if method == "GET" and path == "/info":
            url = _require_http_url((query.get("url") or [""])[0])
            try:
                return 200, actions.info(url)
            except Exception as exc:
                log.info("info falhou para %s: %s", url, exc)
                raise ApiError(422, classify_error(str(exc)).short) from None

        if path == "/queue" and method == "GET":
            return 200, {"items": queue.list()}

        if path == "/queue" and method == "POST":
            body = self._json_body()
            urls = body.get("urls")
            if not isinstance(urls, list) or not urls:
                raise ApiError(400, "envie ao menos um link")
            if len(urls) > MAX_URLS:
                raise ApiError(400, f"no máximo {MAX_URLS} links por vez")
            clean = [_require_http_url(u) for u in urls]
            try:
                added, duplicates = queue.add(clean, body.get("mode"), body.get("quality"))
            except InvalidOptions as exc:
                raise ApiError(400, str(exc)) from None
            return 200, {"added": added, "duplicates": duplicates}

        match = _ITEM_ACTION.fullmatch(path)
        if method == "POST" and match:
            item_id, action = match.groups()
            try:
                item = queue.cancel(item_id) if action == "cancel" else queue.retry(item_id)
            except KeyError:
                raise ApiError(404, "item não encontrado") from None
            except ValueError as exc:
                raise ApiError(409, str(exc)) from None
            return 200, item

        if method == "POST" and path == "/open-folder":
            actions.open_folder()
            return 200, {"ok": True}

        if method == "POST" and path == "/update-ytdlp":
            try:
                return 200, actions.update_ytdlp()
            except Exception as exc:
                log.warning("atualização falhou: %s", exc)
                raise ApiError(502, f"Falha ao atualizar: {exc}") from None

        raise ApiError(404, "rota não encontrada")

    def _json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "corpo inválido") from None
        if length > MAX_BODY:
            raise ApiError(413, "corpo grande demais")
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError):
            raise ApiError(400, "JSON inválido") from None
        if not isinstance(data, dict):
            raise ApiError(400, "JSON inválido")
        return data
```

- [ ] **Step 4: Rodar e ver passar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_server.py -v`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```powershell
git add helper/videodl/server.py helper/tests/test_server.py
git commit -m "feat(helper): API HTTP local com validação de origem" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Atualizador do yt-dlp e atalhos do Windows

**Files:**
- Create: `helper/videodl/updater.py`, `helper/videodl/startup.py`
- Test: `helper/tests/test_updater.py`, `helper/tests/test_startup.py`

**Interfaces:**
- Produces:
  - `class updater.UpdateError(Exception)`
  - `class updater.Updater(state_path: Path, *, python: str | None = None, run=subprocess.run, clock=time.time)`: `INTERVAL = 86400`; `due() -> bool`; `installed_version() -> str`; `update() -> tuple[bool, str]` (mudou?, versão atual). Só grava `last_update` quando o pip termina com sucesso.
  - `startup.SHORTCUT_NAME = "Video Downloader.lnk"`, `startup.HELPER_DIR: Path`, `startup.startup_shortcut() -> Path`, `startup.start_menu_shortcut() -> Path`, `startup.create_shortcut(link: Path, run=subprocess.run) -> None`, `startup.is_enabled() -> bool`, `startup.enable(run=subprocess.run) -> None`, `startup.disable() -> None`, `startup.install_shortcuts(run=subprocess.run) -> None`.

- [ ] **Step 1: Escrever os testes que falham**

`helper/tests/test_updater.py`:
```python
import json
from types import SimpleNamespace

import pytest

from videodl.updater import UpdateError, Updater


class FakeRun:
    def __init__(self, versions, pip_rc=0, pip_err=""):
        self.versions = list(versions)
        self.pip_rc = pip_rc
        self.pip_err = pip_err
        self.commands = []

    def __call__(self, cmd, **kwargs):
        self.commands.append(cmd)
        if "-c" in cmd:
            return SimpleNamespace(returncode=0, stdout=self.versions.pop(0) + "\n", stderr="")
        return SimpleNamespace(returncode=self.pip_rc, stdout="", stderr=self.pip_err)


def make(tmp_path, run, now=1_000_000.0):
    return Updater(tmp_path / "update.json", python="py", run=run, clock=lambda: now)


def test_due_without_state(tmp_path):
    assert make(tmp_path, FakeRun([])).due() is True


def test_not_due_right_after_update_and_due_a_day_later(tmp_path):
    make(tmp_path, FakeRun(["2026.09.01", "2026.10.01"])).update()
    assert make(tmp_path, FakeRun([]), now=1_000_000.0 + 3600).due() is False
    assert make(tmp_path, FakeRun([]), now=1_000_000.0 + 86400).due() is True


def test_corrupt_state_is_due(tmp_path):
    (tmp_path / "update.json").write_text("lixo", encoding="utf-8")
    assert make(tmp_path, FakeRun([])).due() is True


def test_update_reports_change_and_calls_pip(tmp_path):
    run = FakeRun(["2026.09.01", "2026.10.01"])
    assert make(tmp_path, run).update() == (True, "2026.10.01")
    assert ["py", "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "yt-dlp[default]"] in run.commands
    assert json.loads((tmp_path / "update.json").read_text(encoding="utf-8"))["version"] == "2026.10.01"


def test_update_without_change(tmp_path):
    assert make(tmp_path, FakeRun(["2026.10.01", "2026.10.01"])).update() == (False, "2026.10.01")


def test_pip_failure_raises_and_stays_due(tmp_path):
    updater = make(tmp_path, FakeRun(["2026.09.01"], pip_rc=1, pip_err="ERROR: sem internet"))
    with pytest.raises(UpdateError, match="sem internet"):
        updater.update()
    assert updater.due() is True
```

`helper/tests/test_startup.py`:
```python
from videodl import startup


def test_enable_creates_startup_shortcut_via_powershell(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    commands = []
    startup.enable(run=lambda cmd, **kwargs: commands.append(cmd))
    expected = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Video Downloader.lnk"
    [cmd] = commands
    assert cmd[:2] == ["powershell", "-NoProfile"]
    assert str(expected) in cmd[-1]
    assert "-m videodl" in cmd[-1]
    assert expected.parent.is_dir()


def test_install_shortcuts_creates_both(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    commands = []
    startup.install_shortcuts(run=lambda cmd, **kwargs: commands.append(cmd))
    assert len(commands) == 2
    assert str(startup.start_menu_shortcut()) in commands[0][-1]
    assert str(startup.startup_shortcut()) in commands[1][-1]


def test_is_enabled_and_disable(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    link = startup.startup_shortcut()
    link.parent.mkdir(parents=True)
    link.write_bytes(b"")
    assert startup.is_enabled() is True
    startup.disable()
    assert startup.is_enabled() is False
    startup.disable()  # não falha se já não existe


def test_quotes_apostrophes_for_powershell():
    assert startup._ps_quote("C:\\a'b") == "'C:\\a''b'"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_updater.py helper\tests\test_startup.py -v`
Expected: FAIL com `ModuleNotFoundError` para `videodl.updater` e `videodl.startup`.

- [ ] **Step 3: Implementar**

`helper/videodl/updater.py`:
```python
"""Atualiza o yt-dlp via pip, no máximo uma vez por dia."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class UpdateError(Exception):
    """pip falhou ao atualizar o yt-dlp."""


def _console_python() -> str:
    exe = Path(sys.executable)
    candidate = exe.with_name("python.exe")
    return str(candidate if candidate.exists() else exe)


class Updater:
    INTERVAL = 24 * 3600

    def __init__(self, state_path: Path, *, python: str | None = None,
                 run: Callable = subprocess.run, clock: Callable[[], float] = time.time):
        self._state_path = Path(state_path)
        self._python = python or _console_python()
        self._run = run
        self._clock = clock

    def due(self) -> bool:
        try:
            last = float(json.loads(self._state_path.read_text(encoding="utf-8"))["last_update"])
        except (FileNotFoundError, ValueError, KeyError, TypeError):
            return True
        return self._clock() - last >= self.INTERVAL

    def installed_version(self) -> str:
        result = self._run(
            [self._python, "-c", "import yt_dlp.version as v; print(v.__version__)"],
            capture_output=True, text=True, timeout=60, creationflags=_NO_WINDOW,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def update(self) -> tuple[bool, str]:
        before = self.installed_version()
        try:
            result = self._run(
                [self._python, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "yt-dlp[default]"],
                capture_output=True, text=True, timeout=600, creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            raise UpdateError("o pip demorou demais") from None
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "").strip()[-500:]
            raise UpdateError(message or f"pip saiu com código {result.returncode}")
        after = self.installed_version()
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps({"last_update": self._clock(), "version": after}), encoding="utf-8")
        return after != before, after
```

`helper/videodl/startup.py`:
```python
"""Atalhos do Windows: menu Iniciar e pasta Inicializar (abrir com o Windows)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

SHORTCUT_NAME = "Video Downloader.lnk"
HELPER_DIR = Path(__file__).resolve().parent.parent
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _programs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def startup_shortcut() -> Path:
    return _programs_dir() / "Startup" / SHORTCUT_NAME


def start_menu_shortcut() -> Path:
    return _programs_dir() / SHORTCUT_NAME


def _pythonw() -> Path:
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return candidate if candidate.exists() else exe


def _ps_quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def create_shortcut(link: Path, run: Callable = subprocess.run) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({_ps_quote(link)});"
        f"$s.TargetPath = {_ps_quote(_pythonw())};"
        "$s.Arguments = '-m videodl';"
        f"$s.WorkingDirectory = {_ps_quote(HELPER_DIR)};"
        "$s.Description = 'Vídeo Downloader';"
        "$s.Save()"
    )
    run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True, capture_output=True, creationflags=_NO_WINDOW)


def is_enabled() -> bool:
    return startup_shortcut().exists()


def enable(run: Callable = subprocess.run) -> None:
    create_shortcut(startup_shortcut(), run)


def disable() -> None:
    startup_shortcut().unlink(missing_ok=True)


def install_shortcuts(run: Callable = subprocess.run) -> None:
    create_shortcut(start_menu_shortcut(), run)
    enable(run)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_updater.py helper\tests\test_startup.py -v`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```powershell
git add helper/videodl/updater.py helper/videodl/startup.py helper/tests/test_updater.py helper/tests/test_startup.py
git commit -m "feat(helper): atualização diária do yt-dlp e atalhos do Windows" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: ID fixo da extensão e caminhos

**Files:**
- Create: `helper/videodl/extension_key.py`, `helper/videodl/paths.py`, `scripts/gen_extension_key.py`, `extension/manifest.json`
- Generated: `helper/videodl/extension_id.txt` (pelo script)
- Test: `helper/tests/test_paths.py`

**Interfaces:**
- Produces:
  - `extension_key.extension_id_from_der(der: bytes) -> str` (32 letras `a`–`p`, algoritmo do Chrome: SHA-256 da chave pública DER, 32 primeiros dígitos hex mapeados 0→a … f→p)
  - `extension_key.manifest_key_from_der(der: bytes) -> str` (base64)
  - `paths.app_dir() -> Path`, `paths.download_dir() -> Path`, `paths.EXTENSION_ID_FILE: Path`, `paths.extension_origin(path: Path = EXTENSION_ID_FILE) -> str` (levanta `RuntimeError` com dica se faltar/inválido)

- [ ] **Step 1: Escrever os testes que falham**

`helper/tests/test_paths.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_paths.py -v`
Expected: FAIL com `ImportError` (`videodl.paths` / `videodl.extension_key` não existem).

- [ ] **Step 3: Implementar**

`helper/videodl/extension_key.py`:
```python
"""Cálculo do ID de extensão Chromium a partir da chave pública."""

from __future__ import annotations

import base64
import hashlib


def extension_id_from_der(der: bytes) -> str:
    digest = hashlib.sha256(der).hexdigest()[:32]
    return "".join(chr(ord("a") + int(ch, 16)) for ch in digest)


def manifest_key_from_der(der: bytes) -> str:
    return base64.b64encode(der).decode("ascii")
```

`helper/videodl/paths.py`:
```python
"""Pastas do programa e origem permitida da extensão."""

from __future__ import annotations

import os
import re
from pathlib import Path

EXTENSION_ID_FILE = Path(__file__).with_name("extension_id.txt")
_HINT = "rode: helper\\.venv\\Scripts\\python scripts\\gen_extension_key.py"


def app_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "VideoDownloader"


def download_dir() -> Path:
    return Path.home() / "Downloads" / "Video Downloader"


def extension_origin(path: Path = EXTENSION_ID_FILE) -> str:
    try:
        ext_id = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise RuntimeError(f"ID da extensão não encontrado em {path}; {_HINT}") from None
    if not re.fullmatch(r"[a-p]{32}", ext_id):
        raise RuntimeError(f"ID da extensão inválido em {path}; {_HINT}")
    return f"chrome-extension://{ext_id}"
```

`extension/manifest.json`:
```json
{
  "manifest_version": 3,
  "name": "Vídeo Downloader",
  "version": "0.1.0",
  "description": "Baixe vídeos e áudios do YouTube, TikTok, Instagram e Pinterest.",
  "action": {
    "default_popup": "popup.html",
    "default_title": "Vídeo Downloader"
  },
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["http://127.0.0.1:47321/*"]
}
```

`scripts/gen_extension_key.py`:
```python
"""Gera a chave fixa da extensão: grava "key" no manifest e o ID em helper/videodl/extension_id.txt.

Rode uma única vez: trocar a chave muda o ID da extensão.
Uso: helper\\.venv\\Scripts\\python scripts\\gen_extension_key.py [--force]
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "helper"))

from videodl.extension_key import extension_id_from_der, manifest_key_from_der  # noqa: E402

MANIFEST = ROOT / "extension" / "manifest.json"
ID_FILE = ROOT / "helper" / "videodl" / "extension_id.txt"
GIT_OPENSSL = (
    Path(r"C:\Program Files\Git\usr\bin\openssl.exe"),
    Path(r"C:\Program Files\Git\mingw64\bin\openssl.exe"),
)


def find_openssl() -> str:
    found = shutil.which("openssl")
    if found:
        return found
    for candidate in GIT_OPENSSL:
        if candidate.exists():
            return str(candidate)
    sys.exit("openssl não encontrado (ele vem com o Git for Windows)")


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("key") and "--force" not in sys.argv:
        sys.exit("o manifest já tem 'key'; use --force para trocar (isso muda o ID da extensão)")
    openssl = find_openssl()
    private_pem = subprocess.run(
        [openssl, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048"],
        check=True, capture_output=True,
    ).stdout
    public_der = subprocess.run(
        [openssl, "pkey", "-pubout", "-outform", "DER"],
        input=private_pem, check=True, capture_output=True,
    ).stdout
    manifest["key"] = manifest_key_from_der(public_der)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ext_id = extension_id_from_der(public_der)
    ID_FILE.write_text(ext_id + "\n", encoding="utf-8")
    print(f"ID da extensão: {ext_id}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_paths.py -v`
Expected: todos PASS.

- [ ] **Step 5: Gerar a chave e o ID**

Run: `helper\.venv\Scripts\python scripts\gen_extension_key.py`
Expected: imprime `ID da extensão: <32 letras a-p>`; `extension/manifest.json` passa a ter `"key"`; `helper/videodl/extension_id.txt` existe com o mesmo ID.

Run: `helper\.venv\Scripts\python -c "import sys; sys.path.insert(0,'helper'); from videodl.paths import extension_origin; print(extension_origin())"`
Expected: `chrome-extension://<mesmo ID>`.

- [ ] **Step 6: Commit**

```powershell
git add helper/videodl/extension_key.py helper/videodl/paths.py helper/videodl/extension_id.txt helper/tests/test_paths.py scripts/gen_extension_key.py extension/manifest.json
git commit -m "feat: ID fixo da extensão e caminhos do programa" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: App — ícone, bandeja e inicialização

**Files:**
- Create: `helper/videodl/icon.py`, `helper/videodl/tray.py`, `helper/videodl/app.py`, `helper/videodl/__main__.py`
- Test: `helper/tests/test_app.py`

**Interfaces:**
- Consumes: `paths` (Task 9), `startup` + `Updater`/`UpdateError` (Task 8), `ApiServer` (Task 7), `YtDlpDownloader` (Task 6), `DownloadQueue` com `start/stop/pause/active_count` (Tasks 4–5).
- Produces:
  - `icon.draw_icon(size: int) -> PIL.Image.Image` (RGBA, `size`×`size`)
  - `tray.build_icon(actions, on_quit: Callable[[], None], on_update: Callable[[], None]) -> pystray.Icon`
  - `app.PORT = 47321`
  - `app.start_server_with_retry(factory: Callable[[], T], attempts: int, delay: float = 0.5, sleep=time.sleep) -> T | None`
  - `class app.AppActions(downloader, updater, download_dir: Path, request_restart: Callable[[], None])` — implementa `server.Actions`.
  - `app.main(argv: list[str] | None = None) -> int`; flag `--wait-for-port` (tenta a porta por ~10 s, usada no reinício).

- [ ] **Step 1: Escrever os testes que falham**

`helper/tests/test_app.py`:
```python
import pytest

from videodl.app import AppActions, start_server_with_retry
from videodl.icon import draw_icon
from videodl.updater import UpdateError


def test_retry_returns_server_when_port_frees():
    attempts = []

    def factory():
        attempts.append(1)
        if len(attempts) < 3:
            raise OSError("porta ocupada")
        return "server"

    assert start_server_with_retry(factory, attempts=5, sleep=lambda s: None) == "server"
    assert len(attempts) == 3


def test_retry_gives_up_when_another_instance_holds_port():
    attempts = []

    def factory():
        attempts.append(1)
        raise OSError("porta ocupada")

    assert start_server_with_retry(factory, attempts=1, sleep=lambda s: None) is None
    assert len(attempts) == 1


class FakeUpdater:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def update(self):
        if self.error:
            raise self.error
        return self.result


def test_status_reports_missing_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr("videodl.app.shutil.which", lambda name: None)
    status = AppActions(None, FakeUpdater(), tmp_path, lambda: None).status()
    assert status["ok"] is True and status["ffmpeg"] is False and status["version"] == "0.1.0"


def test_update_requests_restart_when_version_changes(tmp_path):
    restarts = []
    actions = AppActions(None, FakeUpdater((True, "2026.10.01")), tmp_path, lambda: restarts.append(1))
    assert actions.update_ytdlp() == {"ok": True, "version": "2026.10.01", "restarting": True}
    assert restarts == [1]


def test_update_without_change_does_not_restart(tmp_path):
    restarts = []
    actions = AppActions(None, FakeUpdater((False, "2026.10.01")), tmp_path, lambda: restarts.append(1))
    assert actions.update_ytdlp()["restarting"] is False
    assert restarts == []


def test_update_failure_propagates(tmp_path):
    actions = AppActions(None, FakeUpdater(error=UpdateError("sem internet")), tmp_path, lambda: None)
    with pytest.raises(UpdateError):
        actions.update_ytdlp()


def test_icon_has_requested_size():
    image = draw_icon(16)
    assert image.size == (16, 16) and image.mode == "RGBA"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `helper\.venv\Scripts\python -m pytest helper\tests\test_app.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'videodl.app'`.

- [ ] **Step 3: Implementar**

`helper/videodl/icon.py`:
```python
"""Desenho do ícone (bandeja e extensão): seta de download branca sobre fundo vermelho."""

from __future__ import annotations

from PIL import Image, ImageDraw

BACKGROUND = (225, 48, 64, 255)
FOREGROUND = (255, 255, 255, 255)


def draw_icon(size: int) -> Image.Image:
    s = size * 4  # desenha maior e reduz para suavizar as bordas
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=BACKGROUND)
    cx = s / 2
    draw.rectangle((cx - s * 0.08, s * 0.18, cx + s * 0.08, s * 0.50), fill=FOREGROUND)
    draw.polygon([(cx - s * 0.24, s * 0.46), (cx + s * 0.24, s * 0.46), (cx, s * 0.70)], fill=FOREGROUND)
    draw.rounded_rectangle((s * 0.22, s * 0.76, s * 0.78, s * 0.84), radius=int(s * 0.04), fill=FOREGROUND)
    return image.resize((size, size), Image.LANCZOS)
```

`helper/videodl/tray.py`:
```python
"""Ícone na bandeja do Windows."""

from __future__ import annotations

from typing import Callable

import pystray

from . import startup
from .icon import draw_icon


def build_icon(actions, on_quit: Callable[[], None], on_update: Callable[[], None]) -> pystray.Icon:
    def toggle_startup(icon, item) -> None:
        if startup.is_enabled():
            startup.disable()
        else:
            startup.enable()

    menu = pystray.Menu(
        pystray.MenuItem("Abrir pasta", lambda icon, item: actions.open_folder(), default=True),
        pystray.MenuItem("Atualizar yt-dlp", lambda icon, item: on_update()),
        pystray.MenuItem("Iniciar com o Windows", toggle_startup, checked=lambda item: startup.is_enabled()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", lambda icon, item: on_quit()),
    )
    return pystray.Icon("video-downloader", draw_icon(64), "Vídeo Downloader", menu)
```

`helper/videodl/app.py`:
```python
"""Ponto de entrada: sobe a fila, a API e o ícone da bandeja."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, TypeVar

from . import __version__, paths
from .downloader import YtDlpDownloader
from .queue import DownloadQueue
from .server import ApiServer
from .updater import Updater

PORT = 47321
HELPER_DIR = Path(__file__).resolve().parent.parent
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
log = logging.getLogger("videodl")
T = TypeVar("T")


def start_server_with_retry(factory: Callable[[], T], attempts: int, delay: float = 0.5,
                            sleep: Callable[[float], None] = time.sleep) -> T | None:
    for n in range(attempts):
        try:
            return factory()
        except OSError as exc:
            log.info("porta %d ocupada (%s), tentativa %d/%d", PORT, exc, n + 1, attempts)
            if n + 1 < attempts:
                sleep(delay)
    return None


def _ytdlp_version() -> str | None:
    try:
        from yt_dlp.version import __version__ as version
    except Exception:
        return None
    return version


class AppActions:
    def __init__(self, downloader, updater, download_dir: Path, request_restart: Callable[[], None]):
        self._downloader = downloader
        self._updater = updater
        self._dir = Path(download_dir)
        self._request_restart = request_restart

    def status(self) -> dict:
        return {
            "ok": True,
            "version": __version__,
            "ytdlp_version": _ytdlp_version(),
            "ffmpeg": shutil.which("ffmpeg") is not None,
        }

    def info(self, url: str) -> dict:
        return self._downloader.get_info(url)

    def open_folder(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self._dir)  # type: ignore[attr-defined]  # só existe no Windows

    def update_ytdlp(self) -> dict:
        changed, version = self._updater.update()
        if changed:
            self._request_restart()
        return {"ok": True, "version": version, "restarting": changed}


class App:
    def __init__(self, wait_for_port: bool):
        self._wait_for_port = wait_for_port
        self._restarting = threading.Event()
        self.icon = None

    def run(self) -> int:
        app_dir = paths.app_dir()
        app_dir.mkdir(parents=True, exist_ok=True)
        download_dir = paths.download_dir()
        node = "node" if shutil.which("node") else None
        if node is None:
            log.warning("Node não encontrado: downloads do YouTube podem falhar")
        downloader = YtDlpDownloader(download_dir, js_runtime=node)
        self.queue = DownloadQueue(app_dir / "queue.json", downloader)
        self.updater = Updater(app_dir / "update.json")
        self.actions = AppActions(downloader, self.updater, download_dir, self.request_restart)
        origin = paths.extension_origin()

        self.server = start_server_with_retry(
            lambda: ApiServer(("127.0.0.1", PORT), self.queue, self.actions, origin),
            attempts=20 if self._wait_for_port else 1,
        )
        if self.server is None:
            log.info("outra instância já está rodando; saindo")
            return 0

        self.queue.start()
        threading.Thread(target=self.server.serve_forever, name="api", daemon=True).start()
        threading.Thread(target=self._auto_update, name="auto-update", daemon=True).start()
        log.info("Vídeo Downloader %s ouvindo em 127.0.0.1:%d", __version__, PORT)

        from .tray import build_icon  # import tardio: pystray só é necessário aqui

        self.icon = build_icon(self.actions, on_quit=self.shutdown, on_update=self._tray_update)
        self.icon.run()
        return 0

    def shutdown(self) -> None:
        log.info("encerrando")
        self.server.shutdown()
        self.server.server_close()
        self.queue.stop()
        if self.icon is not None:
            self.icon.stop()

    def request_restart(self) -> None:
        if self._restarting.is_set():
            return
        self._restarting.set()
        self.queue.pause()
        threading.Thread(target=self._restart_when_idle, name="restart", daemon=True).start()

    def _restart_when_idle(self) -> None:
        while self.queue.active_count() > 0:
            time.sleep(2)
        log.info("reiniciando para carregar a nova versão do yt-dlp")
        subprocess.Popen([sys.executable, "-m", "videodl", "--wait-for-port"],
                         cwd=HELPER_DIR, creationflags=_NO_WINDOW)
        self.shutdown()

    def _auto_update(self) -> None:
        if not self.updater.due():
            return
        try:
            changed, version = self.updater.update()
        except Exception:
            log.exception("atualização automática do yt-dlp falhou")
            return
        log.info("yt-dlp verificado: %s (mudou: %s)", version, changed)
        if changed:
            self.request_restart()

    def _tray_update(self) -> None:
        def work() -> None:
            try:
                result = self.actions.update_ytdlp()
                message = f"yt-dlp {result['version']}" + (" — reiniciando" if result["restarting"] else " — já está atualizado")
            except Exception as exc:
                message = f"Falha ao atualizar: {exc}"
            if self.icon is not None:
                self.icon.notify(message, "Vídeo Downloader")

        threading.Thread(target=work, name="tray-update", daemon=True).start()


def _fix_std_streams() -> None:
    # pythonw não tem console: sys.stdout/stderr são None
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _setup_logging(app_dir: Path) -> None:
    app_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(app_dir / "log.txt", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="videodl")
    parser.add_argument("--wait-for-port", action="store_true", help="espera a porta liberar (usado ao reiniciar)")
    args = parser.parse_args(argv)
    _fix_std_streams()
    _setup_logging(paths.app_dir())
    try:
        return App(args.wait_for_port).run()
    except Exception:
        log.exception("falha fatal")
        return 1
```

`helper/videodl/__main__.py`:
```python
import sys

from .app import main

sys.exit(main())
```

- [ ] **Step 4: Rodar e ver passar (suíte inteira)**

Run: `helper\.venv\Scripts\python -m pytest helper\tests -v`
Expected: todos PASS.

- [ ] **Step 5: Verificação manual do programa rodando**

Run (deixa o helper rodando em segundo plano):
```powershell
Start-Process helper\.venv\Scripts\pythonw.exe -ArgumentList "-m","videodl" -WorkingDirectory helper
```
Run:
```powershell
$origin = "chrome-extension://" + (Get-Content helper\videodl\extension_id.txt).Trim()
curl.exe -s -H "Origin: $origin" http://127.0.0.1:47321/status
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:47321/status
```
Expected: primeiro comando imprime JSON com `"ok": true`; segundo imprime `403`. O ícone vermelho aparece na bandeja.

Run (segunda instância deve sair sozinha; `-m videodl` precisa rodar de dentro de `helper`):
```powershell
Push-Location helper; .\.venv\Scripts\python -m videodl; echo "saiu: $LASTEXITCODE"; Pop-Location
```
Expected: `saiu: 0` em poucos segundos; o log `$env:LOCALAPPDATA\VideoDownloader\log.txt` contém `outra instância já está rodando`.

Encerre pelo menu da bandeja → **Sair**.

- [ ] **Step 6: Commit**

```powershell
git add helper/videodl/icon.py helper/videodl/tray.py helper/videodl/app.py helper/videodl/__main__.py helper/tests/test_app.py
git commit -m "feat(helper): app com bandeja, reinício após atualização e instância única" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Extensão — lógica pura (links, formatação, preferências, cliente da API)

**Files:**
- Create: `package.json`, `extension/lib/links.js`, `extension/lib/format.js`, `extension/lib/prefs.js`, `extension/lib/api.js`
- Test: `extension/tests/links.test.js`, `extension/tests/format.test.js`, `extension/tests/prefs.test.js`, `extension/tests/api.test.js`

**Interfaces:**
- Produces:
  - `links.js`: `detectSite(url: string): "youtube"|"tiktok"|"instagram"|"pinterest"|null`; `isLikelyVideoUrl(url: string): boolean`; `parseLinks(text: string): {urls: string[], ignored: number}`
  - `format.js`: `formatSpeed(bytesPerSec): string`; `percent(p): string`; `statusLabel(status): string`; `qualityOptions(mode): [value, label][]`; `qualityLabel(mode, quality): string`
  - `prefs.js`: `DEFAULT_PREFS`; `normalizePrefs(raw): {mode, quality}`; `loadPrefs(storage): Promise<prefs>`; `savePrefs(storage, prefs): Promise<void>` (`storage` = `chrome.storage.local` ou fake com `get/set`)
  - `api.js`: `BASE = "http://127.0.0.1:47321"`; `class ApiError extends Error { status; get offline() }`; `api.status()`, `api.info(url)`, `api.addToQueue(urls, mode, quality)`, `api.queue()`, `api.cancel(id)`, `api.retry(id)`, `api.openFolder()`, `api.updateYtdlp()`

- [ ] **Step 1: Criar `package.json` (raiz)**

```json
{
  "name": "video-downloader",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test \"extension/tests/*.test.js\""
  }
}
```

- [ ] **Step 2: Escrever os testes que falham**

`extension/tests/links.test.js`:
```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { detectSite, isLikelyVideoUrl, parseLinks } from "../lib/links.js";

test("parseLinks extrai links de texto do WhatsApp", () => {
  const text = "olha isso https://youtu.be/abc123!!\n\nbom dia\nhttps://www.tiktok.com/@a/video/123, https://youtu.be/abc123";
  assert.deepEqual(parseLinks(text), {
    urls: ["https://youtu.be/abc123", "https://www.tiktok.com/@a/video/123"],
    ignored: 1,
  });
});

test("parseLinks aceita CRLF, parênteses e ignora ftp", () => {
  const text = "(https://pin.it/abc)\r\nftp://arquivo\r\nhttps://www.instagram.com/reel/xyz/";
  assert.deepEqual(parseLinks(text), {
    urls: ["https://pin.it/abc", "https://www.instagram.com/reel/xyz/"],
    ignored: 1,
  });
});

test("parseLinks com texto vazio", () => {
  assert.deepEqual(parseLinks("  \n "), { urls: [], ignored: 0 });
});

test("detectSite reconhece domínios e links curtos", () => {
  assert.equal(detectSite("https://m.youtube.com/watch?v=x"), "youtube");
  assert.equal(detectSite("https://youtu.be/x"), "youtube");
  assert.equal(detectSite("https://vm.tiktok.com/ZM123/"), "tiktok");
  assert.equal(detectSite("https://www.instagram.com/reel/abc/"), "instagram");
  assert.equal(detectSite("https://br.pinterest.com/pin/123/"), "pinterest");
  assert.equal(detectSite("https://pin.it/abc"), "pinterest");
});

test("detectSite rejeita o resto", () => {
  assert.equal(detectSite("https://example.com"), null);
  assert.equal(detectSite("https://notyoutube.com/watch?v=x"), null);
  assert.equal(detectSite("chrome://extensions"), null);
  assert.equal(detectSite("não é url"), null);
});

test("isLikelyVideoUrl aceita páginas de vídeo", () => {
  for (const url of [
    "https://www.youtube.com/watch?v=abc",
    "https://www.youtube.com/shorts/abc",
    "https://youtu.be/abc",
    "https://www.tiktok.com/@a/video/123",
    "https://vm.tiktok.com/ZM123/",
    "https://www.instagram.com/reel/abc/",
    "https://www.instagram.com/p/abc/",
    "https://br.pinterest.com/pin/123/",
    "https://pin.it/abc",
  ]) {
    assert.equal(isLikelyVideoUrl(url), true, url);
  }
});

test("isLikelyVideoUrl recusa páginas que não são vídeo", () => {
  for (const url of [
    "https://www.youtube.com/",
    "https://www.youtube.com/@canal",
    "https://www.instagram.com/usuario/",
    "https://www.tiktok.com/@a",
    "https://example.com/video/1",
  ]) {
    assert.equal(isLikelyVideoUrl(url), false, url);
  }
});
```

`extension/tests/format.test.js`:
```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { formatSpeed, percent, qualityLabel, qualityOptions, statusLabel } from "../lib/format.js";

test("formatSpeed", () => {
  assert.equal(formatSpeed(0), "");
  assert.equal(formatSpeed(null), "");
  assert.equal(formatSpeed(2048), "2 KB/s");
  assert.equal(formatSpeed(1572864), "1,5 MB/s");
});

test("percent", () => {
  assert.equal(percent(0.456), "46%");
  assert.equal(percent(2), "100%");
  assert.equal(percent(undefined), "0%");
});

test("statusLabel", () => {
  assert.equal(statusLabel("converting"), "Convertendo");
  assert.equal(statusLabel("done"), "Concluído");
  assert.equal(statusLabel("estranho"), "estranho");
});

test("qualityOptions e qualityLabel", () => {
  assert.deepEqual(qualityOptions("video")[0], ["best", "Melhor disponível"]);
  assert.deepEqual(qualityOptions("audio")[0], ["320", "320 kbps"]);
  assert.equal(qualityLabel("video", "720"), "720p");
  assert.equal(qualityLabel("audio", "192"), "192 kbps");
  assert.equal(qualityLabel("video", "999"), "999");
});
```

`extension/tests/prefs.test.js`:
```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPrefs, savePrefs } from "../lib/prefs.js";

function fakeStorage(initial = {}) {
  const data = { ...initial };
  return {
    data,
    async get(key) { return key in data ? { [key]: data[key] } : {}; },
    async set(obj) { Object.assign(data, obj); },
  };
}

test("sem nada salvo usa vídeo na melhor qualidade", async () => {
  assert.deepEqual(await loadPrefs(fakeStorage()), { mode: "video", quality: "best" });
});

test("carrega o que foi salvo", async () => {
  const storage = fakeStorage();
  await savePrefs(storage, { mode: "audio", quality: "192" });
  assert.deepEqual(await loadPrefs(storage), { mode: "audio", quality: "192" });
});

test("qualidade incompatível com o modo é corrigida", async () => {
  const storage = fakeStorage({ prefs: { mode: "audio", quality: "720" } });
  assert.deepEqual(await loadPrefs(storage), { mode: "audio", quality: "320" });
});
```

`extension/tests/api.test.js`:
```js
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { api, ApiError, BASE } from "../lib/api.js";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

function mockFetch(handler) {
  const calls = [];
  globalThis.fetch = async (url, init) => { calls.push({ url, init }); return handler(url, init); };
  return calls;
}

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

test("addToQueue envia JSON por POST", async () => {
  const calls = mockFetch(() => json(200, { added: ["a"], duplicates: 0 }));
  const result = await api.addToQueue(["https://youtu.be/x"], "audio", "192");
  assert.deepEqual(result, { added: ["a"], duplicates: 0 });
  assert.equal(calls[0].url, `${BASE}/queue`);
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body), { urls: ["https://youtu.be/x"], mode: "audio", quality: "192" });
});

test("info codifica a URL", async () => {
  const calls = mockFetch(() => json(200, { title: "t" }));
  await api.info("https://youtu.be/x?a=1&b=2");
  assert.equal(calls[0].url, `${BASE}/info?url=${encodeURIComponent("https://youtu.be/x?a=1&b=2")}`);
});

test("erro do servidor vira ApiError com a mensagem", async () => {
  mockFetch(() => json(400, { error: "link inválido" }));
  await assert.rejects(api.queue(), (err) => err instanceof ApiError && err.message === "link inválido" && err.status === 400);
});

test("servidor desligado vira ApiError offline", async () => {
  mockFetch(() => { throw new TypeError("Failed to fetch"); });
  await assert.rejects(api.status(), (err) => err instanceof ApiError && err.offline && err.message === "Programa não está rodando");
});
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `npm test`
Expected: FAIL com `Cannot find module ... extension/lib/links.js` (e os outros).

- [ ] **Step 4: Implementar**

`extension/lib/links.js`:
```js
const SITE_PATTERNS = [
  ["youtube", /(^|\.)(youtube\.com|youtu\.be)$/],
  ["tiktok", /(^|\.)tiktok\.com$/],
  ["instagram", /(^|\.)instagram\.com$/],
  ["pinterest", /(^|\.)(pinterest\.[a-z.]+|pin\.it)$/],
];

function parseUrl(url) {
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u : null;
  } catch {
    return null;
  }
}

export function detectSite(url) {
  const u = parseUrl(url);
  if (!u) return null;
  const host = u.hostname.toLowerCase();
  for (const [site, pattern] of SITE_PATTERNS) {
    if (pattern.test(host)) return site;
  }
  return null;
}

export function isLikelyVideoUrl(url) {
  const site = detectSite(url);
  if (!site) return false;
  const u = new URL(url);
  const host = u.hostname.toLowerCase();
  const path = u.pathname;
  switch (site) {
    case "youtube":
      if (host === "youtu.be") return path.length > 1;
      return (path === "/watch" && u.searchParams.has("v")) || /^\/(shorts|live)\/[^/]+/.test(path);
    case "tiktok":
      return /^(vm|vt)\./.test(host) || /\/video\/\d+/.test(path);
    case "instagram":
      return /^\/(reels?|p|tv)\/[^/]+/.test(path) || /^\/[^/]+\/(reel|p)\/[^/]+/.test(path);
    case "pinterest":
      return host === "pin.it" || /^\/pin\/[^/]+/.test(path);
  }
  return false;
}

const URL_IN_TEXT = /https?:\/\/[^\s<>"']+/gi;
const TRAILING_PUNCTUATION = /[.,;:!?)\]}»"'…]+$/;

export function parseLinks(text) {
  const urls = [];
  const seen = new Set();
  let ignored = 0;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    const found = line.match(URL_IN_TEXT);
    if (!found) {
      ignored++;
      continue;
    }
    for (const candidate of found) {
      const url = candidate.replace(TRAILING_PUNCTUATION, "");
      if (!parseUrl(url) || seen.has(url)) continue;
      seen.add(url);
      urls.push(url);
    }
  }
  return { urls, ignored };
}
```

`extension/lib/format.js`:
```js
const STATUS_LABELS = {
  waiting: "Aguardando",
  downloading: "Baixando",
  converting: "Convertendo",
  done: "Concluído",
  error: "Erro",
  cancelled: "Cancelado",
};

const QUALITY_OPTIONS = {
  video: [["best", "Melhor disponível"], ["1080", "1080p"], ["720", "720p"], ["480", "480p"], ["360", "360p"]],
  audio: [["320", "320 kbps"], ["192", "192 kbps"], ["128", "128 kbps"]],
};

export function formatSpeed(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec <= 0) return "";
  if (bytesPerSec >= 1024 * 1024) return `${(bytesPerSec / (1024 * 1024)).toFixed(1).replace(".", ",")} MB/s`;
  return `${Math.round(bytesPerSec / 1024)} KB/s`;
}

export function percent(progress) {
  const p = Math.min(Math.max(Number(progress) || 0, 0), 1);
  return `${Math.round(p * 100)}%`;
}

export function statusLabel(status) {
  return STATUS_LABELS[status] ?? status;
}

export function qualityOptions(mode) {
  return QUALITY_OPTIONS[mode === "audio" ? "audio" : "video"];
}

export function qualityLabel(mode, quality) {
  const found = qualityOptions(mode).find(([value]) => value === quality);
  return found ? found[1] : quality;
}
```

`extension/lib/prefs.js`:
```js
import { qualityOptions } from "./format.js";

export const DEFAULT_PREFS = { mode: "video", quality: "best" };

export function normalizePrefs(raw) {
  const mode = raw?.mode === "audio" ? "audio" : "video";
  const values = qualityOptions(mode).map(([value]) => value);
  const quality = values.includes(raw?.quality) ? raw.quality : values[0];
  return { mode, quality };
}

export async function loadPrefs(storage) {
  const { prefs } = await storage.get("prefs");
  return normalizePrefs(prefs);
}

export async function savePrefs(storage, prefs) {
  await storage.set({ prefs: normalizePrefs(prefs) });
}
```

`extension/lib/api.js`:
```js
export const BASE = "http://127.0.0.1:47321";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  get offline() {
    return this.status === 0;
  }
}

async function request(method, path, body) {
  let response;
  try {
    response = await fetch(BASE + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Programa não está rodando", 0);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(data.error || `Erro ${response.status}`, response.status);
  return data;
}

export const api = {
  status: () => request("GET", "/status"),
  info: (url) => request("GET", `/info?url=${encodeURIComponent(url)}`),
  addToQueue: (urls, mode, quality) => request("POST", "/queue", { urls, mode, quality }),
  queue: () => request("GET", "/queue"),
  cancel: (id) => request("POST", `/queue/${encodeURIComponent(id)}/cancel`),
  retry: (id) => request("POST", `/queue/${encodeURIComponent(id)}/retry`),
  openFolder: () => request("POST", "/open-folder"),
  updateYtdlp: () => request("POST", "/update-ytdlp"),
};
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npm test`
Expected: todos os testes `ok`, `# fail 0`.

- [ ] **Step 6: Commit**

```powershell
git add package.json extension/lib extension/tests
git commit -m "feat(extensão): links, formatação, preferências e cliente da API" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Extensão — popup e ícones

**Files:**
- Create: `extension/popup.html`, `extension/popup.css`, `extension/popup.js`, `scripts/make_icons.py`
- Generated: `extension/icons/icon16.png`, `icon32.png`, `icon48.png`, `icon128.png`
- Modify: `extension/manifest.json` (acrescentar ícones)

**Interfaces:**
- Consumes: `lib/api.js`, `lib/links.js`, `lib/format.js`, `lib/prefs.js` (Task 11); `videodl.icon.draw_icon` (Task 10); API do helper (Task 7).

- [ ] **Step 1: Gerar os ícones**

`scripts/make_icons.py`:
```python
"""Gera os ícones PNG da extensão a partir do mesmo desenho usado na bandeja."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "helper"))

from videodl.icon import draw_icon  # noqa: E402

OUT = ROOT / "extension" / "icons"

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 48, 128):
        draw_icon(size).save(OUT / f"icon{size}.png")
        print(f"icons/icon{size}.png")
```

Run: `helper\.venv\Scripts\python scripts\make_icons.py`
Expected: imprime os 4 caminhos; arquivos existem em `extension/icons/`.

- [ ] **Step 2: Acrescentar ícones ao manifest**

Em `extension/manifest.json`, dentro de `"action"` acrescentar `"default_icon"` e no nível raiz `"icons"` (mantendo `"key"` intacta):
```json
  "icons": { "16": "icons/icon16.png", "32": "icons/icon32.png", "48": "icons/icon48.png", "128": "icons/icon128.png" },
```
e em `"action"`:
```json
    "default_icon": { "16": "icons/icon16.png", "32": "icons/icon32.png" },
```

Run: `node -e "JSON.parse(require('fs').readFileSync('extension/manifest.json','utf8')); console.log('manifest ok')"`
Expected: `manifest ok`.

- [ ] **Step 3: Criar `extension/popup.html`**

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Vídeo Downloader</title>
  <link rel="stylesheet" href="popup.css">
</head>
<body>
  <header class="top">
    <h1>Vídeo Downloader</h1>
    <span id="conn" class="conn"><span class="dot"></span><span id="conn-text">Conectando…</span></span>
  </header>

  <div id="offline" class="banner banner-error" hidden>
    O programa não está rodando. Abra <b>Video Downloader</b> pelo menu Iniciar.
  </div>
  <div id="ffmpeg-warn" class="banner banner-warn" hidden>
    ffmpeg não encontrado — rode <code>scripts\install.ps1</code>.
  </div>

  <section class="options">
    <div class="segmented" role="radiogroup" aria-label="Formato">
      <button type="button" data-mode="video" role="radio">🎬 Vídeo</button>
      <button type="button" data-mode="audio" role="radio">🎵 Áudio</button>
    </div>
    <select id="quality" aria-label="Qualidade"></select>
  </section>

  <section id="page" class="card page" hidden>
    <img id="page-thumb" alt="" hidden>
    <div class="page-info">
      <div class="label">Esta página</div>
      <div id="page-title" class="page-title"></div>
      <div id="page-msg" class="msg"></div>
    </div>
    <button type="button" id="page-add" class="primary">Adicionar</button>
  </section>

  <section class="card">
    <label for="links" class="label">Colar links (um por linha)</label>
    <textarea id="links" rows="3" placeholder="https://..."></textarea>
    <div class="row">
      <span id="links-msg" class="msg"></span>
      <button type="button" id="links-add" class="primary">Adicionar à fila</button>
    </div>
  </section>

  <section>
    <div class="queue-head">
      <h2>Fila</h2>
      <button type="button" id="open-folder" class="link">Abrir pasta</button>
    </div>
    <div id="update-box" class="banner banner-warn" hidden>
      Algum site mudou. <button type="button" id="update-btn" class="link">Atualizar yt-dlp</button>
      <span id="update-msg"></span>
    </div>
    <ul id="queue" class="queue"></ul>
    <p id="queue-empty" class="empty">Nada na fila ainda.</p>
  </section>

  <script type="module" src="popup.js"></script>
</body>
</html>
```

- [ ] **Step 4: Criar `extension/popup.css`**

```css
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --fg: #1d1d1f;
  --muted: #6b6b70;
  --card: #f4f4f6;
  --border: #dcdce1;
  --accent: #e13040;
  --accent-fg: #ffffff;
  --ok: #1f9d55;
  --err: #c62828;
  --warn-bg: #fff4d6;
  --err-bg: #fde7e9;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1c1c1e;
    --fg: #f2f2f4;
    --muted: #a1a1a8;
    --card: #2a2a2d;
    --border: #3a3a3e;
    --warn-bg: #3d3420;
    --err-bg: #3d2226;
    --err: #ff8a80;
  }
}
* { box-sizing: border-box; }
body {
  width: 380px; margin: 0; padding: 12px;
  font: 13px/1.4 system-ui, "Segoe UI", sans-serif;
  background: var(--bg); color: var(--fg);
}
h1 { font-size: 15px; margin: 0; }
h2 { font-size: 13px; margin: 0; }
.top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.conn { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 12px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--err); }
.conn.on .dot { background: var(--ok); }
.banner { padding: 8px 10px; border-radius: 8px; margin-bottom: 10px; font-size: 12px; }
.banner-error { background: var(--err-bg); }
.banner-warn { background: var(--warn-bg); }
.options { display: flex; gap: 8px; margin-bottom: 10px; }
.segmented { display: flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.segmented button { border: 0; background: transparent; color: var(--fg); padding: 6px 10px; cursor: pointer; font: inherit; }
.segmented button.active { background: var(--accent); color: var(--accent-fg); }
select, textarea {
  font: inherit; color: var(--fg); background: var(--bg);
  border: 1px solid var(--border); border-radius: 8px; padding: 6px 8px;
}
select { flex: 1; }
textarea { width: 100%; resize: vertical; }
.card { background: var(--card); border-radius: 10px; padding: 10px; margin-bottom: 10px; }
.label { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; margin-bottom: 4px; }
.page { display: flex; gap: 10px; align-items: center; }
.page img { width: 64px; height: 40px; object-fit: cover; border-radius: 6px; flex: none; }
.page-info { flex: 1; min-width: 0; }
.page-title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 8px; }
.msg { color: var(--muted); font-size: 12px; }
button.primary {
  background: var(--accent); color: var(--accent-fg); border: 0; border-radius: 8px;
  padding: 7px 12px; font: inherit; font-weight: 600; cursor: pointer; flex: none;
}
button.primary:disabled { opacity: .5; cursor: default; }
button.link { background: none; border: 0; color: var(--accent); cursor: pointer; padding: 0; font: inherit; }
.queue-head { display: flex; justify-content: space-between; align-items: center; margin: 4px 0 8px; }
.queue { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.item { background: var(--card); border-radius: 10px; padding: 8px 10px; }
.item-title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-meta { color: var(--muted); font-size: 12px; }
.bar { height: 4px; background: var(--border); border-radius: 2px; margin-top: 6px; overflow: hidden; }
.fill { height: 100%; background: var(--accent); transition: width .3s; }
.item-error { color: var(--err); font-size: 12px; margin-top: 4px; }
.detail { white-space: pre-wrap; word-break: break-word; font-size: 11px; color: var(--muted); margin: 4px 0 0; }
.item-actions { display: flex; gap: 12px; margin-top: 6px; }
.empty { color: var(--muted); text-align: center; margin: 12px 0; }
```

- [ ] **Step 5: Criar `extension/popup.js`**

```js
import { api, ApiError } from "./lib/api.js";
import { isLikelyVideoUrl, parseLinks } from "./lib/links.js";
import { formatSpeed, percent, qualityLabel, qualityOptions, statusLabel } from "./lib/format.js";
import { loadPrefs, savePrefs } from "./lib/prefs.js";

const $ = (id) => document.getElementById(id);
const storage = chrome.storage.local;
const RUNNING = ["downloading", "converting"];
const ACTIVE = ["waiting", ...RUNNING];

let prefs = { mode: "video", quality: "best" };
let online = false;
let pageLoaded = false;
let lastItems = [];
let lastKey = "";
const expanded = new Set();

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function linkButton(label, onClick) {
  const button = el("button", "link", label);
  button.type = "button";
  button.addEventListener("click", onClick);
  return button;
}

// ---- opções ----

function renderOptions() {
  for (const button of document.querySelectorAll("[data-mode]")) {
    const on = button.dataset.mode === prefs.mode;
    button.classList.toggle("active", on);
    button.setAttribute("aria-checked", String(on));
  }
  const select = $("quality");
  select.replaceChildren(...qualityOptions(prefs.mode).map(([value, label]) => new Option(label, value)));
  select.value = prefs.quality;
}

async function setPrefs(next) {
  prefs = next;
  renderOptions();
  await savePrefs(storage, prefs);
}

for (const button of document.querySelectorAll("[data-mode]")) {
  button.addEventListener("click", () => {
    const mode = button.dataset.mode;
    if (mode !== prefs.mode) setPrefs({ mode, quality: qualityOptions(mode)[0][0] });
  });
}
$("quality").addEventListener("change", (event) => setPrefs({ ...prefs, quality: event.target.value }));

// ---- conexão ----

function setOnline(isOnline, status) {
  online = isOnline;
  $("conn").classList.toggle("on", isOnline);
  $("conn-text").textContent = isOnline ? "Conectado" : "Desconectado";
  $("offline").hidden = isOnline;
  $("ffmpeg-warn").hidden = !isOnline || status?.ffmpeg !== false;
  $("page-add").disabled = !isOnline;
  $("links-add").disabled = !isOnline;
}

async function checkStatus() {
  try {
    setOnline(true, await api.status());
  } catch {
    setOnline(false);
  }
}

// ---- adicionar ----

async function addUrls(urls) {
  try {
    const result = await api.addToQueue(urls, prefs.mode, prefs.quality);
    const parts = [];
    if (result.added.length) parts.push(`${result.added.length} adicionado(s)`);
    if (result.duplicates) parts.push(`${result.duplicates} já estava(m) na fila`);
    await refreshQueue();
    return { ok: true, text: parts.join(" · ") };
  } catch (error) {
    return { ok: false, text: error instanceof ApiError ? error.message : String(error) };
  }
}

$("links-add").addEventListener("click", async () => {
  const { urls, ignored } = parseLinks($("links").value);
  const notes = ignored ? [`${ignored} linha(s) ignorada(s)`] : [];
  if (!urls.length) {
    $("links-msg").textContent = [...notes, "nenhum link encontrado"].join(" · ");
    return;
  }
  const result = await addUrls(urls);
  if (result.ok) $("links").value = "";
  $("links-msg").textContent = [...notes, result.text].filter(Boolean).join(" · ");
});

async function loadPage() {
  if (pageLoaded || !online) return;
  pageLoaded = true;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab?.url;
  if (!url || !isLikelyVideoUrl(url)) return;

  $("page").hidden = false;
  $("page-title").textContent = tab.title || url;
  $("page-add").onclick = async () => {
    $("page-msg").textContent = (await addUrls([url])).text;
  };
  try {
    const info = await api.info(url);
    $("page-title").textContent = info.title;
    if (info.thumbnail) {
      const img = $("page-thumb");
      img.onerror = () => { img.hidden = true; };
      img.src = info.thumbnail;
      img.hidden = false;
    }
  } catch (error) {
    $("page-msg").textContent = error.message;
  }
}

// ---- fila ----

function renderItem(item) {
  const li = el("li", `item status-${item.status}`);
  const title = el("div", "item-title", item.title || item.url);
  title.title = item.url;

  const bits = [`${item.mode === "audio" ? "🎵" : "🎬"} ${qualityLabel(item.mode, item.quality)}`, statusLabel(item.status)];
  if (item.status === "downloading") {
    bits.push(percent(item.progress));
    const speed = formatSpeed(item.speed);
    if (speed) bits.push(speed);
  }
  li.append(title, el("div", "item-meta", bits.join(" · ")));

  if (RUNNING.includes(item.status)) {
    const bar = el("div", "bar");
    const fill = el("div", "fill");
    fill.style.width = item.status === "converting" ? "100%" : percent(item.progress);
    bar.append(fill);
    li.append(bar);
  }

  if (item.error_short && item.status !== "done" && item.status !== "cancelled") {
    li.append(el("div", "item-error", item.error_short));
    if (item.status === "error" && item.error_detail) {
      const open = expanded.has(item.id);
      li.append(linkButton(open ? "ocultar detalhes" : "detalhes", () => {
        if (open) expanded.delete(item.id);
        else expanded.add(item.id);
        lastKey = "";
        renderQueue(lastItems);
      }));
      if (open) li.append(el("pre", "detail", item.error_detail));
    }
  }

  const actions = el("div", "item-actions");
  if (ACTIVE.includes(item.status)) {
    actions.append(linkButton("Cancelar", () => api.cancel(item.id).then(refreshQueue, showOffline)));
  }
  if (item.status === "error" || item.status === "cancelled") {
    actions.append(linkButton("Tentar de novo", () => api.retry(item.id).then(refreshQueue, showOffline)));
  }
  if (actions.childElementCount) li.append(actions);
  return li;
}

function renderQueue(items) {
  const key = JSON.stringify(items) + [...expanded].join(",");
  if (key === lastKey) return;
  lastKey = key;
  lastItems = items;
  $("queue").replaceChildren(...[...items].reverse().map(renderItem));
  $("queue-empty").hidden = items.length > 0;
  $("update-box").hidden = !items.some((i) => i.status === "error" && i.error_code === "extractor");
}

function showOffline() {
  setOnline(false);
}

async function refreshQueue() {
  try {
    const { items } = await api.queue();
    if (!online) {
      await checkStatus();
      loadPage();
    }
    renderQueue(items);
  } catch {
    if (online) setOnline(false);
  }
}

// ---- botões gerais ----

$("open-folder").addEventListener("click", () => api.openFolder().catch(showOffline));

$("update-btn").addEventListener("click", async () => {
  const button = $("update-btn");
  button.disabled = true;
  $("update-msg").textContent = "Atualizando… (pode levar 1 minuto)";
  try {
    const result = await api.updateYtdlp();
    $("update-msg").textContent = result.restarting
      ? `Atualizado para ${result.version}. Reiniciando o programa…`
      : `Já está na versão mais recente (${result.version}).`;
  } catch (error) {
    $("update-msg").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

// ---- início ----

async function init() {
  prefs = await loadPrefs(storage);
  renderOptions();
  await checkStatus();
  await refreshQueue();
  loadPage();
  setInterval(refreshQueue, 1000);
}

init();
```

- [ ] **Step 6: Rodar os testes da extensão (nada deve quebrar)**

Run: `npm test`
Expected: `# fail 0`.

- [ ] **Step 7: Verificação manual no navegador**

1. Inicie o helper: `Start-Process helper\.venv\Scripts\pythonw.exe -ArgumentList "-m","videodl" -WorkingDirectory helper`
2. No Brave/Opera abra `brave://extensions` (ou `opera://extensions`), ative **Modo do desenvolvedor**, clique **Carregar sem compactação** e escolha a pasta `extension`.
3. Confira que o ID mostrado é igual ao de `helper\videodl\extension_id.txt`.
4. Abra um vídeo público do YouTube, clique no ícone da extensão.

Expected: bolinha verde "Conectado"; bloco "Esta página" com título (e miniatura); escolher 🎵 Áudio / 192 kbps e clicar **Adicionar** → item aparece na fila com progresso e termina como "Concluído"; arquivo `.mp3` em `Downloads\Video Downloader`. Feche o helper pela bandeja → popup mostra "Desconectado" e a faixa vermelha em até ~1 s.

Se o popup ficar "Desconectado" com o helper rodando: veja `%LOCALAPPDATA%\VideoDownloader\log.txt` (nível DEBUG não é gravado; procure 403 rodando temporariamente `curl.exe -v` como na Task 10) e confirme que o ID da extensão na página de extensões é igual ao de `extension_id.txt`. O helper exige o cabeçalho `Origin` da extensão em **todas** as requisições; se o navegador não o enviar em algum `GET`, essa é a causa.

- [ ] **Step 8: Commit**

```powershell
git add extension scripts/make_icons.py
git commit -m "feat(extensão): popup com página atual, links colados e fila" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Instalador, README e teste real

**Files:**
- Create: `scripts/install.ps1`, `README.md`, `docs/smoke-test.md`

**Interfaces:**
- Consumes: `helper/requirements.txt` (Task 1), `startup.install_shortcuts` (Task 8), `scripts/gen_extension_key.py` (Task 9).

- [ ] **Step 1: Criar `scripts/install.ps1`**

```powershell
# Instala o Vídeo Downloader: venv + dependências, ffmpeg, atalhos e inicia o programa.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$helper = Join-Path $root "helper"
$python = Join-Path $helper ".venv\Scripts\python.exe"
$pythonw = Join-Path $helper ".venv\Scripts\pythonw.exe"

Write-Host "1/5 Ambiente Python..." -ForegroundColor Cyan
if (-not (Test-Path $python)) {
    python -m venv (Join-Path $helper ".venv")
}
& $python -m pip install --upgrade pip --disable-pip-version-check
& $python -m pip install -r (Join-Path $helper "requirements.txt") --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependências Python." }

Write-Host "2/5 ffmpeg..." -ForegroundColor Cyan
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "   ffmpeg já instalado."
} else {
    winget install --id Gyan.FFmpeg -e
    Write-Host "   ffmpeg instalado. Ele passa a valer para programas abertos depois disto." -ForegroundColor Yellow
}

Write-Host "3/5 Node (necessário para o YouTube)..." -ForegroundColor Cyan
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "   Node não encontrado. Instale com: winget install OpenJS.NodeJS.LTS" -ForegroundColor Yellow
}

Write-Host "4/5 ID da extensão e atalhos..." -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $helper "videodl\extension_id.txt"))) {
    & $python (Join-Path $root "scripts\gen_extension_key.py")
}
Push-Location $helper
try {
    & $python -c "from videodl import startup; startup.install_shortcuts()"
} finally {
    Pop-Location
}

Write-Host "5/5 Iniciando o programa..." -ForegroundColor Cyan
Start-Process $pythonw -ArgumentList "-m", "videodl" -WorkingDirectory $helper

Write-Host ""
Write-Host "Pronto! Agora carregue a extensão:" -ForegroundColor Green
Write-Host "  1. Abra brave://extensions (ou opera://extensions)"
Write-Host "  2. Ative 'Modo do desenvolvedor'"
Write-Host "  3. Clique em 'Carregar sem compactação' e escolha: $(Join-Path $root 'extension')"
```

- [ ] **Step 2: Criar `README.md`**

````markdown
# Vídeo Downloader

Extensão para Brave/Opera/Chrome/Edge + programa local que baixa vídeos (MP4) e áudios (MP3)
do YouTube, TikTok, Instagram e Pinterest. Só conteúdo público; uso pessoal.

## Instalar

1. Abra o PowerShell nesta pasta e rode:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
   ```

2. No navegador abra `brave://extensions` (ou `opera://extensions`), ative **Modo do desenvolvedor**,
   clique **Carregar sem compactação** e escolha a pasta `extension`.

O programa fica no ícone vermelho perto do relógio e abre sozinho com o Windows.

## Usar

- **Na página do vídeo:** clique no ícone da extensão → **Adicionar**.
- **Colar links:** cole um ou vários (um por linha) → **Adicionar à fila**.
- Escolha 🎬 Vídeo ou 🎵 Áudio e a qualidade antes de adicionar.
- Os arquivos vão para `Downloads\Video Downloader`.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| Bolinha vermelha "Desconectado" | Abra **Video Downloader** pelo menu Iniciar. |
| "O site mudou — clique em Atualizar" | Clique em **Atualizar yt-dlp** no popup ou no menu da bandeja. |
| "ffmpeg não encontrado" | Rode o instalador de novo e reinicie o programa pela bandeja (Sair → abrir de novo). |
| Outro problema | Veja o log em `%LOCALAPPDATA%\VideoDownloader\log.txt`. |

## Desenvolvimento

```powershell
helper\.venv\Scripts\python -m pytest helper\tests
npm test
```
````

- [ ] **Step 3: Criar `docs/smoke-test.md`**

```markdown
# Teste real (manual)

Pré-requisitos: `scripts\install.ps1` rodado; extensão carregada; helper na bandeja.

Para cada linha: adicionar pelo popup, esperar "Concluído", conferir o arquivo com
`ffprobe -v error -show_entries stream=codec_name,height,bit_rate -of compact "<arquivo>"`
e abrir no player do Windows.

| Site | Modo / qualidade | Esperado no ffprobe | OK? |
|---|---|---|---|
| YouTube (vídeo público) | Vídeo / 720p | `h264`, `height=720` (ou menor), `aac` | |
| YouTube (mesmo vídeo) | Áudio / 192 | `mp3`, bit_rate ≈ 192000 | |
| YouTube `watch?v=X&list=Y` | Vídeo / Melhor | só **um** arquivo baixado | |
| TikTok (vídeo público) | Vídeo / Melhor | `h264` + `aac` | |
| Instagram Reels público | Vídeo / Melhor | `h264` + `aac` | |
| Pinterest (pin com vídeo) | Vídeo / Melhor | `h264` + `aac` | |
| Instagram Reels público | Áudio / 128 | `mp3`, bit_rate ≈ 128000 | |

Extensão:

- [ ] Bloco "Esta página" aparece em vídeo e some na página inicial do YouTube.
- [ ] Colar 3 links (com texto e um repetido) → 2 adicionados, aviso de linha ignorada.
- [ ] Até 2 baixando ao mesmo tempo; o 3º "Aguardando".
- [ ] Cancelar durante o download → "Cancelado" e nenhum `.part` sobra na pasta.
- [ ] Tentar de novo um cancelado → volta para a fila e conclui.
- [ ] Link inválido (`https://example.com`) → "Esse link não tem vídeo suportado" + "detalhes".
- [ ] Sair pela bandeja → popup mostra "Desconectado"; abrir pelo menu Iniciar → volta "Conectado".
- [ ] Reiniciar o PC → helper abre sozinho; itens que estavam "Aguardando" continuam.
```

- [ ] **Step 4: Rodar o instalador**

Run: `powershell -ExecutionPolicy Bypass -File scripts\install.ps1`
Expected: os 5 passos terminam sem erro; mensagem "Pronto!"; ícone na bandeja; atalhos em `shell:startup` e no menu Iniciar.

- [ ] **Step 5: Rodar a suíte completa**

Run:
```powershell
helper\.venv\Scripts\python -m pytest helper\tests
npm test
```
Expected: pytest `passed` sem falhas; node `# fail 0`.

- [ ] **Step 6: Executar `docs/smoke-test.md`**

Percorra a checklist com links públicos reais e marque cada linha. Qualquer falha: abra `%LOCALAPPDATA%\VideoDownloader\log.txt`, corrija na task responsável (com um teste que reproduza, quando for lógica do helper) e repita a linha.

- [ ] **Step 7: Commit**

```powershell
git add scripts/install.ps1 README.md docs/smoke-test.md
git commit -m "docs: instalador, README e checklist de teste real" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
