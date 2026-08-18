# layout-gastos — estado vivo

## 2026-08-18

- **`CONSUMO_INTERNO` reconciliado**: la documentación previa lo excluía
  del universo Cargo/Abono asumiendo "sin póliza por diseño" — falso,
  confirmado con datos reales. Descubierto: cada folio genera dos pólizas
  paralelas (movimiento de inventario vs. reconocimiento de gasto real),
  el join ingenuo sumaba el Cargo de ambas (~2x el importe nativo, Abono
  siempre 0). Filtrando a la póliza de gasto real: **99.12% de
  conciliación** (2,944/2,970 folios, enero 2026), validado también a
  nivel `Grd_ID` y `Grc_ID` (reparto por centro de costo). Detalle
  completo en [index.md](index.md).
- Dos formas de aislar la póliza de gasto real dan el **mismo resultado
  exacto**: filtro por cuenta contable (raíz `F` / empieza `6` /
  descripción "costo estandar") vs. filtro por `Poliza.Pl_Comentario`
  (excluir "CUENTAS DE ORDEN"/"CTS ORDEN"/"CUENTA ORDEN") — el segundo,
  ya usado y validado antes en el proyecto `consumo_interno_trazabilidad`
  para el mismo problema, es más robusto (no depende de adivinar por
  código de cuenta).
- Nuevo hallazgo de calidad de datos documentado en
  `docs/schema/calidad-de-datos.md` — `Poliza_Detalle.Pd_Referencia` es
  ambiguo para `CONSUMO_INTERNO` (dos pólizas comparten la misma
  referencia).
- Re-validada la conciliación v0.5 (casos especiales 1-4) para orígenes
  "normales" contra datos en vivo de enero 2026: 1,425/1,425 folios
  (100% dentro de $1), consistente con lo documentado históricamente.
