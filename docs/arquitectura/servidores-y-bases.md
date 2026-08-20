# Servidores SQL Server y bases del ERP

> Qué servidor es cuál y qué base vive en cada uno. **Leer antes de escribir cualquier query** — es el error más caro de cometer, porque una consulta contra la base equivocada devuelve resultados plausibles pero falsos.
>
> Verificado 2026-08-10 contra los servidores en vivo. **Actualizado
> 2026-08-13: `TRIVASADB3` se movió de `.200` a `.205`** — ver nota al
> final de "Cuál usar para qué".

## Mapa de servidores

| Host | Rol | Bases relevantes |
|---|---|---|
| **`192.168.117.207`** | **Producción — sistema de registro** | `TRIVASADB` ← ERP vivo · `EMPRESAS_2` · `MPROARCHIVOS`, `COCINADB`, `MACIZO`, `TRIVASA2017` |
| **`192.168.117.205`** (`SVR-DEV`, aquí desde 2026-08-13) | Copias restauradas + staging | `TRIVASADB3` ← exploración, ahora aquí · `EMPRESAS_2`, `TRIVASADB`, `TRIVASADB2`, `MACIZO`, `MACIZO2`, `MPROARCHIVOS`, `TRIVASA2017`, `COCINADB`, `ReportServer` (SSRS) |
| **`192.168.117.200`** | Copia de `TRIVASADB3` **congelada** (dejó de recibir refresh, ver nota) — no usar para nada nuevo. `TRIVASADB` (sin el 3) sigue viva aquí, ver más abajo. | `TRIVASADB3` (vieja), `TRIVASADB`, `TRIVASADB2`, `EMPRESAS_2`, `EMPRESAS_3` |
| **`192.168.117.204`** | Origen de los primeros backfills de dlt | `TRIVASADB` |
| **`192.168.117.211`** | Share `SincronizarXml` — XMLs CFDI del SAT | (sistema de archivos) |

Motor: **SQL Server 2016 SP3-OD (13.0.6404.1)** sobre Windows Server 2022.

## Cuál usar para qué

| Necesidad | Base |
|---|---|
| Explorar, perfilar esquema, backfill histórico | `.205/TRIVASADB3` |
| Cifras oficiales, incrementales diarios, cualquier número que vaya a un reporte | `.207/TRIVASADB` |

Conexión **default** de `trivasa-bi-core/connections/`: `.205/TRIVASADB3` (`connection_205_trivasadb3.py`). No cambiar a `.207` salvo pedido explícito.

### 2026-08-13 — `TRIVASADB3` cambió de IP: `.200` → `.205`

Confirmado por evidencia de datos, no por aviso de infraestructura: `.205`
responde con el mismo catálogo de bases que `.200` tenía documentado
arriba (todo lo esperable de `SVR-DEV`), y su copia de `TRIVASADB3` está
**más fresca** que la que sigue en `.200`:

| Señal (`ZTRV_Solicitud_Material`) | `.200` | `.205` |
|---|---|---|
| `MAX(Fecha_Ult_Modif)` | 2026-08-10 15:58 | 2026-08-11 21:11 |
| Filas | 113,758 | 114,501 |

Lectura más probable: `.200` es ahora una copia **congelada** de `SVR-DEV`
que dejó de recibir el refresh periódico (sección de abajo), mientras el
servidor real sigue operando en `.205`. No confirmado con infraestructura.

⚠️ **Es específico a `TRIVASADB3`.** Para `TRIVASADB` (sin el 3, ya
marcada obsoleta más abajo) el patrón es el **inverso**: `.200/TRIVASADB`
sigue más fresca (`MAX(Fecha_Ult_Modif)` de `Consumo_Interno` 2026-08-12)
que `.205/TRIVASADB` (2026-04-24, copia vieja sin refrescar).
`connections/connection.py` (apunta a esa base) se dejó intacto en
`.200` a propósito — no asumir que todo el host se comporta igual para
todas sus bases. **Sin verificar todavía:** si el share CIFS de
`D:\BACKUP`/`D:\DATOS` (sección "Respaldos" más abajo) también se movió
a `.205`, o si sigue sirviéndose desde `.200`.

