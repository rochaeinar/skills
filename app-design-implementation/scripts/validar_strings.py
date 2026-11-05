#!/usr/bin/env python3
"""Valida las traducciones de Android contra el inglés (values/strings.xml).

  python validar_strings.py app/src/main/res

Para cada values-*/strings.xml revisa: claves que faltan o sobran, marcadores distintos
(%1$s, %d, %s...), plurales sin la categoría "other", apóstrofos y comillas sin escapar,
y textos idénticos al inglés (posible texto sin traducir; solo aviso). Sale con 1 si hay errores.
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PH_RE = re.compile(r"%(?:\d+\$)?[-#+ 0,(]*\d*(?:\.\d+)?[sdfxXc%]")
UNESCAPED_RE = re.compile(r"(?<!\\)['\"]")


def load(path: Path):
    """{clave: texto} para <string> y {clave: {cantidad: texto}} para <plurals>; ignora translatable=false."""
    root = ET.parse(path).getroot()
    strings, plurals = {}, {}
    for el in root:
        name = el.get("name")
        if not name or el.get("translatable") == "false":
            continue
        if el.tag == "string":
            strings[name] = "".join(el.itertext())
        elif el.tag == "plurals":
            plurals[name] = {i.get("quantity"): "".join(i.itertext()) for i in el.findall("item")}
    return strings, plurals


def placeholders(text):
    return sorted(p for p in PH_RE.findall(text) if p != "%%")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    res = Path(sys.argv[1])
    base = res / "values" / "strings.xml"
    if not base.exists():
        print(f"No existe {base}")
        return 2
    en_s, en_p = load(base)
    errors = warnings = 0
    for path in sorted(res.glob("values-*/strings.xml")):
        lang = path.parent.name
        try:
            s, p = load(path)
        except ET.ParseError as e:
            print(f"[{lang}] XML inválido: {e}")
            errors += 1
            continue
        problems = []
        problems += [f"falta <string> {k}" for k in en_s if k not in s]
        problems += [f"sobra <string> {k}" for k in s if k not in en_s]
        problems += [f"falta <plurals> {k}" for k in en_p if k not in p]
        for k, text in s.items():
            if k in en_s and placeholders(text) != placeholders(en_s[k]):
                problems.append(f"marcadores distintos en {k}: {placeholders(text)} vs {placeholders(en_s[k])}")
            if UNESCAPED_RE.search(text) and not (text.startswith('"') and text.endswith('"')):
                problems.append(f"apóstrofo o comilla sin escapar en {k}")
        for k, items in p.items():
            if "other" not in items:
                problems.append(f"plurals {k} sin 'other'")
            if k in en_p:
                ref = placeholders(en_p[k].get("other", ""))
                for q, text in items.items():
                    if placeholders(text) != ref:
                        problems.append(f"marcadores distintos en {k}[{q}]")
        same = [k for k, t in s.items() if k in en_s and t == en_s[k] and len(t) > 3 and not PH_RE.fullmatch(t)]
        for msg in problems:
            print(f"[{lang}] {msg}")
        if same:
            print(f"[{lang}] aviso: {len(same)} textos iguales al inglés (¿sin traducir?): {', '.join(same[:8])}")
            warnings += 1
        errors += len(problems)
    print(f"{errors} errores, {warnings} idiomas con avisos")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
