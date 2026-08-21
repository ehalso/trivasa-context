# Calidad de datos — gotchas confirmados

> Todo lo de aquí se probó con queries contra la base. **No re-descubrirlo dos veces**: si algo cambia, actualizar este archivo.
>
> Consolidado de exploraciones 2026-07-22 a 2026-08-18.

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

### El estado de detalle no hereda el de cabecera (`ZTRV_Solicitud_Material_Detalle`)

`ZTRV_Solicitud_Material.Es_Cve_Estado` (cabecera) **no** determina el estado de cada línea. Cada renglón de `ZTRV_Solicitud_Material_Detalle` trae su propio `Es_Cve_Estado`, independiente entre sí y de la cabecera. Ejemplo real, folio `05-0066443` (cabecera en `PR`):

| Línea | Producto | `Es_Cve_Estado` |
|---|---|---|
| 0001 | CANAL U DE 4" | `CE` |
| 0002 | SOLERA DE 3" X 5/16" | `AB` |
| 0003 | CINTA REFLEJANTE 3M | `AC` |

Cualquier pantalla o reporte que muestre "solicitudes en estado X" por pestaña (p. ej. las pestañas AC/AU/AB/PR de `ZTRV098` "Control de Solicitudes de material v3") probablemente filtra por el estado de la **línea**, no solo por el de la cabecera. No asumir que basta con filtrar la cabecera. Ver [Solicitud de material](solicitud-material.md).

