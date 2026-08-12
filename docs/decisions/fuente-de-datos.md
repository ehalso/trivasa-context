# Decisión: qué base usar como fuente

**Fecha:** 2026-07-22 · **Ampliada:** 2026-08-10 · **Estado:** Confirmada

## Contexto

Explorando `Consumo_Interno`, un query filtrado a enero 2026 regresó casi vacío usando la conexión por defecto, que apuntaba a `192.168.117.200/TRIVASADB`.

## Hallazgo

`192.168.117.200/TRIVASADB` es una **copia desactualizada**. `192.168.117.200/TRIVASADB3` (misma IP, otra base) sí tiene datos vivos.

La ampliación de 2026-08-10 completó el mapa: **`TRIVASADB3` tampoco es producción.** Es una copia restaurada (última: 2026-07-23). Producción es `192.168.117.207/TRIVASADB`, que mueve ~1,900 movimientos/día contra ~30 de `TRIVASADB3`.

## Decisión

| Uso | Base |
|---|---|
| Explorar, perfilar esquema, backfill histórico | `.200/TRIVASADB3` |
| Cifras oficiales, incrementales diarios, cualquier número que vaya a un reporte | `.207/TRIVASADB` |

Conexión **default** en `trivasa-bi-core/connections/`: `.200/TRIVASADB3`. No cambiar a `.207` salvo pedido explícito.

`.200/TRIVASADB` (sin el 3) **nunca se usa**.

## Consecuencia no obvia

`TRIVASADB3` **recibe escrituras propias**: la app .NET `Autenticacion` la usa como staging del módulo de solicitudes de material. Eso rompe el patrón "backfill desde `.200`" para esas tablas, porque el cursor incremental queda en "ahora" y la primera corrida contra `.207` se salta la historia intermedia **sin error visible**.

Antes de backfillear desde `.200`, comprobar siempre:

```sql
SELECT MAX(Fecha_Ult_Modif) FROM <tabla>;   -- en .200/TRIVASADB3
```

Si devuelve una fecha reciente en vez de la del respaldo, `.200` no sirve como origen para esa tabla.

Detalle en [Servidores y bases](../arquitectura/servidores-y-bases.md).
