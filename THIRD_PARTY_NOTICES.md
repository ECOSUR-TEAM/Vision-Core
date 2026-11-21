# Third-Party Notices

Vision Core uses the following third-party components. Licenses are listed for
distribution/SaaS compliance review (AGPL risk noted).

| Component | Version | License | Notes |
|---|---|---|---|
| ultralytics | 8.4.201 | AGPL-3.0 | YOLO. AGPL obligations apply on distribution/SaaS. |
| torch | 2.15.0+cpu | BSD-3-Clause | |
| torchvision | 0.29.2+cpu | BSD-3-Clause | |
| opencv-python | 5.0.0.93 | Apache-2.0 | |
| numpy | 2.4.6 | BSD-3-Clause | |
| pillow | 13.0.0 | HPND | |
| pyyaml | 6.0.2 | MIT | |

Decision: AGPL obligations evaluated; do not distribute/offer as SaaS without
legal review or commercial license. See docs/privacy-retention.md.
" filePath="/Users/bj_dev/Estadia/Ecosur/Vision-Core/THIRD_PARTY_NOTICES.md">
cd /Users/bj_dev/Estadia/Ecosur/Vision-Core && cat > docs/privacy-retention.md <<'EOF'
# Política de privacidad y retención de video

## Finalidad y base legal
Procesar video para detección de personas/eventos en sala; base legal según
contexto (consentimiento/interés legítimo). Aviso a personas en la sala.

## Minimización
No guardar video/frames por defecto. Si se guarda, definir plazo y acceso.

## Retención
| Dato | Plazo | Borrado |
|---|---|---|
| video | configurable | automático |
| frames | configurable | automático |
| eventos | configurable | automático |
| embeddings | configurable | automático |
| logs | configurable | automático |

## Acceso
Acceso restringido a video/eventos; auth/TLS fuera de localhost; registro de accesos.

## Revisión legal
Validar antes de producción.
EOF
git add THIRD_PARTY_NOTICES.md docs/privacy-retention.md && git commit -m "docs: add third-party notices and privacy/retention policy" && git push