## `TRIVASADB3` no es producción

Es una **copia restaurada** (última: 2026-07-23, full, según `msdb.dbo.restorehistory`). Evidencia:

| Señal | `.200/TRIVASADB3` | `.207/TRIVASADB` |
|---|---|---|
| Movimientos/día (ago-2026) | ~30 | ~1,900 |
| `MAX(Fecha_Ult_Modif)` en `Movimiento` | — | al minuto |
| `Movimiento` filas | 4,516,659 | 4,548,991 |
| `Poliza_Detalle` filas | 14,275,918 | 14,411,645 |

El esquema es prácticamente idéntico (1,454 vs 1,449 tablas; 9 tablas `ZTRV_*` extra en `.200`, 4 `LOG_*` extra en `.207`) y el rezago total es **~0.7 %**. Por eso sirve como fuente de exploración y backfill.

**No se refresca sola:** no hay job de SQL Agent ni replicación. Cada refresh es una restauración manual del `.bak`. Si el análisis depende de datos recientes, revisar primero:

```sql
SELECT TOP 5 destination_database_name, restore_date, restore_type
FROM msdb.dbo.restorehistory ORDER BY restore_date DESC;
```

### ⚠️ Pero sí recibe escrituras propias

`TRIVASADB3` es la base más concurrida de `.200` (29 sesiones). Casi toda la escritura es de infraestructura, **no de negocio**:

- **`HangFire.*`** — scheduler de una app .NET llamada `Autenticacion` (host `trv930`), con 3 jobs recurrentes: `actualizar-fechas` (cron `0 6 * * *`), `cerrar-solicitudes`, `notificar-24h`. Es el módulo de **solicitudes de material** apuntado a `TRIVASADB3` como entorno de staging.
- **`oqs.*`** — Open Query Store, monitoreo de rendimiento de queries. No es dato de negocio.

