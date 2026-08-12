# Convenciones del esquema del ERP

> Cómo está construido el esquema de Management Pro. Saber esto ahorra la mitad de la exploración de cualquier tabla nueva.
>
> Verificado 2026-08-10 sobre `TRIVASADB3` (1,454 tablas, 1,140 FKs declaradas).

## Prefijo de dos letras por tabla

Cada columna lleva el prefijo de su tabla:

| Prefijo | Tabla |
|---|---|
| `Vn_` | Venta |
| `Fc_` | Factura |
| `Rm_` | Remisión |
| `Pd_` | Pedido |
| `Mv_` | Movimiento |
| `Cl_` | Cliente |
| `Pr_` | Producto |
| `Pv_` | Proveedor |
| `Sc_` | Sucursal |
| `Al_` | Almacén |
| `Em_` | Empresa |
| `Es_` | Estado |
| `Sm_` | Solicitud de Material |
| `Oc_` | Orden de Compra |
| `Rc_` | Requisición de Compra |
| `Co_` | Compra |
| `Gr_` | Gasto Registro |

## Llaves foráneas

`Xx_Cve_Tabla` apunta a `Tabla.Xx_Cve_Tabla` — p. ej. `Cl_Cve_Cliente` → `Cliente`. La convención se cumple de forma consistente en las 1,140 FKs declaradas.

## El patrón cabecera/detalle

Casi todo documento transaccional es un par **`X_Encabezado` (1) → `X` (N partidas)**, unidos por `X_Folio`, con impuestos en tablas satélite (`X_Impuesto`, `X_Total_Impuesto`). Aplica a `Venta`, `Pedido`, `Remision`, `Factura`, `Cotizacion`, `Compra`, `Traspaso`.

## El patrón polimórfico `Xx_Tabla` + `Xx_Documento`

Recurrente en todo el ERP: en vez de una FK por tipo de origen, dos columnas genéricas guardan **de qué tabla viene** y **cuál es el folio**. Lo usan `Comprobante_Digital` (`Cd_Tabla`/`Cd_Documento`), `Compra_Encabezado` (`Co_Tabla`/`Co_Documento`), `Gasto_Registro` (`Gr_Tabla`), `ZTRV_Presupuesto_Autorizacion_Documento` (`Pad_Tabla`/`Pad_Documento`), entre otras.

**Es el enlace correcto y diseñado.** Cuando existe un campo polimórfico, usarlo — no intentar unir por folios directos, que colisionan (ver [Calidad de datos](calidad-de-datos.md#joins-que-parecen-obvios-pero-son-falsos)).

## Columnas de auditoría

Presentes en casi toda tabla. **Excluirlas del análisis de negocio:**

- `Oper_Alta` / `Fecha_Alta`
- `Oper_Ult_Modif` / `Fecha_Ult_Modif`
- `Oper_Baja` / `Fecha_Baja`
- `Es_Cve_Estado`

**`Fecha_Ult_Modif` es el cursor incremental estándar** de todos los pipelines. Dos advertencias en [Calidad de datos](calidad-de-datos.md): puede existir y estar vacía, y no siempre cambia después de la creación.

## Claves como texto con ceros a la izquierda

Casi todas las claves son `nvarchar`: `'0001'`, no `1`. Al comparar contra Postgres o al unir entre sistemas, **cuidar el padding** — es una fuente clásica de joins vacíos.

## Tipos

Montos en `money`, cantidades en `decimal(18,3)`, fechas en `datetime` sin zona horaria (las de negocio vienen truncadas a medianoche).

## Las familias de tablas

Distinguirlas es clave para no perder tiempo:

| Prefijo | Tablas con datos | Qué es |
|---|---:|---|
| *(sin prefijo)* | 541 | Estándar del ERP Management Pro |
| **`ZTRV_`** | **170** | **Personalizaciones hechas para Trivasa** — aquí vive la lógica propia del negocio |
| `ZFB_`, `Zfb_` | 75 | Módulo de facturación electrónica (CFDI) |
| `opc_` | 25 | **Copias/snapshots de optimización** — duplican tablas base (`opc_MOVIMIENTO`, `opc_VENTA`). **No usar como fuente**: sumarlas junto a las tablas base duplica cifras. |
| `ZTVA_`, `ZTIC_`, `ZBG_` | 10 | Personalizaciones menores |

De las 632 tablas vacías, **611 son del ERP estándar y solo 21 son personalizaciones** — es decir, casi todo lo que se personalizó para Trivasa sí se usa.

## Multi-empresa: se llega a la empresa vía `Sucursal`

Las tablas transaccionales (`Venta`, `Movimiento`) **no traen `Em_Cve_Empresa`**. Hay que pasar por `Sucursal`:

```sql
JOIN Sucursal s ON t.Sc_Cve_Sucursal = s.Sc_Cve_Sucursal   -- s.Em_Cve_Empresa
```

| Empresa | Sucursales | Ventas |
|---|---:|---:|
| `0001` TRIVASA | 23 | 507,366 |
| `0002` FACILITADORES DE LA CONSTRUCCIÓN | 11 | 46,174 |
| `0003` FLEXBEEL | 1 | 772 |
| `0004` TRITURADOS DE VALLADOLID | 1 | 622 |
| `0097`/`0098`/`0099` BACKUP * | 5 | **0** |

Las tres `BACKUP *` son cascarones sin movimiento — excluirlas por convención.

## Cómo inventariar el esquema

⚠️ **No unir `sys.partitions` con `sys.allocation_units` en la misma agregación.** `allocation_units` tiene una fila por tipo (`IN_ROW_DATA` / `LOB_DATA` / `ROW_OVERFLOW_DATA`), así que el join **multiplica el conteo de filas** en toda tabla con columnas LOB (`ntext`, `varbinary`, `nvarchar(MAX)`). Afecta a 142 tablas de `TRIVASADB3` — llegó a reportar `Comprobante_Digital` con 1.37 M filas cuando son 684,466.

```sql
SELECT s.name AS esquema, t.name AS tabla,
  (SELECT SUM(p.rows) FROM sys.partitions p
    WHERE p.object_id=t.object_id AND p.index_id IN (0,1)) AS filas,
  CAST((SELECT SUM(a.total_pages)*8.0/1024 FROM sys.partitions p2
        JOIN sys.allocation_units a ON p2.partition_id=a.container_id
        WHERE p2.object_id=t.object_id AND p2.index_id IN (0,1)) AS DECIMAL(12,2)) AS mb,
  t.create_date, t.modify_date
FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id
ORDER BY 3 DESC;
```

Y **`sys.tables.modify_date` es la fecha del último cambio de esquema, no de datos** — no sirve para decidir si una tabla está viva. Para eso, `MAX(Fecha_Ult_Modif)` (lento, full scan) o `sys.dm_db_index_usage_stats.last_user_update` (instantáneo, pero se reinicia con el servicio).
