# Vídeo Downloader — Especificação de Design

**Data:** 2026-10-02
**Status:** aguardando revisão

## 1. Objetivo

Uma extensão para navegadores Chromium (Brave/Opera, também Chrome/Edge) que permite baixar vídeo (MP4) ou áudio (MP3) de TikTok, YouTube, Instagram e Pinterest — a partir da página aberta, colando links, ou enfileirando vários de uma vez.

**Sucesso =** colar um link do YouTube, abrir um Reels ou colar 5 links de uma vez, e os arquivos aparecerem na pasta com nome legível, com progresso visível na fila.

### Escopo

**Dentro:**
- Extensão Manifest V3 instalada em modo desenvolvedor (uso pessoal).
- Programa local em Python rodando em segundo plano no Windows.
- Vídeo MP4 com escolha de qualidade; áudio MP3 com escolha de bitrate.
- Fila com até 2 downloads simultâneos, persistente entre reinícios.
- Conteúdo **público** apenas.

**Fora (v1):**
- Publicação em loja de extensões.
- Conteúdo privado / que exige login (cookies).
- Menu de botão direito, legendas, cortes de trecho, escolha de pasta, outros formatos (WebM, M4A, WAV).
- Firefox, macOS, Linux.

### Premissas
- Uso exclusivo no PC do usuário (Windows 11), interface em português.
- Python 3.14 e Node já instalados.

## 2. Arquitetura

```
[Extensão (popup)] --HTTP JSON--> [Helper Python em 127.0.0.1:47321] --> yt-dlp + ffmpeg --> %USERPROFILE%\Downloads\Video Downloader\
        ^                                        |
        +------------ polling da fila -----------+
```

- A extensão é **somente interface**: não guarda estado da fila nem baixa nada.
- O helper é a **única fonte de verdade** da fila. Fechar o popup ou o navegador não interrompe downloads.

### Estrutura de pastas

```
Vídeo Downloader/
├── extension/        manifest.json, popup.html/.css/.js, ícones
├── helper/           pacote Python + tests/
├── scripts/          install.ps1, criação do atalho de inicialização
└── docs/             especificação e plano
```

## 3. Extensão

**Manifest V3**, permissões: `activeTab`, `storage`, `host_permissions` para `http://127.0.0.1:47321/*`.
O campo `key` no manifest fixa o ID da extensão, para o helper poder validar a origem.

### Popup (de cima para baixo)

1. **Indicador de conexão** — bolinha verde/vermelha. Vermelho: "Programa não está rodando" + instrução de como iniciar. Aviso extra se o helper reportar ffmpeg ausente.
2. **"Esta página"** — se a URL da aba ativa for de site suportado (YouTube, TikTok, Instagram, Pinterest), mostra miniatura + título (via `/info`) e botão **Adicionar à fila**. Oculto em outros sites.
3. **Colar links** — textarea, um link por linha. Linhas que não são URL http(s) são ignoradas com aviso "N linhas ignoradas". Botão **Adicionar à fila**.
4. **Opções** — alternância 🎬 Vídeo / 🎵 Áudio + seletor de qualidade:
   - Vídeo: Melhor, 1080p, 720p, 480p, 360p
   - Áudio: 320, 192, 128 kbps
   - Última escolha salva em `chrome.storage.local`.
5. **Fila** — por item: título (ou URL até o título chegar), barra de progresso, velocidade, status (aguardando / baixando / convertendo / concluído / erro / cancelado). Ações: **Cancelar** (aguardando/baixando), **Tentar de novo** (erro/cancelado), **Abrir pasta** (global). Erro mostra mensagem curta; "detalhes" expande o texto técnico.

O popup consulta `GET /queue` a cada 1 s enquanto está aberto.

## 4. Helper (programa local)

### Dependências
- `yt-dlp` (pip) — usado como biblioteca, com `progress_hooks`.
- `ffmpeg` (winget `Gyan.FFmpeg`) — merge de vídeo+áudio e conversão para MP3.
- Node (já instalado) — runtime JS exigido pelo yt-dlp para o YouTube (`js_runtimes`).
- `pystray` + `Pillow` — ícone na bandeja.
- Servidor HTTP: `http.server.ThreadingHTTPServer` da biblioteca padrão (sem framework).

`scripts/install.ps1` instala as dependências e cria o atalho de inicialização.

### Servidor
- Escuta **somente** em `127.0.0.1:47321`.
- **Validação de origem:** toda requisição precisa do cabeçalho `X-Video-Downloader: 1` e, se vier `Origin`, ele tem de ser `chrome-extension://<ID fixo>`; caso contrário → `403`. O preflight (OPTIONS) exige essa origem e CORS responde apenas para ela. Uma página web não consegue mandar o cabeçalho próprio sem preflight, então fica bloqueada. (O `Origin` pode faltar porque o Brave não o envia nos GET de extensão com `host_permissions`.)

### API

| Método | Caminho | Corpo / parâmetros | Resposta |
|---|---|---|---|
| GET | `/status` | — | `{ok, version, ytdlp_version, ffmpeg: bool}` |
| GET | `/info` | `?url=` | `{title, thumbnail, site}` ou erro |
| POST | `/queue` | `{urls: [..], mode: "video"\|"audio", quality: "best"\|"1080"\|"720"\|"480"\|"360"\|"320"\|"192"\|"128"}` | `{added: [ids], duplicates: n}` |
| GET | `/queue` | — | `{items: [...]}` |
| POST | `/queue/{id}/cancel` | — | item atualizado |
| POST | `/queue/{id}/retry` | — | item atualizado |
| POST | `/open-folder` | — | `{ok}` |
| POST | `/update-ytdlp` | — | `{ok, version}` |

