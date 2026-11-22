# Registro de revisión legal

| Campo | Valor |
|---|---|
| Estado | **Pendiente — bloqueante para producción** |
| Fecha del registro | 2026-11-20 |
| Alcance | Distribución, publicación de imágenes y/o explotación como servicio de Vision Core |
| Responsable técnico | Equipo Vision Core |
| Asesoría legal externa | **No contratada todavía** |

## Materias revisadas técnicamente

- Inventario de dependencias y licencias: `THIRD_PARTY_NOTICES.md`.
- Riesgo AGPL-3.0 de Ultralytics/YOLO para distribución y SaaS, con tres vías
  de resolución documentadas.
- Política de privacidad, minimización, retención y acceso:
  `docs/privacy-retention.md`.
- Configuración de retención: `VISION_CORE_*_TTL_SECONDS` en
  `docs/persistence.md`; borrado por `RetentionJob`.
- Exposición del monitor: binding local por defecto en el proceso Python y
  publicación en loopback en Compose. `Dockerfile` y Compose fuerzan
  `0.0.0.0` dentro del contenedor; el control real es la publicación del puerto.
  El criterio de acceso restringido fuera de localhost (autenticación, RBAC,
  TLS y registro de accesos) sigue **pendiente y bloqueante**; ECM-87 documenta
  la brecha y los tickets 42/46/47 son complementarios, no sustitutos.
- Publicación de imágenes: `push: true` está condicionado a
  `vars.PUBLISH_CONTAINER_IMAGES == 'true'` en
  `.github/workflows/docker.yml`. La variable permanece desactivada hasta que
  exista dictamen legal, porque la imagen `runtime` incluye Ultralytics AGPL.
- Derechos de las personas y rotación de logs: procedimiento y retención
  documentados en `docs/privacy-retention.md`, pero sin implementación
  operativa; siguen como pendientes bloqueantes para producción.

## Decisión técnica actual

No distribuir ni ofrecer Vision Core como servicio, ni activar
`PUBLISH_CONTAINER_IMAGES`, hasta completar la revisión legal. No activar
exposición fuera de localhost hasta implementar y validar autenticación, RBAC,
TLS y registro de accesos (criterio bloqueante pendiente). Tampoco abrir el
procedimiento de derechos ni la retención de logs sin la implementación y la
evidencia correspondientes.

## Checklist para la revisión externa

- [ ] Confirmar base legal y redactar aviso para la sala.
- [ ] Nombrar responsable del tratamiento y contacto de privacidad.
- [ ] Elegir vía AGPL: licencia comercial, detector alternativo o publicación
      AGPL, y revisar licencia de los pesos del modelo.
- [ ] Revisar el contrato de tratamiento de datos si hay terceros que alojen
      el servicio.
- [ ] Validar plazos de retención frente a normativa local.
- [ ] Verificar borrado automático con una prueba sobre datos reales de prueba,
      incluidas `persons` e `identity_gallery`.
- [ ] Confirmar que `PUBLISH_CONTAINER_IMAGES` sigue desactivada o documentar la
      aprobación expresa de la distribución AGPL.
- [ ] Implementar y probar el procedimiento de supresión por `person_id` y la
      retención de logs.
- [ ] Confirmar controles de acceso, auth/TLS y registro de accesos (pendiente
      bloqueante; no cerrado por ECM-87 ni por los tickets 42/46/47).
- [ ] Aprobar o rechazar la puesta en producción y dejar constancia firmada.

## Registro de aprobación

Pendiente. Este documento debe completarse con nombre del asesor, fecha,
dictamen y firma antes de cualquier despliegue de producción o de activar la
publicación de imágenes.
