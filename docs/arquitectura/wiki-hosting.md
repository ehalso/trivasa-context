# Hosting de la wiki (trivasa-context)

## Decisión

Cloudflare Pages. Dominio: trivasa.ehas.uk.

## Nota sobre el motor de build: mkdocs → properdocs

En 2026 MkDocs entró en crisis de mantenimiento: el autor original retuvo
control de PyPI para publicar un "MkDocs 2.0" incompatible con plugins y
temas existentes, y un ex-mantenedor forkeó el proyecto 1.x como
[ProperDocs](https://github.com/ProperDocs/properdocs) — drop-in
replacement, mismo formato de config. Este repo usa ProperDocs como motor
(`properdocs build`, config en `properdocs.yml`), manteniendo
`mkdocs-material` como theme (sigue funcionando: ProperDocs redirige los
imports `mkdocs.*` de forma transparente) y los plugins de siempre
(`mkdocs-gen-files`, `mkdocs-literate-nav`).

Nota aparte: `mkdocs-material` no migró a ProperDocs — sigue dependiendo
del `mkdocs` real y entra en mantenimiento final el 5 de noviembre de 2026,
con [Zensical](https://github.com/squidfunk) como sucesor anunciado por su
propio equipo. Si Material deja de funcionar sobre ProperDocs en algún
punto, evaluar migrar el theme a Zensical por separado — son rutas de
sucesión distintas dentro del mismo ecosistema.

## Cómo desplegar un cambio

Desde una máquina con wrangler autenticado (hoy: solo surface-ehas, como
ehalsou):

```bash
cd trivasa-context
git pull --ff-only origin main
pip install -r requirements-docs.txt --break-system-packages  # solo si cambiaron deps
properdocs build
npx wrangler pages deploy site --project-name=trivasa-context-wiki
```

## Estado del dominio custom

El proyecto Pages (`trivasa-context-wiki`) y el registro de dominio custom
(`trivasa.ehas.uk`) se crearon vía API de Cloudflare (`POST
.../pages/projects/trivasa-context-wiki/domains`), pero quedó en estado
`pending` — el token OAuth de `wrangler login` trae `zone:read` pero no
`dns_records:edit`, así que no pudo crear el CNAME automáticamente. Falta
completar manualmente uno de estos dos pasos en el dashboard:

- Cloudflare > Workers & Pages > `trivasa-context-wiki` > Custom domains
  — debería mostrar `trivasa.ehas.uk` como pendiente; reintentar/confirmar
  ahí para que la UI (con permisos completos del usuario) cree el CNAME, o
- Cloudflare > DNS de la zona `ehas.uk` > agregar manualmente un CNAME
  `trivasa` → `trivasa-context-wiki.pages.dev` (proxied).

Mientras tanto el sitio ya está en vivo en
`https://trivasa-context-wiki.pages.dev`.

## Pendiente

No hay redeploy automático. Un cambio en docs/ no se refleja en el sitio
hasta correr el deploy manual de arriba. Automatizar (sin resolver aún):
wrangler + auth en ctunlinux con systemd timer, o GitHub Actions con API
token de Cloudflare como secret (necesitaría scope `dns_records:edit`
también, para poder resolver el pendiente del dominio custom sin pasos
manuales).
