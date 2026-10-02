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
