# Third-Party Notices

Este archivo inventaría las dependencias directas declaradas en
`requirements*.txt` y las herramientas fijadas en `pyproject.toml` y los
workflows de CI, sus licencias y las obligaciones relevantes para distribución,
SaaS o escalado. Las versiones son las fijadas en esos archivos; la licencia
efectiva de cada paquete debe verificarse también con `pip-licenses` o leyendo
el `LICENSE` del wheel instalado.

| Componente | Versión | Uso | Licencia | Fuente |
|---|---|---|---|---|
| ultralytics | 8.4.201 | Detector de personas (YOLO) | **AGPL-3.0** | `ultralytics/LICENSE` |
| torch | 2.10.0 | Inferencia (índice CPU) | BSD-3-Clause y componentes incluidos (Apache-2.0, BSD-2/3, MIT, BSL-1.0, LLVM-exception) | `torch/LICENSE` |
| torchvision | 0.25.0 | Transformaciones de visión (índice CPU) | BSD-3-Clause | `torchvision/LICENSE` |
| opencv-python | 5.0.0.93 | Captura/decodificación de video | Apache-2.0 y componentes incluidos | `LICENSE-3RD-PARTY.txt` |
| numpy | 2.4.6 | Arreglos | BSD-3-Clause y componentes incluidos | `LICENSE.txt` |
| pillow | 13.0.0 | Procesamiento de imágenes | MIT-CMU (HPND) | `LICENSE` |
| pyyaml | 6.0.2 | Configuración de zonas | MIT | `LICENSE` |
| pytest | 9.1.1 | Desarrollo/test (también instalado en runtime) | MIT | `LICENSE` |
| pytest-cov | 7.1.0 | Desarrollo/test (también instalado en runtime) | MIT | `AUTHORS.rst`/`LICENSE` |
| mypy | 1.11.2 | Solo desarrollo/typecheck | MIT | `LICENSE` |
| types-PyYAML | 6.0.12.20261113 | Stubs de typing | Apache-2.0 | `LICENSE` |
| setuptools | >=61 | Backend de build | MIT | `LICENSE` |
| ruff | 0.3.0 | Lint y formato en CI | MIT | `LICENSE` |

`torch` y `torchvision` se instalan desde el índice CPU de PyTorch. Los pesos
de modelos (por ejemplo `yolov8n.pt`) pueden tener términos distintos al código
y requieren revisión separada antes de redistribuirlos.

## Decisión AGPL

Ultralytics/YOLO es AGPL-3.0. Esto no es un riesgo menor:

- **Distribución**: al entregar el binario o una imagen que incluya Ultralytics
  hay que cumplir AGPL-3.0, conservar avisos y ofrecer el código fuente
  correspondiente bajo AGPL, incluyendo modificaciones.
- **SaaS/servicio**: AGPL §13 exige ofrecer el Corresponding Source a quienes
  interactúan con el programa por red cuando se ejecuta una versión modificada.
  No basta con no distribuir el binario.
- **Obra combinada**: integrar el detector en el producto puede exigir que el
  conjunto se distribuya bajo AGPL; debe revisarse caso por caso.

Decisión actual: **no distribuir ni ofrecer Vision Core como servicio antes de
la revisión legal**. La publicación automática de imágenes en GHCR está
deshabilitada por defecto: `.github/workflows/docker.yml` solo ejecuta
`push: true` cuando `vars.PUBLISH_CONTAINER_IMAGES == 'true'`. Esa variable debe
activarse únicamente después de la aprobación registrada en
`docs/legal-review.md`; hasta entonces los workflows pueden construir y escanear
imágenes, pero no distribuir artefactos que incluyan Ultralytics.

Si el producto debe distribuirse o SaaS, las opciones son:

1. Obtener una licencia comercial de Ultralytics que cubra el uso previsto.
2. Sustituir el detector por una alternativa con licencia permisiva
   (BSD/MIT/Apache) revisando también pesos y derechos de modelo.
3. Publicar el código bajo AGPL-3.0 cumpliendo todas las obligaciones.

Esta decisión es una evaluación técnica, no asesoría legal; ver
`docs/legal-review.md` para la revisión formal pendiente.
