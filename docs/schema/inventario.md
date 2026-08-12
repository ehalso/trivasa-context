# Inventario: tipos de movimiento y existencia a una fecha

> Dos piezas de conocimiento validadas al 100 % contra reportes reales de MPRO. Es lo que hay que saber antes de tocar `Movimiento` o `Existencia`.
>
> Validado 2026-07-25 y 2026-07-28 contra enero 2026, empresa `0001`.

## Clasificación de `Tm_Cve_Tipo_Movimiento`

### Excluidos — traspaso / transferencia interna

Verificado empíricamente que **netean exactamente a 0 por producto** en el periodo. No son negocio, son reacomodos:

| Tipos | Qué son |
|---|---|
| `100`/`101`/`500`/`501` | Transferencia entre sucursales |
| `102`/`103`/`502`/`503` | Entrada/salida de tránsito |
| `106`/`107`/`506`/`507` | Traspaso entre almacenes |
| `112`/`113`/`512`/`513` | Traspaso a producción (material que se reubica antes de consumirse) |

⚠️ Las cuatro de transferencia **netean a 0 solo en conjunto**, no individualmente: hay desfase cuando una transferencia queda "en tránsito" al cruzar el fin de mes.

### Incluidos — movimientos reales de negocio

| Entrada | Salida |
|---|---|
| Compra (`050`) | Consumo interno (`060`) |
| Consignación (`052`) | Conversión (`508`) |
| Conversión (`108`) | Salida de producción en proceso (`514`) |
| Entrada producto terminado (`114`) | Merma (`510`) |
| Rechazo (`200`) | Venta — remisión (`600`) |
| Devolución de cliente (`202`) | Venta — nota de venta (`700`) |
| Ajuste de inventario físico (`902`) | Refacciones / consumo (`800`) |
| Merma, entrada (`974`) | Ajuste de inventario físico (`904`) |
| | Reproceso (`972`) |
| | Ajuste MP bloquera/viguera (`980`/`982`) |
| | Reposición física (`986`) |

> **Gotcha de nomenclatura:** lo que el usuario llama "salida de orden de producción" (producto terminado) es el tipo **`114`** (`ENTRADA PRODUCTO TERMINADO`, entrada a inventario); lo que llama "entrada a orden de producción" (consumo de materia prima) es el tipo **`514`** (`SALIDA DE PRODUCCION EN PROCESO`, salida de inventario). **La dirección de la OP es inversa a la dirección del inventario.**

### Cancelaciones y anulaciones

Excluidas por default: `Es_Cve_Estado='CA'` + tipos `051`/`061`/`109`/`115`/`203`/`509`/`511`/`515`/`601`/`701`/`801`/`973`.

⚠️ **No excluir cancelación + reverso a ciegas asumiendo que empatan 1:1.** No siempre empatan: en `0000018553` (BLOCK XC 15X20X40) el tipo `600` tiene 396 filas canceladas pero su anulación `601` solo 393 — 3 reversos huérfanos. El enfoque correcto es reactivarlas solo para los productos donde la reconciliación no cuadre sin ellas.

### Resultado de la validación

Enero 2026: 22,090 filas de movimiento efectivas (de 59,708 antes de excluir traspasos). Reconciliación por producto (existencia inicial + neto vs existencia final): **7,179 / 7,179 productos cuadran exactamente (100 %)**.

## Existencia a una fecha pasada

Tres métodos evaluados contra ground truth real (exports de MPRO):

| Método | Definición | Match |
|---|---|---|
| **A** | `Existencia.Ex_Cantidad_Control_1` (hoy) − `SUM(Movimiento.Mv_Cantidad_1)` posterior a la fecha | 99.3 % |
| **B** | Réplica literal de `RPEXF01_10.asp`: `SUM(Mv_Cantidad_Control_1) WHERE Es_Cve_Estado='AC' AND Tm_Anulacion='NO' AND Mv_Fecha <= fecha` | 98.9 % |
| **C** | Igual que B pero **sin** el filtro de estado/anulación (equivale a la opción "considera cancelaciones/anulaciones" del reporte) | **100 %** |

**El método oficial es el C.** Corresponde a la consulta que el propio contador usa para generar el reporte "EXISTENCIAS A UNA FECHA" con la opción *considera cancelaciones/anulaciones* activada:

```sql
WHERE Sucursal.Em_Cve_Empresa = '0001' AND Movimiento.Mv_Fecha <= @fecha
-- agrupado por producto
```

Validado contra 3 fechas ancla: `2025-01-01` (5,845 productos), `2026-01-01` (6,858), `2025-03-31` (5,945).

### Por qué el método B falla en productos de alto volumen

B excluye cancelaciones y reversos por status/tipo **asumiendo que siempre empatan 1:1**. Cuando no empatan —por correcciones históricas posteriores— el resultado se desvía. Los fallos se concentraban en BLOCK/VIGA/BOVEDILLA/ADOCRETO (producción propia, alto volumen y muchas anulaciones).

### `Mv_Cantidad_1` vs `Mv_Cantidad_Control_1`

Difieren en solo **589 de 4,516,292 filas (0.013 %)**. La preocupación de "unidades distintas" es real pero prácticamente irrelevante.

## Trazabilidad FIFO

Para ligar cada salida de inventario con el UUID del CFDI de compra que la respalda existe una lógica FIFO "on the fly" validada: semilla hacia atrás vía método C + capas nuevas del periodo + cola FIFO línea a línea. Validada al 100 % para enero 2026.
