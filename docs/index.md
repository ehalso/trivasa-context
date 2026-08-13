# Trivasa BI — Context

Documentación, decisiones y proyectos curados de BI para Trivasa.

Este sitio guarda el **conocimiento transversal**: cómo está construido el ERP, qué contiene su base de datos, dónde están las trampas, y cómo está montado el stack de BI. Lo que se aprendió una vez y no debería volver a descubrirse.

---

## Empezar por aquí

Si es tu primera vez, o vuelves después de un tiempo:

1. **[Servidores y bases](arquitectura/servidores-y-bases.md)** — qué base es cuál. Es el error más caro de cometer: una query contra la base equivocada devuelve resultados plausibles pero falsos.
2. **[Convenciones del esquema](schema/convenciones.md)** — cómo está construido el esquema del ERP.
3. **[Calidad de datos](schema/calidad-de-datos.md)** — los gotchas confirmados, antes de escribir cualquier query de negocio.

---

## Secciones

### [Arquitectura](arquitectura/index.md)

De dónde sale la data, por dónde pasa y dónde termina.

- [Servidores y bases](arquitectura/servidores-y-bases.md) — topología SQL Server, `EMPRESAS_2`, respaldos
- [El ERP: Management Pro](arquitectura/erp-management-pro.md) — el sistema origen y sus tres capas
- [Stack de BI en ctunlinux](arquitectura/stack-bi.md) — servicios, puertos, dlt, dbt, observabilidad
- [Hosting de la wiki](arquitectura/wiki-hosting.md) — cómo se publica este sitio

### [Esquema del ERP](schema/index.md)

Qué hay en la base de datos y cómo usarla.

- [Convenciones](schema/convenciones.md) — prefijos, FKs, patrones, familias de tablas
- [Dominios de negocio](schema/dominios.md) — los 14 dominios y los catálogos núcleo
- [Modelos de datos de `raw`](schema/modelos-raw.md) — diagramas ER de lo que ya está replicado
- [Calidad de datos](schema/calidad-de-datos.md) — gotchas confirmados
- [Inventario](schema/inventario.md) — tipos de movimiento y existencia a una fecha
- [Solicitud de material](schema/solicitud-material.md) — el proceso y su máquina de estados
- [Reportes nativos](schema/reportes-nativos.md) — los 549 reportes del ERP y dónde vive su SQL
- [Warehouse](schema/warehouse.md) — qué está replicado a Postgres y qué falta

### [Decisiones](decisions/index.md)

- [Fuente de datos: TRIVASADB3 vs TRIVASADB](decisions/fuente-de-datos.md)
- [Estrategias de carga: merge vs replace](decisions/merge-vs-replace.md)

### Proyectos

Trabajo curado con su código y estado.

- [Consulta XMLs](proyectos/consulta-xmls/index.md)
- [Layout de gastos](proyectos/layout-gastos/index.md)
- [Consumo interno FIFO](proyectos/consumo-interno-fifo/index.md)
- [varela-bot](proyectos/varela-bot/index.md) — bot de Telegram para avisos y acuses de material listo
- [notificacion-solicitud-material](proyectos/notificacion-solicitud-material/index.md) — reconstrucción vía SQL de las pestañas de "Control de Solicitudes de material v3" (`ZTRV098`)

---

## Los tres hechos que más cuesta ignorar

| | |
|---|---|
| **`Es_Cve_Estado = 'ACTI'` no existe** | Devuelve cero filas siempre. El criterio robusto es excluir cancelados (`!= 'CA'`), no incluir activos. |
| **`TRIVASADB3` no es producción** | Es una copia restaurada. Las cifras oficiales salen de `.207/TRIVASADB`. |
| **Los folios colisionan entre tablas** | `Rc_Folio` y `Oc_Folio` matchean por casualidad en el 41 % de los casos, con 83 % de fechas invertidas. Usar el campo polimórfico `Xx_Tabla`/`Xx_Documento`. |

## Regla de oro

Nunca improvisar nombres de tabla, columna, servicio o convención que no estén confirmados en este sitio o verificados explícitamente en la conversación. Si hace falta un dato que no está documentado, preguntar — no inventar.
