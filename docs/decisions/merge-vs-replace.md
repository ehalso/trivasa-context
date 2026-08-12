# Decisión: cuándo usar `merge` incremental y cuándo `replace`

**Fecha:** 2026-07-29 · **Ampliada:** 2026-08-10 · **Estado:** Confirmada

## Contexto

Los pipelines de dlt pueden cargar una tabla de dos formas: `merge` con cursor incremental sobre `Fecha_Ult_Modif`, o `replace` (recarga completa). La primera parece siempre mejor por eficiencia, pero tiene un costo que no es obvio.

## El problema con `merge`

**`merge` nunca borra en destino.** Si en el origen se elimina un registro, la fila queda en Postgres para siempre.

Se detectó con `reorden`: Postgres tenía 2,053 filas contra 2,022 en el origen — **31 huérfanas**. Al cambiar a `replace` quedó en 2,022/2,022 exacto.

## Decisión

| Modo | Cuándo |
|---|---|
| `merge` + incremental | Tabla grande, con PK única verificada y cursor poblado |
| `replace` | Tablas chicas (hasta cientos de miles de filas), sin cursor usable, o sin PK única |

Para tablas chicas, **`replace` es más simple y más correcto**. `reorden` (2 k filas) recarga completa en ~18 segundos junto con producto y catálogos.

## Pre-flight obligatorio antes de elegir `merge`

Tres comprobaciones que cuestan un minuto y evitan pérdidas silenciosas. Las tres salieron de fallos reales.

**1. ¿La PK es realmente única en el origen?**

```sql
SELECT COUNT(*) FROM (SELECT <cols_pk> FROM <tabla> GROUP BY <cols_pk> HAVING COUNT(*)>1) x;
```

Debe dar 0. `ZTRV_SOLICITUD_MATERIA_DOCUMENTO` da 31,583 — no tiene clave natural, solo admite `replace`.

**2. ¿La columna cursor está realmente poblada?** Que exista `Fecha_Ult_Modif` no basta: dlt **descarta las filas cuyo cursor es NULL**.

```sql
SELECT COUNT(*) total, SUM(CASE WHEN Fecha_Ult_Modif IS NULL THEN 1 ELSE 0 END) nulos FROM <tabla>;
```

`ZTRV_Solicitud_Agenda_Logistica` tiene la columna pero 96 % de sus filas la traen NULL — el incremental cargaba 6 de 142 filas.

**3. ¿`.200` escribe esa tabla por su cuenta?** Ver [Fuente de datos](fuente-de-datos.md#consecuencia-no-obvia).

## Gotchas del cursor

- **`initial_value` debe ser `datetime.datetime(1900, 1, 1)`**, no el string `"1900-01-01"`. Si la columna es `datetime` en SQL Server, dlt compara `str > datetime` y falla con `IncrementalCursorInvalidCoercion`.
- **Hacer el backfill con `dlt.sources.incremental` ya activo**, para que el cursor quede persistido. Si el backfill se hace con una query a pelo, el estado queda vacío y la primera corrida incremental intenta re-traer la tabla completa. Le pasó a `movimiento` (4.4 M filas, >20 min, proceso muerto).
- **Tablas muy grandes: trocear el backfill por año.** `movimiento` moría sin traceback cargando 4.4 M filas de una (sin memoria, VM de 5.2 GB con swap al límite).
