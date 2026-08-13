"""
Notebook de cierre — hito: query que reproduce la pestaña DISPONIBLE de
"Control de Solicitudes de material v3" (ZTRV098), validado contra
baseline real exportado 2026-08-13 (baseline/disponible-sol-material-13-08-2026.xlsx).

Resultado: 100% de cobertura del baseline (510/510 folios), 87.9% de
precision (77 folios de mas sin explicar, mayormente Ap_Tabla='COMPRA'
con cabecera en estado 'PR' -- pendiente de investigar en sesion futura).

Conexion: connection_207 (produccion) -- pedido explicito del usuario
porque comparaba contra la pantalla en vivo.
"""
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '/home/esteban/trivasa-bi-dev/core/lib')
import pandas as pd
from core.connections.connection_207 import show, engine
from helpers_output import console, resumen
from rich.table import Table

baseline = pd.read_excel('baseline/disponible-sol-material-13-08-2026.xlsx')
folios_baseline = set(baseline['FOLIO'].astype(str).str.strip())
console.print(f"\n[bold]Baseline cargado: {len(folios_baseline)} folios unicos "
              f"({len(baseline)} lineas totales)[/bold]\n")

# ─────────────────────────────────────────────────────────────────────────
# Celda 1 — Hallazgo clave: Ap_Documento es polimorfico, NO usar para volver a la solicitud
# ─────────────────────────────────────────────────────────────────────────
# ZTRV_Apartado tiene Ap_Tabla/Ap_Documento como campo polimorfico (puede
# apuntar a 'COMPRA' con el folio de una orden de compra, no de la
# solicitud). La columna correcta para volver siempre a la solicitud
# original es la columna dedicada Sm_Folio -- confirmado con folio
# 05-0056696: Ap_Tabla='COMPRA', Ap_Documento='05-0025529' (folio de
# compra), pero Sm_Folio='05-0056696' (la solicitud real, la que esta
# en el baseline). Un query que filtre por Ap_Documento pierde estos casos.
q1 = """
SELECT DISTINCT ap.Sm_Folio AS FOLIO
FROM ZTRV_Apartado ap
WHERE ap.Es_Cve_Estado = 'AC'
"""
candidato_v1 = pd.read_sql(q1, engine)
folios_v1 = set(candidato_v1['FOLIO'].astype(str).str.strip())
console.print(f"[dim]Paso 1 (Apartado.Es_Cve_Estado='AC', join por Sm_Folio): "
              f"{len(folios_v1)} folios, interseccion con baseline: "
              f"{len(folios_baseline & folios_v1)}[/dim]")

# ─────────────────────────────────────────────────────────────────────────
# Celda 2 — Excluir cabecera cerrada (CE) y finalizada (FN)
# ─────────────────────────────────────────────────────────────────────────
# El SQL fuente de la pantalla (RP_CTR_SM1/SM2, confirmado via Reporte.Rp_SQL)
# ya trae comentado el filtro sm.Es_Cve_Estado not in ('CE') -- lo activamos.
# FN (finalizado) se agrego por iteracion: folios ya surtidos en su
# totalidad tampoco deberian aparecer como "disponibles".
q2 = """
SELECT DISTINCT ap.Sm_Folio AS FOLIO
FROM ZTRV_Apartado ap
INNER JOIN ZTRV_Solicitud_Material sm ON sm.Sm_Folio = ap.Sm_Folio
WHERE ap.Es_Cve_Estado = 'AC'
  AND sm.Es_Cve_Estado NOT IN ('CE', 'FN')
"""
candidato_final = pd.read_sql(q2, engine)
folios_candidato = set(candidato_final['FOLIO'].astype(str).str.strip())

# ─────────────────────────────────────────────────────────────────────────
# Celda 3 — Reconciliacion final
# ─────────────────────────────────────────────────────────────────────────
interseccion = folios_baseline & folios_candidato
solo_baseline = folios_baseline - folios_candidato
solo_candidato = folios_candidato - folios_baseline
pct = 100 * len(interseccion) / len(folios_baseline)

t = Table(title="Reconciliacion final: DISPONIBLE (Control de Solicitudes de material v3)")
t.add_column("Metrica")
t.add_column("n", justify="right")
t.add_column("%", justify="right")
t.add_row("Baseline", str(len(folios_baseline)), "100.00%")
t.add_row("Candidato", str(len(folios_candidato)), f"{100*len(folios_candidato)/len(folios_baseline):.2f}%")
t.add_row("[green]Interseccion[/green]", str(len(interseccion)), f"[green]{pct:.2f}%[/green]")
t.add_row("[red]Solo baseline (nos falta)[/red]", str(len(solo_baseline)), f"{100*len(solo_baseline)/len(folios_baseline):.2f}%")
t.add_row("[yellow]Solo candidato (de mas)[/yellow]", str(len(solo_candidato)), f"{100*len(solo_candidato)/len(folios_baseline):.2f}%")
console.print(t)
resumen(cobertura=f"{pct:.2f}%", precision=f"{100*len(interseccion)/len(folios_candidato):.2f}%")

# ─────────────────────────────────────────────────────────────────────────
# PENDIENTE (siguiente sesion)
# ─────────────────────────────────────────────────────────────────────────
# 77 folios de mas, causa dominante (71%, 55/77): Ap_Tabla='COMPRA' con
# cabecera sm.Es_Cve_Estado='PR' -- posible hipotesis sin confirmar: el
# apartado esta ligado a una orden de compra que aun no llega, no a
# existencia real disponible ahora mismo. No investigado a fondo.
#
# Tambien pendiente: documentar en trivasa-context (docs/schema/) el
# hallazgo de Ap_Documento vs Sm_Folio en ZTRV_Apartado -- no esta ahi
# todavia.

console.print("\n[bold]Query de produccion (v5, mejor resultado a la fecha):[/bold]")
console.print(q2)
