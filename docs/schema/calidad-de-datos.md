# Calidad de datos — gotchas confirmados

> Todo lo de aquí se probó con queries contra la base. **No re-descubrirlo dos veces**: si algo cambia, actualizar este archivo.
>
> Consolidado de exploraciones 2026-07-22 a 2026-08-10.

## Lo que está bien

La **integridad referencial es impecable**. Cero huérfanos en las relaciones críticas verificadas:

| Verificación | Huérfanos |
|---|---:|
| `Venta_Encabezado` sin `Cliente` | 0 |
| `Venta_Encabezado` sin `Sucursal` | 0 |
| `Movimiento` sin `Producto` | 0 |
| `Venta` sin `Venta_Encabezado` | 0 |

PKs declaradas en prácticamente todas las tablas de negocio.

---

## Estados

### `Es_Cve_Estado` NO usa `'ACTI'`

El catálogo `Estado` tiene **66 valores de 2–3 caracteres** y **ninguno es `ACTI`** (verificado: `SELECT COUNT(*) FROM Estado WHERE Es_Cve_Estado='ACTI'` → **0**). Filtrar por `'ACTI'` devuelve **cero filas siempre**.

Valores reales: `AC` ACTIVO · `BA` BAJA · `CA` CANCEL PR. INIC. · `FA` FACTURADO · `AP` APLICADO · `PA` PAGADO · `PD` PENDIENTE · `CE` CERRADO · `AU` AUTORIZADO · `EN` ENVIADO · `AB` ABIERTO · `CO` CONFIRMADO…

### El significado de "activo" cambia por tabla

No hay un filtro universal:

| Tabla | Distribución real |
|---|---|
| `Venta_Encabezado` | `FA` 521,778 · `CA` 32,064 · `AC` 1,092 |
| `Factura_Encabezado` | `AC` 146,744 · `AP` 22,577 · `CA` 5,706 · `PXC` 4 |
| `Cliente` | `AC` 41,884 · `BA` 167 |
| `Producto` | `AC` 14,565 · `BA` **12,794** |
| `Consumo_Interno` | `AC` / `CA` |
| `Gasto_Registro` | el reporte nativo excluye `CA` **y `PXA`** |

**Regla práctica:** el criterio robusto es **excluir cancelados (`!= 'CA'`)**, no incluir activos (`= 'AC'`). Es lo que hacen los modelos de dbt. Siempre validar antes:

```sql
SELECT Es_Cve_Estado, COUNT(*) FROM <tabla> GROUP BY Es_Cve_Estado ORDER BY 2 DESC;
```

### Casi la mitad del catálogo de productos está de baja

12,794 de 27,359 en `BA`. Cualquier conteo de "productos" sin filtrar duplica la cifra real.

---

## Joins que parecen obvios pero son falsos

### ❌ `Requisicion_Compra` ↔ `Orden_Compra` por `(Rc_Folio=Oc_Folio, Rc_ID=Oc_ID)`

`Orden_Compra.Rc_ID` sugiere fuertemente una FK. El join naive matchea 33,238 de 81,336 requisiciones (41 %) — parece razonable. Pero al validar coherencia de fecha (`Oc_Fecha >= Rc_Fecha`), **83 % de los matches tienen la fecha invertida**, en algunos casos por años.

Es **colisión de numeración de folio**: ambas tablas usan el patrón `SS-NNNNNNN` por sucursal y los IDs bajos coinciden por casualidad. **No usar este join.**

Existe un puente *indirecto* validado al 99.9 % vía `ZTRV_Presupuesto_Solicitud_Cambio.Sm_Folio` compartido, pero cubre solo ~41 % de las requisiciones formales y solo desde 2024-03-31.

### ❌ `Compra_Encabezado.Co_Folio = Orden_Compra.Oc_Folio`

Mismo patrón de colisión — 77 % de fechas invertidas.

### ✅ La dirección correcta: `Compra_Encabezado.Co_Documento = Orden_Compra.Oc_Folio`

Con `Co_Tabla='ORDEN_COMPRA'`. Este **sí** es el campo polimórfico diseñado para el enlace. Confirmado: 40,312 `Compra_Encabezado` con `Co_Tabla='ORDEN_COMPRA'`, 95,117 matches (el fan-out es esperado: una OC puede recibirse en partes y tiene múltiples líneas).

---

## Fechas sentinela — no son NULL

- **`ZTRV_Estado_Solicitud.Fecha_Fin = '2000-01-01'`** cuando el tramo sigue abierto. No es `NULL`. Filtrar con `Fecha_Fin > '2001-01-01'` antes de calcular cualquier duración.
- **`ZTRV_Solicitud_Material.Sm_Fecha_Cierre = '2001-01-01'`** para "no cerrado" — **valor distinto** al anterior.

Cada tabla parece tener su propio placeholder de "fecha no aplica". **No asumir que es universal.**

---

## Cursores incrementales

### `Fecha_Ult_Modif` puede existir y estar vacía

`ZTRV_Solicitud_Agenda_Logistica` **tiene** la columna, pero el **96 % de sus filas la trae NULL** (136/142 en `.200`, 164/170 en `.207`). dlt descarta las filas cuyo cursor es NULL, así que el incremental cargaba **6 de 142**.

