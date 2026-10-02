r"""Gera a chave fixa da extensão: grava "key" no manifest e o ID em helper/videodl/extension_id.txt.

Rode uma única vez: trocar a chave muda o ID da extensão.
Uso: helper\.venv\Scripts\python scripts\gen_extension_key.py [--force]
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
