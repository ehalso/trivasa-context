# Runbook: agregar una tabla nueva al pipeline (dlt → mart → Lightdash)

> De cero a un tablero nuevo en Lightdash, pasando por las cuatro paradas de
> [Stack de BI](stack-bi.md): backfill con dlt, incremental diario contra
> producción, modelo de dbt, deploy y construcción del tablero por GUI.
> Código real verificado en `trivasa-bi-core` el 2026-08-20 — los nombres de
> función y patrones de este runbook son los que ya usan
> `dlt/load_reorden.py`, `dlt/load_solicitudes.py` y
> `dlt/load_compras_inventario.py`, no una convención inventada. Reemplaza
> a un runbook previo sin curar en `~/por_ordenar/docs/dlt_pipelines_runbook.md`
> (ctunlinux) — ese seguía el patrón manual `pymssql.connect()` y el backfill
> contra `.200`, ambos ya obsoletos; puede borrarse.

Sigue los pasos en orden. Cada uno da por hecho que el anterior ya quedó
verificado — no hay atajos seguros, sobre todo entre el paso 2 (backfill) y
el 4 (enganchar al incremental): si te saltas la verificación de en medio,
un backfill mal hecho se ve exactamente igual a uno bueno hasta que alguien
nota que faltan filas.

---

## Paso 0 — Ubicar las piezas

Todo el código vive en `trivasa-bi-core` (ctunlinux, `~/ehalso/trivasa-bi-core/`):

| Carpeta | Qué agregas ahí |
|---|---|
| `dlt/` | La función que extrae la tabla del ERP y la carga a Postgres |
| `connections/` | Credenciales reutilizables — normalmente no necesitas tocarla, ya existen para `.205` y `.207` |
| `dbt/models/staging/` | Un modelo `stg_<tabla>.sql` por tabla cruda |
| `dbt/models/marts/` | El modelo final `fct_*`/`dim_*` que se conecta a Lightdash |

No hay `venv`: `dlt` y `dbt-core` están instalados en el Python del sistema
en ctunlinux. Los comandos de este runbook corren directo con `python3`.

**Regla de oro de todo el repo, aplica aquí también:** no inventes nombres
de columna o tabla — perfila la tabla real en `.205/TRIVASADB3` antes de
escribir una sola línea de código. Si el nombre no está confirmado, se
verifica con una query, no se adivina.

---

## Paso 1 — Elegir la tabla y decidir `merge` vs. `replace`

