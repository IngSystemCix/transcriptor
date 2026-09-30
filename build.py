"""Compila Transcriptor con PyInstaller (Windows, macOS y Linux).

Uso:
    uv run build.py                 # Windows/Linux: un solo ejecutable · macOS: Transcriptor.app
    uv run build.py --onedir        # carpeta en lugar de un solo archivo (Windows/Linux)
    uv run build.py --with-ffmpeg   # incrusta ffmpeg (para equipos donde PyAV está bloqueado)

Salida:
    Windows -> dist/Transcriptor.exe
    macOS   -> dist/Transcriptor.app   (siempre en carpeta: onefile + .app está obsoleto)
    Linux   -> dist/Transcriptor

Requiere:  uv add --dev pyinstaller
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

import PyInstaller.__main__
from main import APP_AUTHOR, APP_TITLE, APP_VERSION, DRAWERS, C, _Canvas  # fuente única de datos

ROOT = Path(__file__).parent
NAME = "Transcriptor"
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
ICON = ROOT / ("app.ico" if IS_WIN else "app.icns")
VERSION_FILE = ROOT / "version_info.txt"
FFMPEG = "ffmpeg.exe" if IS_WIN else "ffmpeg"

# Paquetes con DLLs, modelos o datos que PyInstaller no detecta solo.
COLLECT_ALL = ["faster_whisper", "ctranslate2", "onnxruntime", "tokenizers", "av"]


def make_icon(path: Path, size: int = 512) -> None:
    """.ico en Windows, .icns en macOS (Linux no usa icono de ejecutable)."""
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
    if path.suffix == ".ico":
        base.save(path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    else:
        base.save(path, format="ICNS")


def make_version_file(path: Path) -> None:
    """Metadatos que Windows muestra en Propiedades > Detalles del .exe (solo Windows)."""
    from PyInstaller.utils.win32.versioninfo import (  # import perezoso: no existe fuera de Windows
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
    )

    v = tuple(([int(x) for x in APP_VERSION.split(".")] + [0, 0, 0, 0])[:4])
    info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=v, prodvers=v, mask=0x3F, flags=0x0, OS=0x40004,
                          fileType=0x1, subtype=0x0, date=(0, 0)),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", APP_AUTHOR),
                StringStruct("FileDescription", APP_TITLE),
                StringStruct("FileVersion", APP_VERSION),
                StringStruct("InternalName", NAME),
                StringStruct("LegalCopyright", f"Copyright (c) {datetime.now().year} {APP_AUTHOR}"),
                StringStruct("OriginalFilename", f"{NAME}.exe"),
                StringStruct("ProductName", APP_TITLE),
                StringStruct("ProductVersion", APP_VERSION),
            ])]),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )
    path.write_text(str(info), encoding="utf-8")


def find_ffmpeg() -> str:
    local = ROOT / FFMPEG
    found = str(local) if local.is_file() else shutil.which("ffmpeg")
    if not found:
        sys.exit(f"No se encontró {FFMPEG}. Instálalo o colócalo junto a build.py.")
    return found


def main() -> None:
    onedir = "--onedir" in sys.argv or IS_MAC  # macOS: .app => carpeta
    args = [
        str(ROOT / "main.py"),
        "--name", NAME,
        "--noconfirm", "--clean",
        "--windowed",  # sin consola (en Linux se ignora)
        "--onedir" if onedir else "--onefile",
    ]
    if IS_WIN or IS_MAC:
        make_icon(ICON)
        args += ["--icon", str(ICON)]
    if IS_WIN:
        make_version_file(VERSION_FILE)
        args += ["--version-file", str(VERSION_FILE)]
    if IS_MAC:
        args += ["--osx-bundle-identifier", f"com.{APP_AUTHOR.lower()}.{NAME.lower()}"]
    for pkg in COLLECT_ALL:
        args += ["--collect-all", pkg]
    if "--with-ffmpeg" in sys.argv:
        args += ["--add-binary", f"{find_ffmpeg()}{os.pathsep}."]

    print(f"Compilando {APP_TITLE} para {sys.platform}…")
    PyInstaller.__main__.run(args)
    target = f"dist/{NAME}.app" if IS_MAC else (f"dist/{NAME}" if onedir or not IS_WIN else f"dist/{NAME}.exe")
    if IS_WIN and onedir:
        target = f"dist/{NAME}"
    print(f"\nListo: {target}")


if __name__ == "__main__":
    main()