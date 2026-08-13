# Proceso: solicitud de material → compra → entrega

> Cómo funciona de verdad el proceso, con evidencia de datos. Es una **personalización de Trivasa** (`ZTRV_*`), no existe en el ERP estándar.
>
> Exploración 2026-07-31, corregida y ampliada 2026-08-10 y 2026-08-13.

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

### El flujo NO es monótono — existe ciclo de retrabajo

El catálogo de `Pad_Estado` de arriba sugiere un flujo lineal (`RE` → `AU` como final feliz, o `RZR`/`RZA`/`RZ` como rechazo final). **En la práctica no es así**: un folio rechazado en revisión puede corregirse y reingresar, generando una secuencia más larga sobre el mismo folio en la misma tabla (`Pad_Documento` repetido con `Pad_Fecha` distintas).

Patrón de retrabajo confirmado (2026-08-13), sobre la traza completa de `ZTRV_Presupuesto_Autorizacion_Documento`:

```
RZR (rechazado en revisión) → RZRE (reenviado tras corrección) → RE (revisado de nuevo) → AU o RZA
```

Secuencias completas observadas (`Pad_Estado` ordenado por `Pad_Fecha`, muestra sobre folios de `Pad_Tabla='ZTRV_SOLICITUD_MATERIAL'`, 15 secuencias distintas en total):

| Secuencia | n folios | % |
|---|---:|---:|
| `RE>AU` | 30,115 | 96.27% |
| `RZR` (solo, sin seguimiento aún) | 412 | 1.32% |
| `RE>RZA` | 365 | 1.17% |
| `AU` (solo, autorización directa sin `RE` previo) | 271 | 0.87% |
| `RE` (solo, sin resolución aún) | 76 | 0.24% |
| `RZR>RZRE>RE>AU` | 15 | 0.05% |
| `RZ` (solo) | 14 | 0.04% |
| `RE>RZA>JU>AU` | 6 | 0.02% |
| `AU>RE>RZA` | 2 | 0.01% |

**Casos que rompen la intuición de "una sola pasada":**

- Un folio puede tener `AU` seguido de `RE`/`RZA` posteriores, **meses después** (ej. autorizado en julio, vuelto a revisar y rechazado en agosto del mismo año) — `AU` no es garantía de estado final estable.
- Un folio puede tener dos ciclos completos de rechazo separados por meses (`RZR` en febrero, otro `RZR` en agosto para el mismo folio).

**Implicación práctica:** al tomar "el último `Pad_Estado`" de un folio (`ROW_NUMBER() ... ORDER BY Pad_Fecha DESC`), ese valor es el más reciente observado **a la fecha de la consulta**, no necesariamente un estado terminal — puede volver a cambiar. No cachear ni asumir estabilidad de este campo sin volver a consultar.

### Folios con autorización sin resolver siguen "activos" en la cabecera

De los folios cuyo último `Pad_Estado` (a fecha de corte 2026-06-30) **no** es `AU` (873 folios: `RZR` 404, `RZA` 358, `RE` 51, `RZ` 14, `RZRE` 1), se cruzó contra `ZTRV_Solicitud_Material.Es_Cve_Estado` de la cabecera:

| `Es_Cve_Estado` (cabecera) | n | % |
|---|---:|---:|
| `AC` (activa) | 508 | 58.19% |
| `CE` (cerrada) | 300 | 34.36% |
| `FN` (finalizada) | 31 | 3.55% |
| `CA` (cancelada) | 22 | 2.52% |
| `AB` (abierta) | 7 | 0.80% |
| `RZ` | 3 | 0.34% |
| `PR` | 2 | 0.23% |

**Hallazgo operativo:** 508 folios (58% de los que nunca resolvieron a `AU`) siguen con la solicitud en estado **`AC` (activa)** en la cabecera — la solicitud sigue "viva" en el sistema mientras su autorización presupuestal está trabada (en revisión o rechazada) sin resolverse. "Activa" en la cabecera no implica que la autorización esté avanzando.

## Estado en el warehouse

Las 7 tablas del dominio están replicadas a Postgres (`raw.ztrv_solicitud_*`, 974,866 filas, reconciliadas al 100 % contra `.207`). Ver [Warehouse](warehouse.md#solicitudes-de-material).

Este dominio es **la excepción a la regla de backfillear desde `TRIVASADB3`**: `.200` es el staging de la app de solicitudes y escribe estas tablas a diario. Ver [Servidores y bases](../arquitectura/servidores-y-bases.md#gotcha-el-backfill-desde-200-puede-perder-datos-en-silencio).

## Reporte nativo equivalente

`RPTRV04` "Pendientes por surtir" — ver [Reportes nativos](reportes-nativos.md).
