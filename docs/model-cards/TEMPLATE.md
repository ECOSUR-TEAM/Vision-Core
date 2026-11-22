# Model card: `<model_id>`

| Campo | Valor |
|---|---|
| ID | `<model_id>` |
| Nombre | `<nombre>` |
| Versión | `<version>` (`artifact_version: <artifact_version>`) |
| Tarea | `detection` o `embedding` |
| Selector | `<selector>` |
| Hash/checksum | `sha256:<hex>` o `unverified` |
| Registro | `config/models.yml` |
| Fecha de registro | `YYYY-MM-DD` |

## Uso previsto

Describe el uso dentro del pipeline de Vision Core: tipo de entrada, resolución y salida.

## Fuera de uso

Enumera usos no soportados: reconocimiento de identidad, videovigilancia normativa,
medición de aforo certificada, etc., según corresponda.

## Datos de entrenamiento o proveniencia conocida

Indica el dataset o los pesos declarados por el proveedor, con fuente y fecha de consulta.
Si un dato no está verificado, escribe `UNKNOWN` y la acción pendiente.

## Métricas del ticket 36

| Métrica | Valor | Origen |
|---|---:|---|
|  |  | `reports/...` o documentación oficial |

Separa claramente mediciones locales sintéticas de métricas publicadas por el proveedor.
Si no hay ground truth anotado, indícalo.

## Limitaciones y sesgos conocidos

- Limitaciones del modelo, resolución, iluminación, oclusiones y dominio.
- Sesgos conocidos del dataset de origen o riesgos para personas.
- Qué no puede afirmarse con la evidencia disponible.

## Dependencias y licencias

| Componente | Versión | Licencia |
|---|---|---|
|  |  |  |

Incluye la licencia del código y la de los pesos cuando esté declarada. Si no lo está,
marca `UNKNOWN` y referencia el ticket 42.

## Configuración esperada

Resume `expected_config` y las variables de entorno que deben coincidir.

## Procedimiento de rollback

1. Restaurar la ruta/nombre del artefacto anterior.
2. Fijar el `model_id` anterior en la variable correspondiente.
3. Reiniciar y verificar `model_id`, `model_version` y `model_hash` en logs y `/ready`.

## Verificación

Cómo reproducir la medición y dónde quedan los reportes.
