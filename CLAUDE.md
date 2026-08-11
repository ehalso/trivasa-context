# Convenciones — trivasa-context

## Qué es este repo
Documentación + proyectos curados, agent-first: un solo lugar donde un
agente encuentra código, queries, estado del proyecto, y contexto de negocio
juntos. Servido como sitio con MkDocs Material.

## Regla de promoción — nada llega aquí sin curar
El trabajo de exploración vive local (no en este repo, ej. `~/por_ordenar/`
o el scratch de turno). Solo se promueve a `docs/proyectos/<x>/` lo que YA
validó al 100% — código funcionando, queries correctas. No se sincroniza
exploración cruda ni intentos fallidos.

## Cada proyecto en docs/proyectos/<x>/ tiene DOS archivos de estado,
## nunca fusionados:
- `index.md` — narrativa, decisiones, contexto. Se edita con cuidado,
  en milestones.
- `PROGRESS.md` — estado vivo. Se sobreescribe libremente, incluso por un
  agente autónomo sin supervisión (ej. Claude Code corriendo de noche en
  ctunlinux). Nunca meter narrativa cuidada aquí, se puede perder.

## scripts/gen_code_pages.py
Se ejecuta automático en cada `mkdocs build` (plugin gen-files +
literate-nav). Recorre `docs/proyectos/**/*.py` y `**/*.sql`, genera
`docs/codigo/` con cada archivo envuelto en bloque de código, navegación
autoconstruida. Nunca editar `docs/codigo/` a mano — se regenera solo.

## Cómo se sirve (producción)
NO es `mkdocs serve` (eso es solo para iterar en desarrollo, vía tmux
`mkdocs-wiki`). El sitio real: `mkdocs build` → genera `site/` → nginx en
`~/stack/mkdocs-wiki/` lo sirve (bind-mount de solo lectura) → expuesto vía
Cloudflare Tunnel. Un systemd timer (`mkdocs-wiki-rebuild.timer`) hace
`git pull` + rebuild automático cada pocos minutos — así un `git push` desde
cualquier lado actualiza el sitio solo, sin intervención manual.

## Conexiones a BD
Si un proyecto necesita conectarse a TRIVASADB3, la conexión se copia
manualmente desde `trivasa-bi-core/connections/` — no hay symlink ni
dependencia automática entre los dos repos.
