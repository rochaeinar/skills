#!/usr/bin/env python3
"""Genera la matriz de cobertura (pantallas y variantes) a partir de un lienzo de Claude Design.

Lee <carpeta>/canvas.json y cada *.dc.html. De cada tablero toma sus props enumerables
(p. ej. "v", "mode", "os") del atributo data-props, y arma una tabla con casillas para
código, unit/humo, Maestro y QA. Los tableros de flujo, adaptativos e idiomas se listan aparte.

Uso: python cobertura_diseno.py design/canvas --out impl/cobertura.md
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

PROPS_RE = re.compile(r"data-props='([^']*)'")
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
IMPORT_RE = re.compile(r'<dc-import\s+name="([^"]+)"')


def read_board(path: Path):
    text = path.read_text(encoding="utf-8")
    props = {}
    m = PROPS_RE.search(text)
    if m:
        try:
            props = json.loads(html.unescape(m.group(1)))
        except json.JSONDecodeError:
            props = {}
    enums = {k: v.get("options", []) for k, v in props.items()
             if isinstance(v, dict) and v.get("editor") == "enum"}
    bools = [k for k, v in props.items() if isinstance(v, dict) and v.get("editor") == "boolean"]
    title = TITLE_RE.search(text)
    imports = sorted(set(IMPORT_RE.findall(text)))
    return {"title": html.unescape(title.group(1).strip()) if title else path.stem,
            "enums": enums, "bools": bools, "imports": imports}


def kind_of(name: str, page: str) -> str:
    if name.startswith("Flow"):
        return "flujo"
    if name.startswith(("Adaptive", "Lang-", "A11y")) or page in ("adaptive", "languages"):
        return "variante-entorno"
    if name in ("Main.dc.html", "DesignSystem.dc.html"):
        return "sistema"
    return "pantalla"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("canvas_dir")
    ap.add_argument("--out", default="impl/cobertura.md")
    a = ap.parse_args()

    root = Path(a.canvas_dir)
    index_path = root / "canvas.json"
    if not index_path.exists():
        print(f"No existe {index_path}", file=sys.stderr)
        return 1
    index = json.loads(index_path.read_text(encoding="utf-8"))
    boards = index.get("boards", {})
    names = index.get("order") or sorted(boards)
    for p in sorted(root.glob("*.dc.html")):
        if p.name not in names:
            names.append(p.name)

    rows = {"pantalla": [], "variante-entorno": [], "flujo": [], "sistema": []}
    total_variants = 0
    for name in names:
        path = root / name
        if not path.exists():
            continue
        b = read_board(path)
        meta = boards.get(name, {})
        k = kind_of(name, meta.get("page", ""))
        if k == "pantalla":
            enums = b["enums"]
            main_key = "v" if "v" in enums else (next(iter(enums)) if enums else None)
            variants = enums.get(main_key, ["(única)"]) if main_key else ["(única)"]
            extra = {kk: vv for kk, vv in enums.items() if kk != main_key}
            extra_txt = "; ".join(f"{kk}: {', '.join(vv)}" for kk, vv in extra.items())
            themes = "claro + oscuro" if "dark" in b["bools"] else "—"
            for v in variants:
                total_variants += 1
                rows[k].append(f"| {meta.get('title', b['title'])} | `{name}` | {v} | {extra_txt or '—'} | {themes} | [ ] | [ ] | [ ] | [ ] |")
        else:
            uses = ", ".join(b["imports"]) or "—"
            rows[k].append(f"| {meta.get('title', b['title'])} | `{name}` | {uses} | [ ] | [ ] |")

    out = [f"# Cobertura del diseño — {index.get('title', '')}", "",
           f"Generado desde `{root.as_posix()}`. {len(rows['pantalla'])} filas de pantalla/variante. "
           "Cada fila se marca al implementarla, al tener su test (unit o humo), su flujo Maestro y al pasar QA.", "",
           "Además de cada variante: teléfono vertical/horizontal, tablet vertical/horizontal, claro/oscuro, RTL y fuente grande "
           "(ver la sección de variantes de entorno).", "",
           "## Pantallas y variantes", "",
           "| Pantalla | Tablero | Variante | Otras props | Tema | Código | Test | Maestro | QA |",
           "|---|---|---|---|---|---|---|---|---|", *rows["pantalla"], "",
           "## Variantes de entorno (adaptativo, idiomas, accesibilidad)", "",
           "| Tablero | Archivo | Pantallas que usa | Implementado | Probado |", "|---|---|---|---|---|", *rows["variante-entorno"], "",
           "## Flujos (secuencias que Maestro debe recorrer)", "",
           "| Flujo | Archivo | Pantallas | Implementado | Maestro |", "|---|---|---|---|---|", *rows["flujo"], "",
           "## Sistema de diseño", "",
           "| Tablero | Archivo | Usa | Tokens en código | Componentes |", "|---|---|---|---|---|", *rows["sistema"], ""]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(out), encoding="utf-8")
    print(f"{a.out}: {total_variants} variantes de pantalla, {len(rows['flujo'])} flujos, "
          f"{len(rows['variante-entorno'])} tableros de entorno")
    return 0


if __name__ == "__main__":
    sys.exit(main())
