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

## 2026-08-13/14 — tablas raw subidas al warehouse

Las 3 tablas usadas en la reconciliación de AB/PR/AU (`ZTRV_Apartado`,
`ZTRV_Presupuesto_Autorizacion_Documento`, `Requisicion_Compra`) ya están
en `raw.*` de Postgres, 100% reconciliadas contra `.207` en el momento de
la carga (30,518 / 104,064 / 83,146 filas). Backfill inicial contra
`TRIVASADB3` (que se descubrió cambió de IP `.200`→`.205` en esta misma
sesión) + sync incremental contra `.207`. Las dos tablas de solicitudes
ya quedaron enganchadas al cron existente de `load_solicitudes.run_incremental_207_all()`
(06:50) y `requisicion_compra` al de `load_compras_inventario.run_incremental_207_all()`
(06:30) — no hizo falta tocar la programación. Detalle completo,
incluyendo el hallazgo de la IP y el pre-flight de seguridad del backfill,
en [Warehouse](../../schema/warehouse.md#solicitudes-de-material) y
[Servidores y bases](../../arquitectura/servidores-y-bases.md#2026-08-13-trivasadb3-cambio-de-ip-200-205).
Código en `trivasa-bi-core` (`load_solicitudes.py`, `load_compras_inventario.py`,
`connections/connection_205_trivasadb3.py`).

## 2026-08-14 — marts de dbt y tablero de Lightdash

Construidos `fct_solicitud_material_pipeline` (grano línea, 250,992
filas) y `fct_solicitud_material_autorizacion` (grano folio, 31,294
filas) en `trivasa-bi-core` — capa completa staging→intermediate→marts
sobre las tablas raw subidas el día anterior. Publicado el dashboard
[Solicitudes de material · Backlog vivo](https://dash.frento.com.mx/projects/df98464b-9806-49f2-b5cb-2f99d47905ad/dashboards/6655b5bf-cfce-46de-97b1-07e87eeb4e48/view)
(8 charts + 1 dashboard, como contenido-como-código en
`lightdash/charts/`/`lightdash/dashboards/`). Hallazgos de negocio (no
metodología) en [hallazgos-de-negocio.md](hallazgos-de-negocio.md).

Gotcha nuevo encontrado en el camino: `Pad_Tabla` tiene dos variantes de
casing (`ZTRV_SOLICITUD_MATERIAL` / `ZTRV_Solicitud_Material`) y
`upper()` en el filtro arruina la estimación de cardinalidad de Postgres
(una tabla de <1s se volvió >4 min) — documentado en
`docs/schema/calidad-de-datos.md` y `docs/schema/warehouse.md`.

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
