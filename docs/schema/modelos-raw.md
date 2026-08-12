# Modelos de datos — lo que hay en `raw`

> Modelo conceptual y lógico de las **22 tablas ya replicadas** a `trivasa_dw.raw`. Solo se dibujan relaciones **verificadas**: FKs declaradas en SQL Server, o joins validados con datos reales. Las que son convención sin respaldo del motor van punteadas y anotadas.
>
> Verificado 2026-08-12 contra `information_schema` de Postgres, `sys.foreign_keys` de SQL Server y conteos sobre `raw`.

## Cómo leer estos diagramas

| Notación | Significado |
|---|---|
| Línea continua | **FK declarada** en SQL Server |
| Línea punteada | Relación **real pero no declarada** — validada con datos, se documenta el join |
| `||--o{` | Uno a muchos |
| `}o--||` | Muchos a uno |
| Caja gris "(falta)" | Dimensión que el ERP referencia pero **aún no está en `raw`** |

Nombres en minúsculas porque así los normaliza dlt en Postgres. En el origen son `Pr_Cve_Producto`, aquí `pr_cve_producto`.

---

## Modelo conceptual

El negocio que hoy cubre `raw`, sin detalle de columnas:

```mermaid
flowchart TB
    subgraph ORG["Organización"]
        SUC["Sucursal"] --> ALM["Almacén"]
    end

    subgraph CAT["Catálogo de producto"]
        FAM["Familia"] --> SUB["Subfamilia"]
        CATG["Categoría"]
        DEP["Departamento"]
        PROD["Producto"]
    end

    subgraph ABAST["Abastecimiento"]
        SOL["Solicitud de material"]
        OC["Orden de compra"]
        CMP["Compra"]
        PROV["Proveedor"]
        CFDI["Comprobante digital (CFDI)"]
    end

    subgraph INV["Inventario"]
        MOV["Movimiento"]
        EXI["Existencia"]
        REO["Punto de reorden"]
    end

    FAM --> PROD
    SUB --> PROD
    CATG --> PROD
    DEP --> PROD
    PROV --> PROD

    SOL -->|99.97% se surte de almacén| MOV
    SOL -->|0.03%| OC
    OC --> CMP
    CMP --> MOV
    PROV --> OC
    PROV --> CMP
    CMP -.->|UUID| CFDI

    PROD --> MOV
    PROD --> EXI
    ALM --> MOV
    ALM --> EXI
    ALM --> REO
    MOV -->|acumula| EXI

    style SOL fill:#fff3cd,stroke:#856404
    style MOV fill:#cce5ff,stroke:#004085
```

**La lectura de negocio:** una solicitud de material casi siempre se resuelve contra inventario (genera un `Movimiento` de salida). Solo una fracción mínima escala a orden de compra → compra → entrada de inventario. Ver [Solicitud de material](solicitud-material.md).

---

## Modelo lógico por dominio

### Catálogo de producto

El único bloque completo en `raw`: todas las dimensiones que `producto` referencia y que ya están replicadas.

```mermaid
erDiagram
    familia ||--o{ sub_familia : "fm_cve_familia"
    familia ||--o{ producto : "fm_cve_familia"
    sub_familia ||--o{ producto : "sf_cve_sub_familia"
    categoria ||--o{ producto : "ct_cve_categoria"
    departamento ||--o{ producto : "dp_cve_departamento"
    proveedor ||--o{ producto : "pv_cve_proveedor"

    familia {
        nvarchar fm_cve_familia PK
        nvarchar fm_descripcion
        nvarchar es_cve_estado
    }
    sub_familia {
        nvarchar sf_cve_sub_familia PK
        nvarchar fm_cve_familia FK
        nvarchar sf_descripcion
    }
    categoria {
        nvarchar ct_cve_categoria PK
        nvarchar ct_descripcion
    }
    departamento {
        nvarchar dp_cve_departamento PK
        nvarchar dp_descripcion
    }
    producto {
        nvarchar pr_cve_producto PK
        nvarchar pr_descripcion
        nvarchar ct_cve_categoria FK
        nvarchar dp_cve_departamento FK
        nvarchar fm_cve_familia FK
        nvarchar sf_cve_sub_familia FK
        nvarchar pv_cve_proveedor FK
        nvarchar mr_cve_marca "FK -- marca NO esta en raw"
        nvarchar ln_cve_linea "FK -- linea NO esta en raw"
        nvarchar cm_cve_comprador "FK -- comprador NO esta en raw"
        money pr_costo_promedio
        nvarchar es_cve_estado
    }
    proveedor {
        nvarchar pv_cve_proveedor PK
        nvarchar pv_razon_social
        nvarchar pv_r_f_c
        decimal pv_saldo
    }
```

