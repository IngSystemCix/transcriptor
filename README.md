# Transcriptor de audio

Aplicación de escritorio para convertir audio y video en texto **sin conexión**, con [faster-whisper](https://github.com/SYSTRAN/faster-whisper) e interfaz en Tkinter.

## Características

- Transcripción local (tus archivos no salen de tu equipo).
- Modelos `tiny`, `base`, `small`, `medium`, `large-v3` y `turbo`.
- Detección automática de idioma o selección manual (ES, EN, PT, FR, DE, IT).
- Resultado en vivo, segmento a segmento, con marcas de tiempo opcionales.
- Filtro de silencios (VAD) y selección de dispositivo (Automático, CPU, GPU CUDA).
- Cancelación en cualquier momento.
- Exporta a **TXT** y **SRT** (subtítulos) o copia al portapapeles.
- Interfaz oscura accesible: contraste WCAG AA, anillos de foco visibles, botones de 44 px, estado con icono + color + texto y atajos de teclado.

## Formatos admitidos

MP3, WAV, M4A, FLAC, OGG, OPUS, AAC, WMA, MP4, MKV, WEBM.

## Atajos de teclado

| Atajo | Acción |
|---|---|
| `Ctrl+O` | Seleccionar archivo |
| `Ctrl+Enter` | Transcribir |
| `Esc` | Cancelar |
| `Ctrl+S` | Guardar como TXT |

## Ejecutar desde el código

Requisitos: [uv](https://docs.astral.sh/uv/) y Python 3.11 o superior (recomendado 3.12; `onnxruntime` ya no publica ruedas para 3.10).

```powershell
uv python install 3.12
uv python pin 3.12
uv add faster-whisper pillow
uv run main.py
```

En Linux con Python del sistema, instala también Tkinter: `sudo apt install python3-tk`.

## Compilar a un `.exe`

```powershell
uv add --dev pyinstaller
uv run build.py
```

El resultado queda en `dist/Transcriptor.exe`.

| Comando | Resultado |
|---|---|
| `uv run build.py` | Un solo `.exe` (más simple de distribuir, arranque más lento porque se extrae a una carpeta temporal) |
| `uv run build.py --onedir` | Carpeta `dist/Transcriptor/` (arranque rápido, más fiable con antivirus y políticas de Windows) |
| `uv run build.py --with-ffmpeg` | Incrusta `ffmpeg.exe` (ver «Control de aplicaciones»). Añade unos 100 MB o más |

Notas:

- El `.exe` pesa varios cientos de MB porque incluye el motor de inferencia y sus librerías. Es normal.
- Los **modelos no van dentro del `.exe`**: se descargan la primera vez que se usa cada uno (necesita internet) y se guardan en `%USERPROFILE%\.cache\huggingface`. Después funciona sin conexión.
- El `.exe` no está firmado digitalmente. Windows SmartScreen o tu antivirus pueden mostrar avisos o marcarlo como falso positivo (algo habitual en ejecutables de PyInstaller).

## Solución de problemas

### «Una directiva de Control de aplicaciones bloqueó este archivo»

Windows (Smart App Control, WDAC o AppLocker) bloquea una DLL sin firma, normalmente la de PyAV (`av`). La aplicación lo detecta y decodifica el audio con `ffmpeg.exe` en su lugar:

1. Instala ffmpeg: `winget install Gyan.FFmpeg` y reabre la terminal (o compila con `--with-ffmpeg`).
2. Comprueba que funciona: `ffmpeg -version`.

Si `ffmpeg.exe` o el propio `.exe` también son bloqueados, la política del equipo rechaza todo binario sin firma. Opciones: pedir una excepción al administrador de TI, firmar el ejecutable con un certificado de firma de código, o ejecutar la aplicación desde el código dentro de WSL2.

### Error con GPU (CUDA)

Cambia el dispositivo a **CPU**. Para usar GPU necesitas los controladores NVIDIA y las librerías cuBLAS y cuDNN compatibles con CTranslate2.

### `No se encontró ffmpeg en el PATH`

Solo aparece cuando PyAV no puede cargarse. Instala ffmpeg como se indica arriba.

### La primera transcripción tarda mucho

Se está descargando el modelo. Los modelos grandes (`medium`, `large-v3`) pesan varios GB. Para empezar, usa `small`.

### En macOS los botones no tienen color

`tk.Button` ignora los colores de fondo en macOS y usa el estilo nativo. En Windows y Linux se ve como está diseñado.

## Estructura del proyecto

```
transcriptor/
├── main.py        # Aplicación completa (utilidades, iconos, worker, UI)
├── build.py       # Script de compilación a .exe (PyInstaller)
├── pyproject.toml
└── README.md
```

`main.py` se organiza en capas: utilidades de formato → iconos PNG generados con Pillow → `Worker` (hilo que se comunica por `queue.Queue`) → widgets propios → `App`.