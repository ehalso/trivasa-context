"""
Cierre de la pestana AB ("SOLICITUD CON REQUISICION DE COMPRA") de
"Control de Solicitudes de material v3" (ZTRV098).

Baseline real exportado por el usuario: baseline/AB-13-08-2026.xlsx
(89 lineas). Reconciliacion a nivel (FOLIO, PRODUCTO).

Hallazgo clave: Requisicion_Compra tiene el mismo patron polimorfico que
ZTRV_Apartado (Rc_Tabla/Rc_Documento) y puede apuntar DIRECTO a
'ZTRV_Solicitud_Material' (Rc_Documento=Sm_Folio). Es_Cve_Estado='AC' en
esa tabla = requisicion activa/pendiente; 'RCT' = ya se convirtio en
Orden_Compra (avanzo a la pestana PR); 'CA'/'CE' = cancelada/cerrada.

Query final (v2), resultado: 92.13% cobertura, 93.18% precision
(82/89 interseccion, 7 solo_baseline, 6 solo_candidato -- ver
33_diagnostico_ab_v2_resto.py para el detalle de los residuos, ambos con
causa razonablemente explicada: RC_ESTADO='RCT' que igual sigue
mostrandose en pantalla, y filas 'AC' viejas de 2024 nunca cerradas
--posible deuda de datos, no bug de la query).

Conexion: connection_207 (produccion), pedido explicito del usuario.
"""
import sys
sys.path.insert(0, '/home/ealcocer/trivasa-bi-core/connections')
sys.path.insert(0, '/home/ealcocer/trivasa-bi-core/shared')
import pandas as pd
from connection_207 import engine

QUERY_AB = """
SELECT DISTINCT rc.Rc_Documento AS FOLIO, rc.Pr_Cve_Producto AS PRODUCTO
FROM Requisicion_Compra rc
INNER JOIN ZTRV_Solicitud_Material sm ON sm.Sm_Folio = rc.Rc_Documento
WHERE rc.Rc_Tabla = 'ZTRV_Solicitud_Material'
  AND rc.Es_Cve_Estado = 'AC'
  AND sm.Es_Cve_Estado NOT IN ('CE', 'FN')
"""

if __name__ == '__main__':
    from helpers_output import console_err
    df = pd.read_sql(QUERY_AB, engine)
    console_err.print(f"[bold]AB candidato: {len(df)} lineas (FOLIO, PRODUCTO)[/bold]")
