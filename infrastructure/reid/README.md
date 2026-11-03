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
