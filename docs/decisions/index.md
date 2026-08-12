# Decisiones

Decisiones con alcance **transversal** — las que cambian cómo se trabaja con los datos en general, no las de un proyecto puntual.

| Decisión | Fecha | Estado |
|---|---|---|
| [Fuente de datos: TRIVASADB3 vs TRIVASADB](fuente-de-datos.md) | 2026-07-22 | Confirmada, ampliada 2026-08-10 |
| [Estrategias de carga: merge vs replace](merge-vs-replace.md) | 2026-07-29 | Confirmada, ampliada 2026-08-10 |

## Dónde están las decisiones de proyecto

Las ADRs específicas de un proyecto viven junto a su código, no aquí. Las que encierran conocimiento reusable ya se promovieron a [`docs/schema/`](../schema/index.md):

| ADR original | Conocimiento promovido a |
|---|---|
| Método existencia a fecha (resta vs suma vs método C) | [Inventario](../schema/inventario.md#existencia-a-una-fecha-pasada) |
| Clasificación de tipos de movimiento | [Inventario](../schema/inventario.md#clasificacion-de-tm_cve_tipo_movimiento) |
| Movimientos + UUID vía FIFO | [Inventario](../schema/inventario.md#trazabilidad-fifo) |
| `uuid_compras` de CSV a Postgres | [Warehouse](../schema/warehouse.md) |
