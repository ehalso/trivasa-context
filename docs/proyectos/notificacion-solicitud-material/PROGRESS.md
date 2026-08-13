# notificacion-solicitud-material — estado vivo

## 2026-08-13

- **DISPONIBLE**: resuelto, 100% cobertura / 87.9% precisión contra
  baseline real exportado. Notebook `06_notebook_disponible_solicitud_material.py`
  promovido a `scripts/`. Detalle y query final en [index.md](index.md).
- **AU**: sin resolver, conteos no convergen contra la captura de pantalla
  (38 esperados vs. 882/1390 según base). Falta baseline exportado real.
- **AB, PR, APG, AC RECHAZADO, OC SIN AU, PXC**: sin empezar.
- Documentación de calidad de datos y flujo de autorización de esta sesión
  ya integrada en `docs/schema/calidad-de-datos.md` y
  `docs/schema/solicitud-material.md`.
- Regla de promoción de este repo relajada explícitamente para este
  proyecto (ver `CLAUDE.md`): un notebook guardado ya es un hallazgo
  curado, no hace falta 100% de precisión para que sea accesible aquí.

## Pendiente

- [ ] **AU**: conseguir un baseline exportado real (como DISPONIBLE) y
  repetir el diff iterativo — los intentos por conteo puro no
  convergieron.
- [ ] **DISPONIBLE**: investigar los 77 folios sobrantes de v5
  (`Ap_Tabla='COMPRA'` + cabecera `PR`, 55 de 77) — o aceptar 87.9% de
  precisión como resultado final.
- [ ] **AB, PR, APG, AC RECHAZADO, OC SIN AU, PXC**: sin empezar.
- [ ] Confirmar si `RP_CTR_SM1`/`RP_CTR_SM2` son de verdad el origen de
  `ZTRV098` v3, o si tiene su propio SQL en otro lado no explorado (patrón
  C, carpeta `pro/Z/`, ver [Reportes nativos](../../schema/reportes-nativos.md)).

## Fuente

Trabajo local en
`~/trivasa-bi-dev/proyectos-bi/notificacion-solicitud-material/` (no
promovido a este repo: baseline exportado, scripts intermedios 01-05 sin
guardar individualmente).
