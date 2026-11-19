# Desarrollo local

## Requisitos

- Python 3.11
- Docker con Compose (opcional)
- FFmpeg, `libgl1` y `libglib2.0-0`
- Git

## Arranque en menos de 15 minutos

Linux/macOS con Bash:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
make setup
make test
make lint
make run
```

`make setup` instala dependencias CPU, copia `.env.example` a `.env` si no existe
y genera `dev-data/sample.avi` con `dev-data/zones.json`. No requiere cámara ni
credenciales reales.

El monitor estará disponible en `http://127.0.0.1:8080`.

## Comandos únicos

| Comando | Uso |
|---|---|
| `make setup` | Crear entorno, instalar dependencias y datos sintéticos |
| `make test` | Ejecutar pytest completo |
| `make lint` | Ejecutar Ruff lint |
| `make format` | Aplicar Ruff format |
| `make format-check` | Comprobar formato sin modificar |
| `make run` | Ejecutar monitor local con video sintético |
| `make docker-build` | Construir imágenes de Compose |
| `make synthetic` | Generar solo los datos sintéticos |
| `make clean` | Eliminar datos sintéticos generados |

## Dev Container

Abre la carpeta en VS Code y selecciona **Dev Containers: Reopen in Container**.
El contenedor usa Python 3.11 y recomienda las extensiones Python, Ruff y Docker.
La primera creación ejecuta `make setup`.

El Dev Container es opcional: quien ya tenga `.venv` puede continuar con Make.

## Perfiles de Compose

```bash
docker compose --profile synthetic up
docker compose --profile webcam up
docker compose --profile camera up
docker compose --profile file up
```

- `synthetic` / `file`: video sintético sin cámara.
- `webcam`: usa el dispositivo configurado en `FRIGATE_WEBCAM_DEVICE`.
- `camera`: inicia el puente Ethernet y Frigate para una cámara RTSP.

Detén los servicios:

```bash
docker compose --profile synthetic down
```

Ejecuta `make synthetic` antes de levantar el perfil sintético si falta
`dev-data/sample.avi`.

## Troubleshooting

### No aparece Python 3.11

Instala Python 3.11 antes de ejecutar `make setup`. En Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv ffmpeg libgl1 libglib2.0-0
```

### FFmpeg u OpenCV no decodifican

Comprueba:

```bash
ffmpeg -version
python -c "import cv2; print(cv2.__version__, cv2.getBuildInformation())"
```

### GPU/CUDA

CPU funciona para desarrollo. Para CUDA, instala una pareja torch/torchvision
compatible con el driver antes de `make setup` y configura
`VISION_CORE_DETECTION_DEVICE=cuda` o `VISION_CORE_EMBEDDING_DEVICE=cuda`.

### Permisos de cámara

En Linux añade tu usuario al grupo `video` y vuelve a iniciar sesión:

```bash
sudo usermod -aG video "$USER"
```

### Puertos ocupados

El monitor usa `8080`, Frigate `15000` y RTSP `8554`. Comprueba procesos:

```bash
lsof -nP -iTCP:8080 -iTCP:15000 -iTCP:8554 -sTCP:LISTEN
```