Esto tiene una consecuencia práctica seria para los pipelines — ver [Gotcha del backfill](#gotcha-el-backfill-desde-200-puede-perder-datos-en-silencio).

### `.200/TRIVASADB` (sin el 3) está desactualizada

Nunca usarla. Un query filtrado a enero 2026 sobre `Consumo_Interno` regresó casi vacío ahí, mientras `TRIVASADB3` sí tenía datos. Fue el hallazgo que originó esta separación.

## `EMPRESAS_2` — la base de control del ERP

No es base de negocio. Registra **qué empresas existen y en qué base vive cada una**, más usuarios (`Operadores`, `Login_ERP`, `Perfiles`), menús, módulos y licencias.

Su tabla `Empresas` mapea:

| Clave | Base de datos | Razón social |
|---:|---|---|
| 15 | `TRIVASADB` | TRIVASA S.A. DE C.V. |
| 50 | `TRIVASA2017` | TRIVASA S.A. DE C.V. |
| 62 | `MACIZO` | FACILITADORES DE LA CONSTRUCCIÓN S.A. DE C.V. |
| 64 | `ERIXDB` | ERIX SA DE CV |
| 65 | `COCINADB` | Cocina Trivasa |
| 66 | `TRIVASADB2` | TRIVASA |
| **67** | **`TRIVASADB3`** | **TRIVASA** |
| 68 | `TRIVASADB4` | TRIVASA |

`EMPRESAS_3` es una copia vieja: su `Empresas` llega solo hasta la clave 65.

`EMPRESAS_2.Diccionario_Campos` **está vacía** (0 filas) — sería la fuente natural de descripciones de negocio por columna, pero hoy no aporta nada.

## Gotcha: el backfill desde `.200` puede perder datos en silencio

El patrón general es *backfill desde `.200`, incrementales contra `.207`*. **No aplica a tablas que `.200` escribe por su cuenta.**

Si `.200` tiene actividad propia sobre una tabla, `MAX(Fecha_Ult_Modif)` ahí es **la fecha de hoy**, no la del respaldo. Un backfill desde `.200` deja el cursor incremental en "ahora", y la primera corrida contra `.207` solo trae lo modificado **después** de ese instante — saltándose toda la historia intermedia, sin ningún error visible.

Pasó de verdad con las solicitudes de material: quedaron **690 filas de menos** en `ztrv_solicitud_material` (113,768 vs 114,458) con el cursor aparentemente al día.

**Comprobación obligatoria antes de backfillear desde `.200`:**

```sql
-- en .200/TRIVASADB3 — si devuelve una fecha reciente, .200 NO sirve como origen
SELECT MAX(Fecha_Ult_Modif) FROM <tabla>;
```

## Respaldos y sistema de archivos

Montados en ctunlinux por CIFS, **solo lectura**, usuario `bi_readonly`:

```
//192.168.117.200/C_readonly → /mnt/win200_c
//192.168.117.200/D_readonly → /mnt/win200_d
```

| Ruta | Contenido |
|---|---|
| `D:\BACKUP` | `TRIVASADB3.bak` (125 GB), `TRIVASADB_backup_*.bak`, `EMPRESAS_2_backup_*.bak`. De aquí sale cada refresh de `TRIVASADB3`. |
| `D:\DATOS` (716 GB) | Directorio de datos de SQL Server (`.mdf`/`.ldf`) + 53 archivos `.sqlaudit` |
| `C:\DATOS`, `C:\XML_PORTAL` | Vacías desde la vista `bi_readonly` |

Los `.sqlaudit` son de una auditoría **`Audit_Delete_DML`** (rastro de borrados). Existe a nivel servidor pero **sin especificación ligada a `TRIVASADB3`**: hoy no captura nada de esta base. Los borrados físicos no dejan rastro; las bajas lógicas sí (`Fecha_Baja` / `Es_Cve_Estado`).

### Cómo se configura el acceso (para replicar en otro host)

Requiere: paquete `cifs-utils`, y conectividad a `192.168.117.200` — misma
LAN física, o vía NetBird (la red `192.168.117.0/24` ya está anunciada ahí).

1. `apt install cifs-utils`
2. Crear `/root/.smbcreds-200` (permisos `600`, dueño root):
   ```
   username=bi_readonly
   password=<SMB_200_PASSWORD>
   domain=WORKGROUP
   ```
   Credenciales guardadas en Infisical, proyecto `secret-management`
   (`secrets.ehas.uk`), entorno `dev`, raíz `/`: `SMB_200_HOST`,
   `SMB_200_USERNAME`, `SMB_200_PASSWORD`, `SMB_200_DOMAIN`,
   `SMB_200_SHARE_C`, `SMB_200_SHARE_D`.
3. Agregar a `/etc/fstab`:
   ```
   //192.168.117.200/C_readonly  /mnt/win200_c  cifs  credentials=/root/.smbcreds-200,ro,uid=<user>,gid=<user>,iocharset=utf8,vers=3.0,file_mode=0444,dir_mode=0555,_netdev  0  0
   //192.168.117.200/D_readonly  /mnt/win200_d  cifs  credentials=/root/.smbcreds-200,ro,uid=<user>,gid=<user>,iocharset=utf8,vers=3.0,file_mode=0444,dir_mode=0555,_netdev  0  0
   ```
4. `mount -a`

En ctunlinux la conectividad es por LAN física (`192.168.117.0/24` directo
en `ens18`), no por el túnel NetBird activo en el host — aunque NetBird
también anuncia esa red, así que un host remoto sin acceso a la LAN física
puede llegar por ahí en su lugar.