> ⚠️ **Cuidado con el nombre de la subfamilia.** En SQL Server la columna es `Sf_Cve_SubFamilia` y la tabla `SubFamilia`; dlt las normaliza a `sf_cve_sub_familia` y `sub_familia`. Es el único caso del set donde el nombre cambia de forma no trivial.

### Organización e inventario

```mermaid
erDiagram
    sucursal ||--o{ almacen : "sc_cve_sucursal"
    almacen ||--o{ movimiento : "sc_cve_sucursal + al_cve_almacen"
    almacen ||--o{ existencia : "sc_cve_sucursal + al_cve_almacen"
    almacen ||--o{ reorden : "sc_cve_sucursal + al_cve_almacen"
    producto ||--o{ movimiento : "pr_cve_producto"
    producto ||--o{ existencia : "pr_cve_producto"

    sucursal {
        nvarchar sc_cve_sucursal PK
        nvarchar sc_descripcion
        nvarchar em_cve_empresa "FK -- empresa NO esta en raw"
        nvarchar zn_cve_zona "FK -- zona NO esta en raw"
        nvarchar es_cve_estado
    }
    almacen {
        nvarchar sc_cve_sucursal PK "FK"
        nvarchar al_cve_almacen PK
        nvarchar al_descripcion
    }
    movimiento {
        nvarchar mv_folio PK
        nvarchar mv_id PK
        datetime mv_fecha
        nvarchar mv_tabla "polimorfico -- documento origen"
        nvarchar mv_documento
        nvarchar tm_cve_tipo_movimiento "FK -- tipo_movimiento NO esta en raw"
        nvarchar pr_cve_producto FK
        nvarchar sc_cve_sucursal FK
        nvarchar al_cve_almacen FK
        decimal mv_cantidad_1
        decimal mv_cantidad_control_1
        money mv_costo_importe
        nvarchar es_cve_estado
    }
    existencia {
        nvarchar sc_cve_sucursal PK "FK"
        nvarchar al_cve_almacen PK "FK"
        nvarchar pr_cve_producto PK "FK"
        nvarchar tl_cve_talla PK
        nvarchar cl_cve_color PK
        decimal ex_cantidad_control_1
        money ex_costo_promedio
    }
    reorden {
        nvarchar sc_cve_sucursal PK "FK"
        nvarchar al_cve_almacen PK "FK"
        nvarchar re_tipo PK
        nvarchar re_tipo_valor PK
        decimal re_min_cantidad_control_1
        decimal re_max_cantidad_control_1
    }
```

