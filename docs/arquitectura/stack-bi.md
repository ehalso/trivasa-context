# Stack de BI en ctunlinux

> Qué corre en la máquina de BI, en qué puerto, y quién lo mantiene. Verificado 2026-08-12.

## La máquina

`ctunlinux` — Ubuntu 26.04 LTS. Es donde vive todo lo de BI: extracción, warehouse, transformación, dashboards y observabilidad.

## Flujo de datos

```
SQL Server .207/.204  ──dlt──►  PostgreSQL :5433/trivasa_dw  ──dbt Core──►  analytics_marts  ──►  Lightdash / Metabase
//.211/SincronizarXml ──py──►   raw_sat
```

## Servicios (docker)

Los `docker-compose.yml` viven en **`~/stack/`**, fuera de git — un yaml por servicio, nunca uno consolidado. Es config operativa de esta máquina, no código.

| Servicio | Contenedor | Puerto | Notas |
|---|---|---|---|
| **PostgreSQL warehouse** | `postgres-dw` (`postgres:16`) | `0.0.0.0:5433` | La base `trivasa_dw`. Único expuesto fuera de loopback junto con Metabase. |
| **Lightdash** | `lightdash` | `127.0.0.1:8090` | + `lightdash-db` (pgvector/pg15), `lightdash-minio`, `lightdash-headless-browser`. Público vía tunnel: `dash.frento.com.mx` |
| **Metabase** | `metabase-metabase-1` | `0.0.0.0:3000` | + su propia `postgres:16` |
| **Loki** | `loki` (`grafana/loki:3.7.6`) | `127.0.0.1:3100` | Destino de los checks de calidad |
| **Perses** | `perses` (`persesdev/perses:v0.54.0`) | `127.0.0.1:8080` | Dashboards de observabilidad |

**Lightdash usa volúmenes con nombre** (`lightdash_lightdash-db-data`, `lightdash_lightdash-minio-data`), persistentes entre `down`/`up`. Tras cambiar `.env`, siempre `down` + `up` — nunca solo `restart`, porque las variables de interpolación solo se leen al crear el contenedor.

## Repos y qué vive en cada uno

| Repo | Contenido |
|---|---|
| **`trivasa-bi-core`** | ELT como código: `dlt/` (ingesta), `dbt/` (transformación), `lightdash/`, `observability/`, `orchestration/`, `connections/` |
| **`trivasa-context`** | Este sitio: docs, decisiones, proyectos curados |
| **`~/por_ordenar/`** | Exploración cruda, **fuera de git**. Nada llega a `trivasa-context` sin curar. |
| **`~/stack/`** | docker-compose de cada servicio, sin git |

## Extracción — dlt, no Meltano

