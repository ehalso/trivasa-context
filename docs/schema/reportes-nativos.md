# Reportes nativos del ERP — dónde vive cada consulta

> Los **549 reportes** accesibles desde el menú de Management Pro son la **definición operativa de las métricas de Trivasa**: lo que el negocio ya considera "el número correcto". Antes de escribir un modelo de dbt para *ventas netas* o *antigüedad de saldos*, conviene leer cómo lo calcula el reporte que la gente usa hoy.
>
> Verificado 2026-08-10.

## El código de transacción

El catálogo maestro es **`EMPRESAS_2.dbo.Menus`** — la base de *control*, no la de negocio:

| Columna | Contenido |
|---|---|
| `Clave` | **Código de transacción** — `RPAG008`, `RPCA001`, `RPTRV0003` |
| `Texto` | Nombre visible — "Gastos", "Sucursales" |
| `Modulo` | Código de módulo → une con `EMPRESAS_2.Modulos` |
| `URL` | Ruta del ASP o del motor genérico |
| `Estado` | `LI` = liberado |

```sql
SELECT m.Clave, m.Texto, m.Modulo, mo.Descripcion AS ModuloDesc, m.URL
FROM EMPRESAS_2.dbo.Menus m
LEFT JOIN EMPRESAS_2.dbo.Modulos mo ON m.Modulo = mo.Clave
WHERE m.URL <> '' ORDER BY m.Modulo, m.Clave;
```

**El prefijo indica el área**, y coincide con la carpeta en el IIS: `RPCA` catálogos · `RPVN` ventas · `RPCT` contabilidad · `RPCXC`/`RPCXP` cuentas · `RPAG` gastos · `RPSR` servicios · `RPAC` activo fijo · `RPEX` existencias · `RPNO` nómina · `RPCO` compras · `RPMV` movimientos · **`RPTRV` personalizados de Trivasa**.

Distribución: 99 Personalizaciones **177** · 02 Ventas 90 · 04 CXC 78 · 03 Inventarios 41 · 14 Servicios 29 · 01 Compras 18 · 08 RRHH 16 · 05 Contabilidad 15 · 98 Utilerías 15 · 10 Nómina 11 · resto ≤9.

## Los cuatro lugares donde vive el SQL

**No todo el SQL está en archivos, y no todo lo que está en la BD es SQL.**

| Patrón | Reportes | Dónde está el SQL | Cómo se reconoce |
|---|---:|---|---|
| **A — ASP dedicado** | 395 | Embebido en el `.asp` | `URL = /RPAG/RPAG008.asp` |
| **B — Motor genérico** | 7 (+152 indirectos) | **En la BD**, `TRIVASADB3.dbo.Reporte.Rp_SQL` | `URL = /include/rpt/reporte.asp?Consulta=RPCA035` |
| **C — Personalización Z** | 147 | En `pro/Z/<Transaccion>/` | `URL = /Z/?Transaccion=RPTRV0003` |
| **D — Tablero (KPIs)** | 12 tableros / 66 widgets | Metadatos en BD, **SQL en `pro/include/tablero/funciones/`** | `URL = /include/tablero/TAB002.asp?Transaccion=TAB003` |

### Patrón B — SQL almacenado en la base

El motor genérico lee la consulta desde la tabla `Reporte` en tiempo de ejecución (`pro/include/funciones.asp:3131`):

```vbscript
SQL = "SELECT Rp_SQL FROM " & Session("Var").Conexion.DefaultDatabase & "..Reporte WHERE Rp_Cve_Reporte = '" & Id & "'"
```

| Tabla | Filas | Columnas |
|---|---:|---|
| `TRIVASADB3.dbo.Reporte` | **339** | `Rp_Cve_Reporte` (PK), `Rp_Descripcion`, `Rp_SQL` (`ntext`) |
| `TRIVASADB3.dbo.Consultas` | **58** | `Clave` (PK), `Descripcion`, `SQL` (`ntext`), `Modificado`, `Reporte` |

> ⚠️ Al leer estos SQL: muchos empiezan con un **apóstrofo suelto** (`'SELECT ...`) que es parte del valor almacenado, y llevan **placeholders de filtros** que el motor sustituye en runtime — no son ejecutables tal cual.

> ⚠️ **363 de las 397 definiciones no tienen entrada de menú.** Son consultas invocadas dinámicamente o huérfanas. Su nombre es descriptivo, no un código (`CLIENTE`, `BACKORDER_OC`, `CXP_UUID`). **No asumir que una definición en `Reporte` esté en uso.**

`CAST(... AS nvarchar(MAX))` es obligatorio al extraerlas: son `ntext` y los drivers las truncan.

