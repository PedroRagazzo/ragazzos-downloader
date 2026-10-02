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
