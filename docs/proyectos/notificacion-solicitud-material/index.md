# notificacion-solicitud-material

Reconstruir vía SQL el filtro que usa **"Control de Solicitudes de material
v3"** (transacción `ZTRV098`, catálogo `EMPRESAS_2.Menus`) para cada una de
sus pestañas (AU, AB, PR, APG, DISPONIBLE, AC RECHAZADO, OC SIN AU, PXC),
validando contra exports reales de la pantalla como baseline — objetivo
final: alimentar un bot de notificaciones (`varela-bot`) sin depender de
que alguien abra la pantalla de escritorio a mano.

`ZTRV098` es una pantalla VB6 de escritorio, no ASP: no tiene `URL` en
`Menus` ni SQL propio guardado en `Reporte`/`Consultas`. El SQL más cercano
encontrado es `RP_CTR_SM1`/`RP_CTR_SM2` ("REPORTE DE CONTROL DE SOLICITUD DE
MATERIAL V1/V2"), con columnas casi idénticas a lo que se ve en pantalla —
probable origen real de la v3, **sin confirmar al 100%**.

## Pestaña DISPONIBLE — resuelta, 100% cobertura / 87.9% precisión

Baseline real exportado por el usuario (2026-08-13, 842 líneas, 510 folios
únicos, `SUM(SALDO)=4800`), comparado contra el candidato vía diff de
conjuntos de folios (no solo conteos).

**Hallazgo clave que desbloqueó la validación:** `ZTRV_Apartado.Ap_Documento`
es polimórfico (`Ap_Tabla`/`Ap_Documento`) — cuando `Ap_Tabla='COMPRA'`,
`Ap_Documento` es el folio de la orden de compra, **no** el de la
solicitud. La columna correcta para volver a la solicitud es `Sm_Folio`
(columna dedicada en la misma tabla). Detalle completo en
[Calidad de datos](../../schema/calidad-de-datos.md#joins-que-parecen-obvios-pero-son-falsos).

Query final (v5):

```sql
SELECT DISTINCT ap.Sm_Folio AS FOLIO
FROM ZTRV_Apartado ap
INNER JOIN ZTRV_Solicitud_Material sm ON sm.Sm_Folio = ap.Sm_Folio
WHERE ap.Es_Cve_Estado = 'AC'
  AND sm.Es_Cve_Estado NOT IN ('CE', 'FN')
```

Resultado: 510/510 folios del baseline cubiertos (100% cobertura), 77
folios de más (candidato total 587, 86.9% precisión). **Causa dominante de
los 77 sobrantes, sin resolver:** 71% (55/77) son `Ap_Tabla='COMPRA'` con
cabecera `sm.Es_Cve_Estado='PR'` — hipótesis sin confirmar de que el
apartado está ligado a una orden de compra que aún no llega (no es
existencia real disponible ahora mismo). Se probó acotar con
`d.Es_Cve_Estado='AC'` (línea de detalle, join por `Pr_Cve_Producto`) pero
**empeoró el resultado** (bajó cobertura a 59%, 301/510) — el join por
producto entre `Apartado` y `Detalle` es frágil (productos repetidos en la
misma solicitud, posibles ediciones). Descartado por ahora.

Notebook de cierre del hito:
[`06_notebook_disponible_solicitud_material.py`](../../codigo/notificacion-solicitud-material/scripts/06_notebook_disponible_solicitud_material.py.md)
— corre contra `connection_207` (producción), pedido explícito del usuario
porque comparaba contra la pantalla en vivo.

## Pestaña AU — sin resolver

Se intentó reproducir el filtro (38 folios visibles en captura original)
cruzando `ZTRV_Presupuesto_Autorizacion_Documento.Pad_Estado='AU'` (más
reciente por folio) + `ZTRV_Solicitud_Material_Detalle.Es_Cve_Estado='AC'`
+ saldo pendiente ≠ 0. Los conteos contra `.200/TRIVASADB3` nunca
convergieron a 38 (882, luego 1390 al repetir contra `.207`). **No se llegó
a una validación limpia** — a diferencia de DISPONIBLE, no hubo baseline
exportado real para esta pestaña, solo comparación de conteos contra la
captura de pantalla. Pendiente retomar con un export real.

## Pestañas AB, PR, APG, AC RECHAZADO, OC SIN AU, PXC

Sin empezar.

## Exploración adicional: el flujo de autorización no es monótono

A partir de un caso puntual (folio `23-0001183`, `Pad_Estado` final `RZA`),
se confirmó que el flujo de autorización presupuestal tiene ciclos de
retrabajo (`RZR→RZRE→RE→AU/RZA`), y que 508 folios (58%) con autorización
sin resolver siguen con cabecera `Es_Cve_Estado='AC'`. Detalle completo en
[Solicitud de material](../../schema/solicitud-material.md#el-flujo-no-es-monotono-existe-ciclo-de-retrabajo).

También se confirmó que el estado de `ZTRV_Solicitud_Material_Detalle` varía
por línea, independiente de la cabecera — ver
[Calidad de datos](../../schema/calidad-de-datos.md#el-estado-de-detalle-no-hereda-el-de-cabecera-ztrv_solicitud_material_detalle).

## Ver también

- [PROGRESS.md](PROGRESS.md) — estado vivo.
