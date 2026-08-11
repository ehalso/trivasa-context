---
description: "Audita docs/proyectos/ buscando inconsistencias — sin editar nada, solo reporta."
---

Recorre todo `docs/proyectos/` y reporta, sin modificar ningún archivo:

1. **Proyectos sin `index.md` o sin `PROGRESS.md`** — ambos archivos deben
   existir siempre, aunque `PROGRESS.md` esté vacío.
2. **`index.md` que no está enlazado desde `docs/index.md`** — página
   huérfana, nadie la encuentra navegando desde la raíz.
3. **Código en `docs/proyectos/<x>/` sin mención en `index.md`** — un
   script o query que existe pero la narrativa no explica qué es.
4. **`PROGRESS.md` con fecha de última modificación muy vieja vs. commits
   recientes en el proyecto** — señal de que el estado vivo quedó
   desactualizado respecto al código real.
5. **Referencias a tablas/columnas que no aparecen en `docs/schema/`** —
   posible dato inventado o schema no documentado todavía.
6. **Archivos sueltos en la raíz de un proyecto que deberían estar en
   `queries/` o `scripts/`** — desorden de convención de carpetas.

Presenta el resultado como lista corta y accionable, agrupada por tipo,
con la ruta del archivo. No apliques fixes automáticamente — Esteban
decide qué corregir y cuándo.
