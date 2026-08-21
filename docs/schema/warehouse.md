# Warehouse — qué está replicado y qué falta

> Estado de `trivasa_dw` (PostgreSQL `:5433`): qué tablas del ERP ya viven en Postgres, con qué estrategia se mantienen, y qué falta.
>
> Verificado 2026-08-12.

## Schemas

| Schema | Contenido | Quién lo puebla |
|---|---|---|
| `raw` | Tablas crudas desde SQL Server, 1:1 con la fuente | `trivasa-bi-core/dlt/` |
| `raw_staging` | Staging interno de dlt para escrituras `merge` | dlt (automático, no tocar) |
| `raw_sat` | Datos derivados de XMLs CFDI del SAT — fuente distinta a MPRO | `cargar_cfdi_recibidos.py` |
| `analytics_staging` | Vistas `stg_*` de dbt (marcadas `hidden`) | dbt |
| `analytics_marts` | Tablas `fct_*`/`dim_*` | dbt |
| `monitoring` | Trace de corridas de dlt (duración, filas, éxito/error) | `log_run_metrics.py` |

## Estrategias de carga

| Modo | Cuándo | Riesgo |
|---|---|---|
| `merge` + incremental sobre `Fecha_Ult_Modif` | Tabla grande con PK única y cursor poblado | **Nunca borra en destino**: si en el origen se borran registros, quedan huérfanos para siempre |
| `replace` | Tablas chicas (hasta cientos de miles de filas), sin cursor o sin PK única | Recarga completa cada vez |

La lección que fijó el criterio: `reorden` estaba en `merge` y Postgres acumuló 2,053 filas contra 2,022 en origen — 31 huérfanas. Con `replace` quedó exacto. **Para tablas chicas, `replace` es más simple y más correcto.**

## Catálogos (`replace`)

`familia` (116) · `sub_familia` (297) · `categoria` (19) · `departamento` (37) · `almacen` (464) · `sucursal` (41) · `proveedor` (4,774) · `reorden` (2,022)

## Incrementales (`merge`)

| Tabla | Filas | Fuente | PK | Cursor |
|---|---:|---|---|---|
| `movimiento` | 4,546,520 | `Movimiento` | `(mv_folio, mv_id)` | `Fecha_Ult_Modif` |
| `comprobante_digital` | 690,418 | `Comprobante_Digital` | `(cd_tabla, cd_documento)` | `Fecha_Ult_Modif` |
| `compra` | 150,190 | `Compra` | `(co_folio, co_id)` | `Fecha_Ult_Modif` |
| `orden_compra` | 122,417 | `Orden_Compra` | `(oc_folio, oc_id)` | `Fecha_Ult_Modif` |
| `existencia` | 84,857 | `Existencia` | 5 columnas | `Fecha_Ult_Modif` |
| `compra_encabezado` | 69,297 | `Compra_Encabezado` | `(co_folio)` | `Fecha_Ult_Modif` |
| `producto` | 27,462 | `Producto` | `(pr_cve_producto)` | `Fecha_Ult_Modif` |
| `requisicion_compra` | 83,146 | `Requisicion_Compra` | `(rc_folio, rc_id)` | `Fecha_Ult_Modif` |
| `transferencia` | — (agregado 2026-08-21) | `Transferencia` | `(tr_folio, tr_id)` | `Fecha_Ult_Modif` |

`comprobante_digital` cubre 2012-01-10 en adelante, con 14 valores de `cd_tabla` (`FACTURA`, `TRASLADO`, `GASTO_REGISTRO`, `NOMINA`, `COMPROBANTE_PAGO`, `COMPRA`, `CHEQUE`, `NOTA_CREDITO`, `CUENTA_X_PAGAR`, `COMPRA_INDIRECTO`, `NOTA_CREDITO_PROVEEDOR`, `ANTICIPO_CXP`, `CONSTANCIA_RETENCION`, `CONTABILIDAD_ELECTRONICA`).

## Solicitudes de material

9 tablas, **1,109,448 filas**, reconciliadas al 100 % contra `.207`. Backfill ~3 min, incremental diario ~1 min.

