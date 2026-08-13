# varela-bot

Bot de Telegram (python-telegram-bot v20+, async, webhook) para personal de recursos
materiales de Trivasa: avisa que hay que notificar a un cliente que su material está
listo, y espera la foto del acuse de entrega/recolección.

**Código:** repo separado, [`ehalso/varela-bot`](https://github.com/ehalso/varela-bot)
(privado) — no vive dentro de este repo. Copia local en `~/varela-bot` en ctunlinux.

## Cómo funciona

1. Un job (`poller`, APScheduler) consulta TRIVASADB por folios con material listo,
   dedup por `folio_id`, y manda un mensaje de aviso al chat configurado.
2. La persona responde (reply) a ese mensaje con la foto del acuse. El bot empareja
   por `reply_to_message.message_id` contra `notificaciones.avisos`.
3. Si mandan la foto **sin reply**, cae a un fallback: `InlineKeyboardMarkup` con los
   avisos pendientes recientes del chat para elegir a mano.
4. `media_group_id` (álbumes de varias fotos) se bufferea con un debounce de 1.5s vía
   `job_queue`, porque en un álbum solo el primer mensaje suele traer el `reply`.
5. Otro job (`checker`, APScheduler) revisa folios con `check_at` vencido
   (`acuse_at + 2 días hábiles`, salta domingo) y, si el folio sigue pendiente en
   TRIVASADB, encadena un aviso nuevo (`aviso_num + 1`) para el mismo folio.

## Storage

- **Postgres propio y ligero**, contenedor dedicado (`varela-bot-postgres`,
  `postgres:16-alpine`) definido en el `docker-compose.yml` del propio repo del bot —
  **no** usa `trivasa_dw` (el warehouse). Decisión explícita 2026-08-12: separar el
  dato operativo del bot del dato analítico, aunque el costo de un Postgres aparte sea
  mínimo (~27 MB RAM, ~46 MB disco en reposo, medido en el contenedor real).
- Schema `notificaciones`, tabla `avisos` (`folio_id`, `aviso_num`, `message_id`,
  `chat_id`, `status`, `foto_file_id`, `acuse_at`, `check_at`, `checked`,
  `created_at`). DDL en `bot/schema.sql` del repo del bot, se aplica solo al arrancar
  (`CREATE ... IF NOT EXISTS`, sin migraciones).
- **Las fotos no se guardan en ningún lado propio.** Solo se persiste
  `foto_file_id` (referencia de Telegram); el binario se queda en los servidores de
  Telegram. Para verlo después haría falta `getFile(file_id)`, no implementado. Si el
  acuse necesita evidencia archivada independiente de Telegram (auditoría, o por si el
  bot cambia de token), es una decisión pendiente, no tomada.

## TRIVASADB — pendiente

`bot/trivasadb.py` (`fetch_folios_listos`, `folio_sigue_pendiente`) tiene **queries
placeholder** (`dbo.Folios` / `EstatusMaterial`) sin verificar contra el esquema real
de TRIVASADB — no confirmadas en `docs/schema/` de este repo. `bot/config.py` hace que
TRIVASADB sea opcional: si `TRIVASADB_HOST/USER/PASSWORD` faltan, `main.py` no agenda
`poller` ni `checker`, y el bot igual sirve el webhook de fotos/acuses. Así está hoy
(2026-08-12): TRIVASADB deshabilitado a propósito, probado solo el flujo Telegram +
Postgres.

## Infra en ctunlinux

- Puerto local `8091`, expuesto vía el túnel cloudflared existente (`ctunlinux`,
  mismo tunnel que Metabase/Lightdash/etc. — ver
  [Stack de BI en ctunlinux](../../arquitectura/stack-bi.md#acceso-remoto)),
  hostname `bot.frento.com.mx`.
- `run_webhook` de python-telegram-bot sirve HTTP plano — el TLS lo pone el túnel.
- Secret de bootstrap (`TELEGRAM_BOT_TOKEN`) respaldado en Infisical
  (`secrets.estebanalcocer.cloud`, proyecto `secret-management`, environment `dev`,
  UUID `b6567423-9986-448e-b2b8-dffe44fe1657`) **solo como copia de resguardo** — el
  bot lee todo de `.env` en runtime, no está conectado a Infisical. Decisión explícita
  2026-08-12, después de que una primera versión sí lo conectaba vía `infisical run` y
  se revirtió por ser más de lo que se pidió.

## Destinatario de los avisos

Configurado hoy como **chat individual** (`TELEGRAM_TARGET_CHAT_ID`, DM con Esteban
Alcocer Souza, `@Ealcocer`), no un grupo — el caso de uso real terminó siendo una sola
persona de recursos materiales, no un equipo. Si eso cambia a grupo, falta desactivar
el *privacy mode* del bot en BotFather (`/setprivacy` → Disable) o hacerlo admin, para
que pueda leer fotos que llegan como reply sin ser comandos — en DM no aplica, el bot
ve todo.

## Límite conocido: teclado de fallback

`MAX_OPCIONES_FALLBACK = 5` en `bot/handlers/photos.py` — si hay más de 5 avisos
pendientes en el chat, el teclado del fallback solo muestra los 5 más recientes
(`ORDER BY created_at DESC`). Los demás solo se pueden marcar respondiendo (reply)
directo a su mensaje original. No resuelto (paginar el teclado o dejar escribir el
folio como texto), abierto si el volumen real de pendientes lo justifica.

## Ver también

- [PROGRESS.md](PROGRESS.md) — estado vivo.
