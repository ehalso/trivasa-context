# trivasa-context — instrucciones para Claude

Docs + proyectos curados de BI para Trivasa. Un solo lugar: código, queries,
estado, y contexto de negocio juntos. Servido como sitio estático con
ProperDocs + Material (Cloudflare Pages, ver docs/arquitectura/).

## Orden de lectura obligatorio al iniciar sesión

1. Este archivo.
2. `docs/index.md` — punto de entrada, qué proyectos existen.
3. El `index.md` del proyecto específico que se va a tocar (narrativa,
   decisiones) y su `PROGRESS.md` (estado vivo) — nunca asumir estado sin
   leer ambos primero.
4. `docs/schema/` relevante al dominio, si la tarea toca datos del ERP.

## Regla de oro

Nunca improvisar nombres de tabla, columna, servicio, o convención que no
estén confirmados en `docs/schema/` o verificados explícitamente con Esteban
en la conversación. Si hace falta un dato que no está documentado, preguntar
— no inventar. Esto incluye nombres de conexión, puertos, y rutas de
`trivasa-bi-core` — si no está en `docs/` de este repo, no se asume.

## Flujo git — doble pull, no solo uno

```text
git pull --ff-only origin main   # al iniciar sesión
... trabajo ...
git pull --ff-only origin main   # INMEDIATO antes del push, no lo saltes
git add .
git commit -m "mensaje descriptivo"
git push
```

Este repo lo puede tocar más de una sesión de Claude Code en paralelo (una
en tu WS, otra corriendo de forma autónoma en ctunlinux) — el pull del
inicio de sesión no cubre toda la ventana de trabajo si la tarea tarda.
El segundo pull, justo antes del push, reduce la carrera a los segundos
entre pull y push, que es lo más que se puede achicar sin coordinación
explícita entre sesiones.

Si ese segundo pull trae conflicto, es casi siempre en `PROGRESS.md` de
algún proyecto — se resuelve fusionando ambos lados (nunca descartando uno),
ya que normalmente son líneas de estado distintas, no contradictorias.

## Regla de promoción — nada llega aquí sin curar

Exploración cruda vive local, fuera de este repo (`~/por_ordenar/` o scratch
de turno en WS). Solo se promueve a `docs/proyectos/<x>/` código que ya
validó al 100%. Un commit de promoción trae código + actualización de
`index.md` juntos, nunca uno sin el otro.

## Dos archivos de estado por proyecto, nunca fusionados

- `index.md` — narrativa, decisiones, contexto. Se edita con cuidado.
- `PROGRESS.md` — estado vivo. Se sobreescribe libremente, incluso por un
  agente autónomo sin supervisión.

## scripts/gen_code_pages.py

Se ejecuta automático en cada `properdocs build` (gen-files + literate-nav,
mismos plugins de siempre — solo cambió el motor de build de mkdocs a
properdocs, ver docs/arquitectura/wiki-hosting.md). Recorre
`docs/proyectos/**/*.py` y `**/*.sql`, genera `docs/codigo/` con navegación
autoconstruida. Nunca editar `docs/codigo/` a mano.

## Cómo se sirve (producción)

Cloudflare Pages. `properdocs build` (config en `properdocs.yml`, ya no
`mkdocs.yml` — mkdocs entró en fork tras abandono de mantenimiento en 2026,
ver nota de decisión en docs/arquitectura/wiki-hosting.md) genera `site/`,
el deploy lo publica. Dominio: trivasa.ehas.uk.

Deploy es automático: Cloudflare Pages está conectado al repo de GitHub
(`ehalso/trivasa-context`, rama `main`) y corre
`pip install -r requirements-docs.txt --break-system-packages && properdocs
build` en cada push, publicando `site/`. `git push` desde cualquier lado
actualiza el sitio solo — no hace falta wrangler ni surface-ehas para el
día a día. Ver docs/arquitectura/wiki-hosting.md.

Nota de decisión: se evaluó self-hosted (nginx + Cloudflare Tunnel, mismo
patrón que Lightdash/Metabase/Perses) y se descartó a favor de Cloudflare
Pages por simplicidad de despliegue, aceptando que el contenido queda en
infraestructura de Cloudflare en vez de exclusivamente en ctunlinux. Ese
plan self-hosted nunca se llegó a ejecutar.

## Conexiones a BD

Se copian manualmente desde `trivasa-bi-core/connections/` cuando un
proyecto las necesita — no hay symlink ni dependencia automática entre
los dos repos.