`existencia` es el **saldo vigente** mantenido por el ERP; `movimiento` es el libro de asientos. No se derivan uno del otro en `raw` — la relación es de acumulación y se resuelve en dbt. El método validado para reconstruir existencia a una fecha pasada está en [Inventario](inventario.md#existencia-a-una-fecha-pasada).

`reorden` no apunta a `producto` con una FK: su clave es `(re_tipo, re_tipo_valor)`, un par genérico que puede referirse a producto, familia u otro nivel según `re_tipo`. **No unir a `producto` sin filtrar por `re_tipo` primero.**

### Compras

```mermaid
erDiagram
    compra_encabezado ||--o{ compra : "co_folio"
    proveedor ||--o{ compra_encabezado : "pv_cve_proveedor"
    proveedor ||--o{ orden_compra : "pv_cve_proveedor"
    proveedor ||--o{ compra : "pv_cve_proveedor"
    almacen ||--o{ compra_encabezado : "sc + al"
    almacen ||--o{ compra : "sc + al"
    sucursal ||--o{ orden_compra : "sc_cve_sucursal"
    producto ||--o{ orden_compra : "pr_cve_producto"
    producto ||--o{ compra : "pr_cve_producto"
    orden_compra |o..o{ compra_encabezado : "co_documento = oc_folio (polimorfico)"
    compra_encabezado |o..o| comprobante_digital : "cd_tabla='COMPRA' (por documento)"

    orden_compra {
        nvarchar oc_folio PK
        nvarchar oc_id PK
        datetime oc_fecha
        datetime oc_fecha_entrega
        nvarchar pv_cve_proveedor FK
        nvarchar pr_cve_producto FK
        nvarchar sc_cve_sucursal FK
        nvarchar rc_id "NO es FK usable a requisicion"
        nvarchar oc_autorizo "100% vacio -- proceso migrado"
        decimal oc_cantidad_1
        money oc_precio_neto_importe
        nvarchar es_cve_estado
    }
    compra_encabezado {
        nvarchar co_folio PK
        datetime co_fecha
        nvarchar co_tabla "polimorfico"
        nvarchar co_documento "polimorfico"
        nvarchar pv_cve_proveedor FK
        nvarchar sc_cve_sucursal FK
        nvarchar al_cve_almacen FK
        money co_precio_neto_importe
        nvarchar es_cve_estado
    }
    compra {
        nvarchar co_folio PK "FK"
        nvarchar co_id PK
        nvarchar pr_cve_producto FK
        decimal co_cantidad_1
        money co_costo_importe
        money co_precio_neto_importe
        nvarchar es_cve_estado
    }
    comprobante_digital {
        nvarchar cd_tabla PK
        nvarchar cd_documento PK
        nvarchar cd_timbre_uuid
        datetime fecha_alta
    }
```

Dos advertencias que este diagrama codifica:

- **`orden_compra.rc_id` NO sirve para unir con requisición.** Parece una FK y no lo es: el join naive tiene 83 % de fechas invertidas por colisión de folios. Ver [Calidad de datos](calidad-de-datos.md#joins-que-parecen-obvios-pero-son-falsos).
- **El enlace OC→Compra es polimórfico**, no por folio directo. Validado en `raw`: 95,913 filas de `compra_encabezado` con `co_tabla='ORDEN_COMPRA'`, que enlazan a 22,952 órdenes distintas.

### Solicitud de material

El bloque `ZTRV_*` es una personalización de Trivasa. **Casi no tiene FKs declaradas** — solo `ceco → solicitud_material`. Todo lo demás es convención sobre `sm_folio`, validada aquí con datos.

```mermaid
erDiagram
    ztrv_solicitud_material ||--o{ ztrv_solicitud_material_detalle : "sm_folio (sin FK)"
    ztrv_solicitud_material ||--o{ ztrv_estado_solicitud : "sm_folio (sin FK)"
    ztrv_solicitud_material ||--o{ ztrv_solicitud_material_ceco : "sm_folio (FK declarada)"
    ztrv_solicitud_material ||--o{ ztrv_solicitu_material_producto : "sm_folio (sin FK)"
    ztrv_solicitud_material ||--o{ ztrv_solicitud_materia_documento : "sm_folio (sin FK)"
    ztrv_solicitud_materia_documento }o..o{ movimiento : "smd_documento = mv_folio"

    ztrv_solicitud_material {
        nvarchar sm_folio PK
        datetime sm_fecha
        datetime sm_fecha_entrega
        datetime sm_fecha_cierre "sentinela 2001-01-01 = no cerrado"
        nvarchar sc_cve_sucursal
        nvarchar al_cve_almacen
        nvarchar cm_cve_comprador
        nvarchar pv_cve_proveedor
        nvarchar sm_revisor
        nvarchar sm_autorizador
        nvarchar sm_prioridad
        nvarchar es_cve_estado
    }
    ztrv_solicitud_material_detalle {
        nvarchar sm_folio PK
        nvarchar sm_id PK
        nvarchar pr_cve_producto
        nvarchar sm_concepto
        decimal sm_cantidad_1
        money sm_costo_importe
        decimal sm_monto_ppto
        nvarchar tg_cve_tipo_gasto
    }
    ztrv_estado_solicitud {
        nvarchar sm_folio "sin PK"
        nvarchar estado
        datetime fecha_inicio
        datetime fecha_fin "sentinela 2000-01-01 = abierto"
        nvarchar estado_activo
    }
    ztrv_solicitud_material_ceco {
        nvarchar sm_folio PK "FK"
        nvarchar cc_cve_centro_costo PK
        decimal smc_porcentaje
    }
    ztrv_solicitu_material_producto {
        nvarchar sm_folio PK
        nvarchar sm_id PK
        nvarchar smp_id PK
        nvarchar pr_cve_producto
        decimal smp_cantidad
        money smp_costo_importe
    }
    ztrv_solicitud_materia_documento {
        nvarchar sm_folio "sin PK -- 31,583 grupos duplicados"
        nvarchar sm_id
        nvarchar smd_tabla "MOVIMIENTO (189,056) / ORDEN_COMPRA (53)"
        nvarchar smd_documento
        decimal smd_cantidad
        nvarchar estatus
    }
```

`ztrv_solicitud_agenda_logistica` (170 filas) queda fuera del diagrama: no comparte `sm_folio` — se relaciona con pedido (`pd_folio`), orden de entrega (`oe_folio`), vehículo y chofer, ninguno de los cuales está en `raw` todavía.

---

## Integridad verificada en `raw`

Conteos de huérfanos sobre los joins por convención (2026-08-12):

| Relación | Huérfanos | Sobre |
|---|---:|---|
| `ceco` → `solicitud_material` | **0** | 35,123 |
| `solicitu_material_producto` → `solicitud_material` | **0** | 74,359 |
| `solicitud_material_detalle` → `solicitud_material` | 3 | 250,987 |
| `estado_solicitud` → `solicitud_material` | 4 | 310,661 |
| **`solicitud_materia_documento` → `solicitud_material`** | **2,222** | 189,107 |
| `solicitud_materia_documento` → `movimiento` | 59 | 971,664 |

Los tres primeros son limpios. Los 2,222 documentos sin cabecera (**1.2 %**) son el único hallazgo material: hay documentos que apuntan a solicitudes que no existen en la tabla madre. Usar `INNER JOIN` cuando la cabecera sea necesaria, y no asumir que todo documento tiene solicitud.

> El join `smd_documento = mv_folio` es a **nivel folio**, y `movimiento` tiene varias líneas por folio (PK `mv_folio + mv_id`). De ahí el fan-out: 189,056 documentos producen 971,664 filas. Agregar antes de unir si no se quiere multiplicar.

---

## Lo que falta para cerrar los modelos

Las dimensiones que el ERP referencia con FK declarada pero que **aún no están en `raw`**:

```mermaid
flowchart LR
    subgraph EN_RAW["Ya en raw"]
        P["producto"]
        M["movimiento"]
        OC["orden_compra"]
        C["compra"]
        S["sucursal"]
        SM["solicitud_material"]
    end

    subgraph FALTA["Faltan -- todas juntas < 8,000 filas"]
        E["estado (66)"]
        TM["tipo_movimiento"]
        MR["marca (304)"]
        LN["linea (253)"]
        CM["comprador (179)"]
        MO["moneda (184)"]
        CO["color (5)"]
        TA["talla (9)"]
        UN["unidad (33)"]
        EM["empresa (7)"]
        ZO["zona (6)"]
        CC["centro_costo (633)"]
        TG["tipo_gasto (249)"]
    end

    P -.-> MR & LN & CM & UN & E
    M -.-> TM & CO & TA & E
    OC -.-> MO & CM & CO & TA & E
    C -.-> MO & CM & E
    S -.-> EM & ZO & E
    SM -.-> CC & TG & CM

    style FALTA fill:#f8d7da,stroke:#721c24
```

**`estado` es la más urgente**: la referencian 660 FKs en toda la base y son **66 filas**. Sin ella, ningún modelo puede traducir `es_cve_estado` a una descripción legible, y el filtro de cancelados queda como literal mágico (`!= 'CA'`) en cada modelo.

Después: `tipo_movimiento` (para clasificar `movimiento` según [Inventario](inventario.md#clasificacion-de-tm_cve_tipo_movimiento)), y el resto de dimensiones de producto (`marca`, `linea`, `unidad`).

Detalle de prioridades en [Warehouse](warehouse.md#que-falta-800-tablas-con-datos).

---

## Referencia rápida de joins

Los que están confirmados y se pueden usar sin volver a validar:

```sql
-- Producto con toda su jerarquía de catálogo
FROM raw.producto p
LEFT JOIN raw.familia      f  ON p.fm_cve_familia     = f.fm_cve_familia
LEFT JOIN raw.sub_familia  sf ON p.sf_cve_sub_familia = sf.sf_cve_sub_familia
LEFT JOIN raw.categoria    c  ON p.ct_cve_categoria   = c.ct_cve_categoria
LEFT JOIN raw.departamento d  ON p.dp_cve_departamento= d.dp_cve_departamento
LEFT JOIN raw.proveedor    pv ON p.pv_cve_proveedor   = pv.pv_cve_proveedor

-- Movimiento con producto y ubicación (almacén es clave compuesta)
FROM raw.movimiento m
JOIN raw.producto p ON m.pr_cve_producto = p.pr_cve_producto
JOIN raw.almacen  a ON m.sc_cve_sucursal = a.sc_cve_sucursal
                   AND m.al_cve_almacen  = a.al_cve_almacen
JOIN raw.sucursal s ON m.sc_cve_sucursal = s.sc_cve_sucursal
WHERE m.es_cve_estado <> 'CA'

-- Compra: cabecera + partidas + la orden que la originó (polimórfico)
FROM raw.compra_encabezado ce
JOIN raw.compra c  ON c.co_folio = ce.co_folio
LEFT JOIN raw.orden_compra oc ON ce.co_documento = oc.oc_folio
                             AND ce.co_tabla     = 'ORDEN_COMPRA'

-- Solicitud con su traza de estados (deduplicar y filtrar sentinela)
FROM raw.ztrv_solicitud_material sm
JOIN (
    SELECT DISTINCT sm_folio, estado, fecha_inicio, fecha_fin
    FROM raw.ztrv_estado_solicitud
    WHERE fecha_fin > '2001-01-01'
) e ON e.sm_folio = sm.sm_folio

-- Solicitud → el movimiento que la surtió (INNER: 1.2% de docs son huérfanos)
FROM raw.ztrv_solicitud_material sm
JOIN raw.ztrv_solicitud_materia_documento d ON d.sm_folio = sm.sm_folio
                                           AND d.smd_tabla = 'MOVIMIENTO'
JOIN raw.movimiento m ON m.mv_folio = d.smd_documento
```
