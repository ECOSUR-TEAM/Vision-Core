# Contratos de DTOs entre slices

El snapshot `tests/contracts/dto_snapshot.json` congela la forma pública de los
DTOs compartidos y de los módulos `dto/` descubiertos en los slices, incluido
`reid` si llega a publicar DTOs: nombre de clase, módulo, campos, tipos
serializables, valores por defecto y banderas `frozen`/`slots`.

## Invariantes

- Todo DTO público es `frozen` y usa `slots` cuando el ADR lo requiere.
- Todo DTO se puede construir desde un dict externo y serializar con
  `to_json_value` sin perder sus campos. Los campos `bytes` son la excepción
  documentada: se serializan como `null` y se sirven por el endpoint de imagen.
- Ningún módulo bajo `dto/` importa `numpy`, `cv2`, `torch`, `torchvision`,
  `ultralytics`, dominio ni infraestructura.
- Renombrar, quitar o cambiar el tipo de un campo hace fallar la suite con un
  diff unificado; agregar un campo también es un cambio explícito.

## Cómo actualizar el golden

Solo después de una decisión de contrato aprobada en el PR:

```bash
python -m tests.contracts.generate_golden
python -m pytest tests/contracts -q
```

El diff del golden debe revisarse junto con el cambio que lo provoca. No se
aceptan regeneraciones sin esa revisión; los tests de mutación inyectan snapshots
modificados en la comparación real y verifican que un cambio incompatible la
rompe.
