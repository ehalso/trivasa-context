# varela-bot — estado vivo

## 2026-08-12

- Estructura inicial del proyecto creada (handlers, services, jobs, db.py, schema.sql,
  Dockerfile, docker-compose.yml) en `~/varela-bot`. Repo con commits locales, sin
  remote todavía.
- `TELEGRAM_BOT_TOKEN` recibido y respaldado en Infisical (`secret-management`, env
  `dev`) — solo como copia, no conectado al runtime del bot (ver decisión en
  `index.md`).
- Postgres propio (`varela-bot-postgres`) levantado vía `docker compose`, separado del
  warehouse `trivasa_dw` a propósito.
- Túnel cloudflared existente (`ctunlinux`) extendido: hostname nuevo
  `bot.frento.com.mx` → `127.0.0.1:8091`, agregado a
  `/etc/cloudflared/config.yml` y ruteado por DNS. Servicio reiniciado sin afectar los
  demás hostnames (`metabase`, `explore`, `monitor`, `data`, `dash`).
- `TELEGRAM_TARGET_CHAT_ID` capturado en vivo (chat individual, `@Ealcocer`) vía
  `getUpdates` después de que la persona mandó `/start` al bot.
- **Test end-to-end contra el bot real, corriendo (no mock):**
  - Aviso simulado (dos folios, `TEST-001`/`TEST-002`) creado con el mismo código que
    usaría el poller real (`crear_aviso` + `bot.send_message`).
  - Foto como reply al aviso → match directo, `status=acuse_recibido`,
    `foto_file_id` correcto (resolución más grande), `check_at = acuse_at + 2` días
    hábiles calculado bien.
  - Foto sin reply → fallback con teclado inline mostrado, botón tocado por el usuario
    real en Telegram → callback resolvió el aviso correcto.
  - Filas de prueba borradas después de confirmar.
- TRIVASADB queda **deshabilitado a propósito** (poller/checker no se agendan): las
  queries en `bot/trivasadb.py` son placeholder, no verificadas contra el esquema real.

## Pendiente

- [ ] Verificar/reescribir las queries de `bot/trivasadb.py` contra el esquema real de
  TRIVASADB (tabla de folios / estatus de material) — nada de esto está en
  `docs/schema/` de este repo todavía.
- [ ] Decidir si las credenciales de TRIVASADB para el bot son las mismas
  (`EALCOCER`) que usan otros scripts (`trivasa-bi-core/connections/connection_207.py`)
  o unas dedicadas.
- [ ] Decidir si se archivan las fotos del acuse fuera de Telegram (auditoría/respaldo)
  o se deja solo el `file_id`.
- [ ] Confirmar si el destinatario se queda como chat individual o pasa a ser un grupo
  (implica desactivar *privacy mode* en BotFather).
- [ ] Revisar el límite de 5 opciones en el teclado de fallback si el volumen real de
  avisos pendientes lo amerita.
- [ ] Crear repo remoto (GitHub) para `varela-bot` si se quiere respaldo/colaboración
  fuera de ctunlinux — hoy solo existe local.
