"""Genera páginas de referencia para cada script/query dentro de docs/proyectos/.
Se ejecuta automáticamente en cada build de mkdocs (plugin gen-files).
"""
from pathlib import Path
import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

proyectos_dir = Path("docs/proyectos")
extensiones = {".py": "python", ".sql": "sql"}

for path in sorted(proyectos_dir.rglob("*")):
    if path.suffix not in extensiones:
        continue

    rel_path = path.relative_to(".")
    doc_path = Path("codigo") / path.relative_to(proyectos_dir).with_suffix(path.suffix + ".md")
    full_doc_path = Path("docs") / doc_path

    nav_parts = list(doc_path.parts[:-1]) + [path.name]
    nav[nav_parts] = doc_path.as_posix()

    lang = extensiones[path.suffix]
    with mkdocs_gen_files.open(doc_path, "w") as f:
        f.write(f"# `{path.name}`\n\n")
        f.write(f"Ruta original: `{rel_path}`\n\n")
        f.write(f"```{lang}\n")
        f.write(path.read_text(encoding="utf-8", errors="replace"))
        f.write("\n```\n")

    mkdocs_gen_files.set_edit_path(full_doc_path, rel_path)

with mkdocs_gen_files.open("codigo/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
