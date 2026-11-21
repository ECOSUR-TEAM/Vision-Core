# Registro de revisión legal

| Campo | Valor |
|---|---|
| Estado | **Pendiente — bloqueante para producción** |
| Fecha del registro | 2026-11-20 |
| Alcance | Distribución y/o explotación como servicio de Vision Core |
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
- Exposición del monitor: binding local por defecto, publicación en loopback y
  dependencia de autenticación/TLS del ticket 42.

## Decisión técnica actual

No distribuir ni ofrecer Vision Core como servicio hasta completar la revisión
legal. No activar exposición fuera de localhost sin ticket 42.

## Checklist para la revisión externa

- [ ] Confirmar base legal y redactar aviso para la sala.
- [ ] Nombrar responsable del tratamiento y contacto de privacidad.
- [ ] Elegir vía AGPL: licencia comercial, detector alternativo o publicación
      AGPL, y revisar licencia de los pesos del modelo.
- [ ] Revisar el contrato de tratamiento de datos si hay terceros que alojen
      el servicio.
- [ ] Validar plazos de retención frente a normativa local.
- [ ] Verificar borrado automático con una prueba sobre datos reales de prueba.
- [ ] Confirmar controles de acceso, auth/TLS y registro de accesos.
- [ ] Aprobar o rechazar la puesta en producción y dejar constancia firmada.

## Registro de aprobación

Pendiente. Este documento debe completarse con nombre del asesor, fecha,
dictamen y firma antes de cualquier despliegue de producción.
