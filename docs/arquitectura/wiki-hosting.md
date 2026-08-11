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

Automático: Cloudflare Pages está conectado al repo de GitHub
(`ehalso/trivasa-context`, rama `main`, proyecto `trivasa-context-wiki`).
Cada `git push` a `main` dispara un build en la infraestructura de
Cloudflare que corre:

```bash
pip install -r requirements-docs.txt --break-system-packages && properdocs build
```

y publica el `destination_dir: site`. No requiere wrangler ni ninguna
máquina en particular — cualquier `git push` a `main` (desde cualquier
sesión de Claude Code o directo) actualiza el sitio en unos ~15-20
segundos.

Deploy manual (fallback, si el auto-build falla o para probar un cambio
sin pushear) sigue disponible desde una máquina con wrangler autenticado:

```bash
cd trivasa-context
properdocs build
npx wrangler pages deploy site --project-name=trivasa-context-wiki
```

## Estado del dominio custom

`trivasa.ehas.uk` está `active` en Cloudflare Pages (dominio + certificado
Google Trust Services confirmados vía API). El registro inicial se creó
por API con el token de `wrangler login` (que trae `zone:read` pero no
`dns_records:edit`, así que no pudo crear el CNAME solo); quedó resuelto
después, aparentemente vía dashboard.

**Posible falso positivo a vigilar:** al verificar desde este entorno,
`https://trivasa.ehas.uk` devolvió un 403 "Web Filter Violation — Nuevos
dominios registrados" con un certificado no confiable (TLS interceptado) —
signatura típica de un filtro de contenido/DNS de red bloqueando por
categoría "dominio recién registrado" (`ehas.uk` se registró el
2026-08-09). No parece ser un problema de Cloudflare ni del deploy —
`https://trivasa-context-wiki.pages.dev` sirve el mismo contenido sin
problema. Si el dominio custom no carga desde el navegador normal,
revisar el resolver DNS / filtro de red usado (NextDNS, Cisco Umbrella,
firewall corporativo, etc.) antes de tocar la config de Cloudflare.

## Gotcha: primer auto-deploy vacío al conectar Git

Al conectar `trivasa-context-wiki` al repo de GitHub, el proyecto quedó
sin `build_command`/`destination_dir` configurados. El primer push activó
un deploy automático que no corrió ningún build y publicó un
deployment vacío, que quedó marcado como el más reciente y rompió la
resolución de `assets/` (el HTML raíz seguía sirviéndose desde caché de
un deploy manual previo, pero CSS/JS devolvían 404 — mismatch entre el
deployment "latest" real y lo cacheado). Se corrigió configurando
`build_config.build_command` y `build_config.destination_dir=site` en el
proyecto (`PATCH .../pages/projects/trivasa-context-wiki`). Si el sitio
se ve sin estilos después de un push, es la primera sospecha: revisar
que el build_command siga configurado y que el build haya corrido
(`GET .../pages/projects/trivasa-context-wiki/deployments`, stage
`build` debe decir `success`, no saltarse).

## Pendiente

Nada crítico. Ideas para más adelante: notificación (email/Slack) cuando
un build automático falla; darle al token de CI/CD scope
`dns_records:edit` si se necesita volver a tocar el dominio custom sin
pasos manuales en dashboard.
