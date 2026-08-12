# Esquema del ERP

Conocimiento sobre la base de datos de Management Pro: cómo está construida, qué contiene, dónde están las trampas.

## Orden de lectura sugerido

1. **[Convenciones](convenciones.md)** — cómo está construido el esquema. Prefijos, FKs, el patrón cabecera/detalle, el patrón polimórfico, columnas de auditoría, familias de tablas. Saber esto ahorra la mitad de la exploración de cualquier tabla nueva.
2. **[Dominios de negocio](dominios.md)** — qué hay y dónde. Los 14 dominios, los catálogos núcleo ordenados por centralidad, el modelo del núcleo transaccional.
3. **[Calidad de datos](calidad-de-datos.md)** — los gotchas confirmados. **Leer antes de escribir cualquier query de negocio.**

## Por tema

- **[Inventario](inventario.md)** — clasificación de tipos de movimiento y el método validado para calcular existencia a una fecha pasada.
- **[Solicitud de material](solicitud-material.md)** — el proceso completo, su máquina de estados y dónde vive la autorización presupuestal.
- **[Reportes nativos](reportes-nativos.md)** — los 549 reportes del ERP, su código de transacción y dónde vive el SQL de cada uno. Son la definición operativa de las métricas del negocio.
- **[Warehouse](warehouse.md)** — qué está replicado a Postgres, con qué estrategia, y qué falta.

## Las tres cosas que más caro cuesta ignorar

1. **`Es_Cve_Estado = 'ACTI'` no existe.** Devuelve cero filas siempre. El criterio robusto es excluir cancelados (`!= 'CA'`), no incluir activos. Ver [Calidad de datos](calidad-de-datos.md#estados).
2. **`TRIVASADB3` no es producción.** Es una copia restaurada. Las cifras oficiales salen de `.207/TRIVASADB`. Ver [Servidores y bases](../arquitectura/servidores-y-bases.md).
3. **Los folios colisionan entre tablas.** `Requisicion_Compra.Rc_Folio` y `Orden_Compra.Oc_Folio` matchean por casualidad en el 41 % de los casos, con 83 % de fechas invertidas. Usar siempre el campo polimórfico `Xx_Tabla`/`Xx_Documento`. Ver [Calidad de datos](calidad-de-datos.md#joins-que-parecen-obvios-pero-son-falsos).

## Regla de oro

Nunca improvisar nombres de tabla, columna o convención que no estén confirmados aquí o verificados explícitamente en la conversación. Si hace falta un dato que no está documentado, preguntar — no inventar.
