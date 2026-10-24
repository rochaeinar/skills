"""Paso 3 de 5 de Modules/README.md: traduce la reflexión diaria de Bible Versions (coffee_*.dev) a otros idiomas
desde el español y deja coffee_<idioma>.dev en Modules/languages/<idioma>/modules, anotado en su pack.json (contents).
No arma ni sube paquetes: siguiente, pack.py build <idioma> (bible-language-pack) y luego bible-language-ship.

El original es Modules/common/es/coffee_es.dev (tabla DAILY: Id, Book, Chapter, Verse, VerseEnd, Comments). Cada idioma
guarda su traducción en languages/<idioma>/devotional/state.json con el hash del texto español de cada fila: si el
español cambia o crece, solo esas filas vuelven a quedar pendientes. Rutas: Modules/config.json (BIBLE_VERSIONS_CONFIG).

Comandos (python coffee.py <comando> ...):
  status                       estado de todos los idiomas
  check-source                 revisa coffee_es.dev (ids, referencias, textos)
  prepare <idioma> [--size N] [--ids 12,40]
                               arma las tandas pendientes (batches/todo-NNN.json); --ids agrega filas a corregir
  apply <idioma>               guarda las tandas traducidas (batches/done-NNN.json)
  import <idioma> <archivo>    toma como traducción vigente un coffee_*.dev existente
  validate <idioma>            controles de calidad -> report.md (sale con 1 si hay errores)
  build <idioma>               escribe el módulo coffee_<idioma>.dev
  integrate <idioma>           después de pack.py build: dailyImage y sizeInBytes en languages.json

El inglés y el español (en, es, es-lite) se rearman con  pack.py build en | es | es-lite  (antes: repack).
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import unicodedata
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TODAY = datetime.date.today().isoformat()
FIRST_NEW_ID = 100  # igual que bible-language-pack: los ids < 100 son los paquetes originales
ENGLISH_COFFEE_ID = 43

BOOKS = ["Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1Sam", "2Sam", "1Kgs", "2Kgs", "1Chr",
         "2Chr", "Ezra", "Neh", "Esth", "Job", "Ps", "Prov", "Eccl", "Song", "Isa", "Jer", "Lam", "Ezek", "Dan",
         "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal", "Matt", "Mark",
         "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim",
         "2Tim", "Titus", "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John", "Jude", "Rev"]

# Escritura de pack.json -> prefijos de unicodedata.name() que cuentan como esa escritura
SCRIPTS = {
    "Latina": ("LATIN",), "Cirílica": ("CYRILLIC",), "Han": ("CJK",), "Kanji/Kana": ("CJK", "HIRAGANA", "KATAKANA"),
    "Hangul": ("HANGUL",), "Árabe (RTL)": ("ARABIC",), "Devanagari": ("DEVANAGARI",), "Tamil": ("TAMIL",),
    "Telugu": ("TELUGU",), "Kannada": ("KANNADA",), "Malayalam": ("MALAYALAM",), "Birmana": ("MYANMAR",),
    "Ge'ez (etíope)": ("ETHIOPIC",), "Ge'ez": ("ETHIOPIC",), "Bengalí": ("BENGALI",), "Gujarati": ("GUJARATI",),
    "Gurmukhi": ("GURMUKHI",), "Tailandesa": ("THAI",), "Jemer": ("KHMER",), "Hebrea": ("HEBREW",), "Griega": ("GREEK",),
}

# Palabras que solo tiene el español (para, que, vida... también están en portugués o italiano)
SPANISH_WORDS = {"dios", "nuestra", "nuestro", "nuestras", "nuestros", "también", "señor", "ustedes", "tienes",
                 "eres", "hacer", "nosotros", "ellos", "cuando", "siempre", "puedes", "debemos"}
ENGLISH_WORDS = {"the", "and", "with", "your", "that", "this", "life", "lord", "for", "our", "who", "will"}
ATTRIBUTIONS = ["Paul Tripp", "C.S. Lewis", "C. S. Lewis", "John Newton", "Spurgeon", "Corrie ten Boom", "Oswald Chambers",
                "Elliot", "R. C. Sproul", "Kierkegaard"]


# ---------------------------------------------------------------- configuración y destinos

DEFAULT_CONFIG = "D:/Documents/BibleVersions/Modules/config.json"


def cfg():
    p = Path(os.environ.get("BIBLE_VERSIONS_CONFIG") or DEFAULT_CONFIG)
    if not p.exists():
        fail(f"Falta {p} (ver Modules/README.md)")
    c = json.loads(p.read_text(encoding="utf-8"))
    root = p.parent
    c["app_repo"] = Path(c["app_repo"])
    c["packs_dir"] = root / "languages"
    c["source"] = root / "common" / "es" / "coffee_es.dev"
    c["english"] = root / "common" / "en" / "coffee_en.dev"
    c["rv1960"] = root / "languages" / "es" / "modules" / "reina-valera-1960.bblx"
    c["cdn_dir"] = root / "cdn" / "bible"
    c["registry"] = c["app_repo"] / "cdn" / "bible" / "module-ids.json"
    c["languages_json"] = c["app_repo"] / "app" / "src" / "main" / "assets" / "languages.json"
    c["manifest"] = c["app_repo"] / "cdn" / "bible" / "manifest.json"
    return c


def fail(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def write_text(path, text, encoding="utf-8"):
    """Escribe con el fin de línea que ya tiene el archivo (LF si es nuevo): en Windows write_text pondría CRLF."""
    path = Path(path)
    crlf = path.exists() and b"\r\n" in path.read_bytes()
    text = text.replace("\r\n", "\n")
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode(encoding))


def target(c, name):
    """El idioma pedido: 'en' (common/en/coffee_en.dev) o la carpeta / código de un idioma de Modules/languages."""
    if name == "en":
        return {"key": "en", "lang": "en", "script": "Latina", "kind": "english",
                "out": c["english"],
                "bible": c["packs_dir"] / "en" / "modules" / "king-james-version.bblx",
                "work": c["packs_dir"] / "en" / "devotional"}
    for d in sorted(c["packs_dir"].iterdir()):
        pj = d / "pack.json"
        if not pj.exists():
            continue
        pack = json.loads(pj.read_text(encoding="utf-8"))
        if pack.get("kind") == "base":  # en, es, es-lite: the original and the English, not translations
            continue
        if name in (d.name, pack.get("module_language"), pack.get("lang")):
            lang = pack["module_language"]
            bible = next((d / "modules" / m["file"] for m in pack.get("build", {}).get("modules", [])
                          if m.get("source") == pack.get("default_bible")), None)
            script = pack.get("script", "Latina")
            if script.startswith("Latina"):  # "Latina (diacríticos)"
                script = "Latina"
            return {"key": d.name, "lang": lang, "script": script, "kind": "pack", "pack_dir": d, "pack": pack, "out": d / "modules" / f"coffee_{lang}.dev",
                    "bible": bible, "work": d / "devotional", "name": pack.get("language_name", d.name)}
    fail(f"No conozco el idioma '{name}': use 'en' o una carpeta de {c['packs_dir']}")


def all_targets(c):
    names = ["en"] + [d.name for d in sorted(c["packs_dir"].iterdir()) if (d / "pack.json").exists()
                      and json.loads((d / "pack.json").read_text(encoding="utf-8")).get("kind") != "base"]
    return [target(c, n) for n in names]


# ---------------------------------------------------------------- datos

def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def source_rows(c):
    con = sqlite3.connect(f"file:{c['source']}?mode=ro", uri=True)
    rows = con.execute("select Id, Book, Chapter, Verse, VerseEnd, Comments, rowid from DAILY order by Id").fetchall()
    con.close()
    return [{"id": r[0], "book": r[1], "chapter": r[2], "verse": r[3], "verse_end": r[4], "es": r[5] or "", "rowid": r[6]}
            for r in rows]


def ref(r):
    book = BOOKS[r["book"] - 1] if 1 <= r["book"] <= 66 else f"Libro{r['book']}"
    v = f"{r['verse']}" if r["verse_end"] in (None, r["verse"]) else f"{r['verse']}-{r['verse_end']}"
    return f"{book} {r['chapter']}:{v}"


def verse_text(path, r, limit=420):
    if not path or not Path(path).exists():
        return None
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    end = min(r["verse_end"] or r["verse"], r["verse"] + 5)
    rows = con.execute("select Scripture from Bible where Book=? and Chapter=? and Verse between ? and ? order by Verse",
                       (r["book"], r["chapter"], r["verse"], end)).fetchall()
    con.close()
    text = re.sub(r"\s+", " ", " ".join(x[0] for x in rows if x[0])).strip()
    return text[:limit] + ("…" if len(text) > limit else "") if text else None


def english_rows(c):
    p = c["english"]
    if not p.exists():
        return {}
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    out = dict(con.execute("select Id, Comments from DAILY"))
    con.close()
    return out


def load_state(t):
    p = t["work"] / "state.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"lang": t["lang"], "rows": {}}


def save_state(t, state):
    t["work"].mkdir(parents=True, exist_ok=True)
    state["updated"] = TODAY
    write_text(t["work"] / "state.json", json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def pending(src, state):
    rows = state["rows"]
    return [r for r in src if str(r["id"]) not in rows or rows[str(r["id"])]["es"] != sha(r["es"])]


def registry(c):
    return json.loads(c["registry"].read_text(encoding="utf-8"))


# ---------------------------------------------------------------- check-source

def check_source(c, quiet=False):
    src = source_rows(c)
    errors, warnings = [], []
    ids = [r["id"] for r in src]
    if len(ids) != len(set(ids)):
        errors.append("hay Id repetidos")
    if ids != list(range(1, len(ids) + 1)):
        warnings.append("los Id no son 1..N seguidos (la app elige la reflexión por Id)")
    con = sqlite3.connect(f"file:{c['rv1960']}?mode=ro", uri=True)
    mx = {(b, ch): v for b, ch, v in con.execute("select Book, Chapter, max(Verse) from Bible group by Book, Chapter")}
    con.close()
    seen = {}
    for r in src:
        m = mx.get((r["book"], r["chapter"]))
        ve = r["verse_end"] if r["verse_end"] is not None else r["verse"]
        if m is None or not r["verse"] or r["verse"] < 1 or ve < r["verse"] or ve > m:
            errors.append(f"{r['id']}: referencia inválida {r['book']} {r['chapter']}:{r['verse']}-{r['verse_end']} "
                          f"(el capítulo tiene {m} versículos)")
        if not r["es"].strip():
            errors.append(f"{r['id']}: texto vacío")
        elif r["es"] != r["es"].strip() or "  " in r["es"] or "\n" in r["es"]:
            warnings.append(f"{r['id']}: espacios de más o saltos de línea")
        seen.setdefault(r["es"].strip(), []).append(r["id"])
    for ids_ in seen.values():
        if len(ids_) > 1:
            warnings.append(f"texto repetido en {ids_}")
    if not quiet or errors:
        print(f"coffee_es.dev: {len(src)} reflexiones, {len(errors)} errores, {len(warnings)} advertencias")
        for e in errors:
            print("  ERROR", e)
        if not quiet:
            for w in warnings:
                print("  aviso", w)
    return src, errors


def cmd_check_source(a):
    _, errors = check_source(cfg())
    sys.exit(1 if errors else 0)


# ---------------------------------------------------------------- status

def cmd_status(a):
    c = cfg()
    src = source_rows(c)
    langs = {}
    if c["languages_json"].exists():
        langs = {e["code"]: e for e in json.loads(c["languages_json"].read_text(encoding="utf-8"))["languages"]}
    print(f"Original: {c['source']} ({len(src)} reflexiones)\n")
    print(f"{'idioma':10} {'traducidas':>10} {'pendientes':>10}  módulo              dailyImage")
    for t in all_targets(c):
        state = load_state(t)
        pend = len(pending(src, state))
        built = t["out"].exists()
        mod = t["out"].name if built else "-"
        di = "43 (en)" if t["lang"] == "en" else str(langs.get(t["lang"], {}).get("dailyImage", "no está en la app"))
        print(f"{t['key']:10} {len(src) - pend:>10} {pend:>10}  {mod:19} {di}")


# ---------------------------------------------------------------- prepare / apply / import

def cmd_prepare(a):
    c = cfg()
    t = target(c, a.lang)
    src, errors = check_source(c, quiet=True)
    if errors:
        fail("corrija coffee_es.dev antes de traducir (python coffee.py check-source)")
    bdir = t["work"] / "batches"
    if bdir.exists() and list(bdir.glob("done-*.json")):
        fail(f"hay tandas traducidas sin aplicar en {bdir}: python coffee.py apply {t['key']}")
    if bdir.exists():
        shutil.rmtree(bdir)
    bdir.mkdir(parents=True)
    state = load_state(t)
    todo = pending(src, state)
    if a.ids:  # corregir filas ya traducidas: entran con su traducción en "previous"
        wanted = {int(x) for x in a.ids.split(",")}
        todo = [r for r in src if r["id"] in wanted or r in todo]
    en = english_rows(c)
    glossary = t["work"] / "glossary.md"
    if not glossary.exists():
        write_text(glossary, GLOSSARY_TEMPLATE.format(lang=t["lang"], name=t.get("name", t["lang"]),
                                                     bible=t["bible"].name if t["bible"] else "-"), encoding="utf-8")
    for n in range(0, len(todo), a.size):
        items = []
        for r in todo[n:n + a.size]:
            item = {"id": r["id"], "ref": ref(r), "es": r["es"]}
            if t["lang"] != "en" and en.get(r["id"]):
                item["en"] = en[r["id"]]
            prev = state["rows"].get(str(r["id"]))
            if prev:
                item["previous"] = prev["text"]  # el español cambió: ajustar la traducción anterior
            vt = verse_text(c["rv1960"], r)
            if vt:
                item["verse_es"] = vt
            vl = verse_text(t["bible"], r) if t["lang"] != "es" else None
            if vl:
                item["verse"] = vl
            item["es_sha"] = sha(r["es"])
            items.append(item)
        write_text(bdir / f"todo-{n // a.size + 1:03}.json", json.dumps(items, ensure_ascii=False, indent=1) + "\n",
                                                             encoding="utf-8")
    nb = len(list(bdir.glob("todo-*.json")))
    print(f"{t['key']}: {len(todo)} reflexiones pendientes en {nb} tandas -> {bdir}")
    print(f"Glosario y registro: {glossary}")
    if todo:
        print("Traducir cada todo-NNN.json a done-NNN.json ({\"<id>\": \"texto\"}) y luego: "
              f"python coffee.py apply {t['key']}")


def cmd_apply(a):
    c = cfg()
    t = target(c, a.lang)
    bdir = t["work"] / "batches"
    state = load_state(t)
    current = {str(r["id"]): sha(r["es"]) for r in source_rows(c)}
    done_files = sorted(bdir.glob("done-*.json")) if bdir.exists() else []
    if not done_files:
        fail(f"no hay tandas traducidas (done-*.json) en {bdir}")
    applied = 0
    for df in done_files:
        tf = df.with_name(df.name.replace("done-", "todo-"))
        if not tf.exists():
            fail(f"{df.name} no tiene su {tf.name}")
        todo = {str(i["id"]): i for i in json.loads(tf.read_text(encoding="utf-8"))}
        done = json.loads(df.read_text(encoding="utf-8"))
        extra = set(done) - set(todo)
        if extra:
            fail(f"{df.name}: ids que no estaban en la tanda: {sorted(extra)}")
        missing = set(todo) - set(done)
        for k, text in done.items():
            text = re.sub(r"[  ]{2,}", " ", (text or "").replace("\n", " ")).strip()
            if not text:
                fail(f"{df.name}: la reflexión {k} está vacía")
            state["rows"][k] = {"es": todo[k]["es_sha"], "text": text}
            if current.get(k) != todo[k]["es_sha"]:
                print(f"  aviso {k}: el español cambió después de preparar la tanda; queda pendiente otra vez")
            applied += 1
        if missing:
            print(f"  aviso {df.name}: faltan {sorted(missing, key=int)}; quedan pendientes")
        df.unlink()
        tf.unlink()
    save_state(t, state)
    left = len(pending(source_rows(c), state))
    print(f"{t['key']}: {applied} reflexiones guardadas, {left} pendientes")
    print(f"Siguiente: python coffee.py {'prepare' if left else 'validate'} {t['key']}")


def cmd_import(a):
    c = cfg()
    t = target(c, a.lang)
    con = sqlite3.connect(f"file:{a.file}?mode=ro", uri=True)
    rows = dict(con.execute("select Id, Comments from DAILY"))
    con.close()
    state = load_state(t)
    n = 0
    for r in source_rows(c):
        text = rows.get(r["id"])
        if text and text.strip() and (not a.only_missing or str(r["id"]) not in state["rows"]):
            state["rows"][str(r["id"])] = {"es": sha(r["es"]), "text": text.strip()}
            n += 1
    save_state(t, state)
    print(f"{t['key']}: {n} reflexiones importadas de {a.file} como traducción del español actual")


# ---------------------------------------------------------------- validate

def letters_by_script(text):
    out = {}
    for ch in text:
        if ch.isalpha():
            name = unicodedata.name(ch, "")
            if name.startswith("MODIFIER LETTER"):  # el apóstrofo ʼ del igbo u oromo no es de otra escritura
                continue
            out[name.split(" ")[0]] = out.get(name.split(" ")[0], 0) + 1
    return out


def validate(c, t, write=True):
    src = source_rows(c)
    state = load_state(t)
    errors, warnings = [], []
    expected = SCRIPTS.get(t["script"]) or SCRIPTS.get(t["script"].split(" (")[0])
    if not expected:
        errors.append(f"escritura desconocida '{t['script']}': agregarla a SCRIPTS en coffee.py")
        expected = ("LATIN",)
    by_es = {}
    for r in src:
        k = str(r["id"])
        row = state["rows"].get(k)
        if not row:
            errors.append(f"{k}: sin traducir")
            continue
        if row["es"] != sha(r["es"]):
            errors.append(f"{k}: el español cambió, falta actualizar la traducción")
        text = row["text"]
        if re.search(r"[<>{}\\]|\*\*|\n", text):
            errors.append(f"{k}: marcas o saltos de línea: {text[:80]}")
        counts = letters_by_script(text)
        total = sum(counts.values()) or 1
        own = sum(v for s, v in counts.items() if s in expected)
        if t["script"] == "Latina":
            if own / total < 0.95:
                errors.append(f"{k}: letras fuera del alfabeto latino ({own}/{total})")
        elif own / total < 0.85:
            errors.append(f"{k}: solo {own}/{total} letras en {t['script']}")
        words = set(re.findall(r"[a-záéíóúñ]+", text.lower()))
        if t["lang"] != "en" and t["script"] == "Latina" and len(words & ENGLISH_WORDS) >= 3:
            warnings.append(f"{k}: ¿quedó en inglés? ({', '.join(sorted(words & ENGLISH_WORDS))})")
        if t["script"] == "Latina" and len(words & SPANISH_WORDS) >= 2:
            warnings.append(f"{k}: ¿quedó en español? ({', '.join(sorted(words & SPANISH_WORDS))})")
        ratio = len(text) / max(len(r["es"]), 1)
        lo, hi = {"Han": (0.2, 0.9), "Kanji/Kana": (0.2, 0.9), "Hangul": (0.3, 1.0),
                  "Árabe (RTL)": (0.45, 1.6), "Ge'ez (etíope)": (0.3, 1.0)}.get(t["script"], (0.55, 2.0))
        if not lo <= ratio <= hi:
            warnings.append(f"{k}: largo raro ({len(text)} letras contra {len(r['es'])} del español)")
        for num in re.findall(r"\d+", r["es"]):
            if num not in text:
                warnings.append(f"{k}: falta el número {num}")
        if "📖" in r["es"] and "📖" not in text:
            warnings.append(f"{k}: falta el emoji 📖")
        if t["script"] == "Latina":
            for name in ATTRIBUTIONS:
                surname = name.split()[-1]
                if name in r["es"] and surname not in text:
                    warnings.append(f"{k}: falta la atribución {name}")
        if text.count('"') % 2 or text.count("«") != text.count("»") or text.count("「") != text.count("」"):
            warnings.append(f"{k}: comillas sin pareja")
        by_es.setdefault(r["es"].strip(), []).append((k, text))
    for group in by_es.values():
        if len({x[1] for x in group}) > 1:
            warnings.append(f"textos iguales en español traducidos distinto: {[x[0] for x in group]}")
    extra = set(state["rows"]) - {str(r["id"]) for r in src}
    if extra:
        warnings.append(f"filas que ya no están en el español (se quitan al construir): {sorted(extra, key=int)}")
    if write:
        t["work"].mkdir(parents=True, exist_ok=True)
        rep = [f"# Validación de la reflexión: {t['key']} ({t['lang']})\n", f"Fecha: {TODAY}  ",
               f"Original: `{c['source']}` ({len(src)} reflexiones)  ", f"Escritura esperada: {t['script']}\n",
               f"## Errores ({len(errors)})\n"] + [f"- {e}" for e in errors] + \
              ["", f"## Advertencias ({len(warnings)})\n"] + [f"- {w}" for w in warnings] + [""]
        write_text(t["work"] / "report.md", "\n".join(rep), encoding="utf-8")
    return errors, warnings


def cmd_validate(a):
    c = cfg()
    t = target(c, a.lang)
    errors, warnings = validate(c, t)
    print(f"{t['key']}: {len(errors)} errores, {len(warnings)} advertencias -> {t['work'] / 'report.md'}")
    for e in errors[:20]:
        print("  ERROR", e)
    for w in warnings[:20]:
        print("  aviso", w)
    sys.exit(1 if errors else 0)


# ---------------------------------------------------------------- build

def module_id(c, t):
    if t["kind"] == "english":
        return ENGLISH_COFFEE_ID, None
    reg = registry(c)
    fname = t["out"].name
    prev = next((m for m in reg["modules"] if m["file"] == fname and m["language"] == t["lang"]), None)
    if prev:
        return prev["id"], None
    mid = max([FIRST_NEW_ID - 1] + [m["id"] for m in reg["modules"] if m["id"] >= FIRST_NEW_ID]) + 1
    reg["modules"].append({"id": mid, "language": t["lang"], "file": fname, "abbreviation": "", "pack": t["key"],
                           "source": "coffee_es.dev", "added": TODAY})
    reg["modules"].sort(key=lambda m: m["id"])
    return mid, reg


def cmd_build(a):
    c = cfg()
    t = target(c, a.lang)
    errors, warnings = validate(c, t)
    if errors:
        fail(f"{len(errors)} errores de validación ({t['work'] / 'report.md'})")
    mid, reg = module_id(c, t)
    src = source_rows(c)
    state = load_state(t)
    tmp = t["work"] / f"_{t['out'].name}"
    shutil.copyfile(c["source"], tmp)  # mismo esquema que el original
    con = sqlite3.connect(tmp)
    for r in src:
        con.execute("update DAILY set Comments=? where Id=?", (state["rows"][str(r["id"])]["text"], r["id"]))
    con.execute("update Details set Id=?, Language=?", (mid, t["lang"]))
    con.commit()
    assert con.execute("pragma integrity_check").fetchone()[0] == "ok"
    assert con.execute("select count(*) from DAILY").fetchone()[0] == len(src)
    assert con.execute("select Id, Language from Details").fetchall() == [(mid, t["lang"])]
    con.execute("vacuum")
    con.close()
    if t["out"].exists():
        bdir = t["work"] / "backups"
        bdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(t["out"], bdir / f"{t['out'].stem}-{time.strftime('%Y%m%d-%H%M%S')}.dev")
    t["out"].parent.mkdir(parents=True, exist_ok=True)
    shutil.move(tmp, t["out"])
    if reg:
        write_text(c["registry"], json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Id nuevo {mid} registrado en {c['registry']}")
    print(f"OK: {t['out']} (Id {mid}, {len(src)} reflexiones, {len(warnings)} advertencias)")
    if t["kind"] == "english":
        print("Siguiente: python <bible-language-pack>/scripts/pack.py build en  (y es / es-lite si cambió el español)")
        return
    # pack.json contents: this language's coffee in place of the English one (the only entry this skill touches).
    pack = json.loads((t["pack_dir"] / "pack.json").read_text(encoding="utf-8"))
    contents = [x for x in pack.get("contents", []) if x["file"] not in ("coffee_en.dev", t["out"].name)]
    pack["contents"] = contents + [{"from": "modules", "file": t["out"].name}]
    write_text(t["pack_dir"] / "pack.json", json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"pack.json: {t['out'].name} en contents (reemplaza a common/en coffee_en.dev)")
    print(f"Siguiente: python <bible-language-pack>/scripts/pack.py build {t['key']}  y luego  "
          f"python coffee.py integrate {t['key']}")


# ---------------------------------------------------------------- integrate

def cmd_integrate(a):
    c = cfg()
    t = target(c, a.lang)
    if t["kind"] != "pack":
        fail("integrate es para los idiomas de Modules/languages (el inglés y el español van con pack.py build en / es / es-lite)")
    pack = json.loads((t["pack_dir"] / "pack.json").read_text(encoding="utf-8"))
    b = pack.get("build")
    obb = c["cdn_dir"] / "modules" / b["file"] if b else None
    if not obb or not obb.exists():
        fail(f"falta el paquete: pack.py build {t['key']}")
    with zipfile.ZipFile(obb) as z:
        if t["out"].name not in z.namelist():
            fail(f"{obb.name} no trae {t['out'].name}: vuelva a correr pack.py build {t['key']} (después de coffee.py build)")
    mid, _ = module_id(c, t)
    text = c["languages_json"].read_text(encoding="utf-8")
    m = re.search(r'\{[^{}]*"code":\s*"' + re.escape(t["lang"]) + r'"[^{}]*\}', text)
    if not m:
        print(f"{t['lang']} todavía no está en languages.json: queda listo en el paquete para cuando se integre "
              f"(bible-language-ship pone dailyImage {mid} y sizeInBytes {b['size']})")
        return
    block = m.group(0)
    new = re.sub(r'"dailyImage":\s*\d+', f'"dailyImage": {mid}', block)
    new = re.sub(r'"sizeInBytes":\s*\d+', f'"sizeInBytes": {b["size"]}', new)
    write_text(c["languages_json"], text.replace(block, new), encoding="utf-8")
    print(f"languages.json: {t['lang']} dailyImage {mid}, sizeInBytes {b['size']}")
    print(f"Siguiente (con permiso del usuario): ship.py cdn {t['key']} (bible-language-ship, paso 4), publish-manifest.ps1 y una versión "
          f"nueva de la app (languages.json va dentro del APK)")


GLOSSARY_TEMPLATE = """# Glosario y decisiones: {name} ({lang})

