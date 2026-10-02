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