**Cuantificado 2026-08-21** con un join real cabecera↔detalle sobre todo el histórico: la divergencia **no es un caso raro, es el patrón dominante**. La combinación más frecuente de todas (129,055 líneas / 69,593 folios) es cabecera `CE` (cerrada) con detalle `AC` (activa) — más frecuente que cabecera=detalle=`CE` (66,370 líneas, la combinación que "coincide"). Por eso `fct_documento_trazabilidad` expone `solicitud_estado_encabezado` y `solicitud_estado_detalle` como dos columnas separadas en vez de una sola — ver [Warehouse](warehouse.md#rediseño-2026-08-21-mismo-día-doble-estado--autorización-por-documento--oc-canceladas).

Para contraste, el mismo tipo de divergencia **no** aplica a `Compra_Encabezado`↔`Compra`: de 150,727 líneas, 150,726 coinciden exactamente con su cabecera — ahí sí es seguro usar solo el estado de cabecera.

---

## Joins que parecen obvios pero son falsos

### ❌ `Requisicion_Compra` ↔ `Orden_Compra` por `(Rc_Folio=Oc_Folio, Rc_ID=Oc_ID)`

`Orden_Compra.Rc_ID` sugiere fuertemente una FK. El join naive matchea 33,238 de 81,336 requisiciones (41 %) — parece razonable. Pero al validar coherencia de fecha (`Oc_Fecha >= Rc_Fecha`), **83 % de los matches tienen la fecha invertida**, en algunos casos por años.

Es **colisión de numeración de folio**: ambas tablas usan el patrón `SS-NNNNNNN` por sucursal y los IDs bajos coinciden por casualidad. **No usar este join.**

Existe un puente *indirecto* validado al 99.9 % vía `ZTRV_Presupuesto_Solicitud_Cambio.Sm_Folio` compartido, pero cubre solo ~41 % de las requisiciones formales y solo desde 2024-03-31.

### ✅ La ruta correcta: patrón polimórfico `_Tabla`/`_Documento`

Exploración 2026-08-13. `Requisicion_Compra` y `Orden_Compra` siguen el **mismo patrón polimórfico** que `ZTRV_Apartado` (más abajo) — no hay que reconstruir el link por coincidencia de folio, ambas tablas ya traen el campo diseñado para eso:

- `Requisicion_Compra.Rc_Tabla`/`Rc_Documento` puede apuntar **directo** a `'ZTRV_Solicitud_Material'` (`Rc_Documento = Sm_Folio`). Confirmado sin fan-out: 0 combinaciones `(Rc_Folio, Pr_Cve_Producto)` con más de un `Rc_Documento` distinto.
- `Orden_Compra.Oc_Tabla`/`Oc_Documento` tiene **dos** rutas hacia la solicitud original:
  - directa: `Oc_Tabla='ZTRV_SOLICITUD_MATERIAL'`, `Oc_Documento=Sm_Folio`.
  - indirecta (cuando la OC nació de una requisición formal): `Oc_Tabla='REQUISICION_COMPRA'`, `Oc_Documento=Rc_Folio` — hay que volver a `Requisicion_Compra` (con `Rc_Tabla='ZTRV_Solicitud_Material'` y mismo `Pr_Cve_Producto`) para llegar al `Sm_Folio`.

```sql
-- ruta directa
FROM Orden_Compra oc
INNER JOIN ZTRV_Solicitud_Material sm
        ON sm.Sm_Folio = oc.Oc_Documento AND oc.Oc_Tabla = 'ZTRV_SOLICITUD_MATERIAL'

-- ruta indirecta (via requisicion)
FROM Orden_Compra oc
INNER JOIN Requisicion_Compra rc
        ON rc.Rc_Folio = oc.Oc_Documento AND oc.Oc_Tabla = 'REQUISICION_COMPRA'
       AND rc.Pr_Cve_Producto = oc.Pr_Cve_Producto AND rc.Rc_Tabla = 'ZTRV_Solicitud_Material'
```

**Catálogo `Es_Cve_Estado` de estas dos tablas** (propio de cada una, no relacionado al de `ZTRV_Solicitud_Material`):

| Tabla | Valor | Significado |
|---|---|---|
| `Requisicion_Compra` | `AC` | activa/pendiente (aún no se generó una OC) |
| `Requisicion_Compra` | `RCT` | ya se convirtió en `Orden_Compra` — mayoritario (13,604) |
| `Requisicion_Compra` | `CA`/`CE` | cancelada/cerrada |
| `Orden_Compra` | `AC` | vigente — **ojo:** no distingue "a tiempo" de "atrasada" (ver más abajo) |
| `Orden_Compra` | `RCT`/`RCP` | recibida total/parcial |
| `Orden_Compra` | `CA` | cancelada |

⚠️ `Orden_Compra.Es_Cve_Estado='AC'` **no equivale a "pendiente de entregar a tiempo"**: hay órdenes `AC` con `Oc_Fecha_Entrega` de hasta 2020, nunca cerradas ni canceladas — deuda de datos, no seguimiento real. Para saber si una orden sigue vigente y a tiempo, filtrar además `Oc_Fecha_Entrega >= HOY`. Detalle completo (con el caso de uso real: pestañas PR/APG de `ZTRV098`) en [Solicitud de material](solicitud-material.md#pestanas-ab-pr-y-apg-de-ztrv098-control-de-solicitudes-de-material-v3).

### ❌ `Compra_Encabezado.Co_Folio = Orden_Compra.Oc_Folio`

Mismo patrón de colisión — 77 % de fechas invertidas.

### ✅ La dirección correcta: `Compra_Encabezado.Co_Documento = Orden_Compra.Oc_Folio`

Con `Co_Tabla='ORDEN_COMPRA'`. Este **sí** es el campo polimórfico diseñado para el enlace. Confirmado: 40,312 `Compra_Encabezado` con `Co_Tabla='ORDEN_COMPRA'`, 95,117 matches (el fan-out es esperado: una OC puede recibirse en partes y tiene múltiples líneas).

### ❌ `ZTRV_Apartado.Ap_Documento` no es `Sm_Folio` cuando `Ap_Tabla='COMPRA'`

`ZTRV_Apartado` (registra apartados de inventario contra una solicitud de material) sigue el mismo patrón polimórfico `Ap_Tabla`/`Ap_Documento` que el resto del ERP — pero **además** trae una columna dedicada `Sm_Folio` que siempre apunta a la solicitud de material original, sin importar qué haya en `Ap_Tabla`. Cuando `Ap_Tabla='COMPRA'`, `Ap_Documento` trae el folio de la **orden de compra**, no el de la solicitud. Confirmado con folio real:

```
Ap_Tabla='COMPRA', Ap_Documento='05-0025529'  (folio de compra)
Sm_Folio='05-0056696'                          (la solicitud real)
```

Un query que una por `Ap_Documento` esperando volver a la solicitud pierde silenciosamente todos los apartados originados desde compra — sin error, solo resultados incompletos. En una validación contra un baseline exportado de pantalla (2026-08-13), este error de join dejó fuera ~37 % de los folios esperados (188 de 510) hasta corregirlo.

### ✅ Usar siempre `Sm_Folio` para volver a la solicitud

```sql
FROM ZTRV_Apartado ap
INNER JOIN ZTRV_Solicitud_Material sm ON sm.Sm_Folio = ap.Sm_Folio   -- correcto
-- NO: ON sm.Sm_Folio = ap.Ap_Documento
```

`ZTRV_Apartado.Es_Cve_Estado` es un campo de estado **propio** de la tabla, no relacionado con el `Es_Cve_Estado` de `ZTRV_Solicitud_Material` ni el de su detalle. Valores observados: `SUR` (surtido, mayoritario), `CA` (cancelado), `CE` (cerrado), `AC` (activo) — para apartados vigentes, filtrar `ap.Es_Cve_Estado = 'AC'`. Columnas relevantes adicionales: `Ap_Cantidad_Control_1` (cantidad apartada), `Ap_Consumido_Control_1` (cantidad ya consumida) — en la muestra explorada, para folios con `Es_Cve_Estado='AC'`, `Ap_Consumido_Control_1` siempre fue 0 (no confirmado que sea invariante).

### ❌ `Poliza_Detalle.Pd_Referencia = Gr_Folio` sin aislar la póliza real en `CONSUMO_INTERNO`

Exploración 2026-08-18 ([layout-gastos](../proyectos/layout-gastos/index.md)). `Poliza_Detalle.Pd_Referencia` es el único campo que liga una línea de póliza de vuelta a `Gasto_Registro`, pero es ambiguo de dos formas distintas:

1. **Colisiona entre años**: es solo el número de folio, sin año ni sucursal — 3,179 referencias distintas colisionan entre 2020-2026 en toda la tabla. Por eso nunca se hace `GROUP BY Pd_Referencia` global sin pasar antes por `Poliza_Control` (`Pc_Documento = gr.Gr_Folio`) fila por fila.
2. **`CONSUMO_INTERNO` genera DOS pólizas paralelas por folio**, bajo el mismo `Pc_Documento`, cada una con su propia línea `Pd_Referencia = Gr_Folio`:
   - movimiento de inventario — cuenta `10500.012.003` ("Salida Por Consumo Interno"), raíz de grupo contable `H` (Cuentas de Orden/memo).
   - reconocimiento de gasto real — cuenta variable (ej. `6200.001.003.001` "Combustible", o `2120.010.xxx.002` "Gastos A Cuenta De Costo Estandar"), raíz `F` (Gastos) o sin grupo con esa descripción.

Un join que suma el Cargo de ambas líneas (`SUM(Pd_Importe) WHERE Pd_Tipo=1 AND Pd_Referencia=Gr_Folio`, sin más filtro) da un Cargo total ≈ **2x** el importe nativo del folio, con Abono siempre en 0 — no es partida doble normal, es la duplicación de las dos pólizas. Confirmado con folio real:

```
folio 05-0174493, importe nativo $179.47
  Pl_Folio 0000472906 -- Cargo 6200.001.003.001 "Combustible" $179.47        <- gasto real
  Pl_Folio 0000472693 -- Cargo 10500.012.003 "Salida Por Consumo Interno" $179.47  <- inventario, memo
```

### ✅ Aislar la póliza de gasto real (dos formas, mismo resultado exacto)

**Por cuenta contable** (mismo filtro que ya usaba el caso especial 3 de la conciliación Cargo/Abono para Abono en otros orígenes, aplicado aquí también a Cargo):

```sql
SUM(CASE WHEN pd.Pd_Tipo = 1 AND (
        ga.raiz = 'F'
     OR (ga.raiz IS NULL AND LEFT(pd.Cc_Cve_Cuenta_Contable, 1) = '6')
     OR (ga.raiz IS NULL AND LOWER(cc.Cc_Descripcion) LIKE '%gastos a cuenta de costo estandar%')
    ) THEN pd.Pd_Importe ELSE 0 END)
```

**Por `Poliza.Pl_Comentario`** (validado antes en el proyecto `consumo_interno_trazabilidad` para el mismo problema — más robusto, no depende de adivinar por código de cuenta):

```sql
AND pd.Pd_Tipo = 1
AND UPPER(pl.Pl_Comentario) LIKE '%CONSUMO INT%'
AND UPPER(pl.Pl_Comentario) NOT LIKE 'CUENTAS DE ORDEN%'
AND UPPER(pl.Pl_Comentario) NOT LIKE 'CTS ORDEN%'
AND UPPER(pl.Pl_Comentario) NOT LIKE 'CUENTA ORDEN%'
```

Ambos filtros dan el **mismo total exacto** ($6,388,627.47, enero 2026) — confirman que identifican el mismo conjunto de líneas por caminos distintos. Resultado: 99.12% de conciliación (2,944/2,970 folios, enero 2026); los 26 folios restantes no tienen ninguna póliza de gasto real (solo la de inventario) — hueco de datos real, no de filtro. Detalle completo en [layout-gastos](../proyectos/layout-gastos/index.md#consumo_interno--antes-excluido-ahora-conciliado-2026-08-18).

---

## Personalizaciones `ZTRV_Orden_Compra_*` sin uso real (o de otro propósito)

Existen tres tablas personalizadas con nombre que sugiere ser catálogo/detalle de Orden de Compra. **Ninguna es la fuente correcta** para consultas de negocio sobre OC — esa sigue siendo `Orden_Compra` (sin prefijo, del ERP estándar), que **ya es tabla a nivel línea** (trae `Pr_Cve_Producto` como columna propia, confirmado vía el `.asp` nativo de `RPCO001`) — no hace falta ni existe un `Orden_Compra_Detalle` separado.

| Tabla | Filas (`.207`) | Qué es en realidad |
|---|---:|---|
| `ZTRV_Orden_Compra_Requisicion` | **0** | Vacía. Aunque tiene columnas que sugieren ser el puente correcto `Orden_Compra ↔ Requisicion_Compra` (`Oc_Folio`, `Rc_Folio`, `Rc_Id`), no tiene ninguna fila cargada. |
| `ZTRV_Orden_Compra_Requisicion_Ceco` | **0** | Vacía también. |
| `ZTRV_Orden_Compra_Ceco` | 20,502 | **Sí tiene datos**, pero es reparto por centro de costo a nivel línea (`Oc_Folio`, `Oc_Id`, `Cc_Cve_Centro_Costo`, `Ocrc_Importe`, `Ocrc_Porcentaje`). **No tiene columna de fecha propia** — para filtrar por periodo hay que unir contra `Orden_Compra.Oc_Fecha`. Fan-out esperado: múltiples filas por folio (una por línea × centro de costo). |

Fácil confundirlas con el puente falso `Rc_ID` de `Orden_Compra` (ver [Joins que parecen obvios pero son falsos](#joins-que-parecen-obvios-pero-son-falsos)) y asumir que alguna resuelve el enlace — validar con `COUNT(*)` antes de usarlas.

### Filtro validado para "Órdenes de Compra activas"

Confirmado por reconciliación contra el reporte nativo `RPCO001` (vía Metabase): 310 folios vs 309 esperados, diferencia de 1 atribuible a timing del corte ("hasta hoy").

```sql
SELECT COUNT(DISTINCT Oc_Folio) AS n
FROM Orden_Compra
WHERE Es_Cve_Estado <> 'CA'
  AND Oc_Fecha >= '20260801'
  AND Oc_Fecha < '20260819';
```

- **`Es_Cve_Estado <> 'CA'`**, no `= 'AC'` — consistente con la regla general de [Estados](#estados), y confirmado específicamente para esta tabla vía la lógica real del `.asp` de `RPCO001`.
- El conteo de negocio es **por folio distinto** (`COUNT(DISTINCT Oc_Folio)`), no por filas crudas — como `Orden_Compra` es a nivel línea, contar filas sobreestima el número de "órdenes".
- No hizo falta filtrar por `Empresa`/`Sucursal`/`Comprador` para reconciliar este número — si una pregunta de negocio distinta lo requiere, no está validado aquí.

`RPCO001` es patrón A ([Reportes nativos](reportes-nativos.md)) — el `.asp` completo trae más columnas y lógica (join contra `Compra` para "entregado vs ordenado", moneda, tipo de cambio) no validadas en esta sesión por venir el archivo truncado al copiarlo. Para replicar el reporte completo, volver a extraer `RPCO001.asp` íntegro y confirmar en particular las condiciones exactas del `LEFT JOIN Compra` (columnas de color/talla no confirmadas contra el esquema real).

---

## Comparar fechas con separadores puede invertir día/mes (`DATEFORMAT`)

Una comparación aparentemente inofensiva contra una columna `datetime`:

```sql
WHERE Oc_Fecha >= '2026-08-01' AND Oc_Fecha < '2026-08-19'
```

puede fallar con un error de conversión, o **peor todavía, puede NO fallar y devolver resultados silenciosamente incorrectos** si el día del mes es ≤ 12.

**Causa raíz:** con `@@LANGUAGE = 'Español'` (default de sesión en `.207/TRIVASADB`, collation `Modern_Spanish_CI_AS`), el `DATEFORMAT` de sesión es **`dmy`** (día-mes-año), no `mdy` — el que casi todos asumen implícitamente al escribir `'YYYY-MM-DD'`. Confirmarlo en cualquier sesión sospechosa:

```sql
SELECT
    @@LANGUAGE AS idioma_sesion,
    @@DATEFIRST AS datefirst,
    (SELECT dateformat FROM sys.syslanguages WHERE langid = @@LANGID) AS dateformat_default_idioma;
```

Con `dmy` activo, un literal como `'2026-08-19'` se interpreta con los segmentos de día y mes potencialmente invertidos:

- **Día > 12** (ej. `'2026-08-19'`, día=19): no existe "mes 19" → error `22007` explícito. Molesto, pero al menos avisa.
- **Día ≤ 12** (ej. `'2026-08-01'`, día=01): el intercambio día/mes **no truena** — ambos números son meses válidos — y la query corre "exitosamente" pero filtrando por la fecha equivocada, **sin ningún error visible**. Este es el caso peligroso.

**Regla:** usar siempre el formato `'YYYYMMDD'` (sin separadores) al comparar contra columnas `datetime`/`date`. Es el único literal de fecha que SQL Server interpreta de forma inequívoca sin importar `DATEFORMAT`/`LANGUAGE` de la sesión — garantía del estándar, no convención de este proyecto.

```sql
-- ❌ Riesgoso: depende del DATEFORMAT de la sesión
WHERE Oc_Fecha >= '2026-08-01' AND Oc_Fecha < '2026-08-19'

-- ✅ Seguro: inequívoco en cualquier sesión
WHERE Oc_Fecha >= '20260801' AND Oc_Fecha < '20260819'
```

Nota sobre herramientas de exploración ad-hoc (Harlequin/hsql): su adaptador ODBC no acepta hooks de "SQL de inicialización", solo el connection string. Se puede forzar `Language=us_english;` en la cadena de conexión (da `DATEFORMAT mdy`, a costa de mensajes de error del servidor en inglés) — se evaluó y **se descartó** a favor de la regla `'YYYYMMDD'` de arriba, más robusta porque no depende de la configuración de la conexión en turno.

**Ámbito confirmado:** solo `.207/TRIVASADB`. No se verificó si `.200`/`.205/TRIVASADB3` tienen el mismo `@@LANGUAGE` de sesión por default — revisar antes de asumir que aplica igual ahí.

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

### `Pad_Tabla` tiene dos variantes de casing para la misma tabla

`ZTRV_Presupuesto_Autorizacion_Documento.Pad_Tabla='ZTRV_Solicitud_Material'` (61,841 filas) y `'ZTRV_SOLICITUD_MATERIAL'` (25 filas) — mismo origen, casing distinto. Filtrar solo por uno de los dos pierde las 25 filas en silencio.

⚠️ **No arreglar con `upper(Pad_Tabla) = '...'`.** Sin estadísticas sobre el resultado de la función, Postgres estimó ~520 filas en vez de ~62,000 (100x de error) y eligió *nested loop* para los joins siguientes — una tabla que debía tardar <1 segundo tardó **más de 4 minutos** (confirmado 2026-08-14 construyendo `int_solicitud_material_autorizacion` en `trivasa-bi-core`). Usar una lista explícita en su lugar:

```sql
WHERE Pad_Tabla IN ('ZTRV_SOLICITUD_MATERIAL', 'ZTRV_Solicitud_Material')
```

---

## Campos que no son catálogos cerrados

**`Cuenta_X_Pagar.Cxp_Tabla` tiene ~75,000 valores distintos.** Para nómina el patrón es `GASTO_REGISTRO_NOMINA_CXP:<folio>`, con el folio embebido en el valor. Nunca hacer `GROUP BY Cxp_Tabla` exploratorio sin `TOP N`; filtrar siempre por el valor explícito que interese.

---

## Tablas con nombre casi idéntico

`dbo.Estado_Solicitud` (sin prefijo `ZTRV_`) existe con columnas casi iguales — incluido un typo, `Fecha_Incio` — pero está **vacía**. La tabla viva es **`ZTRV_Estado_Solicitud`** (con `Fecha_Inicio` bien escrito).

Fácil escribir mal el nombre y obtener 0 filas **sin error**. Validar con `COUNT(*)` antes de asumir que una tabla está vacía por diseño.

---

## "NUMERO PARTE" en la pantalla de Solicitud de material NO es `Pr_Numero_Parte`

Confirmado 2026-08-21, construyendo la tabla de detalle de Solicitud de
material para `fct_documento_trazabilidad`. Hay **tres** campos candidatos
con nombre parecido, y solo uno es el que la pantalla nativa (`ZTRV098`)
realmente muestra bajo la columna `NUMERO PARTE`:

| Campo | Qué es en realidad |
|---|---|
| `Producto.Pr_Cve_Producto` (`producto_id`) | **Es el correcto.** Confirmado contra un folio real de pantalla: `producto_id='0000037010'` = "CINTA 20 MTS FIBRA DE VIDRIO", coincide exacto con el resto de la fila. |
| `Producto.Pr_Clave_Corta` (`producto_clave_corta` en `dim_producto`) | Otro campo real de `Producto`, pero **no** es lo que la pantalla muestra — se asumió que sí en una sesión anterior, quedó mal etiquetado en `_marts.yml` hasta que se corrigió. |
| `ZTRV_Solicitud_Material_Detalle.Pr_Numero_Parte` | Existe en la tabla de detalle (nombre más parecido al de la columna en pantalla), pero casi siempre viene vacío y **tampoco** es lo que se muestra. |

**Lección:** un nombre de columna parecido al de la pantalla no garantiza que sea el campo correcto — verificar siempre contra un folio real exportado de pantalla, no solo por coincidencia de nombre.

---

## Otros

- **`raw.sucursal` (41) y `raw.almacen` (465) SÍ están completos** — verificado 2026-08-21 con query directa contra `.205/TRIVASADB3` (vía SSH a `ctunlinux`): `SELECT COUNT(*) FROM Sucursal` → 41 (exacto) y `SELECT COUNT(*) FROM Almacen` → 464 (vs 465 en `raw`, diferencia de 1 por timing). La nota anterior en [Warehouse](warehouse.md#nota-de-reconciliación) afirmaba un gap de `raw.almacen` contra 928 filas en origen — **ese 928 era un dato incorrecto**, corregido.
- **Empresas fantasma**: `0097`, `0098`, `0099` (`BACKUP *`) tienen 5 sucursales entre las tres y **0 ventas**. Excluirlas.
- **Sucursales marcadas en el nombre**: hay descripciones como `KANTUNILKIN (NO UTILIZAR)` y duplicadas (`0005 FABRICA` en `AC`, `0006 FABRICA` en `BA`). Agrupar por `Sc_Cve_Sucursal`, no por `Sc_Descripcion`.
- **`opc_*` duplican tablas base** — sumarlas junto a las originales duplica cifras.
- **`Requisicion_Documento`** (536 filas) es un agregador administrativo para compras recurrentes de volumen (diésel, uniformes), no parte del camino crítico.
- **Los borrados físicos no dejan rastro**: la auditoría `Audit_Delete_DML` no tiene especificación ligada a `TRIVASADB3`. Las bajas lógicas sí (`Fecha_Baja`, `Es_Cve_Estado`).

---

## No toda Orden_Compra/Requisicion_Compra nace de una solicitud de material

> Confirmado 2026-08-21 con conteos reales sobre `origen_tabla`
> (`Oc_Tabla`/`Rc_Tabla`) contra `raw.orden_compra`/`raw.requisicion_compra`,
> construyendo `fct_documento_trazabilidad` ([Warehouse](warehouse.md#fct_documento_trazabilidad-2026-08-21)).

Es fácil asumir que el flujo de compras siempre arranca en una solicitud
de material (`Solicitud de material → Requisición → Orden de compra`, ver
[Solicitud de material](solicitud-material.md)) y que basta con seguir el
patrón polimórfico hacia atrás para siempre llegar a un `Sm_Folio`. **No
es así**: la mayoría de las órdenes de compra y requisiciones del ERP no
pasan por ese flujo en absoluto.

Distribución real de `origen_tabla`:

| Tabla | `origen_tabla` | n | Qué es |
|---|---|---:|---|
| `Orden_Compra` | `REQUISICION_COMPRA` | 42,271 | viene de una requisición formal |
| `Orden_Compra` | *(vacío)* | 18,021 | sin origen registrado |
| `Orden_Compra` | `REQUISICION_DOCUMENTO` | 4,097 | agregador de compras recurrentes de volumen, ver [Otros](#otros) |
| `Orden_Compra` | `ZTRV_SOLICITUD_MATERIAL` | 861 | ruta directa desde la solicitud |
| `Requisicion_Compra` | *(vacío)* | 53,224 | sin origen registrado — la mayoría |
| `Requisicion_Compra` | `ZTRV_Solicitud_Material` | 19,526 | viene de una solicitud de material |
| `Requisicion_Compra` | `Resurtido` | 7,579 | resurtido automático |
| `Requisicion_Compra` | `RESURTIDO` | 2,347 | mismo resurtido automático, casing distinto — mismo gotcha de casing duplicado ya documentado para `Pad_Tabla` ([Basura de plantillas](#basura-de-plantillas-capturada-como-dato-real)) |
| `Requisicion_Compra` | `ORDEN_SERVICIO` | 745 | viene de una orden de servicio, no de compras |

**Implicación práctica:** de las 42,271 líneas de OC que sí vienen de una
requisición, solo 19,526 de esas requisiciones trazan a su vez a
`ZTRV_Solicitud_Material` — el resto queda sin solicitud de origen
resoluble. Un modelo que intente "subir" desde cualquier OC/RC hasta una
solicitud de material va a dejar `solicitud_folio` en `NULL` para la
mayoría de las filas (~44% de las líneas de OC, ~86% de las de RC en
`fct_documento_trazabilidad`) — **es dato real, no un hueco de join**. No
asumir que un `solicitud_folio` vacío en ese contexto es un error de
código.
