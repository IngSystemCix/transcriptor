# Transcriptor

Aplicación de escritorio para transcribir audio y video en texto de forma local, sin depender de servicios externos. Está desarrollada con Python, Tkinter y [faster-whisper](https://github.com/SYSTRAN/faster-whisper), y permite trabajar directamente desde el equipo del usuario.

## ¿Qué hace?

- Convierte archivos de audio y video en texto localmente.
- Soporta modelos `tiny`, `base`, `small`, `medium`, `large-v3` y `turbo`.
- Detecta el idioma automáticamente o permite seleccionarlo manualmente.
- Muestra resultados por segmentos y permite activar marcas de tiempo.
- Incluye filtro de silencios (VAD) y selección de dispositivo (`auto`, `cpu`, `cuda`).
- Exporta a TXT y SRT y permite copiar el texto al portapapeles.
- Tiene una interfaz oscura, accesible y pensada para uso local.

## Formatos admitidos

- Audio: MP3, WAV, M4A, FLAC, OGG, OPUS, AAC, WMA
- Video: MP4, MKV, WEBM

## Requisitos

- Python 3.11 o superior (recomendado 3.12)
- [uv](https://docs.astral.sh/uv/)
- Windows, Linux o macOS

En Linux, si Tkinter no está instalado, puede ser necesario ejecutar:

```bash
sudo apt install python3-tk
```

## Instalación

1. Clona el repositorio:

```bash
git clone <url-del-repositorio>
cd transcriptor
```

2. Instala las dependencias del proyecto:

```powershell
uv python install 3.12
uv python pin 3.12
uv sync
```

Si quieres configurarlo manualmente:

```powershell
uv add faster-whisper pillow
```

## Uso

Lanza la app con:

```powershell
uv run main.py
```

Desde la interfaz puedes:

- abrir un archivo de audio o video,
- elegir modelo, idioma y dispositivo,
- activar o desactivar VAD,
- iniciar la transcripción,
- guardar el resultado en TXT o SRT.

## Atajos de teclado

| Atajo | Acción |
|---|---|
| `Ctrl+O` | Abrir archivo |
| `Ctrl+Enter` | Iniciar transcripción |
| `Esc` | Cancelar |
| `Ctrl+S` | Guardar como TXT |

## Compilar a ejecutable

El proyecto incluye un script de empaquetado con PyInstaller:

```powershell
uv add --dev pyinstaller
uv run build.py
```

Genera un ejecutable en `dist/Transcriptor.exe`.

### Variantes de compilación

| Comando | Resultado |
|---|---|
| `uv run build.py` | Un único `.exe` |
| `uv run build.py --onedir` | Carpeta `dist/Transcriptor/` |
| `uv run build.py --with-ffmpeg` | Incluye `ffmpeg.exe` dentro del paquete |

## Observaciones importantes

- Los modelos de Whisper no se empaquetan dentro del ejecutable; se descargan la primera vez que se usan.
- El ejecutable puede ser grande porque incluye el motor de inferencia y sus dependencias.
- En Windows es habitual que aparezca un aviso de SmartScreen o antivirus por ser un binario no firmado.

## Solución de problemas

### PyAV bloqueado por Windows

Si la DLL de PyAV está bloqueada, la app detecta este caso y usa `ffmpeg` para decodificar el audio.

Instala FFmpeg:

```powershell
winget install Gyan.FFmpeg
```

Compruébalo con:

```powershell
ffmpeg -version
```

### Error con GPU (CUDA)

Si falla la GPU, cambia el dispositivo a `CPU` desde la interfaz. Para usar CUDA necesitas drivers NVIDIA compatibles y librerías de CTranslate2.

### `No se encontró ffmpeg en el PATH`

Instala FFmpeg o compila con `--with-ffmpeg`.

### La primera transcripción tarda mucho

Es normal: la primera vez que se usa un modelo, este se descarga y se prepara. Los modelos grandes pueden tardar más.

## Estructura del proyecto

```text
transcriptor/
├── main.py
├── build.py
├── pyproject.toml
├── README.md
├── LICENSE
├── Transcriptor.spec
└── docs/
```

La lógica principal está en `main.py`, donde se separan las utilidades, la generación de iconos, el worker de transcripción y la interfaz de usuario.

## Licencia

Este proyecto está protegido por una licencia de derechos reservados. No está permitido copiar, redistribuir, modificar, reutilizar ni comercializar el código sin autorización previa por escrito del titular de los derechos. Consulta [LICENSE](LICENSE) para más detalles.
