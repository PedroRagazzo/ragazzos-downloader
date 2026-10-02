"""Cálculo do ID de extensão Chromium a partir da chave pública."""

from __future__ import annotations

import base64
import hashlib


def extension_id_from_der(der: bytes) -> str:
    digest = hashlib.sha256(der).hexdigest()[:32]
    return "".join(chr(ord("a") + int(ch, 16)) for ch in digest)


def manifest_key_from_der(der: bytes) -> str:
    return base64.b64encode(der).decode("ascii")