Ver el detalle completo en
[Decisión: merge vs. replace](../decisions/merge-vs-replace.md); aquí solo
el checklist accionable. Corre las tres contra `.205/TRIVASADB3` —
**y repite la 1 y la 2 también contra `.207`**, no asumas que lo que es
cierto en la copia lo es también en producción. Es el patrón que ya siguió
`load_solicitudes.py` para `ZTRV_Apartado` y
`ZTRV_Presupuesto_Autorizacion_Documento` ("0 duplicados de PK en `.205` y
en `.207`") — una tabla que pasa el pre-flight en `.205` pero falla en
`.207` (o viceversa) es justo el caso que este doble check existe para
atrapar antes de que llegue a producción.

**1. ¿La PK es realmente única?**

```sql
SELECT COUNT(*) FROM (
  SELECT <cols_pk> FROM <Tabla> GROUP BY <cols_pk> HAVING COUNT(*) > 1
) x;
-- debe dar 0 -- correr en .205 y en .207
```

**2. ¿El cursor incremental está poblado de verdad?**

```sql
SELECT COUNT(*) total,
       SUM(CASE WHEN Fecha_Ult_Modif IS NULL THEN 1 ELSE 0 END) nulos
FROM <Tabla>;
-- si "nulos" es una fracción grande del total, el cursor no sirve -- correr en .205 y en .207
```

**3. ¿`.205` escribe esta tabla por su cuenta?** (rompería el backfill en
silencio — ver paso 2)

```sql
SELECT MAX(Fecha_Ult_Modif) FROM <Tabla>;  -- en .205/TRIVASADB3
```

Si la fecha es de **hoy** en vez de la fecha del último restore
(`SELECT TOP 5 restore_date FROM msdb.dbo.restorehistory ORDER BY restore_date DESC;`
en `.205`), esa tabla recibe escritura propia — no uses `.205` como origen
del backfill para ella, backfillea directo contra `.207` (ver el caso real
de `ZTRV_Solicitud_Material` en `load_solicitudes.py:main()`, que existe
justo por esto). En ese caso, pasa `refresh="drop_resources"` a
`pipeline.run(...)` (o al `run_tracked(...)` que lo envuelve) — fuerza a
dlt a tirar el estado incremental que pudiera haber quedado de una corrida
anterior y traer el histórico completo desde cero, en vez de asumir que ya
existe un punto de corte previo.

| Resultado | Estrategia |
|---|---|
| PK única + cursor bien poblado | `merge` incremental |
| Sin PK única, o cursor NULL en su mayoría, o tabla chica (hasta cientos de miles de filas) | `replace` completo |

---

## Paso 2 — Backfill inicial contra `.205/TRIVASADB3`

Añade la función al `load_<dominio>.py` que ya exista para ese dominio de
negocio (`load_compras_inventario.py`, `load_solicitudes.py`,
`load_movimiento.py`, `load_reorden.py`), o crea uno nuevo si es un dominio
sin archivo todavía — usa `load_reorden.py` como plantilla mínima, tiene un
`merge` y un `replace` en el mismo archivo.

**Plantilla `merge` (tabla con PK única y cursor poblado):**

```python
import datetime
import dlt
from dlt.sources.sql_database import sql_table
from sqlalchemy.engine import URL

import log_run_metrics

CREDENTIALS_205 = URL.create(
    "mssql+pyodbc",
    username="sa",
    password="...",       # copia la real de connections/connection_205_trivasadb3.py
    host="192.168.117.205",
    port=1433,
    database="TRIVASADB3",
    query={"driver": "ODBC Driver 18 for SQL Server", "TrustServerCertificate": "yes"},
).render_as_string(hide_password=False)

def mi_tabla_nueva(credentials):
    return sql_table(
        credentials=credentials,
        schema="dbo",
        table="Mi_Tabla_Nueva",
        reflection_level="minimal",
        write_disposition="merge",
        primary_key=["Mtn_Folio"],          # la(s) columna(s) validada(s) en el paso 1
        incremental=dlt.sources.incremental(
            "Fecha_Ult_Modif",
            initial_value=datetime.datetime(1900, 1, 1),  # objeto datetime, NO el string "1900-01-01"
        ),
    )

def backfill_205_mi_tabla_nueva():
    pipeline = dlt.pipeline(pipeline_name="trivasa_<dominio>", destination="postgres", dataset_name="raw")
    print(log_run_metrics.run_tracked(
        pipeline, mi_tabla_nueva(CREDENTIALS_205),
        "load_<dominio>.py:backfill_205_mi_tabla_nueva"
    ))
```

**Plantilla `replace` (sin cursor usable):**

```python
def mi_tabla_chica(credentials):
    return sql_table(
        credentials=credentials,
        schema="dbo",
        table="Mi_Tabla_Chica",
        reflection_level="minimal",
        write_disposition="replace",
    )
```

Corre el backfill una sola vez, a mano:

```bash
cd ~/ehalso/trivasa-bi-core/dlt
python3 -c "from load_<dominio> import backfill_205_mi_tabla_nueva; backfill_205_mi_tabla_nueva()"
```

⚠️ **Tres gotchas confirmados, todos con incidentes reales detrás** (ver
[merge-vs-replace.md](../decisions/merge-vs-replace.md#gotchas-del-cursor)):

- `initial_value` debe ser `datetime.datetime(1900, 1, 1)`, nunca el string
  `"1900-01-01"` — si la columna es `datetime` en SQL Server, dlt compara
  `str > datetime` y truena con `IncrementalCursorInvalidCoercion`.
- El backfill **tiene que correr con `dlt.sources.incremental` ya activo**
  (como en la plantilla de arriba), para que el cursor quede persistido. Si
  se hace con una query a pelo, el estado queda vacío y el primer
  incremental re-trae la tabla completa.
- Si la tabla es grande (varios millones de filas), trocea el backfill por
  año — `load_movimiento.py:cargar_anio()` es la referencia: cargar todo de
  una vez mató el proceso por falta de memoria en la VM de ctunlinux.

---

## Paso 3 — Verificar el backfill antes de seguir

No pases al paso 4 sin esto. Compara conteo de filas entre origen y
destino:

```sql
-- en .205/TRIVASADB3
SELECT COUNT(*) FROM Mi_Tabla_Nueva;
```

```sql
-- en Postgres, trivasa_dw
SELECT COUNT(*) FROM raw.mi_tabla_nueva;
```

Deben coincidir (o estar dentro de un margen mínimo si hubo escritura entre
las dos queries). Si no coinciden, no sigas — revisa el paso 1 antes de
tocar producción en el paso 4.

---

## Paso 4 — Enganchar al incremental diario contra `.207` (producción)

Aquí es donde se cambia de base: de `.205` (exploración) a
**`.207/TRIVASADB`**, la única fuente de cifras oficiales. Añade la
función incremental al mismo archivo:

**Por qué esto no deja huecos:** el `pipeline_name` y el `dataset_name` de
abajo son **los mismos** que usó el backfill del paso 2. dlt persiste el
`last_value` de `Fecha_Ult_Modif` alcanzado por esa corrida (estado local
en `.dlt/pipelines/<pipeline_name>/`), y esta función lo retoma solo — el
`WHERE Fecha_Ult_Modif > <cursor>` que arma `sql_table()` usa ese valor
guardado, no `1900-01-01` otra vez. Si cambias el `pipeline_name` entre el
backfill y el incremental, pierdes esa continuidad y vuelves a traer todo
el histórico contra producción por accidente.

```python
CREDENTIALS_207 = URL.create(
    "mssql+pyodbc",
    username="EALCOCER",
    password="...",       # copia la real de connections/connection_207.py
    host="192.168.117.207",
    port=1433,
    database="TRIVASADB",
    query={"driver": "ODBC Driver 18 for SQL Server", "TrustServerCertificate": "yes"},
).render_as_string(hide_password=False)

def run_incremental_207_mi_tabla_nueva():
    pipeline = dlt.pipeline(pipeline_name="trivasa_<dominio>", destination="postgres", dataset_name="raw")
    print(log_run_metrics.run_tracked(
        pipeline, mi_tabla_nueva(CREDENTIALS_207),
        "load_<dominio>.py:run_incremental_207_mi_tabla_nueva"
    ))
```

Si el dominio ya tiene una función `run_incremental_207_all()` (la mayoría
las tiene — es la que corre el cron), agrega la tabla nueva a su lista en
vez de dejarla suelta, para que quede en el mismo ciclo diario que las
demás del dominio:

```python
def run_incremental_207_all():
    print(log_run_metrics.run_tracked(_pipeline(), [
        # ... tablas existentes ...
        mi_tabla_nueva(CREDENTIALS_207),
    ], "load_<dominio>.py:run_incremental_207_all"))
```

Corre el incremental una vez a mano para confirmar que trae filas nuevas
(0 filas nuevas es normal si el backfill del paso 2 ya trajo todo hasta
hoy):

```bash
python3 -c "from load_<dominio> import run_incremental_207_mi_tabla_nueva; run_incremental_207_mi_tabla_nueva()"
```

### Agendarlo

⚠️ **Antes de tocar el cron: verificado 2026-08-20 que el `crontab` actual
de `ealcocer` apunta a `/home/ealcocer/trivasa-bi-dev/dlt-pipelines`, una
ruta que **ya no existe** (el repo se movió a
`~/ehalso/trivasa-bi-core/dlt`). Los incrementales diarios llevan al menos
desde el 2026-08-11 sin correr — `check_raw_freshness.py` no se ha vuelto
a ejecutar desde esa fecha, y su último resultado guardado ya marcaba
`FAIL` con huecos reales en `producto`, `movimiento`, `compra` y otras.
Esto es independiente de la tabla que estás agregando: repara la ruta del
cron (o termina la migración a systemd timers que ya es la convención
declarada en `trivasa-bi-core/CLAUDE.md`) antes de asumir que "ya quedó
agendado" con solo tocar el archivo de cron.**

Mientras eso se confirma con Esteban, la línea de cron correcta para este
dominio (ruta arreglada, mismo horario que ya usaba) es:

```cron
50 6 * * * cd /home/ealcocer/ehalso/trivasa-bi-core/dlt && /usr/bin/python3 -c "from load_<dominio> import run_incremental_207_all; run_incremental_207_all()" >> /home/ealcocer/ehalso/trivasa-bi-core/dlt/logs/<dominio>.log 2>&1
```

---

## Paso 5 — Dejar que la observabilidad te avise sola

No hace falta tocar nada aquí: `observability/checks/check_raw_freshness.py`
recorre **todas** las tablas de `raw.*` automáticamente — en cuanto tu
tabla nueva tiene filas ahí, entra al check sin configuración extra.
Corre a las 07:00 (una vez arreglado el cron del paso 4) y postea a Loki
para verse en Perses.

---

## Paso 6 — Modelo `staging` en dbt

Un modelo por tabla cruda, en `dbt/models/staging/stg_<tabla>.sql`.
Renombra columnas a español legible, sin lógica de negocio todavía —
mira `stg_orden_compra.sql` o `stg_producto.sql` como referencia real:

```sql
select
    mtn_folio as mi_tabla_folio,
    mtn_fecha::date as fecha,
    sc_cve_sucursal as sucursal_id,
    pr_cve_producto as producto_id,
    mtn_importe as importe,
    es_cve_estado as estado
from {{ source('raw', 'mi_tabla_nueva') }}
where es_cve_estado != 'CA'   -- excluir cancelados; 'ACTI' no existe, no lo uses como filtro
```

Agrega la tabla a `dbt/models/staging/_sources.yml`, dentro de
`sources: - name: raw`:

```yaml
      - name: mi_tabla_nueva
```

---

## Paso 7 — Modelo `intermediate` (solo si hay que juntar varias tablas)

Si el mart necesita joins o reglas de negocio no triviales (varios
`stg_*`, casos especiales, deduplicar historial), ese trabajo va en
`dbt/models/intermediate/int_<algo>.sql` — no directo en el mart. Es un
paso oculto, igual que `staging`. Si tu tabla es autocontenida, salta
este paso.

---

## Paso 8 — Modelo `marts` (lo que Lightdash va a leer)

`dbt/models/marts/fct_<algo>.sql` si cada fila es una transacción/evento,
o `dim_<algo>.sql` si es un catálogo. Referencia real (`fct_ordenes_compra.sql`):

```sql
select
    mtn.mi_tabla_folio,
    mtn.fecha,
    s.sucursal_nombre,
    p.producto_nombre,
    mtn.importe
from {{ ref('stg_mi_tabla_nueva') }} mtn
left join {{ ref('stg_sucursal') }} s on mtn.sucursal_id = s.sucursal_id
left join {{ ref('dim_producto') }} p on mtn.producto_id = p.producto_id
```

**Esta parte es la que determina qué aparece en Lightdash**: en
`dbt/models/marts/_marts.yml`, cada columna que quieras usar como filtro
necesita `meta.dimension`, y cada una que quieras sumar/contar necesita
`meta.metrics`:

```yaml
  - name: fct_mi_tabla_nueva
    description: "Descripción de negocio corta — qué es cada fila."
    columns:
      - name: fecha
        meta:
          dimension:
            type: date
            label: "Fecha"
      - name: sucursal_nombre
        meta:
          dimension:
            label: "Sucursal"
      - name: importe
        meta:
          metrics:
            total_importe:
              type: sum
              label: "Importe total ($)"
              format: "#,##0.00"
```

Corre el modelo (esto es lo que lo materializa de verdad en Postgres —
sin este paso, Lightdash no tiene columnas que ofrecer):

```bash
cd ~/ehalso/trivasa-bi-core/dbt
dbt run --select stg_mi_tabla_nueva+ --profiles-dir ~/.dbt
```

`--select stg_mi_tabla_nueva+` corre ese modelo y todo lo que depende de
él (el `+` al final). Revisa que haya corrido sin error antes de seguir.

---

## Paso 9 — Desplegar a Lightdash (CLI)

Ya documentado en [Stack de BI](stack-bi.md#deploy-de-lightdash-dbt--explores);
resumen accionable:

```bash
# Si no has hecho login en esta sesión de terminal:
lightdash login https://dash.frento.com.mx --token <PAT>
lightdash config set-project --uuid df98464b-9806-49f2-b5cb-2f99d47905ad

# El modelo YA debe estar corrido (paso 8) -- Lightdash lee columnas reales
# del warehouse, no solo el .yml.
lightdash deploy --exclude staging --profiles-dir ~/.dbt -y
```

⚠️ Si es la primera vez que despliegas este proyecto de Lightdash desde
cero (`--create` en vez de `deploy`), corre después
`lightdash set-warehouse --target lightdash -y` — sin esto la UI de
Lightdash intenta conectar a `localhost:5433` desde dentro de su propio
contenedor y truena con `ECONNREFUSED`. Ver el gotcha completo en
[Stack de BI](stack-bi.md#gotcha-host-del-warehouse--localhost-no-sirve-para-queries-2026-08-12).

Confirma que el explore nuevo aparece: en `https://dash.frento.com.mx`,
barra lateral izquierda → debe listarse `fct_mi_tabla_nueva` (o el nombre
que le hayas dado) junto a los explores existentes.

---

## Paso 10 — Construir el tablero (Lightdash, por GUI)

Desde aquí ya no hay CLI ni código — todo es clicks en
`https://dash.frento.com.mx`.

1. **Explore → elige tu tabla nueva** en la barra lateral
   (`fct_mi_tabla_nueva`). Se abre el panel de exploración con las
   dimensiones y métricas que definiste en `_marts.yml` (paso 8) —
   si algo no aparece, casi siempre es porque le faltó
   `meta.dimension`/`meta.metrics` en el `.yml`, no un problema de la UI.
2. **Marca las casillas** de las dimensiones (ej. "Sucursal", "Fecha") y
   métricas (ej. "Importe total ($)") que quieras ver juntas.
3. **Run query** (arriba a la derecha) — confirma que los números se ven
   razonables antes de guardar nada.
4. Elige el tipo de visualización en la pestaña **Chart** (tabla, barras,
   línea, big number, etc.) y ajusta ejes/formato ahí mismo.
5. **Save chart** — dale un nombre descriptivo (mismo criterio que los
   charts existentes en `lightdash/charts/`, ej.
   `kpi-requisiciones-vigentes.yml`: qué muestra + tipo de visual).
6. Para agregarlo a un tablero: abre el **dashboard** de destino (o crea
   uno nuevo con **Dashboards → Create dashboard**), entra a modo
   **Edit**, **Add tile → Saved chart**, elige el chart que acabas de
   guardar, acomódalo, y **Save changes** (arriba a la derecha — los
   cambios no quedan hasta este último click).

No hace falta tocar `lightdash/charts/` ni `lightdash/dashboards/` a mano
para esto — esos `.yml` son la versión "como código" de charts/dashboards
que ya existen (ver los archivos de `solicitudes-de-material-backlog-vivo.yml`
como ejemplo), útil como referencia de qué se puede configurar, pero el
flujo de este paso es 100% por GUI, como se pidió.

---

## Checklist de una página

- [ ] Paso 1 — PK única, cursor poblado, `.205` no escribe la tabla por su cuenta
- [ ] Paso 2 — backfill contra `.205` con `dlt.sources.incremental` activo desde el inicio
- [ ] Paso 3 — conteo de filas Postgres vs. `.205` coincide
- [ ] Paso 4 — función incremental contra `.207`, agregada a `run_incremental_207_all()`, agendada (ruta de cron verificada, no la vieja)
- [ ] Paso 5 — nada que hacer, `check_raw_freshness.py` la recoge sola
- [ ] Paso 6 — `stg_<tabla>.sql` + entrada en `_sources.yml`
- [ ] Paso 7 — `int_*.sql` solo si hace falta juntar varias tablas
- [ ] Paso 8 — `fct_`/`dim_` + `meta.dimension`/`meta.metrics` en `_marts.yml`, `dbt run --select ...+`
- [ ] Paso 9 — `lightdash deploy --exclude staging -y`, explore visible en la UI
- [ ] Paso 10 — chart armado por GUI, guardado, agregado a un dashboard, `Save changes`
