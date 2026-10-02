# Ragazzo's Downloader

Extensão para Brave/Opera/Chrome/Edge + programa local que baixa vídeos (MP4) e áudios (MP3)
do YouTube, TikTok, Instagram e Pinterest. Só conteúdo público; uso pessoal.

A extensão é só a interface. Quem baixa é um programa em Python que roda no seu PC
(em `127.0.0.1`, aceitando apenas a própria extensão) usando o [yt-dlp](https://github.com/yt-dlp/yt-dlp)
e o [ffmpeg](https://ffmpeg.org/).

> **Uso responsável:** baixe apenas conteúdo que você tem direito de baixar e respeite os termos de uso
> de cada site e os direitos autorais de quem criou o conteúdo.

## Requisitos

- Windows 10/11
- Python 3.12+ e Node.js (o yt-dlp usa o Node para o YouTube)
- Git for Windows (traz o `openssl`, usado para gerar a chave da extensão)
- Brave, Opera, Chrome ou Edge

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
| Bolinha vermelha "Desconectado" | Abra **Ragazzo's Downloader** pelo menu Iniciar. |
| "O site mudou — clique em Atualizar" | Clique em **Atualizar yt-dlp** no popup ou no menu da bandeja. |
| "ffmpeg não encontrado" | Rode o instalador de novo e reinicie o programa pela bandeja (Sair → abrir de novo). |
| Outro problema | Veja o log em `%LOCALAPPDATA%\VideoDownloader\log.txt`. |

## Desenvolvimento

```powershell
helper\.venv\Scripts\python -m pytest helper\tests
npm test
```

Projeto e decisões de design: `docs/superpowers/specs/` e `docs/superpowers/plans/`.

## Licença

[MIT](LICENSE)
