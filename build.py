"""Compila Transcriptor a un .exe con PyInstaller.

Uso:
    uv run build.py                 # un solo .exe  -> dist/Transcriptor.exe
    uv run build.py --onedir        # carpeta       -> dist/Transcriptor/ (arranca más rápido)
    uv run build.py --with-ffmpeg   # incrusta ffmpeg.exe (para equipos donde PyAV está bloqueado)

Requiere:  uv add --dev pyinstaller
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import PyInstaller.__main__
from main import APP_TITLE, DRAWERS, C, _Canvas  # reutiliza el mismo icono de la app

ROOT = Path(__file__).parent
ICON = ROOT / "app.ico"
NAME = "Transcriptor"

# Paquetes con DLLs, modelos o datos que PyInstaller no detecta solo.
COLLECT_ALL = ["faster_whisper", "ctranslate2", "onnxruntime", "tokenizers", "av"]


def make_icon(path: Path, size: int = 256) -> None:
    canvas = _Canvas()
    DRAWERS["wave"](canvas)
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(base).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 4, fill=C.ACCENT)
    inner = int(size * 0.62)
    mask = canvas.img.resize((inner, inner), Image.Resampling.LANCZOS)
    white = Image.new("RGBA", (inner, inner), "#FFFFFF")
    white.putalpha(mask)
    off = (size - inner) // 2
    base.alpha_composite(white, (off, off))
    base.save(path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def find_ffmpeg() -> str:
    local = ROOT / "ffmpeg.exe"
    found = str(local) if local.is_file() else shutil.which("ffmpeg")
    if not found:
        sys.exit("No se encontró ffmpeg.exe. Instálalo (winget install Gyan.FFmpeg) o colócalo junto a build.py.")
    return found


def main() -> None:
    onedir = "--onedir" in sys.argv
    with_ffmpeg = "--with-ffmpeg" in sys.argv

    make_icon(ICON)
    args = [
        str(ROOT / "main.py"),
        "--name", NAME,
        "--noconfirm", "--clean",
        "--windowed",  # sin consola negra
        "--icon", str(ICON),
        "--onedir" if onedir else "--onefile",
    ]
    for pkg in COLLECT_ALL:
        args += ["--collect-all", pkg]
    if with_ffmpeg:
        args += ["--add-binary", f"{find_ffmpeg()}{os.pathsep}."]

    print(f"Compilando {APP_TITLE} ({'carpeta' if onedir else 'un solo .exe'})…")
    PyInstaller.__main__.run(args)
    target = f"dist/{NAME}" if onedir else f"dist/{NAME}.exe"
    print(f"\nListo: {target}")


if __name__ == "__main__":
    main()