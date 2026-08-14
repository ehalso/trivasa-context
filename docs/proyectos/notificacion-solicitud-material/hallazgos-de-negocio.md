# Solicitudes de material — qué dicen los datos

> Lectura de negocio, no de metodología (para el detalle técnico ver
> [index.md](index.md)). Cifras del mart `fct_solicitud_material_pipeline`
> / `fct_solicitud_material_autorizacion`, calculadas 2026-08-14. Tablero:
> [Solicitudes de material · Backlog vivo](https://dash.frento.com.mx/projects/df98464b-9806-49f2-b5cb-2f99d47905ad/dashboards/6655b5bf-cfce-46de-97b1-07e87eeb4e48/view).

## El backlog vivo es más grande de lo que cualquier pantalla muestra de un vistazo

**15,143 líneas de solicitud de material siguen activas ahora mismo** —
ni surtidas, ni canceladas. La pantalla operativa (`ZTRV098`) las reparte
en pestañas separadas y nunca las suma; verlas juntas es lo que expone el
tamaño real de la cola de trabajo.

## La autorización presupuestal casi nunca es el cuello de botella

Una vez que una solicitud entra a revisión, la mediana para autorizarla
es de **~1.4 minutos**. Pero desde que se **crea** la solicitud hasta que
queda autorizada, la mediana sube a **~14 horas**. La brecha está toda
concentrada en el tramo "esperar a que alguien la revise" — no en decidir
si aprobarla. Cualquier esfuerzo por acelerar el ciclo de autorización
debería apuntar ahí, no al paso de aprobación en sí, que ya es casi
instantáneo.

## Hay un backlog invisible de folios rechazados que nadie está viendo

**797 folios** tienen al menos un rechazo presupuestal (`RZR`/`RZA`/`RZ`)
y **nunca llegaron a autorizarse** — pero siguen activos en el sistema,
no cerrados ni cancelados. De esos, **499 incluso siguen con la solicitud
en estado "activa" en la cabecera**, es decir: para cualquiera que
consulte el estado general, se ven como solicitudes normales en trámite,
no como rechazos pendientes de corregir. No hay ninguna pantalla ni
reporte nativo que junte "rechazado" + "sigue activo" en un solo lugar —
por diseño, quedan fuera del radar operativo.

## Las órdenes de compra atrasadas están concentradas en 3 sucursales

**298 líneas de material** tienen una orden de compra vigente cuya fecha
de entrega ya venció, por un valor de **$886,306**. No está repartido
parejo:

| Sucursal | Líneas atrasadas |
|---|---:|
| FABRICA | 197 (66%) |
| XKANAKU | 52 |
| PLANTA UMAN | 48 |
| X-CITAN | 1 |

Dos de cada tres órdenes atrasadas del negocio completo están en una sola
sucursal (FABRICA). Si hay un solo lugar donde vale la pena empezar a dar
seguimiento con proveedores, es ahí — el resto de la red apenas aporta al
problema.

## Lectura conjunta

El patrón que emerge de las tres piezas de arriba: el sistema **no
pierde** solicitudes por mal proceso de autorización (eso funciona bien y
rápido) — las pierde por **falta de seguimiento después de que ya se
tomó una decisión**: nadie revisa a tiempo, nadie corrige un rechazo, y
las entregas atrasadas no se escalan hasta que alguien las busca a mano.
El tablero de Lightdash da una foto reproducible de esto todos los días;
antes de esta pieza, verlo requería cruzar mentalmente varias pestañas de
`ZTRV098` y la bitácora de autorización, algo que en la práctica nadie
hacía de forma rutinaria.

## Fuentes y confianza

Ver [index.md](index.md#tablas-raw-subidas-al-warehouse) para los marts y
el detalle técnico de cada etapa. Nivel de confianza por pieza:

| Hallazgo | Confianza |
|---|---|
| Backlog vivo (15,143) | Alta — suma directa de etapas ya validadas |
| Autorización ~1.4 min / ~14h | Alta — timestamps directos de la bitácora |
| 797/499 folios trabados | Alta — mismo criterio validado la sesión anterior (508 a otro corte) |
| 298 OC atrasadas / concentración en sucursales | Media-alta — la regla PR/APG está validada al 97.6%/inferida respectivamente (ver [Solicitud de material](../../schema/solicitud-material.md#pestañas-ab-pr-y-apg-de-ztrv098-control-de-solicitudes-de-material-v3)) |
