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

`comprobante_digital` cubre 2012-01-10 en adelante, con 14 valores de `cd_tabla` (`FACTURA`, `TRASLADO`, `GASTO_REGISTRO`, `NOMINA`, `COMPROBANTE_PAGO`, `COMPRA`, `CHEQUE`, `NOTA_CREDITO`, `CUENTA_X_PAGAR`, `COMPRA_INDIRECTO`, `NOTA_CREDITO_PROVEEDOR`, `ANTICIPO_CXP`, `CONSTANCIA_RETENCION`, `CONTABILIDAD_ELECTRONICA`).

## Solicitudes de material

7 tablas, **974,866 filas**, reconciliadas al 100 % contra `.207`. Backfill ~3 min, incremental diario ~1 min.

| Tabla | Filas | Modo | Clave / cursor |
|---|---:|---|---|
| `ztrv_estado_solicitud` | 310,661 | replace | sin PK ni cursor |
| `ztrv_solicitud_material_detalle` | 250,987 | merge incremental | PK `Sm_Folio, Sm_ID` · `Fecha_Ult_Modif` |
| `ztrv_solicitud_materia_documento` | 189,107 | replace | sin PK ni cursor |
| `ztrv_solicitud_material` | 114,459 | merge incremental | PK `Sm_Folio` · `Fecha_Ult_Modif` |
| `ztrv_solicitu_material_producto` | 74,359 | replace | PK ok, sin cursor |
| `ztrv_solicitud_material_ceco` | 35,123 | replace | PK ok, sin cursor |
| `ztrv_solicitud_agenda_logistica` | 170 | replace | cursor 96 % NULL |

Solo 2 de 7 tienen cursor usable; las demás son tablas hijas puras de `Sm_Folio` sin columnas de auditoría. Ver [Calidad de datos](calidad-de-datos.md#cursores-incrementales).

## Marts de dbt

`dim_producto` (14,668) · `fct_compras` (62,762) · `fct_existencias` (1,516,397) · `fct_gastos_cfdi` (12,229) · `fct_ordenes_compra`

> Hay un modelo `fct_movimientos.sql` en el repo **sin tabla materializada** en `analytics_marts` — revisar si falla o si nunca se corrió.

## Fuente SAT (no MPRO)

`raw_sat.cfdi_recibidos` (12,229) — derivado de los XMLs en `//192.168.117.211/SincronizarXml`. Schema separado a propósito: es otra fuente, aunque represente "lo mismo" a nivel negocio.

## Cron actual

> La convención de `trivasa-bi-core` es systemd timers, pero **la migración no está hecha** — esto sigue en el `crontab` de `ealcocer`.

| Hora | Proceso |
|---|---|
| 05:00 | `cargar_cfdi_recibidos.py` → `raw_sat.cfdi_recibidos` |
| 06:00 | `load_comprobante_digital.run_incremental_207()` |
| 06:15 | `load_reorden.py` (reorden + producto + 6 catálogos) |
| 06:30 | `load_compras_inventario.run_incremental_207_all()` |
| 06:45 | `load_movimiento.run_incremental_207()` |
| 06:50 | `load_solicitudes.run_incremental_207_all()` |
| 07:00 | `check_raw_freshness.py` |

> Los diagramas ER de estas tablas y sus relaciones verificadas están en [Modelos de datos de `raw`](modelos-raw.md).

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

### Nota de reconciliación

`raw.almacen` (464) y `raw.sucursal` (41) traen menos filas que `TRIVASADB3` (928 y 82) porque vienen de `.204`/`.207`, no de la copia. Conviene reconciliarlas contra `.207` antes de usarlas como dimensión.