Que la columna exista no basta:

```sql
SELECT COUNT(*) total, SUM(CASE WHEN Fecha_Ult_Modif IS NULL THEN 1 ELSE 0 END) nulos FROM <tabla>;
```

### `Fecha_Ult_Modif` no siempre cambia después de crear

En `Comprobante_Digital` es **idéntica a `Fecha_Alta`** (muestreo de 20 filas, 2026-07-27): el registro se crea ya con el UUID timbrado y nunca se actualiza. Válido como cursor **para esa tabla**; no asumir que aplica igual a otras.

---

## Duplicados y claves

- **`ZTRV_SOLICITUD_MATERIA_DOCUMENTO`**: sin PK declarada y **31,583 grupos duplicados** sobre `(Sm_Folio, Sm_ID, Smd_Documento)`. No hay clave natural — `merge` no es opción, solo `replace`.
- **`ZTRV_Estado_Solicitud`**: sin PK, 229 grupos duplicados sobre `(Sm_Folio, Estado, Fecha_Inicio)`.
- **`Reorden`**: algunos productos tienen registros duplicados — una fila con talla/color vacíos y otra con `'00'`/`'00'`. Dato sucio del ERP, no error de carga.
- **`Consumo_Interno`**: mismo patrón `'00'`/`'00'` en `Tl_Cve_Talla`/`Cl_Cve_Color`.
- **PKs compuestas y anchas**: `Precio_Minimo` tiene PK de 7 columnas, `Existencia` de 5. Al replicar con `merge`, declararla completa o se generan duplicados.

### `Estado_Activo = 'SI'` no identifica un único estado vigente

En `ZTRV_Estado_Solicitud` hay folios con el mismo `Fecha_Inicio` repetido varias veces, todos con `Estado_Activo='SI'` (un folio observado con 11 filas idénticas). También coexisten estados con secuencia de fecha fuera de orden. Es captura duplicada/administrativa, no multi-estado real.

**Deduplicar por `(Sm_Folio, Estado, Fecha_Inicio, Fecha_Fin)` antes de agregar**, y no usar `Estado_Activo='SI'` como "estado actual" sin tomar el `MAX(Fecha_Inicio)` por folio.

---

## Campos vacíos por cambio de proceso, no por error

`Requisicion_Compra.Rc_Fecha_Autorizacion`/`Rc_Autorizo` y `Orden_Compra.Oc_Fecha_Autorizacion`/`Oc_Autorizo` están **100 % vacíos** (0/81,336 y 0/121,147).

**No es que el dato no se capture:** el proceso se mudó a `ZTRV_Presupuesto_Autorizacion_Documento` a partir de **2024-03-31**. Los campos legacy quedaron muertos porque el proceso que los llenaba fue reemplazado. Ver [Solicitud de material](solicitud-material.md#autorizacion-presupuestal).

De forma análoga, el estado **`AB` (ABIERTO) dejó de usarse después de 2024-11-18**. Al comparar periodos pre/post, tratarlo como cambio de proceso, no como anomalía.

---

## Basura de plantillas capturada como dato real

En `ZTRV_Presupuesto_Autorizacion_Documento` aparece al menos una fila con `Pad_Documento='{FOLIO}'` y `Pad_Operador='{OPERADOR}'` — literal, sin sustituir. Filtrar `Pad_Documento <> '{FOLIO}'` antes de cualquier `JOIN` o agregación.

---

## Campos que no son catálogos cerrados

**`Cuenta_X_Pagar.Cxp_Tabla` tiene ~75,000 valores distintos.** Para nómina el patrón es `GASTO_REGISTRO_NOMINA_CXP:<folio>`, con el folio embebido en el valor. Nunca hacer `GROUP BY Cxp_Tabla` exploratorio sin `TOP N`; filtrar siempre por el valor explícito que interese.

---

## Tablas con nombre casi idéntico

`dbo.Estado_Solicitud` (sin prefijo `ZTRV_`) existe con columnas casi iguales — incluido un typo, `Fecha_Incio` — pero está **vacía**. La tabla viva es **`ZTRV_Estado_Solicitud`** (con `Fecha_Inicio` bien escrito).

Fácil escribir mal el nombre y obtener 0 filas **sin error**. Validar con `COUNT(*)` antes de asumir que una tabla está vacía por diseño.

---

## Otros

- **Empresas fantasma**: `0097`, `0098`, `0099` (`BACKUP *`) tienen 5 sucursales entre las tres y **0 ventas**. Excluirlas.
- **Sucursales marcadas en el nombre**: hay descripciones como `KANTUNILKIN (NO UTILIZAR)` y duplicadas (`0005 FABRICA` en `AC`, `0006 FABRICA` en `BA`). Agrupar por `Sc_Cve_Sucursal`, no por `Sc_Descripcion`.
- **`opc_*` duplican tablas base** — sumarlas junto a las originales duplica cifras.
- **`Requisicion_Documento`** (536 filas) es un agregador administrativo para compras recurrentes de volumen (diésel, uniformes), no parte del camino crítico.
- **Los borrados físicos no dejan rastro**: la auditoría `Audit_Delete_DML` no tiene especificación ligada a `TRIVASADB3`. Las bajas lógicas sí (`Fecha_Baja`, `Es_Cve_Estado`).