Biblia del idioma (para los términos): `{bible}`

Llenar ANTES de la primera tanda y respetarlo en todas. Usar las palabras de esta Biblia.

| Español | {lang} | Nota |
|---|---|---|
| Dios | | |
| Señor | | |
| Jesús / Cristo / Jesucristo | | |
| Espíritu Santo | | |
| gracia | | |
| fe | | |
| Palabra de Dios / Su Palabra | | |
| oración / orar | | |
| bendición / bendecir | | |
| pecado | | |
| salvación | | |
| Biblia | | |

- Tratamiento del lector (tú/usted, registro):
- Mayúscula en los pronombres de Dios (Él, Su):
- Comillas:
- Atribuciones (Paul Tripp, C.S. Lewis…): se escriben

## Bitácora

- {lang}: (fecha) qué se tradujo, dudas resueltas con el inglés, reflexiones a revisar por un hablante nativo
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("check-source").set_defaults(fn=cmd_check_source)
    p = sub.add_parser("prepare")
    p.add_argument("lang")
    p.add_argument("--size", type=int, default=40)
    p.add_argument("--ids", help="filas ya traducidas para corregir, separadas por coma (12,40)")
    p.set_defaults(fn=cmd_prepare)
    for name, fn in (("apply", cmd_apply), ("validate", cmd_validate), ("build", cmd_build), ("integrate", cmd_integrate)):
        p = sub.add_parser(name)
        p.add_argument("lang")
        p.set_defaults(fn=fn)
    p = sub.add_parser("import")
    p.add_argument("lang")
    p.add_argument("file")
    p.add_argument("--only-missing", action="store_true")
    p.set_defaults(fn=cmd_import)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