### Patrón D — tableros

12 dashboards (`TAB001` Principal, `TAB003` Ventas, `TAB005` Finanzas, `TAB008` CRM…) con 66 widgets. El reparto es distinto:

| Qué | Dónde |
|---|---|
| Catálogo de tableros | `dbo.Tablero` (12 filas) |
| Catálogo de widgets + **texto descriptivo** | `dbo.Tablero_Funcion` (132; `Tf_Texto` es descripción, **no** SQL) |
| Layout (posición, tamaño, tipo de gráfica) | `dbo.Tablero_Configuracion` |
| Filtros | `dbo.Tablero_Filtro` + `dbo.Filtro` |
| **SQL del widget** | **`pro/include/tablero/funciones/<CVE>.asp`** (111 archivos) |

Estos widgets son **KPIs ya definidos y en uso** — la lista más cercana a "qué mide Trivasa hoy".

## Anatomía de un reporte

Un reporte del patrón A tiene tres capas:

```
pro/RPAG/RPAG008.asp          ← 1. FORMULARIO de filtros
   ▼
pro/RPAG/RPAG008/RPAG08L.asp  ← 2. DISPATCHER: arma sFiltros y decide destino
   ├──► RPAG008_CO.asp / _71 / _99            ← 3a. SQL inline por variante
   └──► /include/rpt/reporte.asp?Consulta=... ← 3b. SQL desde la BD
```

**El dispatcher es donde están las reglas de negocio reales.** Del `RPAG08L.asp`:

```vbscript
if Es_Cve_Estado = "%" Then
    sFiltros = sFiltros & "Gasto_Registro.Es_Cve_Estado NOT IN ('CA','PXA') AND "
```

El reporte de gastos excluye cancelados **y pre-cancelados (`PXA`)** — un matiz que no está documentado en ningún otro lado y que hay que replicar en dbt.

Filtros estándar que casi todo reporte ofrece (buena guía de las dimensiones que el negocio espera): `Zona`, `Empresa`, `Grupo_Sucursal`, `Sucursal`, `Moneda`, `Proveedor`, `Tipo_Gasto`, `Centro_Costo`, `Proyecto`, `Tipo_Proveedor`, `Grupo_Tipo_Gasto`, `Grupo_Centro_Costo`, rango de fechas.

## Qué tablas consumen los reportes

Resueltas **478 de 549 transacciones (87 %)** siguiendo la cadena de cada una — mediana de **9 tablas por reporte**, máximo 84. En conjunto tocan **490 tablas distintas**.

**Solo el 21 % de las referencias apunta a tablas ya extraídas al warehouse.** Las más usadas que aún faltan:

| Tabla | Reportes | Filas |
|---|---:|---:|
| `Cliente` | 217 | 42,051 |
| `Empresa` | 156 | 7 |
| `Ruta` | 134 | 2,433 |
| `Zona` | 119 | 6 |
| `Estado` | 109 | 66 |
| `Vendedor` | 107 | 260 |
| `Linea` | 103 | 253 |
| `Grupo_Comercial` | 91 | 6 |
| `Marca` | 90 | 304 |
| `Venta` | 89 | 1,063,843 |
| `Cuenta_X_Cobrar` | 59 | 686,636 |
| `Gasto_Registro_Documento` | 56 | 1,473,453 |
| `Cuenta_X_Pagar` | 50 | 306,110 |
| `Pago_CXC` | 45 | 1,054,554 |

**La lectura para el roadmap:** las dimensiones que faltan son **diminutas y de altísimo uso** — `Empresa` (7 filas), `Zona` (6), `Grupo_Comercial` (6), `Estado` (66), `Vendedor` (260), más `Linea`, `Marca`, `Segmento`, `Color`, `Talla`, `Forma_Pago`, `Impuesto`, `Centro_Costo`, `Comprador`, `Ruta`. **Todas juntas suman menos de 8,000 filas.** Cargarlas con `replace` desbloquea prácticamente cualquier mart.

> Nota metodológica: el parseo es por expresión regular sobre `FROM`/`JOIN`, cruzado contra `sys.tables` para descartar alias y CTEs, excluyendo archivos con sufijo de versión. Sirve para **ordenar prioridades**, no como censo exacto.

## Los reportes como fuente de verdad

Un uso comprobado: para validar el cálculo de *existencia a una fecha*, se replicó literalmente `RPEXF01_10.asp` (el ASP real del reporte "Existencias a una fecha" de MPRO) y se comparó contra un export de MPRO como ground truth. Los reportes nativos son el árbitro cuando hay duda sobre cómo debe calcularse una métrica.
