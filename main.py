"""Transcriptor de audio · Tkinter + faster-whisper.

Ejecutar:  uv run main.py

Arquitectura (por capas, de abajo hacia arriba):
  1. Utilidades de formato   -> funciones puras (tiempos, TXT, SRT).
  2. Iconos                  -> PNG generados con Pillow (sin SVG ni archivos externos).
  3. Worker                  -> hilo que transcribe y comunica por queue.Queue.
  4. Widgets propios         -> IconButton (botón accesible con anillo de foco).
  5. App                     -> ventana principal; solo orquesta UI y eventos.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import types
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

APP_TITLE = "Transcriptor de audio"
APP_VERSION = "0.1.0"  # build.py la usa para los metadatos del .exe
APP_AUTHOR = "IngSystemCix"
FONT = ("Segoe UI", 11)
FONT_BOLD = ("Segoe UI", 11, "bold")
FONT_SMALL = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_TEXT = ("Segoe UI", 12)


class C:
    """Paleta. Todos los pares texto/fondo cumplen contraste WCAG AA (>= 4.5:1)."""

    BG = "#0B1220"
    SURFACE = "#152033"
    SURFACE_2 = "#1E2B42"
    SURFACE_HOVER = "#2A3A57"
    BORDER = "#334155"
    TEXT = "#F1F5F9"
    MUTED = "#A8B3C5"
    ACCENT = "#2563EB"  # con texto blanco: 5.2:1
    ACCENT_HOVER = "#1D4ED8"
    ACCENT_LIGHT = "#93C5FD"
    FOCUS = "#FBBF24"  # anillo de foco de alto contraste
    SUCCESS = "#4ADE80"
    ERROR = "#F87171"
    DISABLED_FG = "#7C8AA0"


# ───────────────────────── 1. Utilidades de formato ─────────────────────────


@dataclass
class Segment:
    start: float
    end: float
    text: str


def fmt_clock(t: float) -> str:
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_srt(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_txt(segments: list[Segment], timestamps: bool) -> str:
    if timestamps:
        return "\n".join(f"[{fmt_clock(s.start)}] {s.text}" for s in segments)
    return "\n".join(s.text for s in segments)


def to_srt(segments: list[Segment]) -> str:
    blocks = [
        f"{i}\n{fmt_srt(s.start)} --> {fmt_srt(s.end)}\n{s.text}\n"
        for i, s in enumerate(segments, 1)
    ]
    return "\n".join(blocks)


# ─────────────────────────── 2. Iconos (PNG con Pillow) ─────────────────────
# Se dibujan como máscaras en un lienzo 100x100 con supersampling (x8) y se
# reducen con LANCZOS: bordes suaves a cualquier tamaño y recoloreables.


class _Canvas:
    S = 8

    def __init__(self) -> None:
        self.img = Image.new("L", (100 * self.S, 100 * self.S), 0)
        self.d = ImageDraw.Draw(self.img)

    def _v(self, on: bool) -> int:
        return 255 if on else 0  # on=False "recorta" (agujero en el icono)

    def _b(self, box):
        return [v * self.S for v in box]

    def rrect(self, box, r, on=True, stroke=0):
        kw = {"outline": self._v(on), "width": stroke * self.S} if stroke else {"fill": self._v(on)}
        self.d.rounded_rectangle(self._b(box), radius=r * self.S, **kw)

    def ellipse(self, box, on=True, stroke=0):
        kw = {"outline": self._v(on), "width": stroke * self.S} if stroke else {"fill": self._v(on)}
        self.d.ellipse(self._b(box), **kw)

    def poly(self, pts, on=True):
        self.d.polygon([(x * self.S, y * self.S) for x, y in pts], fill=self._v(on))

    def line(self, pts, w):
        s = self.S
        self.d.line([(x * s, y * s) for x, y in pts], fill=255, width=w * s, joint="curve")
        r = w / 2
        for x, y in (pts[0], pts[-1]):  # extremos redondeados
            self.d.ellipse(((x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s), fill=255)

    def arc(self, box, a0, a1, w):
        self.d.arc(self._b(box), a0, a1, fill=255, width=w * self.S)


def _folder(c: _Canvas):
    c.rrect((6, 16, 44, 44), 6)
    c.rrect((6, 30, 94, 84), 9)


def _play(c: _Canvas):
    c.poly([(30, 14), (30, 86), (86, 50)])


def _stop(c: _Canvas):
    c.rrect((22, 22, 78, 78), 10)


def _copy(c: _Canvas):
    c.rrect((12, 10, 64, 64), 10, stroke=8)
    c.rrect((26, 26, 96, 98), 12, on=False)
    c.rrect((36, 36, 88, 90), 10, stroke=8)


def _doc(c: _Canvas):
    c.rrect((20, 8, 80, 92), 9, stroke=8)
    c.rrect((34, 32, 66, 40), 3)
    c.rrect((34, 48, 66, 56), 3)
    c.rrect((34, 64, 52, 72), 3)


def _subtitle(c: _Canvas):
    c.rrect((8, 18, 92, 82), 12, stroke=8)
    c.rrect((22, 40, 46, 48), 3)
    c.rrect((54, 40, 78, 48), 3)
    c.rrect((22, 55, 40, 63), 3)
    c.rrect((48, 55, 78, 63), 3)


def _check(c: _Canvas):
    c.line([(20, 52), (42, 74), (82, 28)], 12)


def _alert(c: _Canvas):
    c.poly([(50, 8), (96, 88), (4, 88)])
    c.rrect((45, 36, 55, 62), 4, on=False)
    c.ellipse((44, 68, 56, 80), on=False)


def _info(c: _Canvas):
    c.ellipse((6, 6, 94, 94))
    c.ellipse((44, 20, 56, 32), on=False)
    c.rrect((44, 42, 56, 78), 4, on=False)


def _loader(c: _Canvas):
    c.arc((14, 14, 86, 86), 40, 340, 12)


def _wave(c: _Canvas):
    for x, h in [(10, 22), (26, 52), (42, 84), (58, 44), (74, 66), (90, 26)]:
        c.rrect((x - 5, 50 - h / 2, x + 5, 50 + h / 2), 5)


def _audio_file(c: _Canvas):
    c.rrect((20, 8, 80, 92), 9, stroke=8)
    for x, h in [(36, 12), (46, 28), (56, 18)]:
        c.rrect((x - 3, 50 - h / 2, x + 3, 50 + h / 2), 3)


DRAWERS = {
    "folder": _folder, "play": _play, "stop": _stop, "copy": _copy, "doc": _doc,
    "subtitle": _subtitle, "check": _check, "alert": _alert, "info": _info,
    "loader": _loader, "wave": _wave, "audio_file": _audio_file,
}


class IconFactory:
    """Genera PhotoImage recoloreables y las cachea (evita que Tk las recoja el GC)."""

    def __init__(self, scale: float = 1.0) -> None:
        self.scale = scale
        self._masks: dict[str, Image.Image] = {}
        self._cache: dict[tuple, ImageTk.PhotoImage] = {}

    def _mask(self, name: str) -> Image.Image:
        if name not in self._masks:
            canvas = _Canvas()
            DRAWERS[name](canvas)
            self._masks[name] = canvas.img
        return self._masks[name]

    def get(self, name: str, color: str, size: int = 20) -> ImageTk.PhotoImage:
        key = (name, color, size)
        if key not in self._cache:
            px = max(8, round(size * self.scale))
            mask = self._mask(name).resize((px, px), Image.Resampling.LANCZOS)
            im = Image.new("RGBA", (px, px), color)
            im.putalpha(mask)
            self._cache[key] = ImageTk.PhotoImage(im)
        return self._cache[key]

    def logo(self, size: int) -> ImageTk.PhotoImage:
        px = round(size * self.scale)
        base = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        ImageDraw.Draw(base).rounded_rectangle((0, 0, px - 1, px - 1), radius=px // 4, fill=C.ACCENT)
        inner = round(px * 0.62)
        mask = self._mask("wave").resize((inner, inner), Image.Resampling.LANCZOS)
        white = Image.new("RGBA", (inner, inner), "#FFFFFF")
        white.putalpha(mask)
        off = (px - inner) // 2
        base.alpha_composite(white, (off, off))
        photo = ImageTk.PhotoImage(base)
        self._cache[("logo", size)] = photo
        return photo


# ───────────────────────────── 3. Worker (hilo) ─────────────────────────────

# --- Respaldo de decodificación -------------------------------------------
# faster-whisper decodifica con PyAV (`av`). Si Windows bloquea su DLL (Smart App
# Control / WDAC), instalamos un módulo `av` falso solo para que faster-whisper
# pueda importarse, y decodificamos el audio con el ffmpeg del sistema.


class _StubModule(types.ModuleType):
    __path__: list = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _StubModule(f"{self.__name__}.{name}")


class _AvStubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path=None, target=None):
        if name == "av" or name.startswith("av."):
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None

    def create_module(self, spec):
        return _StubModule(spec.name)

    def exec_module(self, module):
        pass


_AV_OK: bool | None = None


def av_available() -> bool:
    """True si PyAV carga; si no, activa el módulo falso y devuelve False."""
    global _AV_OK
    if _AV_OK is None:
        try:
            import av  # noqa: F401

            _AV_OK = True
        except ImportError:
            for name in [n for n in sys.modules if n == "av" or n.startswith("av.")]:
                del sys.modules[name]
            sys.meta_path.insert(0, _AvStubFinder())
            _AV_OK = False
    return _AV_OK


def _find_ffmpeg() -> str | None:
    """Busca ffmpeg: empaquetado en el .exe, junto al .exe, o en el PATH."""
    candidates = []
    if getattr(sys, "frozen", False):
        exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        candidates.append(Path(getattr(sys, "_MEIPASS", "")) / exe_name)
        candidates.append(Path(sys.executable).parent / exe_name)
    for c in candidates:
        if c.is_file():
            return str(c)
    return shutil.which("ffmpeg")


def decode_with_ffmpeg(path: str):
    """Audio -> float32 mono 16 kHz (lo que espera Whisper) usando ffmpeg.exe."""
    import numpy as np

    exe = _find_ffmpeg()
    if not exe:
        raise RuntimeError(
            "No se encontró ffmpeg en el PATH.\n"
            "Instálalo con: winget install Gyan.FFmpeg y reabre la terminal."
        )
    cmd = [exe, "-nostdin", "-i", path, "-f", "s16le", "-ac", "1",
           "-acodec", "pcm_s16le", "-ar", "16000", "-"]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.run(cmd, capture_output=True, creationflags=flags)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg falló:\n" + proc.stderr.decode(errors="replace")[-400:])
    return np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0


_MODEL_CACHE: dict[tuple[str, str], object] = {}


def get_model(name: str, device: str):
    """Carga perezosa + caché: importar faster_whisper es lento y el modelo pesa."""
    key = (name, device)
    if key not in _MODEL_CACHE:
        from faster_whisper import WhisperModel

        _MODEL_CACHE[key] = WhisperModel(name, device=device, compute_type="auto")
    return _MODEL_CACHE[key]


@dataclass
class Options:
    path: str
    model: str
    language: str | None
    device: str
    vad: bool


class Worker(threading.Thread):
    """Nunca toca widgets: solo publica eventos en la cola (Tk no es thread-safe)."""

    def __init__(self, opts: Options, events: queue.Queue, cancel: threading.Event) -> None:
        super().__init__(daemon=True)
        self.opts, self.events, self.cancel = opts, events, cancel

    def run(self) -> None:
        o, put = self.opts, self.events.put
        t0 = time.perf_counter()
        try:
            put(("loading", o.model))
            use_ffmpeg = not av_available()
            model = get_model(o.model, o.device)
            if self.cancel.is_set():
                put(("cancelled",))
                return
            audio = o.path
            if use_ffmpeg:
                put(("decoding",))
                audio = decode_with_ffmpeg(o.path)
                if self.cancel.is_set():
                    put(("cancelled",))
                    return
            segments, info = model.transcribe(
                audio, language=o.language, vad_filter=o.vad, beam_size=5
            )
            put(("info", info.language, info.language_probability, info.duration))
            for seg in segments:
                if self.cancel.is_set():
                    put(("cancelled",))
                    return
                put(("segment", Segment(seg.start, seg.end, seg.text.strip())))
            put(("done", time.perf_counter() - t0))
        except Exception as exc:  # noqa: BLE001 - se muestra al usuario
            put(("error", f"{type(exc).__name__}: {exc}"))


# ─────────────────────────────── 4. Widgets propios ─────────────────────────


class IconButton(tk.Button):
    """Botón con icono + texto, >= 44 px de alto y anillo de foco visible."""

    VARIANTS = {
        "primary": (C.ACCENT, "#FFFFFF", C.ACCENT_HOVER),
        "secondary": (C.SURFACE_2, C.TEXT, C.SURFACE_HOVER),
    }

    def __init__(self, master, text, icon, command, icons: IconFactory, variant="secondary"):
        self._bg, fg, self._hover = self.VARIANTS[variant]
        self._disabled_bg = C.SURFACE_2 if variant == "primary" else C.BG
        self._img = icons.get(icon, fg, 20)
        super().__init__(
            master, text=f"  {text}", image=self._img, compound="left", command=command,
            bg=self._bg, fg=fg, activebackground=self._hover, activeforeground=fg,
            disabledforeground=C.DISABLED_FG, font=FONT_BOLD, relief="flat", bd=0,
            padx=16, pady=11, cursor="hand2", takefocus=True,
            highlightthickness=3, highlightbackground=master.cget("bg"), highlightcolor=C.FOCUS,
        )
        self.bind("<Enter>", lambda _e: self["state"] == "normal" and self.config(bg=self._hover))
        self.bind("<Leave>", lambda _e: self["state"] == "normal" and self.config(bg=self._bg))
        self.bind("<Return>", lambda _e: self.invoke())  # Enter activa, como en la web

    def set_enabled(self, enabled: bool) -> None:
        self.config(
            state="normal" if enabled else "disabled",
            bg=self._bg if enabled else self._disabled_bg,
            cursor="hand2" if enabled else "arrow",
        )


# ─────────────────────────────────── 5. App ─────────────────────────────────

MODELS = {
    "tiny": "Muy rápido · precisión básica",
    "base": "Rápido · precisión moderada",
    "small": "Equilibrado · recomendado para empezar",
    "medium": "Lento en CPU · alta precisión",
    "large-v3": "El más preciso · exige mucha RAM o GPU",
    "turbo": "Casi tan preciso como large-v3, bastante más rápido",
}
LANGUAGES = {
    "Detectar automáticamente": None, "Español": "es", "English": "en",
    "Português": "pt", "Français": "fr", "Deutsch": "de", "Italiano": "it",
}
DEVICES = {"Automático": "auto", "CPU": "cpu", "GPU (CUDA)": "cuda"}
AUDIO_TYPES = [
    ("Audio y video", "*.mp3 *.wav *.m4a *.flac *.ogg *.opus *.aac *.wma *.mp4 *.mkv *.webm"),
    ("Todos los archivos", "*.*"),
]
STATUS_STYLE = {  # color + icono + texto: nunca depende solo del color
    "idle": ("info", C.MUTED),
    "busy": ("loader", "#60A5FA"),
    "ok": ("check", C.SUCCESS),
    "error": ("alert", C.ERROR),
}


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x780")
        self.minsize(1000, 740)
        self.configure(bg=C.BG)

        self.icons = IconFactory(self.winfo_fpixels("1i") / 96)  # escala por DPI
        self.iconphoto(True, self.icons.logo(64))

        self.events: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.audio_path: Path | None = None
        self.segments: list[Segment] = []
        self.busy = False
        self._inputs: list[tk.Widget] = []

        self._build_styles()
        self._build_ui()
        self._bind_keys()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(60, self._poll)

    # ── estilos ttk ──
    def _build_styles(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")  # único tema ttk que respeta colores personalizados en todos los SO
        s.configure(
            "TCombobox", fieldbackground=C.SURFACE_2, background=C.SURFACE_2,
            foreground=C.TEXT, arrowcolor=C.TEXT, bordercolor=C.BORDER,
            lightcolor=C.BORDER, darkcolor=C.BORDER, padding=(10, 11), arrowsize=16,
        )
        s.map(
            "TCombobox",
            fieldbackground=[("readonly", C.SURFACE_2), ("disabled", C.BG)],
            foreground=[("readonly", C.TEXT), ("disabled", C.DISABLED_FG)],
            selectbackground=[("readonly", C.SURFACE_2)],
            selectforeground=[("readonly", C.TEXT)],
            background=[("active", C.SURFACE_HOVER)],
            bordercolor=[("focus", C.FOCUS)],
            lightcolor=[("focus", C.FOCUS)],
            darkcolor=[("focus", C.FOCUS)],
        )
        self.option_add("*TCombobox*Listbox.background", C.SURFACE_2)
        self.option_add("*TCombobox*Listbox.foreground", C.TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", C.ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        self.option_add("*TCombobox*Listbox.font", FONT)
        s.configure(
            "Horizontal.TProgressbar", troughcolor=C.SURFACE_2, background=C.ACCENT,
            bordercolor=C.SURFACE_2, lightcolor=C.ACCENT, darkcolor=C.ACCENT, thickness=8,
        )
        s.configure(
            "Vertical.TScrollbar", troughcolor=C.SURFACE, background=C.BORDER,
            bordercolor=C.SURFACE, lightcolor=C.BORDER, darkcolor=C.BORDER,
            arrowcolor=C.TEXT, arrowsize=14,
        )
        s.map("Vertical.TScrollbar", background=[("active", C.SURFACE_HOVER)])

    # ── helpers de UI ──
    def _card(self, parent, title: str, icon: str):
        outer = tk.Frame(parent, bg=C.SURFACE, highlightthickness=1, highlightbackground=C.BORDER)
        head = tk.Frame(outer, bg=C.SURFACE)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, image=self.icons.get(icon, C.MUTED, 18), bg=C.SURFACE).pack(side="left")
        tk.Label(head, text=title.upper(), bg=C.SURFACE, fg=C.MUTED, font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)
        body = tk.Frame(outer, bg=C.SURFACE)
        body.pack(fill="x", padx=16, pady=(0, 14))
        return outer, body

    def _field(self, parent, label, values, var, row, col, colspan=1, padx=(0, 0)):
        box = tk.Frame(parent, bg=C.SURFACE)
        box.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=padx, pady=(0, 8))
        tk.Label(box, text=label, bg=C.SURFACE, fg=C.MUTED, font=FONT_SMALL).pack(anchor="w", pady=(0, 4))
        cb = ttk.Combobox(box, values=values, textvariable=var, state="readonly", font=FONT)
        cb.pack(fill="x")
        self._inputs.append(cb)
        return cb

    def _check(self, parent, text, var, command=None):
        cb = tk.Checkbutton(
            parent, text=text, variable=var, command=command, bg=C.SURFACE, fg=C.TEXT,
            selectcolor=C.SURFACE_2, activebackground=C.SURFACE, activeforeground=C.TEXT,
            disabledforeground=C.DISABLED_FG, font=FONT, anchor="w", padx=4, pady=8, bd=0,
            cursor="hand2", takefocus=True, highlightthickness=2,
            highlightbackground=C.SURFACE, highlightcolor=C.FOCUS,
        )
        cb.pack(fill="x")
        self._inputs.append(cb)
        return cb

    # ── construcción de la interfaz ──
    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Cabecera
        header = tk.Frame(self, bg=C.BG)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 14))
        tk.Label(header, image=self.icons.logo(44), bg=C.BG).pack(side="left")
        titles = tk.Frame(header, bg=C.BG)
        titles.pack(side="left", padx=14)
        tk.Label(titles, text=APP_TITLE, bg=C.BG, fg=C.TEXT, font=FONT_TITLE).pack(anchor="w")
        tk.Label(titles, text="Convierte audio a texto sin conexión con faster-whisper", bg=C.BG, fg=C.MUTED, font=FONT_SMALL).pack(anchor="w")
        info = tk.Frame(header, bg=C.BG)
        info.pack(side="right")
        tk.Label(info, text="Ctrl+O Abrir   ·   Ctrl+Enter Transcribir   ·   Esc Cancelar", bg=C.BG, fg=C.MUTED, font=FONT_SMALL).pack(anchor="e")
        tk.Label(info, text=f"v{APP_VERSION}  ·  Desarrollado por {APP_AUTHOR}", bg=C.BG, fg=C.MUTED, font=FONT_SMALL).pack(anchor="e", pady=(2, 0))

        # Panel izquierdo (3 grupos: regla de Miller)
        left = tk.Frame(self, bg=C.BG, width=380)
        left.grid(row=1, column=0, sticky="ns", padx=(24, 12))
        left.pack_propagate(False)

        card, body = self._card(left, "Audio", "audio_file")
        card.pack(fill="x", pady=(0, 12))
        self.btn_pick = IconButton(body, "Seleccionar archivo", "folder", self.choose_file, self.icons)
        self.btn_pick.pack(fill="x")
        self.file_label = tk.Label(body, text="Ningún archivo seleccionado", bg=C.SURFACE, fg=C.MUTED, font=FONT_SMALL, anchor="w", justify="left", wraplength=320)
        self.file_label.pack(fill="x", pady=(10, 0))

        card, body = self._card(left, "Reconocimiento", "wave")
        card.pack(fill="x", pady=(0, 12))
        body.columnconfigure((0, 1), weight=1, uniform="c")
        self.var_model = tk.StringVar(value="small")
        self.var_lang = tk.StringVar(value="Detectar automáticamente")
        self.var_device = tk.StringVar(value="Automático")
        cb_model = self._field(body, "Modelo", list(MODELS), self.var_model, 0, 0, padx=(0, 6))
        self._field(body, "Idioma", list(LANGUAGES), self.var_lang, 0, 1, padx=(6, 0))
        self.model_hint = tk.Label(body, text=MODELS["small"], bg=C.SURFACE, fg=C.MUTED, font=FONT_SMALL, anchor="w", justify="left", wraplength=320)
        self.model_hint.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        cb_model.bind("<<ComboboxSelected>>", lambda _e: self.model_hint.config(text=MODELS[self.var_model.get()]))
        self._field(body, "Dispositivo", list(DEVICES), self.var_device, 2, 0, colspan=2)

        card, body = self._card(left, "Opciones", "info")
        card.pack(fill="x", pady=(0, 12))
        self.var_ts = tk.BooleanVar(value=True)
        self.var_vad = tk.BooleanVar(value=True)
        self._check(body, "Mostrar marcas de tiempo", self.var_ts, self._render)
        self._check(body, "Filtrar silencios (VAD)", self.var_vad)

        actions = tk.Frame(left, bg=C.BG)
        actions.pack(fill="x", side="bottom")
        actions.columnconfigure(0, weight=1)
        self.btn_start = IconButton(actions, "Transcribir", "play", self.start, self.icons, "primary")
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.btn_cancel = IconButton(actions, "Cancelar", "stop", self.request_cancel, self.icons)
        self.btn_cancel.grid(row=0, column=1)

        # Panel derecho: resultado
        right = tk.Frame(self, bg=C.BG)
        right.grid(row=1, column=1, sticky="nsew", padx=(12, 24))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        bar = tk.Frame(right, bg=C.BG)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        heading = tk.Frame(bar, bg=C.BG)
        heading.pack(side="left")
        tk.Label(heading, text="Transcripción", bg=C.BG, fg=C.TEXT, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.meta = tk.StringVar(value="")
        tk.Label(heading, textvariable=self.meta, bg=C.BG, fg=C.MUTED, font=FONT_SMALL).pack(anchor="w")
        self.btn_srt = IconButton(bar, "SRT", "subtitle", lambda: self._save("srt"), self.icons)
        self.btn_srt.pack(side="right")
        self.btn_txt = IconButton(bar, "TXT", "doc", lambda: self._save("txt"), self.icons)
        self.btn_txt.pack(side="right", padx=8)
        self.btn_copy = IconButton(bar, "Copiar", "copy", self.copy_text, self.icons)
        self.btn_copy.pack(side="right")

        wrap = tk.Frame(right, bg=C.SURFACE, highlightthickness=1, highlightbackground=C.BORDER)
        wrap.grid(row=1, column=0, sticky="nsew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.text = tk.Text(
            wrap, wrap="word", bg=C.SURFACE, fg=C.TEXT, font=FONT_TEXT, relief="flat", bd=0,
            padx=20, pady=16, spacing3=8, insertbackground=C.TEXT, selectbackground=C.ACCENT,
            selectforeground="#FFFFFF", state="disabled", takefocus=True,
            highlightthickness=2, highlightbackground=C.SURFACE, highlightcolor=C.FOCUS,
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        self.text.tag_configure("ts", foreground=C.ACCENT_LIGHT)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scroll.set)

        # Estado vacío (se superpone al texto hasta que haya resultados)
        self.empty = tk.Frame(wrap, bg=C.SURFACE)
        self.empty.place(relx=0, rely=0, relwidth=1, relheight=1)
        inner = tk.Frame(self.empty, bg=C.SURFACE)
        inner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(inner, image=self.icons.get("wave", "#475569", 56), bg=C.SURFACE).pack()
        self.empty_title = tk.Label(inner, bg=C.SURFACE, fg=C.TEXT, font=("Segoe UI", 13, "bold"))
        self.empty_title.pack(pady=(12, 2))
        self.empty_desc = tk.Label(inner, bg=C.SURFACE, fg=C.MUTED, font=FONT, wraplength=380)
        self.empty_desc.pack()
        self._show_empty_default()

        # Barra de estado
        status = tk.Frame(self, bg=C.SURFACE, highlightthickness=1, highlightbackground=C.BORDER)
        status.grid(row=2, column=0, columnspan=2, sticky="ew", padx=24, pady=(14, 20))
        self.status_icon = tk.Label(status, bg=C.SURFACE)
        self.status_icon.pack(side="left", padx=(16, 8), pady=14)
        self.status_text = tk.Label(status, bg=C.SURFACE, fg=C.TEXT, font=FONT, anchor="w")
        self.status_text.pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(status, length=280, mode="determinate", maximum=100)
        self.progress.pack(side="right", padx=16)
        self.set_status("idle", "Selecciona un archivo de audio para comenzar")

    def _bind_keys(self) -> None:
        self.bind("<Control-o>", lambda _e: self.choose_file())
        self.bind("<Control-Return>", lambda _e: self.start())
        self.bind("<Escape>", lambda _e: self.request_cancel())
        self.bind("<Control-s>", lambda _e: self._save("txt"))

    # ── estado de la UI ──
    def set_status(self, kind: str, message: str) -> None:
        icon, color = STATUS_STYLE[kind]
        self.status_icon.config(image=self.icons.get(icon, color, 20))
        self.status_text.config(text=message)

    def _refresh(self) -> None:
        """Única fuente de verdad para habilitar/deshabilitar controles."""
        has_result = bool(self.segments) and not self.busy
        self.btn_pick.set_enabled(not self.busy)
        self.btn_start.set_enabled(not self.busy and self.audio_path is not None)
        self.btn_cancel.set_enabled(self.busy and not self.cancel.is_set())
        for b in (self.btn_copy, self.btn_txt, self.btn_srt):
            b.set_enabled(has_result)
        for w in self._inputs:
            if isinstance(w, ttk.Combobox):
                w.configure(state="disabled" if self.busy else "readonly")
            else:
                w.configure(state="disabled" if self.busy else "normal")

    def _show_empty_default(self) -> None:
        self.empty_title.config(text="Aún no hay transcripción")
        self.empty_desc.config(text="Selecciona un audio y pulsa «Transcribir». El texto aparecerá aquí.")
        self.empty.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _show_empty(self, title: str, desc: str) -> None:
        self.empty_title.config(text=title)
        self.empty_desc.config(text=desc)
        self.empty.place(relx=0, rely=0, relwidth=1, relheight=1)

    # ── acciones ──
    def choose_file(self) -> None:
        if self.busy:
            return
        path = filedialog.askopenfilename(title="Seleccionar audio", filetypes=AUDIO_TYPES)
        if not path:
            return
        self.audio_path = Path(path)
        size_mb = self.audio_path.stat().st_size / 1_048_576
        self.file_label.config(text=f"{self.audio_path.name}\n{size_mb:.1f} MB", fg=C.TEXT)
        self._refresh()
        self.set_status("idle", "Listo para transcribir")

    def start(self) -> None:
        if self.busy or self.audio_path is None:
            return
        opts = Options(
            path=str(self.audio_path), model=self.var_model.get(),
            language=LANGUAGES[self.var_lang.get()], device=DEVICES[self.var_device.get()],
            vad=self.var_vad.get(),
        )
        self.segments.clear()
        self._clear_text()
        self.meta.set("")
        self.cancel.clear()
        self.busy = True
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._show_empty("Procesando audio…", "Los resultados aparecerán aquí a medida que se transcriban.")
        self._refresh()
        self.set_status("busy", "Preparando…")
        Worker(opts, self.events, self.cancel).start()

    def request_cancel(self) -> None:
        if not self.busy or self.cancel.is_set():
            return
        self.cancel.set()
        self.set_status("busy", "Cancelando…")
        self._refresh()

    def copy_text(self) -> None:
        if not self.segments:
            return
        self.clipboard_clear()
        self.clipboard_append(to_txt(self.segments, self.var_ts.get()))
        self.set_status("ok", "Texto copiado al portapapeles")

    def _save(self, kind: str) -> None:
        if not self.segments or self.busy:
            return
        stem = self.audio_path.stem if self.audio_path else "transcripcion"
        path = filedialog.asksaveasfilename(
            defaultextension=f".{kind}", initialfile=f"{stem}.{kind}",
            filetypes=[(kind.upper(), f"*.{kind}")],
        )
        if not path:
            return
        content = to_srt(self.segments) if kind == "srt" else to_txt(self.segments, self.var_ts.get())
        Path(path).write_text(content, encoding="utf-8")
        self.set_status("ok", f"Guardado: {Path(path).name}")

    # ── texto ──
    def _clear_text(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def _append(self, seg: Segment) -> None:
        self.text.configure(state="normal")
        if self.var_ts.get():
            self.text.insert("end", f"[{fmt_clock(seg.start)}] ", "ts")
        self.text.insert("end", seg.text + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def _render(self) -> None:
        """Repinta todo (al alternar las marcas de tiempo)."""
        self._clear_text()
        for seg in self.segments:
            self._append(seg)
        self.text.see("1.0")

    # ── eventos del worker ──
    def _poll(self) -> None:
        try:
            while True:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        finally:
            self.after(60, self._poll)

    def _finish(self) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.busy = False

    def _handle(self, ev: tuple) -> None:
        kind = ev[0]
        if kind == "loading":
            self.set_status("busy", f"Cargando modelo «{ev[1]}» (la primera vez se descarga)…")
        elif kind == "decoding":
            self.set_status("busy", "Decodificando audio con ffmpeg…")
        elif kind == "info":
            _, lang, prob, duration = ev
            self._duration = max(duration, 0.001)
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
            self.meta.set(f"Idioma: {lang} ({prob:.0%})  ·  Duración: {fmt_clock(duration)}")
            self.set_status("busy", "Transcribiendo…")
        elif kind == "segment":
            seg: Segment = ev[1]
            if not self.segments:
                self.empty.place_forget()
            self.segments.append(seg)
            self._append(seg)
            self.progress.configure(value=min(100, seg.end / self._duration * 100))
        elif kind == "done":
            self._finish()
            self.progress.configure(value=100)
            if self.segments:
                self.set_status("ok", f"Completado en {ev[1]:.1f} s · {len(self.segments)} segmentos")
            else:
                self._show_empty("Sin voz detectada", "Prueba desactivar el filtro de silencios o usa otro archivo.")
                self.set_status("idle", "No se detectó voz en el audio")
        elif kind == "cancelled":
            self._finish()
            self.progress.configure(value=0)
            if not self.segments:
                self._show_empty_default()
            self.set_status("idle", "Transcripción cancelada")
        elif kind == "error":
            self._finish()
            self.progress.configure(value=0)
            if not self.segments:
                self._show_empty_default()
            self.set_status("error", "Error al transcribir")
            messagebox.showerror(
                "No se pudo transcribir",
                f"{ev[1]}\n\nSi usas GPU y falla, cambia el dispositivo a CPU.",
            )
        self._refresh()

    def _on_close(self) -> None:
        self.cancel.set()
        self.destroy()


def _enable_dpi_awareness() -> None:
    try:
        from ctypes import windll  # solo existe en Windows

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    for name in ("stdout", "stderr"):  # .exe --windowed: no hay consola
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    _enable_dpi_awareness()  # debe ir antes de crear la ventana
    App().mainloop()


if __name__ == "__main__":
    main()