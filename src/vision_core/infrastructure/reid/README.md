# Embeddings visuales

`TorchvisionEmbeddingExtractor` recibe un recorte BGR `uint8` H×W×3 y devuelve
un vector NumPy unidimensional `float32`, finito y de norma L2 igual a 1.
Rechaza recortes vacíos, formatos incorrectos y salidas de norma cero/no finitas.

El modelo seleccionado por defecto es MobileNetV3-Small: produce 576 componentes
sin su clasificador. ResNet50 produce 2048 componentes después del average pooling,
sin su capa de clasificación. La salida de ResNet se aplana antes de normalizar;
no se devuelve un tensor 2048×1×1.

```bash
export VISION_CORE_EMBEDDING_MODEL=mobilenet_v3_small
# Alternativa: resnet50
export VISION_CORE_EMBEDDING_DEVICE=cpu
# Alternativa: cuda o cuda:0; si se omite, selecciona CUDA cuando está disponible.
python main.py
```

`main.py` carga esta configuración con `from_env()`. Para usarla con Docker,
incluye las variables en `.env`. CUDA solicitada explícitamente y no disponible
produce un error; no cambia silenciosamente a CPU.

Preprocesamiento: BGR→RGB, conversión PIL y transformaciones oficiales de los
pesos (`weights.transforms()`): resize, recorte central 224×224, escalado y
normalización ImageNet. Se ejecuta con `eval()` e `inference_mode()`. Referencia:
[modelos y preprocesamiento de torchvision](https://docs.pytorch.org/vision/main/models).

Los pesos ImageNet se descargan al primer uso si no existen en la caché de Torch.
Para despliegue sin internet deben prepararse previamente. No cambiar de modelo
mientras se conservan embeddings en ReID: sus dimensiones y espacios difieren.
Son características visuales de ImageNet, no un modelo entrenado específicamente
para identificar personas; la calidad de ReID en la sala requiere evaluación real.

Pruebas: `python -m pytest tests/infrastructure/reid/test_embedder.py -q`.
Las pruebas de contrato verifican canales, dtype, formato, normalización, entradas
inválidas y aplanado ResNet. Las pruebas reales ejecutan ambos modelos en CPU/CUDA
cuando hay pesos locales y hardware disponible; en otro caso se omiten
explícitamente. Nunca descargan pesos durante pytest.

## Memoria durante la sesión

Los puntos de entrada (`main.py`, monitor y runner) construyen la memoria con
`InMemoryReID.from_env()`. `VISION_CORE_REID_TTL_SECONDS=0` conserva las identidades
mientras se ejecute el programa. El control explícito de inicio/fin de reunión
queda pendiente. Detener o reiniciar el proceso vacía la memoria; no hay archivos
de rostros ni persistencia de embeddings en disco.

Puede establecerse un tiempo positivo en segundos, contado desde la primera
observación ausente. El constructor directo conserva el valor anterior de 60 s
para compatibilidad; los ejecutables utilizan el valor de entorno, por defecto 0.

Al dejar de verse una persona, su identidad se libera para ReID inmediatamente:
no espera los 31 frames que necesita el tracker para eliminar su track. Si el
tracker conserva su ID tras una oclusión, se respeta esa asociación. Antes de
resolver nuevas detecciones se reservan los tracks visibles ya conocidos. Una
identidad visible no puede asignarse a otra persona a la vez.

Cada identidad conserva hasta ocho apariencias diferentes normalizadas y la
última vista al desaparecer. Así, la última imagen de espaldas no borra una vista
frontal anterior. Una nueva detección recupera una identidad ausente cuando la
mejor similitud supera `VISION_CORE_REID_THRESHOLD` (0.85) y aventaja al segundo
candidato al menos 0.03. Si dos personas son demasiado parecidas, no se fusionan
por fuerza: se crea una identidad nueva. La galería reduce fallos, pero el modelo
sigue siendo ImageNet y no garantiza reconocer correctamente cada reingreso.

## Personas únicas y ocupación

`SessionAttendance` procesa los eventos de zonas dentro de `VisionCoreApp`.
Cada evento incluye en `metadata`:

- `unique_people_entered`: identidades distintas con entrada confirmada.
- `people_inside`: identidades con entrada confirmada y sin salida posterior.
- `returning_person`: una entrada de alguien registrado previamente.

Ejemplo: A entra → 1 persona única y 1 dentro; A sale → 1 única y 0 dentro;
A vuelve → 1 única y 1 dentro. El nuevo cruce sigue siendo un evento de entrada,
pero no agrega un visitante único. Estos valores dependen de zonas calibradas y
de una identidad correcta. No inicializan automáticamente a quienes ya estaban
en la sala al arrancar. «Personas visibles» en el monitor solo cuenta detecciones
actuales y no es un aforo.

La modalidad `--uncalibrated` no emite eventos de zonas ni inventa ocupación.
Para comprobar el conteo de entradas/salidas reales falta calibrar la sala.

Pruebas: ausencia breve con track nuevo, retorno tras horas dentro de una sesión,
TTL configurable, cambios de vista, candidatos ambiguos, exclusión de personas
visibles y entrada→salida→reingreso sin aumentar visitantes únicos.
