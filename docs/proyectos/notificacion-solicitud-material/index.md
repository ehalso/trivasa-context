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

## Pestañas AB y PR — resueltas contra baseline real (2026-08-13)

Baselines reales exportados por el usuario el mismo día:
`AB-13-08-2026.xlsx` (89 líneas) y `PR-13-08-2026.xlsx` (165 líneas).
Reconciliación a nivel `(FOLIO, PRODUCTO)`.

**Hallazgo de esquema:** `Requisicion_Compra` y `Orden_Compra` son
polimórficas igual que `ZTRV_Apartado` y pueden apuntar directo a
`'ZTRV_Solicitud_Material'`. Detalle completo en
[Calidad de datos](../../schema/calidad-de-datos.md#la-ruta-correcta-patron-polimorfico-_tabla_documento).

| Pestaña | Cobertura | Precisión |
|---|---:|---:|
| AB | 92.13 % | 93.18 % |
| PR | 96.97 % | 97.56 % |

**El hallazgo que subió la precisión de PR de 36 % a 97.6 %:**
`Orden_Compra.Es_Cve_Estado='AC'` no distingue "a tiempo" de "atrasada"
— hay que filtrar además `Oc_Fecha_Entrega >= HOY` (sin eso, se contaban
órdenes vigentes de hasta 2020, nunca cerradas). Ese sería justo el
criterio que separa PR de APG, aunque **no hay baseline de APG que lo
confirme todavía** — es inferencia del nombre del indicador, no dato
verificado.

Detalle completo, incluyendo diagnóstico de los residuos de precisión,
en [Solicitud de material](../../schema/solicitud-material.md#pestanas-ab-pr-y-apg-de-ztrv098-control-de-solicitudes-de-material-v3).

Notebooks de cierre:
[`52_notebook_ab_solicitud_material.py`](../../codigo/notificacion-solicitud-material/scripts/52_notebook_ab_solicitud_material.py.md),
[`53_notebook_pr_solicitud_material.py`](../../codigo/notificacion-solicitud-material/scripts/53_notebook_pr_solicitud_material.py.md).

## Pestaña AU — baseline real conseguido, pero no converge

Con el baseline real (`AU-13-08-2026.xlsx`, 20 líneas/19 folios — muestra
chica) se probó: último `Pad_Estado='AU'` + cabecera no `CE`/`FN` + línea
`Es_Cve_Estado='AC'` + sin apartado/requisición/OC activos. Mejor
resultado: **90 % cobertura / ~26 % precisión**, sin causa raíz clara
para los ~50 sobrantes (se descartaron varias hipótesis: apartados
históricos cerrados/cancelados, `Sm_Revisar_Oc`, `Sm_Es_Servicio`,
antigüedad). Confirmado con un caso real que parte del ruido es
**inherente a reconciliar contra producción en vivo**: a un folio se le
creó un apartado activo la misma tarde, después de exportado el
baseline. Ver [Solicitud de material](../../schema/solicitud-material.md#pestana-au-parcialmente-explorada-sin-converger)
y `PROGRESS.md` de este proyecto para el detalle completo del
diagnóstico.

## Pestañas APG, AC RECHAZADO, OC SIN AU, PXC

Sin baseline exportado — sin empezar. Para APG hay una hipótesis fuerte
(orden de compra vigente vencida, ver arriba) heredada del hallazgo de
PR, pendiente de validar con un export real de esa pestaña.

## Exploración adicional: el flujo de autorización no es monótono

A partir de un caso puntual (folio `23-0001183`, `Pad_Estado` final `RZA`),
se confirmó que el flujo de autorización presupuestal tiene ciclos de
retrabajo (`RZR→RZRE→RE→AU/RZA`), y que 508 folios (58%) con autorización
sin resolver siguen con cabecera `Es_Cve_Estado='AC'`. Detalle completo en
[Solicitud de material](../../schema/solicitud-material.md#el-flujo-no-es-monotono-existe-ciclo-de-retrabajo).

También se confirmó que el estado de `ZTRV_Solicitud_Material_Detalle` varía
por línea, independiente de la cabecera — ver
[Calidad de datos](../../schema/calidad-de-datos.md#el-estado-de-detalle-no-hereda-el-de-cabecera-ztrv_solicitud_material_detalle).

## Tablas raw subidas al warehouse

`ZTRV_Apartado`, `ZTRV_Presupuesto_Autorizacion_Documento` y
`Requisicion_Compra` (las 3 tablas clave de esta reconciliación) ya viven
en `raw.*` de Postgres, 100% reconciliadas contra `.207`. De paso se
encontró que `TRIVASADB3` cambió de IP (`.200` → `.205`). Detalle en
[PROGRESS.md](PROGRESS.md) y [Warehouse](../../schema/warehouse.md#solicitudes-de-material).

## Ver también

- [PROGRESS.md](PROGRESS.md) — estado vivo.
