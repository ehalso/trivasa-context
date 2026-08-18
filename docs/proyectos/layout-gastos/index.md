# layout-gastos

Reconstruir vía SQL el layout de gastos que usa el área de contabilidad, y
conciliar cada folio de `Gasto_Registro` contra su póliza contable
(`Cargo`/`Abono` de `Poliza_Detalle`) para validar que el importe nativo del
gasto cuadra con lo que se contabilizó. Trabajo histórico en
`~/trivasa-bi-dev/exploracion/layout_gastos` y
`layout-gastos-ctunlinux` (v0.1 → v0.5.1); esta entrada documenta el estado
consolidado, no el detalle de cada iteración.

## Piezas resueltas

- **v0.1 — reporte nativo**: `Gasto_Registro` + `Gasto_Registro_Documento` +
  `Comprobante_Digital` (UUID). Validado 1:1 contra export real de MPRO
  (enero 2026: $39,469,269.50 vs $39,469,269.59, diferencia $0.09).
- **v0.5 — Cargo/Abono vs póliza, orígenes "normales"** (general/sin
  `Gr_Tabla`, `VIAJE`, `ORDEN_COMPRA`, `CONTROL_COMBUSTIBLE`,
  `GASTO_RECLASIFICACION`): **100% dentro de $1** de tolerancia (1,425/1,425
  folios, enero 2026; 99.90% en 2025 completo). 4 casos especiales — ver
  [Casos especiales de conciliación](#casos-especiales-de-conciliación-cargoabono) abajo.

## CONSUMO_INTERNO — antes excluido, ahora conciliado (2026-08-18)

La documentación histórica de v0.5 excluía `CONSUMO_INTERNO` del universo
reconciliable asumiendo "sin póliza por diseño" (se registra por otro
subsistema). **Falso**: sí tiene póliza, solo que estructurada distinto a
los demás orígenes. Detalle completo del join ambiguo y la corrección en
[Calidad de datos → joins que parecen obvios pero son falsos](../../schema/calidad-de-datos.md#-poliza_detallepd_referencia--gr_folio-sin-aislar-la-poliza-real-en-consumo_interno).

**Resumen**: cada folio de `CONSUMO_INTERNO` genera **dos pólizas
paralelas** bajo el mismo `Pc_Documento` — una de movimiento de inventario
(cuenta `10500.012.003`, raíz de grupo `H` = Cuentas de Orden/memo) y otra
de reconocimiento de gasto real (cuenta variable, raíz `F` = Gastos, o sin
grupo con descripción "gastos a cuenta de costo estandar"). Filtrando el
Cargo a la póliza de gasto real (dos formas equivalentes, mismo resultado
exacto: por cuenta contable, o por `Poliza.Pl_Comentario` excluyendo
"CUENTAS DE ORDEN"/"CTS ORDEN"/"CUENTA ORDEN"):

| | |
|---|---|
| Folios (enero 2026) | 2,970 |
| Concilian (±$1) | 2,944 (**99.12%**) |
| Sin póliza de gasto real | 26 (0.88%) — causa real, no de filtro |
| Importe total | $6,594,522.55 |
| Cargo (gasto real) total | $6,388,627.47 |

El Abono siempre sale en 0 para este origen: la contrapartida va a una
cuenta de enlace/almacén (ej. `1140.010.012.007`), no a Gastos — aquí el
gasto se reconoce solo por el Cargo, no por la partida doble
Cargo=Gasto/Abono=CxP de los demás orígenes.

Validado también a grano más fino:
- **`Grd_ID`** (línea de documento): mismo 99.12%, coincide 1:1 con folio —
  los 2,970 folios de `CONSUMO_INTERNO` de enero 2026 tienen exactamente 1
  línea cada uno.
- **`Grc_ID`** (`Gasto_Registro_Control`, reparto por centro de costo vía
  `Grc_Factor`): 2,942/2,970 folios tienen 1 sola línea Grc, el resto se
  reparte hasta en 14 centros de costo. La póliza de gasto real **también**
  se reparte por `Pd_Centro_Costo` cuando aplica — emparejando por
  (folio + centro de costo): 3,044/3,071 líneas concilian (99.1%,
  consistente con el resultado a nivel folio).

Los 26 folios sin póliza de gasto real: no tienen ninguna póliza de
reconocimiento de gasto, solo la de movimiento de inventario — hueco real
en los datos para ese subconjunto, pendiente de investigar si el contador
lo necesita resuelto.

## Casos especiales de conciliación Cargo/Abono

1. `CONSUMO_INTERNO`/`GASTO_REGISTRO_NOMINA`: ver arriba —
   `CONSUMO_INTERNO` ya no se excluye, se reconcilia con el filtro de
   cuenta/comentario. `GASTO_REGISTRO_NOMINA` sigue sin investigar (fuera
   de alcance hasta ahora).
2. `GASTO_RECLASIFICACION`: no tiene póliza real de Cargo/Abono — se deriva
   del signo de `Grd_Precio_Descontado_Importe` (positivo=Cargo,
   negativo=Abono), misma cuenta vía `Tipo_Gasto.Tg_Cuenta_Contable`.
3. Abono (`Pd_Tipo=2`) solo cuenta si la cuenta contable es raíz `F`
   (Gastos), o sin grupo asignado y código que empieza en `6`, o sin grupo
   con descripción "gastos a cuenta de costo estandar" — sin este filtro,
   partidas dobles legítimas contra cuentas de Activo (ej. depreciación)
   rompen la conciliación.
4. Reversiones (`Importe` de folio ≤ -$1): usar solo el Abono, forzar
   Cargo a 0.

## Pendiente

- Investigar los 26 folios de `CONSUMO_INTERNO` sin póliza de gasto real
  (enero 2026) — confirmar si es un hueco de datos real o falta de proceso.
- `GASTO_REGISTRO_NOMINA`: nunca se investigó si también tiene póliza
  estructurada distinto, como resultó ser el caso de `CONSUMO_INTERNO`.
- Construir el reporte de producción (dbt/Metabase) — todo lo de arriba
  sigue siendo exploración validada en notebooks Python/SQL, no pipeline.
