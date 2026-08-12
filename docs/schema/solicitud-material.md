# Proceso: solicitud de material → compra → entrega

> Cómo funciona de verdad el proceso, con evidencia de datos. Es una **personalización de Trivasa** (`ZTRV_*`), no existe en el ERP estándar.
>
> Exploración 2026-07-31, corregida y ampliada 2026-08-10.

## Resumen en una línea

El proceso tiene **dos ramas**: 99.97 % de las solicitudes se surten directo de almacén (vía `Movimiento`, sin tocar compras) y solo ~16 % generan una `Requisicion_Compra` formal — de esas, una fracción menor llega a `Orden_Compra` → `Compra` → `Cuenta_X_Pagar`.

## Las dos ramas

```
Solicitud de Material (Sm_Folio)
        │
        ├── 99.97% ──► hay existencia ──► Movimiento (salida de almacén)  [FIN, ciclo corto]
        │
        └── una fracción ──► NO hay existencia
                 │
                 ▼
         Requisicion_Compra (~16% de todas las solicitudes)
                 │
                 ▼
         Orden_Compra ──► Compra_Encabezado/Compra ──► Cuenta_X_Pagar ──► Pago_CXP
```

**La implicación para cualquier modelo:** la inmensa mayoría de "solicitudes de material" no tocan compras. El ciclo largo con aprobación presupuestal es la minoría, y dentro de esa minoría el tramo Requisición→OC→Compra es el que más ruido de datos tiene (ver [Calidad de datos](calidad-de-datos.md#joins-que-parecen-obvios-pero-son-falsos)).

## Máquina de estados: `ZTRV_Estado_Solicitud`

Es la **única tabla que registra tramos de tiempo por estado**, con `Fecha_Inicio`/`Fecha_Fin`. Por eso es la pieza que permite medir tiempo de ciclo y cuellos de botella por etapa.

| Estado | Descripción | Folios que lo visitan |
|---|---|---:|
| `AC` | ACTIVO | 113,681 |
| `CE` | CERRADO | 95,840 |
| `AB` | ABIERTO | 59,782 |
| `PR` | PROGRAMADO | 21,395 |
| `FN` | FINALIZADO | 18,403 |

Secuencias más frecuentes: `AC>CE` (38,623) · `AC>AB>CE` (18,291) · `AB>CE>AC` (9,776) · `AC>PR>CE` (6,103) · `AC` sin cerrar (4,380).

**93 % de las solicitudes pasan por 2–4 estados.** Los casos de 6+ (hasta 19) son outliers de reproceso administrativo, no proceso normal.

### Tres advertencias sobre esta tabla

1. **`AB` dejó de usarse después de 2024-11-18** — cambio de proceso, no anomalía.
2. **`Fecha_Fin = '2000-01-01'` es sentinela de "abierto"**, no NULL. Filtrar antes de restar fechas.
3. **Hay duplicados de captura.** Deduplicar por `(Sm_Folio, Estado, Fecha_Inicio, Fecha_Fin)` y no usar `Estado_Activo='SI'` como estado vigente sin tomar `MAX(Fecha_Inicio)`.

## Autorización presupuestal

> Corrige una conclusión previa: se creía que el sistema *"no captura consistentemente quién aprobó el presupuesto y cuándo"*. **Es incorrecto** — sí se captura, en tablas que no se habían inventariado.

### `ZTRV_Presupuesto_Autorizacion_Documento` (101,348 filas)

Bitácora polimórfica, un renglón por cada paso de revisión/autorización:

| Columna | Rol |
|---|---|
| `Pad_Operador` | quién hizo la acción |
| `Pad_Tabla` | `ZTRV_SOLICITUD_MATERIAL` / `ORDEN_COMPRA` / `Requisicion_Compra` / `ZTRV_Presupuesto_Cambio` / `ZTRV_GASTO_SOLICITUD` |
| `Pad_Documento` | el folio (`Sm_Folio`/`Oc_Folio`/`Rc_Folio`) |
| `Pad_Estado` | código de paso |
| `Pad_Fecha` | **la fecha de autorización** |

**Arranca 2024-03-31** y cubre **98.7 %** de las solicitudes creadas desde entonces (30,489 de 30,886). Un folio tiene como máximo 1 fila `AU` — tabla limpia, sin los duplicados de `ZTRV_Estado_Solicitud`.

Joins validados por coherencia de fecha:

| `Pad_Tabla` | filas | % coherente |
|---|---:|---:|
| `ZTRV_SOLICITUD_MATERIAL` → `Sm_Folio` | 60,272 | 100 % |
| `ORDEN_COMPRA` → `Oc_Folio` | 44,893 | 99.8 % |
| `Requisicion_Compra` → `Rc_Folio` (fan-out por líneas) | 18,144 | 99.99 % |

#### Catálogo `Pad_Estado`

| Código | Significado | n |
|---|---|---:|
| `AU` | Autorizado (paso final positivo) | 52,182 |
| `RE` | Revisado (primer paso) | 39,270 |
| `TE` | Terminado (solo en `ORDEN_COMPRA`) | 8,589 |
| `RZR` | Rechazado en revisión | 760 |
| `RZA` | Rechazado en autorización | 380 |
| `RZ` | Rechazado (genérico) | 141 |
| `RZRE` | Rechazo re-enviado tras modificación | 18 |
| `JU` / `EN` | outliers, casi no se usan | 8 |

**Mediana de ~1.5 min** para autorizar una solicitud ya revisada.

⚠️ Filtrar `Pad_Documento <> '{FOLIO}'` — hay filas con el placeholder de plantilla sin sustituir.

## Estado en el warehouse

Las 7 tablas del dominio están replicadas a Postgres (`raw.ztrv_solicitud_*`, 974,866 filas, reconciliadas al 100 % contra `.207`). Ver [Warehouse](warehouse.md#solicitudes-de-material).

Este dominio es **la excepción a la regla de backfillear desde `TRIVASADB3`**: `.200` es el staging de la app de solicitudes y escribe estas tablas a diario. Ver [Servidores y bases](../arquitectura/servidores-y-bases.md#gotcha-el-backfill-desde-200-puede-perder-datos-en-silencio).

## Reporte nativo equivalente

`RPTRV04` "Pendientes por surtir" — ver [Reportes nativos](reportes-nativos.md).
