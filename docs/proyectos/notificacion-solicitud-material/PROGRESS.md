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

## 2026-08-13 (continuación) — AB y PR resueltos, AU con baseline real sin converger

- **AB**: resuelto contra `baseline/AB-13-08-2026.xlsx` (89 líneas),
  92.13% cobertura / 93.18% precisión. Query final:
  `Requisicion_Compra.Es_Cve_Estado='AC'` (vía el patrón polimórfico
  `Rc_Tabla`/`Rc_Documento`, nuevo hallazgo de esquema) + cabecera no
  `CE`/`FN`. Notebook `52_notebook_ab_solicitud_material.py` promovido.
- **PR**: resuelto contra `baseline/PR-13-08-2026.xlsx` (165 líneas),
  96.97% cobertura / 97.56% precisión. El salto de 36% a 97.6% vino de
  agregar `Oc_Fecha_Entrega >= HOY` a `Orden_Compra.Es_Cve_Estado='AC'`
  — sin eso se contaban órdenes vigentes de hasta 2020 nunca cerradas.
  Notebook `53_notebook_pr_solicitud_material.py` promovido.
- **AU**: por fin se consiguió baseline real
  (`baseline/AU-13-08-2026.xlsx`, 20 líneas/19 folios), pero **no
  convergió** — mejor resultado 90% cobertura / ~26% precisión, sin
  causa raíz clara para los ~50 sobrantes. Confirmado con un caso real
  que parte del ruido es inherente a reconciliar contra `.207` en vivo
  (un apartado se creó *después* del export del baseline). Detalle en
  [Solicitud de material](../../schema/solicitud-material.md#pestana-au-parcialmente-explorada-sin-converger).
- Hallazgo de esquema nuevo: `Requisicion_Compra` y `Orden_Compra`
  también son polimórficas (`_Tabla`/`_Documento`), mismo patrón que
  `ZTRV_Apartado` — integrado en `docs/schema/calidad-de-datos.md`.

## Pendiente

- [ ] **AU**: la muestra de 20 líneas es chica para separar señal de
  ruido — retomar con un baseline más grande, o validando en vivo con el
  usuario por qué un candidato sobrante puntual no aparece en pantalla.
- [ ] **DISPONIBLE**: investigar los 77 folios sobrantes de v5
  (`Ap_Tabla='COMPRA'` + cabecera `PR`, 55 de 77) — o aceptar 87.9% de
  precisión como resultado final.
- [ ] **APG**: hipótesis fuerte heredada de PR (`Oc_Fecha_Entrega <
  HOY`), sin baseline real que la confirme.
- [ ] **AC RECHAZADO, OC SIN AU, PXC**: sin empezar, sin baseline.
- [ ] Confirmar si `RP_CTR_SM1`/`RP_CTR_SM2` son de verdad el origen de
  `ZTRV098` v3, o si tiene su propio SQL en otro lado no explorado (patrón
  C, carpeta `pro/Z/`, ver [Reportes nativos](../../schema/reportes-nativos.md)).

## Fuente

Trabajo local en `notificacion-solicitud-material/` (sesión 2026-08-13
continuación: máquina `ealcocer`, path
`~/proyectos/notificacion-solicitud-material/`; sesión original: máquina
`esteban`, path `~/trivasa-bi-dev/proyectos-bi/notificacion-solicitud-material/`
— confirmar cuál aplica antes de reusar scripts viejos tal cual, las
rutas de conexión a la BD difieren entre ambas). No promovido a este
repo: baselines exportados (`.xlsx`), scripts intermedios de
exploración puntual sin guardar individualmente.