Item da fila: `{id, url, mode, quality, status, title, progress (0–1), speed, filename, error_code, error_short, error_detail, created_at, finished_at}`. `error_code` (`unsupported`, `private`, `unavailable`, `network`, `extractor`, `disk`, `ffmpeg`, `unknown`) permite ao popup mostrar o botão **Atualizar yt-dlp** quando for `extractor`.

### Fila
- Até **2 downloads simultâneos**; demais aguardam (FIFO).
- **Duplicata** = mesmo `url` + `mode` + `quality` já em `waiting`/`downloading`/`converting` → ignorada e contada em `duplicates`.
- **Persistência** em `%LOCALAPPDATA%\VideoDownloader\queue.json`. Ao iniciar, itens `downloading`/`converting` voltam para `waiting`.
- **Histórico:** mantém os últimos 50 itens finalizados.
- **Cancelar:** interrompe o download em curso (via exceção no progress hook) e remove arquivos parciais.

### Formatos

**Vídeo** (limite `H` = qualidade escolhida; "best" = sem limite):
- `format`: `bv*[height<=H]+ba/b[height<=H]/bv*+ba/b`
- `format_sort`: `res:H`, `vcodec:h264`, `acodec:aac` — prioriza H.264/AAC para tocar em qualquer lugar.
- `merge_output_format`: `mp4`.
- Se a altura pedida não existir, usa a maior disponível abaixo dela (filtro `<=`); se nada abaixo existir, cai no último fallback (`bv*+ba/b`) e `format_sort res:H` escolhe a mais próxima.

**Áudio:**
- `format`: `ba/b`
- Pós-processador `FFmpegExtractAudio`, `preferredcodec: mp3`, `preferredquality: 320|192|128`.

### Nomes e pasta
- Pasta: `%USERPROFILE%\Downloads\Video Downloader\` (criada se não existir).
- Modelo: `Título [site].ext`, onde `site` é o extrator do yt-dlp em minúsculas.
- Título sanitizado para Windows (remove `<>:"/\|?*` e caracteres de controle, nomes reservados como `CON`), limitado a 150 caracteres.
- Conflito: `Título [site] (2).ext`, `(3)`, …

### Bandeja e inicialização
- Executado com `pythonw` (sem console).
- Menu: **Abrir pasta**, **Atualizar yt-dlp**, **Iniciar com o Windows** (alterna atalho em `shell:startup`), **Sair**.
- **Atualização automática:** ao iniciar, se a última atualização foi há mais de 24 h, roda `pip install -U yt-dlp` em segundo plano. Se a versão mudou, o helper **se reinicia sozinho assim que a fila estiver sem downloads ativos** (sem recarregar o módulo em memória). O mesmo vale para `POST /update-ytdlp` e o item do menu.

### Log
`%LOCALAPPDATA%\VideoDownloader\log.txt`, rotativo (1 MB × 3 arquivos).

## 5. Tratamento de erros

Erros do yt-dlp são traduzidos para mensagens curtas em português; o texto original vai em `error_detail`.

| Situação | `error_short` | Comportamento |
|---|---|---|
| Helper desligado | (popup) "Programa não está rodando" | Popup tenta reconectar a cada poucos segundos |
| URL não suportada / sem vídeo | "Esse link não tem vídeo suportado" | Erro, sem nova tentativa automática |
| Conteúdo privado / exige login | "Conteúdo privado — por enquanto só baixo vídeos públicos" | Erro |
| Removido / indisponível / bloqueado por região | "Vídeo indisponível" | Erro |
| Falha de rede | "Falha de conexão, tentando de novo…" | 2 novas tentativas com espera (5 s, 15 s), depois erro |
| Extrator quebrado (site mudou) | "O site mudou — clique em Atualizar" | Erro; popup oferece botão **Atualizar yt-dlp** |
| ffmpeg ausente | Aviso no topo do popup | `/status.ffmpeg = false` |
| Disco cheio / sem permissão | "Não consegui salvar o arquivo" | Erro |

## 6. Testes

1. **Unitários (pytest, sem rede)** — download do yt-dlp substituído por um falso:
   - mapeamento modo/qualidade → opções do yt-dlp;
   - sanitização de nomes e numeração de conflitos;
   - máquina de estados da fila: limite de 2 simultâneos, cancelar, tentar de novo, duplicatas, persistência e retomada, corte do histórico em 50;
   - validação de `Origin`;
   - tradução de erros;
   - parsing do texto colado (URLs válidas, linhas ignoradas).
2. **Integração da API** — servidor real em porta de teste, downloader falso, cobrindo todos os endpoints e o `403` sem origem válida.
3. **Smoke test real (checklist manual)** — 1 link público por site (YouTube, TikTok, Instagram Reels, Pinterest) × vídeo e áudio; conferir com `ffprobe`: MP4 em H.264/AAC, áudio em MP3 no bitrate escolhido; arquivo abre no player do Windows.
4. **Extensão (checklist manual)** — carregar sem empacotar no Brave/Opera; verificar bloco "Esta página", colar vários links, progresso, cancelar, tentar de novo, indicador de conexão com o helper ligado e desligado.
