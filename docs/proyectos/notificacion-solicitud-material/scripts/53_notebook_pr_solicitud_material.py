"""
Cierre de la pestana PR ("SOLICITUD CON ORDEN DE COMPRA") de
"Control de Solicitudes de material v3" (ZTRV098).

Baseline real exportado por el usuario: baseline/PR-13-08-2026.xlsx
(165 lineas). Reconciliacion a nivel (FOLIO, PRODUCTO).

Cadena para llegar de la solicitud a la orden de compra (dos rutas):
  a) directa:   Orden_Compra.Oc_Tabla='ZTRV_SOLICITUD_MATERIAL',
                Oc_Documento = Sm_Folio
  b) indirecta: Requisicion_Compra.Rc_Tabla='ZTRV_Solicitud_Material',
                Rc_Documento=Sm_Folio  -->  Rc_Folio  -->
                Orden_Compra.Oc_Tabla='REQUISICION_COMPRA',
                Oc_Documento = Rc_Folio (+ mismo Pr_Cve_Producto)

Hallazgo clave (lo que subio la precision de 36% a 97.6%): Es_Cve_Estado
='AC' en Orden_Compra NO distingue "a tiempo" de "atrasada" -- ese es
justo el criterio que separa las pestanas PR y APG del indicador de
pantalla ("APG: SOLICITUD CON ORDEN DE COMPRA ATRASADA"). Filtrando
ademas Oc_Fecha_Entrega >= HOY (no vencida), las 291 lineas de mas de la
v1 bajaron a solo 4. Sin este filtro, las ordenes vencidas (algunas de
hasta 2020) se contaban de mas porque nunca se cierran/cancelan aunque
ya nadie las siga.

Resultado final (v2): 96.97% cobertura, 97.56% precision
(160/165 interseccion, 5 solo_baseline, 4 solo_candidato).

Conexion: connection_207 (produccion), pedido explicito del usuario.
"""
import sys
sys.path.insert(0, '/home/ealcocer/trivasa-bi-core/connections')
sys.path.insert(0, '/home/ealcocer/trivasa-bi-core/shared')
import pandas as pd
from connection_207 import engine

QUERY_PR = """
SELECT DISTINCT sm.Sm_Folio AS FOLIO, oc.Pr_Cve_Producto AS PRODUCTO
FROM Orden_Compra oc
INNER JOIN ZTRV_Solicitud_Material sm
        ON sm.Sm_Folio = oc.Oc_Documento AND oc.Oc_Tabla = 'ZTRV_SOLICITUD_MATERIAL'
WHERE oc.Es_Cve_Estado = 'AC'
  AND sm.Es_Cve_Estado NOT IN ('CE', 'FN')
  AND oc.Oc_Fecha_Entrega >= CAST(GETDATE() AS DATE)

UNION

SELECT DISTINCT sm.Sm_Folio AS FOLIO, oc.Pr_Cve_Producto AS PRODUCTO
FROM Orden_Compra oc
INNER JOIN Requisicion_Compra rc
        ON rc.Rc_Folio = oc.Oc_Documento AND oc.Oc_Tabla = 'REQUISICION_COMPRA'
       AND rc.Pr_Cve_Producto = oc.Pr_Cve_Producto
       AND rc.Rc_Tabla = 'ZTRV_Solicitud_Material'
INNER JOIN ZTRV_Solicitud_Material sm ON sm.Sm_Folio = rc.Rc_Documento
WHERE oc.Es_Cve_Estado = 'AC'
  AND sm.Es_Cve_Estado NOT IN ('CE', 'FN')
  AND oc.Oc_Fecha_Entrega >= CAST(GETDATE() AS DATE)
"""

if __name__ == '__main__':
    from helpers_output import console_err
    df = pd.read_sql(QUERY_PR, engine)
    console_err.print(f"[bold]PR candidato: {len(df)} lineas (FOLIO, PRODUCTO)[/bold]")
