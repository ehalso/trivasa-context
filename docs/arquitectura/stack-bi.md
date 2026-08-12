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
| **Lightdash** | `lightdash` | `127.0.0.1:8090` | + `lightdash-db` (pgvector/pg15), `lightdash-minio`, `lightdash-headless-browser` |
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

## Acceso remoto

- **Cloudflare Tunnel** (`cloudflared`) — credenciales en `~/.cloudflared/`.
- **ZeroTier** y **RustDesk** instalados en el servidor Windows `.200`.

## Higiene antes de comitear

Revisar `git add -A -n` (dry-run) antes del commit real — ya pasó que `.env`/`secrets.toml` casi se cuelan. Checklist: sin `.env`, sin `secrets.toml`, sin `__pycache__`/`venv`, sin logs generados.
