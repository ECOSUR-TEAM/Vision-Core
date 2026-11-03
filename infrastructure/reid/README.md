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

## Tracks expirados y TTL

Después de `detector.process(frame)`, el pipeline consulta `pop_lost_track_ids()`
y procesa las bajas antes de resolver las detecciones actuales. Así un track que
reaparece con un ID local nuevo en ese mismo frame puede recuperar su `person_id`.
Para cada baja recupera el último embedding observado, llama a `mark_lost` y
elimina sus dos mappings locales. IDs desconocidos o duplicados no generan otra
notificación. El embedding se copia para evitar cambios por reutilización del array.

`InMemoryReID.mark_lost` elimina los mappings activos de esa persona y almacena
una copia del embedding con tiempo monotónico. El TTL de 60 segundos empieza al
expirar el track, no en su primer frame ausente. La tolerancia del tracker de
30 frames y este TTL son dos etapas distintas.

Una reaparición recupera el ID solo si ocurre antes de los 60 segundos y la mejor
similitud coseno es estrictamente mayor a 0.85. A los 60 segundos exactos la entrada
ya está caducada. Al recuperarla se retira de la memoria de perdidos para que no
se asigne simultáneamente a otro track. Las entradas caducadas se purgan en
`resolve` y `mark_lost`; no hay un hilo de limpieza cuando no se procesa actividad.

Las pruebas usan reloj controlado y comprueban reaparición a 59.999, 60 y 61
segundos, último embedding, limpieza de mappings, IDs duplicados/desconocidos,
reaparición en el mismo frame y similitud insuficiente. Ejecutar:

```bash
python -m pytest tests/application/test_vision_core_app.py tests/infrastructure/reid/test_memory_reid.py -q
```