| Tabla | Filas | Modo | Clave / cursor |
|---|---:|---|---|
| `ztrv_estado_solicitud` | 310,661 | replace | sin PK ni cursor |
| `ztrv_solicitud_material_detalle` | 250,987 | merge incremental | PK `Sm_Folio, Sm_ID` · `Fecha_Ult_Modif` |
| `ztrv_solicitud_materia_documento` | 189,107 | replace | sin PK ni cursor |
| `ztrv_presupuesto_autorizacion_documento` | 104,064 | merge incremental | PK `Pad_Tabla, Pad_Documento, Pad_Estado, Pad_Fecha` · `Pad_Fecha` (sin `Fecha_Ult_Modif`) |
| `ztrv_solicitud_material` | 114,459 | merge incremental | PK `Sm_Folio` · `Fecha_Ult_Modif` |
| `ztrv_solicitu_material_producto` | 74,359 | replace | PK ok, sin cursor |
| `ztrv_apartado` | 30,518 | merge incremental | PK `Ap_Folio, Ap_ID` · `Fecha_Ult_Modif` |
| `ztrv_solicitud_material_ceco` | 35,123 | replace | PK ok, sin cursor |
| `ztrv_solicitud_agenda_logistica` | 170 | replace | cursor 96 % NULL |

Solo 4 de 9 tienen cursor usable; las demás son tablas hijas puras de `Sm_Folio` sin columnas de auditoría. Ver [Calidad de datos](calidad-de-datos.md#cursores-incrementales).

**2026-08-13**: se agregaron `ztrv_apartado`, `ztrv_presupuesto_autorizacion_documento`
(en `load_solicitudes.py`) y `requisicion_compra` (arriba, en
`load_compras_inventario.py`) — tablas usadas en la reconciliación de
[notificacion-solicitud-material](../proyectos/notificacion-solicitud-material/index.md).
A diferencia de las 7 tablas originales de este dominio (que se saltan el
backfill desde `TRIVASADB3` por un problema de escritura activa detectado
en su momento — ver `load_solicitudes.py:main()`), estas 3 sí se
backfillearon desde `TRIVASADB3` siguiendo el patrón estándar del runbook:
pre-flight confirmó que la copia actual no tiene esa señal de escritura
activa (`MAX(Fecha_Ult_Modif)`/`MAX(Pad_Fecha)` de las 3 caen en la misma
ventana de ~3h, señal de snapshot restaurado una sola vez).

**Importante — la IP de `TRIVASADB3` cambió de `.200` a `.205`.** Mismo
servidor físico, misma base, solo se movió. Verificado empíricamente
(2026-08-13): `.205` trae `ZTRV_Solicitud_Material` ~1 día más fresco que
`.200` (114,501 filas / `MAX(Fecha_Ult_Modif)` 2026-08-11 vs 113,758 /
2026-08-10) — `.200` quedó como copia congelada, no usar para nada nuevo.
`connections/connection_205_trivasadb3.py` en `trivasa-bi-core` ya
actualizado. **Ojo:** esto es específico a `TRIVASADB3` — se confirmó que
`TRIVASADB` (sin el 3, la base ya marcada como obsoleta en el ADR de
`.200` vs `.200/TRIVASADB3`) tiene el patrón *inverso* en `.205` (copia de
abril, más vieja que la de `.200`), así que `connection.py` (que apunta a
`TRIVASADB` sin el 3) **no se tocó** — sigue en `.200` a propósito.

## Marts de dbt

`dim_producto` (14,668) · `fct_compras` (62,762) · `fct_existencias` (1,516,397) · `fct_gastos_cfdi` (12,229) · `fct_ordenes_compra` · `fct_solicitud_material_pipeline` (250,992, grano línea) · `fct_solicitud_material_autorizacion` (31,294, grano folio) · `fct_transferencia` (143 filas, grano folio — agregado 2026-08-21)

### `fct_transferencia` (2026-08-21)

Mart nuevo para Lightdash, origen: reporte nativo "Transferencias por recibir" (`RPTRF01L`). Detalle de la tabla fuente en [Dominios → Transferencia](dominios.md#transferencia). Fila count re-confirmada en `analytics_marts.fct_transferencia`: **143 filas** (2026-08-21, vía `docker exec postgres-dw psql`).

Pipeline completo:

- `dlt/load_transferencia.py` — archivo dedicado (decisión explícita: no colgarlo de `load_movimiento.py`). Funciones: `transferencia()`, `backfill_205_transferencia()`, `run_incremental_207_transferencia()`. `pipeline_name="trivasa_transferencia"`.
- `dbt/models/staging/stg_transferencia.sql` — view, filtra `tr_tipo='EN' AND es_cve_estado='AC'`, sin joins.
- `dbt/models/intermediate/int_transferencia.sql` — view, `LEFT JOIN` a `sucursal` (x2: origen y destino) + `almacen`.
- `dbt/models/marts/fct_transferencia.sql` — table, agregado por folio: 143 filas desde 207 líneas de detalle.
- `_sources.yml` y `_marts.yml` actualizados.
- Cron: línea agregada a las 06:55 en el crontab de `ealcocer` (ruta ya migrada a `~/ehalso/trivasa-bi-core/dlt`, no la vieja `trivasa-bi-dev` — ver [Cron actual](#cron-actual)).
- Deployado a Lightdash (proyecto `trivasa_dw`), 12/12 explores.

**Pendiente, no resuelto:**
- Resolución de nombre de operador (`EMPRESAS_2.Operadores`) — el mart se queda con la clave `Oper_Alta` por ahora.
- Significado del estado `CE` en `Transferencia`.

> `fct_movimientos` ya está materializado en `analytics_marts` (re-verificado 2026-08-21) — la advertencia anterior sobre que le faltaba tabla ya no aplica.

12 marts materializados en `analytics_marts` a 2026-08-21 (verificado por `information_schema`): `dim_producto`, `fct_compras`, `fct_existencias`, `fct_gastos_cfdi`, `fct_movimientos`, `fct_ordenes_compra`, `fct_requisiciones_compra`, `fct_requisiciones_compra_flujo`, `fct_requisiciones_compra_worklist`, `fct_solicitud_material_autorizacion`, `fct_solicitud_material_pipeline`, `fct_transferencia` — coincide con el "12/12 explores" del deploy de Lightdash de la sesión 2026-08-21.

Los dos marts de solicitudes tienen un dashboard de Lightdash publicado como código en `lightdash/dashboards/solicitudes-de-material-backlog-vivo.yml`:
[Solicitudes de material · Backlog vivo](https://dash.frento.com.mx/projects/df98464b-9806-49f2-b5cb-2f99d47905ad/dashboards/6655b5bf-cfce-46de-97b1-07e87eeb4e48/view).
Lectura de negocio (no metodología) en
[hallazgos-de-negocio.md](../proyectos/notificacion-solicitud-material/hallazgos-de-negocio.md).

⚠️ Gotcha nuevo (2026-08-14) al construir `int_solicitud_material_autorizacion`:
`ZTRV_Presupuesto_Autorizacion_Documento.Pad_Tabla` tiene dos variantes de
casing para la misma tabla (`ZTRV_SOLICITUD_MATERIAL`, 61,841 filas ·
`ZTRV_Solicitud_Material`, 25 filas). Filtrar con `upper(pad_tabla) = ...`
funciona pero **arruina la estimación de cardinalidad de Postgres** (sin
estadísticas sobre la expresión, estimó ~520 filas en vez de ~62k, eligió
nested loop para los joins siguientes, y la tabla tardó **>4 minutos** en
vez de <1 segundo). Usar `pad_tabla IN ('ZTRV_SOLICITUD_MATERIAL', 'ZTRV_Solicitud_Material')`
en su lugar.

## Fuente SAT (no MPRO)

`raw_sat.cfdi_recibidos` (12,229) — derivado de los XMLs en `//192.168.117.211/SincronizarXml`. Schema separado a propósito: es otra fuente, aunque represente "lo mismo" a nivel negocio.

## Cron actual

> La convención de `trivasa-bi-core` es systemd timers, pero **la migración no está hecha** — esto sigue en el `crontab` de `ealcocer`. Decisión explícita (2026-08-21): por ahora se sigue agregando a este mismo `crontab`, incluido el job de `dbt build` de abajo — la migración a systemd timer queda pendiente para el futuro, no bloquea agendar cosas nuevas mientras tanto.

| Hora | Proceso |
|---|---|
| 05:00 | `cargar_cfdi_recibidos.py` → `raw_sat.cfdi_recibidos` |
| 06:00 | `load_comprobante_digital.run_incremental_207()` |
| 06:15 | `load_reorden.py` (reorden + producto + 6 catálogos) |
| 06:30 | `load_compras_inventario.run_incremental_207_all()` (incluye `requisicion_compra` desde 2026-08-13) |
| 06:45 | `load_movimiento.run_incremental_207()` |
| 06:50 | `load_solicitudes.run_incremental_207_all()` (incluye `ztrv_apartado`/`ztrv_presupuesto_autorizacion_documento` desde 2026-08-13) |
| 06:55 | `load_transferencia.run_incremental_207_transferencia()` (agregado 2026-08-21) |
| 06:58 | `dbt build` (`trivasa-bi-core/dbt`, target `prod`) — reconstruye `analytics_staging`/`analytics_marts` a partir del `raw` recién cargado (agregado 2026-08-21) |
| 07:00 | `check_raw_freshness.py` |

### 2026-08-21 — se agregó el job de `dbt build`, no existía ninguno

Hallazgo: `analytics_marts.fct_requisiciones_compra` (mart detrás del dashboard
[Requisiciones de compra · Pipeline](https://dash.frento.com.mx/projects/df98464b-9806-49f2-b5cb-2f99d47905ad))
llevaba desde el **2026-08-18** sin reconstruirse (`MAX(fecha)` de la tabla
tope en 2026-08-13) mientras que `raw.orden_compra`/`raw.requisicion_compra`
sí estaban al día vía dlt. Causa raíz: el `crontab` solo tenía los jobs de
`dlt` (arriba) y `check_raw_freshness.py` (que valida `raw`, no los marts) —
ningún proceso corría `dbt build` después de la carga. Se agregó a las 06:58
(después del último load de dlt a las 06:55, antes del check de las 07:00) y
se corrió una vez manualmente para poner los marts al día
(`fct_requisiciones_compra`: 45,040 → 45,272 filas, `MAX(fecha)` 2026-08-13 →
2026-08-20). Log en `trivasa-bi-core/logs/dbt_build.log`.

> Los diagramas ER de estas tablas y sus relaciones verificadas están en [Modelos de datos de `raw`](modelos-raw.md).

> ⚠️ **Riesgo abierto (reportado 2026-08-21): `dbt run` no está agendado en ningún cron/systemd.** Solo dlt y `check_raw_freshness` corren automático. Todo mart materializado como `table` (incluido `fct_transferencia`) se queda congelado en el warehouse hasta que alguien corra `dbt run` a mano — no es un problema de una tabla en particular, es un hueco del repo completo.

## Qué falta — 800 tablas con datos

La cobertura está sesgada a **compras e inventario**. Prioridades:

| Prioridad | Ausente | Por qué importa |
|---|---|---|
| **Alta — dimensiones** | `Cliente`, `Empresa`, `Zona`, `Vendedor`, `Estado`, `Linea`, `Marca`, `Segmento`, `Centro_Costo`, `Comprador`, `Ruta`, `Forma_Pago`, `Impuesto`, `Color`, `Talla` | **Juntas < 8,000 filas** y aparecen en cientos de reportes. El mejor valor/esfuerzo del backlog. |
| **Alta — Ventas** | `Venta_Encabezado`, `Venta`, `Venta_Total_Impuesto`, `Remision*`, `Pedido*`, `Factura*` | **No hay ni un mart de ventas** |
| **Alta — CXC** | `Cuenta_X_Cobrar`, `Pago_CXC`, `Recibo_Pago` | Sin cobranza ni antigüedad de saldos |
| **Media — Gastos** | `Gasto_Registro*` (3 tablas, 4.05 M filas) | Hoy solo se cubre desde XMLs del SAT, sin el lado ERP |
| **Media — CXP** | `Cuenta_X_Pagar`, `Pago_Cxp_Comprobante` | Cierra el ciclo con compras, ya cargado |
| **Media — Logística** | `Orden_Entrega`, `Entrega_Documento`, `Viaje`, `Complemento_Carta_Porte` | Costo de reparto, cumplimiento |
| **Baja** | `Poliza_Detalle` (14.3 M), `Poliza_Control` (6.1 M) | Alto volumen; solo con caso de uso claro |
| **Baja** | `Pre_Nomina` (4.6 M), `Nomina` (1.8 M) | Datos sensibles — definir acceso antes |
| **Excluir** | `Imagen_Objeto`, `Adjunto`, `ZTRV_Almacen_Digital`, `Comentario` | Binarios: 62 GB sin valor analítico |
| **Excluir** | `opc_*` (25 tablas) | Duplican tablas base |

### Nota de reconciliación — corregida 2026-08-21

La entrada original de esta nota afirmaba `raw.almacen` (465) vs `TRIVASADB3` con 928 filas. **Ese 928 era incorrecto** — verificado por Claude Code vía SSH a `ctunlinux` con `SELECT COUNT(*) FROM Almacen` directo contra `.205/TRIVASADB3`: el conteo real es **464**, prácticamente idéntico a `raw.almacen` (465, diferencia de 1 explicable por timing entre la query y el último incremental). `raw.almacen` **no tiene gap** — ya está reconciliado.

`raw.sucursal` (41) tampoco tiene gap: coincide exacto contra `.205` (`SELECT COUNT(*) FROM Sucursal` → 41).

Ambas cifras confirmadas en la misma sesión de verificación 2026-08-21; no queda gap abierto de este tipo entre `raw.*` y `TRIVASADB3` para estas dos tablas.
