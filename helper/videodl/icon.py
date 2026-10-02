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