La ingesta corre con **[dlt](https://dlthub.com)** desde scripts Python en `trivasa-bi-core/dlt/`. No hay Meltano instalado ni ningún `meltano.yml` en la máquina.

Credenciales: destino Postgres en `dlt/.dlt/secrets.toml` (`[destination.postgres.credentials]`); orígenes SQL Server **hardcodeados en cada script**, no en `secrets.toml`. Todo lo que tenga credenciales va en `.gitignore`.

## Transformación — dbt Core

Proyecto `trivasa_dbt`, perfil en `~/.dbt/profiles.yml` (fuera del repo, se arma a mano por máquina).

| Capa | Materialización | Schema |
|---|---|---|
| `staging` | view | `analytics_staging` (marcado `hidden`) |
| `marts` | table | `analytics_marts` |

Además de `models/{staging,intermediate,marts}/`, el proyecto debe tener `seeds/`, `snapshots/`, `analyses/` y `packages.yml` — aunque estén vacíos, son el lugar oficial para no reinventar convención después.

## Orquestación — systemd timers

La convención de `trivasa-bi-core` es **systemd timers** (`~/.config/systemd/user/`), **no cron**, por consistencia con los servicios persistentes que ya usan systemd (cloudflared, etc.). Un `.service` + `.timer` por tarea agendada.

> ⚠️ **Estado real (2026-08-12): la migración no está hecha.** Los pipelines de dlt siguen agendados en el `crontab` del usuario `ealcocer`; el único timer systemd existente es `claude-skills-pull`. Ver la tabla de horarios en [Warehouse](../schema/warehouse.md#cron-actual).

## Observabilidad

`trivasa-bi-core/observability/checks/check_raw_freshness.py` compara, por cada tabla de `raw.*`, las filas modificadas en los últimos 30 días entre Postgres y `.207`, vía `Fecha_Ult_Modif`. Postea a Loki (`job=soda_real`) para verse en Perses, y escribe `last_status.txt` para consulta rápida.

Tolerancia antes de marcar `fail`: `max(5, 0.1 % del conteo origen)` — producción está viva y el check corre después de las cargas, así que unas pocas filas de diferencia son lag normal.

Sustituyó a `dvt-checks/`, que hacía column+schema checks con un contenedor Docker propio y resultó más pesado de lo necesario. No hay canal de notificación externo (decisión 2026-08-10: no vale la pena un bot dedicado solo para esto).

## `torep` — capturar output de scripts a HTML navegable

Helper personal en ctunlinux (no es parte de `trivasa-bi-core`, vive suelto en el home de `ealcocer`) para no perder el output de scripts Python de exploración/diagnóstico — prints, tracebacks, tablas de `rich` — que de otro modo solo quedan en la terminal.

- **Ejecutable:** `~/torep/torep` (bash). `~/torep` está en el `PATH` vía `~/.bashrc` (`export PATH="$HOME/torep:$PATH"`).
- **Uso:** `torep archivo` — detecta la extensión: `.py` corre con `python3`, `.sql` corre directo con `duckdb -f` (CLI puro, sin envoltura de Python — ver sección de DuckDB abajo). Cualquiera de los dos casos captura la sesión completa de terminal con `script`, la convierte a HTML con `aha --black`, y la agrega a un reporte acumulado por carpeta: `~/torep-www/<nombre-carpeta-del-script>.html`. Archivos de un mismo proyecto se van apilando en el mismo HTML, cada corrida con su propio bloque con encabezado `nombre.ext exit N`.
- **Reportes:** `~/torep-www/`, servido en `http://<ip-de-ctunlinux>:8000/` con `python3 -m http.server 8000 --directory ~/torep-www`, levantado a mano (`nohup` + `disown`, no hay unit de systemd todavía). Un `index.html` autogenerado en cada corrida lista los proyectos, ordenable por nombre o última corrida.

> ⚠️ **Gotcha (2026-08-14): `script` no propaga el exit code sin `-e`.** La primera versión usaba `script -qc "... python3 script.py" archivo` y leía `$?` después — pero `script` sin la flag `-e`/`--return` siempre devuelve el exit status de sí mismo (típicamente 0), no el del proceso hijo. Resultado: **todos los reportes decían `exit 0` aunque el script hubiera fallado con traceback y todo.** Fix: `script -qec "..." archivo` (flag `-e` agregada). Verificado corriendo un script con `sys.exit(1)` a propósito — antes de `-e` reportaba `exit 0`, después `exit 1`. Si se reescribe `torep`, no perder esta flag.

> ⚠️ **Gotcha (2026-08-14): `duckdb` se cuelga bajo la pty de `script` sin `-light-mode`.** Sin flag explícito de tema, `duckdb` auto-detecta si la terminal es clara u oscura mandando una consulta OSC de color de fondo y esperando la respuesta del emulador. Bajo la pty que crea `script` para `torep` no hay emulador real del otro lado que conteste — la consulta se queda colgada para siempre (visto primero corriendo un script que probaba los 18 modos de salida del CLI: se colgó justo al entrar al modo `column`, con result sets grandes). Fix: `torep` invoca `duckdb -light-mode -cmd '.pager off' -f archivo.sql` para `.sql` — la flag evita la auto-detección, y `-cmd '.pager off'` evita que un result set grande dispare el paginador (mismo problema, mismo síntoma: esperar input de una terminal que no está ahí).

## DuckDB CLI + conector MS SQL Server

Instalado 2026-08-14 para exploración rápida vía SQL directo contra SQL Server, sin pasar por Python/pandas/pymssql.

- **Instalación:** `curl -fsSL https://install.duckdb.org | sh` — deja el binario en `~/.duckdb/cli/<version>/duckdb` con symlink `latest`, y crea otro symlink en `~/.local/bin/duckdb` (ya en `PATH`).
- **Conector MS SQL Server:** no es built-in — es la extensión community `mssql` (`INSTALL mssql FROM community; LOAD mssql;`). Ojo: **no se llama `sqlserver`** ni `mssql_scanner` (esos nombres no existen en el repo community, dan 404).
- **Conexión:** `ATTACH 'Server=<host>,<puerto>;Database=<db>;User Id=<user>;Password=<pass>;TrustServerCertificate=yes' AS alias (TYPE mssql);` — el formato de connection string es distinto al de pymssql/sqlalchemy (`Server=host,puerto` con coma, no `host:puerto`). Probado contra `.205/TRIVASADB3` con las credenciales de `trivasa-bi-core/connections/connection_205_trivasadb3.py`. Tras el `ATTACH`, las tablas se referencian como `alias.dbo.NombreTabla`.
- Ver los dos gotchas de `-light-mode`/`.pager off` arriba — aplican a cualquier uso interactivo o via `torep`, no solo a `.sql` corridos por el helper.

## Acceso remoto

- **Cloudflare Tunnel** (`cloudflared`) — credenciales en `~/.cloudflared/` y `/etc/cloudflared/`. Ingress (`/etc/cloudflared/config.yml`), un hostname por servicio:

  | Hostname | Servicio local |
  |---|---|
  | `dash.frento.com.mx` | Lightdash (`127.0.0.1:8090`) |
  | `metabase.frento.com.mx` | Metabase (`localhost:3000`) |
  | `explore.frento.com.mx` | (`localhost:8501`) |
  | `data.frento.com.mx` | (`127.0.0.1:8080`, Perses) |
  | `monitor.frento.com.mx` | (`127.0.0.1:61208`) |
  | `bot.frento.com.mx` | `varela-bot` (`127.0.0.1:8091`) — no es BI, ver [proyectos/varela-bot](../proyectos/varela-bot/index.md) |

- **ZeroTier** y **RustDesk** instalados en el servidor Windows `.200`.

## Deploy de Lightdash (dbt → explores)

El CLI (`@lightdash/cli`) **no viene preinstalado** con el stack — se instala on-demand vía `npm install -g @lightdash/cli` en la máquina desde la que se despliega (hoy, directo en ctunlinux; compila un binding nativo de `ssh2`, tarda ~2 min).

**Login:** headless, con Personal Access Token — no con OAuth de navegador. El flujo OAuth (`lightdash login <url>`) abre un callback en `localhost:<puerto random>` que corre en la misma máquina que el CLI; si el CLI corre en ctunlinux y el navegador está en otra máquina, el callback nunca llega. Generar el PAT desde `https://dash.frento.com.mx` → *Settings → Personal Access Tokens*, luego:

```
lightdash login https://dash.frento.com.mx --token <PAT>
lightdash config set-project --uuid <project-uuid>   # fija el proyecto default
```

**Antes de desplegar, los modelos deben estar materializados de verdad** (`dbt run --profiles-dir ~/.dbt`) — Lightdash lee el catálogo físico del warehouse (columnas reales vía `information_schema`), no solo el `.yml`. Un modelo nunca corrido no tiene columnas que ofrecer como dimensiones.

> ⚠️ **Nota de decisión / gotcha (2026-08-12, corregida 2026-08-21):** `+meta: hidden: true` puesto a nivel `dbt_project.yml` (usado hoy para todo `models/staging/`) **no oculta el explore completo** — oculta las dimensiones individuales. Con 0 dimensiones visibles, Lightdash rechaza el modelo como explore inválido (`No dimensions available`).
>
> **`--exclude staging` YA NO BASTA.** Confirmado 2026-08-21: modelos de `intermediate` que no tienen su propio `meta.dimension` fallan con el mismo error `No dimensions available` — mismo mecanismo que staging, aunque no tengan `hidden: true` explícito. El comando real de deploy es:
>
> ```
> lightdash deploy --exclude staging,intermediate --profiles-dir ~/.dbt -y
> ```
>
> **Corrección sobre una creencia equivocada de esta misma nota:** `meta.dimension` en `_marts.yml` **no es lo que habilita** una columna como dimensión — dbt/Lightdash expone toda columna no oculta como dimensión por default; `meta.dimension` solo personaliza `label`/`type` de una dimensión que ya existiría de todas formas. No hacía falta agregarlo a una columna (ej. `folio`) solo para poder usarla en una tabla/explore.
>
> Con esto se despliegan los explores de `marts` (incluido `fct_transferencia`, agregado 2026-08-21 — deploy exitoso, 12/12 explores), que es lo que se consume en Lightdash de todas formas.

Proyecto activo en Lightdash: `trivasa_dw` (uuid `df98464b-9806-49f2-b5cb-2f99d47905ad`).

> ⚠️ **Riesgo abierto, sin resolver:** el password de `postgres-dw` en `~/stack/postgres-warehouse/.env` sigue siendo el placeholder por defecto — nunca se rotó a uno real. Pendiente de cambiar (recordar `down` + `up`, no `restart`, tras el cambio — ver nota de volúmenes arriba).

### Gotcha: host del warehouse — `localhost` no sirve para queries (2026-08-12)

`lightdash deploy --create` guarda en el proyecto la conexión al warehouse tal cual está en `~/.dbt/profiles.yml` (`host: localhost`) — correcto para `dbt run`, que corre en el **host** de ctunlinux. Pero las queries que corren desde la UI de Lightdash las ejecuta el **contenedor** `lightdash`, y ahí `localhost`/`127.0.0.1` apunta al propio contenedor, no al host. Resultado: al abrir cualquier explore, `Error loading results — connect ECONNREFUSED 127.0.0.1:5433`, aunque `dbt debug` y el deploy hayan salido limpios.

Fix aplicado:

1. `~/stack/lightdash/docker-compose.yml` — se agregó `extra_hosts: ["host.docker.internal:host-gateway"]` al servicio `lightdash`, para que ese hostname resuelva al host real (Docker 20.10+, confirmado con Docker 29.6.1). Requiere recrear el contenedor (`down` + `up`, no `restart`) para que tome efecto.
2. En `profiles.yml` se agregó un target extra `lightdash` (mismo warehouse, solo cambia `host` a `host.docker.internal`) — el target `prod` para `dbt run` en el host queda intacto.
3. `lightdash set-warehouse --target lightdash -y` — actualiza la conexión guardada del proyecto sin tocar el resto de su config. Este comando existe justo para esto; no hace falta editarlo a mano por la UI ni pegarle a la API directo.

Cualquier proyecto **nuevo** creado con `--create` va a nacer con el mismo problema — correr `set-warehouse --target lightdash` es parte del flujo, no un parche de una sola vez.

## Higiene antes de comitear

Revisar `git add -A -n` (dry-run) antes del commit real — ya pasó que `.env`/`secrets.toml` casi se cuelan. Checklist: sin `.env`, sin `secrets.toml`, sin `__pycache__`/`venv`, sin logs generados.
