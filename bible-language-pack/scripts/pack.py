"""Language packs for Bible Versions: one language at a time, from the downloaded Bibles to the
module the app downloads from the CDN (cdn.timelesslabs.app/bible/modules/<lang>-vN.obb).

  pack.py status                         every language of the tracker and how far it got
  pack.py init <lang>                    packs/<lang>/pack.json with the candidate Bibles
  pack.py fetch <lang> getbible:<abbr>   downloads a whole Bible from getBible in ONE request (a better copy of the same
                                         version, e.g. the Synodal with its brackets) into BibleVersionsSelected + manifest + pack.json
  pack.py import <lang>                  reads the chosen Bibles, cleans them and maps them to the app's versification
  pack.py validate <lang>                quality checks -> report.md, review.html; exit 1 if there are errors
  pack.py criteria <lang> [--fetch N]    the pastor's step: criteria.json with every problem and key verse, evidence
                                         from the same version online (cached, rate limited) and proposed solutions
  pack.py verify <lang> <REF> [--bible id]   one verse in our copy, the same version online, RV1960 and KJV
  pack.py apply <lang>                   applies the decisions of criteria.json (only allowed fixes), imports and validates
  pack.py review <lang>                  writes review.html and report.md again (after deciding), without touching the approval
  pack.py approve <lang> --by <name>     records the review (needs 0 errors and every problem of criteria.json decided)
  pack.py build <lang>                   .bblx modules + the English modules -> <lang>-vN.obb, verified like the app reads it
  pack.py publish <lang> [--yes]         uploads the .obb to R2 and adds it to cdn/bible/manifest.json (without --yes: the plan)

<lang> is the tracker code (pt-BR, fr, sw, zh-Hans...). Paths: config.json next to this script.
"""
import argparse, collections, ctypes, datetime, difflib, hashlib, html, io, json, math, os, random, re, shutil, time
import urllib.error
import sqlite3, subprocess, sys, unicodedata, urllib.request, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
ASSETS = SKILL / "assets"
TODAY = datetime.date.today().isoformat()

BOOKS = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZK DAN HOS "
         "JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM "
         "HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
BOOKNUM = {b: i for i, b in enumerate(BOOKS, 1)}
NT_FIRST = 40
# Book codes some eBible VPL files use instead of the USFM ones.
ALIASES = {"SOL": "SNG", "EZE": "EZK", "JOE": "JOL", "NAH": "NAM", "MAR": "MRK", "JOH": "JHN", "PHI": "PHP", "JAM": "JAS",
           "1JO": "1JN", "2JO": "2JN", "3JO": "3JN", "ECL": "ECC", "OBD": "OBA", "JDE": "JUD"}
# Books outside the 66 that a source may carry (deuterocanon / apocrypha): dropped on import.
DEUTERO = {"TOB", "JDT", "ESG", "WIS", "SIR", "BAR", "LJE", "S3Y", "SUS", "BEL", "1MA", "2MA", "3MA", "4MA", "1ES", "2ES",
           "MAN", "PS2", "ODA", "PSS", "EZA", "5EZ", "6EZ", "DAG", "LAO", "JUB", "ENO", "REP", "4BA", "LBA", "FRT", "INT",
           "GLO", "TDX", "NDX", "CNC", "XXA", "XXB", "XXC", "XXD", "XXE", "XXF", "XXG", "BAK", "OTH", "ADE", "PSA151"}
# Verses that the critical text leaves out: a modern translation may have them empty (warning, not error).
OMITTED_OK = {"MAT 17:21", "MAT 18:11", "MAT 23:14", "MRK 7:16", "MRK 9:44", "MRK 9:46", "MRK 11:26", "MRK 15:28",
              "LUK 17:36", "LUK 23:17", "JHN 5:4", "ACT 8:37", "ACT 15:34", "ACT 24:7", "ACT 28:29", "ROM 16:24"}
# Writing systems of the tracker's "Escritura" column -> Unicode name prefixes.
SCRIPTS = {"latina": ["LATIN"], "cirílica": ["CYRILLIC"], "árabe": ["ARABIC"], "devanagari": ["DEVANAGARI"],
           "han": ["CJK"], "hangul": ["HANGUL"], "kanji/kana": ["CJK", "HIRAGANA", "KATAKANA"], "tamil": ["TAMIL"],
           "telugu": ["TELUGU"], "kannada": ["KANNADA"], "malayalam": ["MALAYALAM"], "birmana": ["MYANMAR"],
           "ge'ez": ["ETHIOPIC"]}
NO_SPACES = {"CJK", "HIRAGANA", "KATAKANA", "MYANMAR"}  # no word splitting: skip the word checks
RTL = {"ARABIC", "HEBREW"}
# The English modules every new pack carries for now (files of the English pack, same names and ids).
ENGLISH_MODULES = ["quiz_en.db", "coffee_en.dev", "references_en.db", "jamieson-fausset-brown.cmtx",
                   "normalPlan.db", "chronologicalPlan.db", "flexiblePlan.db"]
ENGLISH_DEFAULTS = {"commentary": 37, "daily_image": 43, "quiz": 44, "reference": 47}
FIRST_NEW_ID = 100
# Tracker code -> the code the app, the manifest and Details.Language use (Android's locale language).
MODULE_LANGUAGE = {"pt-BR": "pt", "tl / fil": "fil", "ak / tw": "ak", "zh-Hans": "zh-hans", "zh-Hant": "zh-hant"}


# ---------------------------------------------------------------------------------------------- config
def cfg():
    p = Path(os.environ.get("BIBLE_PACK_CONFIG") or HERE / "config.json")  # another config for tests
    if not p.exists():
        fail(f"Missing {p}: see SETUP.md")
    c = json.loads(p.read_text(encoding="utf-8"))
    for k in ("bibles_dir", "tracker", "health_report", "packs_dir", "app_repo"):
        c[k] = Path(c[k])
    return c


def fail(msg, code=1):
    print(f"ERROR: {msg}")
    sys.exit(code)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pack_dir(c, lang):
    return c["packs_dir"] / lang.replace(" / ", "-").replace("/", "-")


def load_pack(c, lang):
    p = pack_dir(c, lang) / "pack.json"
    if not p.exists():
        fail(f"No {p}: run  pack.py init {lang}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_pack(c, lang, pack):
    p = pack_dir(c, lang) / "pack.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------------- tracker
def tracker_rows(c):
    """Rows of the language tables: {code: {column: value}}."""
    rows, header = {}, None
    for line in c["tracker"].read_text(encoding="utf-8").split("\n"):
        cells = [x.strip() for x in line.split("|")]
        if len(cells) < 6:
            continue
        if "Código" in cells and "Idioma" in cells:
            header = cells
            continue
        if header and len(cells) == len(header) and cells[1].isdigit():
            rows[cells[header.index("Código")]] = dict(zip(header, cells))
    return rows


def tracker_set(c, lang, column, value, log=None):
    text = c["tracker"].read_text(encoding="utf-8")
    out, header, done = [], None, False
    for line in text.split("\n"):
        cells = line.split("|")
        stripped = [x.strip() for x in cells]
        if "Código" in stripped and "Idioma" in stripped:
            header = stripped
        elif header and len(cells) == len(header) and stripped[1].isdigit() and stripped[header.index("Código")] == lang:
            cells[header.index(column)] = f" {value} "
            line, done = "|".join(cells), True
        out.append(line)
    if not done:
        print(f"  (tracker: no row for {lang})")
        return
    text = "\n".join(out)
    if log:
        text = text.replace("| Fecha | Idioma | Cambio |\n|---|---|---|\n",
                            f"| Fecha | Idioma | Cambio |\n|---|---|---|\n| {TODAY} | {lang} | {log} |\n", 1)
    c["tracker"].write_text(text, encoding="utf-8", newline="\n")
    print(f"  tracker: {lang} {column} = {value}")


def tracker_log(c, lang, log):
    text = c["tracker"].read_text(encoding="utf-8")
    head = "| Fecha | Idioma | Cambio |\n|---|---|---|\n"
    if head in text:
        c["tracker"].write_text(text.replace(head, head + f"| {TODAY} | {lang} | {log} |\n", 1), encoding="utf-8", newline="\n")


def eliminated_ids(c):
    """Bibles rejected by healthReport.md ('Biblias eliminadas' table): ids and file names in backticks."""
    text = c["health_report"].read_text(encoding="utf-8")
    m = re.search(r"## Biblias eliminadas.*?\n(.*?)\n## ", text, re.S)
    ids = set()
    for line in (m.group(1) if m else "").split("\n"):
        cells = line.split("|")
        if len(cells) < 4:
            continue
        for tok in re.findall(r"`([^`]+)`", cells[2]):  # only the "Biblia" column (the reason may name a kept one)
            for part in re.split(r"[ /]+", tok):
                part = part.strip()
                if part:
                    ids.add(part.replace(".sqlite", "").replace("bss_", ""))
    return ids


def health_notes(c, sid):
    text = c["health_report"].read_text(encoding="utf-8")
    return [l.strip() for l in text.split("\n") if f"`{sid}`" in l and "⚠️" in l]


# ---------------------------------------------------------------------------------------------- versification
# Lines of SIL's tables that are wrong, checked verse by verse against the RV1960 (SIL warns its mappings are not
# validated). Sinodal ISA 3:19 = RV 3:19-20, so 3:20 "перстни и кольца в носу" = RV 3:21 "los anillos..." (rsc.vrs has
# the right line).
VRS_FIXES = {"rso": {"ISA 3:20-25 = ISA 3:16-21": "ISA 3:20-25 = ISA 3:21-26"}}


_PAIRS = {}  # every mapping line of each table, in order (one verse may appear in several)


def parse_vrs(name):
    counts, maps = {}, {}
    for line in (ASSETS / "vrs" / f"{name}.vrs").read_text(encoding="utf-8").split("\n"):
        line = VRS_FIXES.get(name, {}).get(line.strip(), line.strip())
        m = re.match(r"^([1-4A-Z]{3}) (\d+):(\d+)(?:-(\d+))? = ([1-4A-Z]{3}) (\d+):(\d+)(?:-(\d+))?\s*$", line)
        if m:
            b1, c1, v1, v1e, b2, c2, v2, v2e = m.groups()
            if b1 not in BOOKNUM:
                continue
            if b2 not in BOOKNUM:
                # Inside a canonical book, a deuterocanonical addition ("DAN 3:24-90 = DAG 3:24-90", the Prayer of
                # Azariah): None = not part of the 66 books, dropped on import.
                for k in range(int(v1e or v1) - int(v1) + 1):
                    maps.setdefault((b1, int(c1), int(v1) + k), None)
                continue
            n = int(v1e or v1) - int(v1) + 1
            for k in range(n):
                # One verse of this scheme = two of the other ("LEV 14:55 = LEV 14:55" and "= LEV 14:56"):
                # it goes to the first one; the second stays empty (combined verse). All the pairs are kept for
                # the way back: "PSA 51:0 = PSA 51:1" and "= PSA 51:2" (a two-verse Hebrew title) both go to 51:0.
                pair = ((b1, int(c1), int(v1) + k), (b2, int(c2), int(v2) + k))
                maps.setdefault(*pair)
                _PAIRS.setdefault(name, []).append(pair)
            continue
        p = line.split()
        if p and p[0] in BOOKNUM and len(p) > 1 and re.match(r"^\d+:\d+$", p[1]):
            counts[p[0]] = {int(a): int(b) for a, b in (x.split(":") for x in p[1:] if re.match(r"^\d+:\d+$", x))}
    return counts, maps


_VRS = {}


def vrs(name):
    if name not in _VRS:
        _VRS[name] = parse_vrs(name)
    return _VRS[name]


_INV = {}


def eng_from_org():
    if not _INV:
        vrs("eng")
        for e, o in _PAIRS.get("eng", []):
            _INV.setdefault(o, e)  # every org verse of a mapping, also the second of a split title
    return _INV


def app_counts():
    """The app's versification: eng.vrs (RSV/RVR) with 3 John 14 and Revelation 12 verses as in the KJV/RV60 modules."""
    counts = {b: dict(ch) for b, ch in vrs("eng")[0].items()}
    counts["3JN"][1] = 14
    counts["REV"][12] = 17
    return counts


def to_app(ref, scheme):
    """(book, ch, v) in `scheme` -> (book, ch, v) in the app's numbering (v may be 0: a Psalm title), or None for a
    deuterocanonical addition inside a canonical book."""
    if scheme != "eng":
        ref = vrs(scheme)[1].get(ref, ref)  # scheme -> org
        if ref is None:
            return None
        ref = eng_from_org().get(ref, ref)  # org -> eng
    b, ch, v = ref
    if (b, ch, v) == ("3JN", 1, 15):
        return ("3JN", 1, 14)
    if (b, ch, v) == ("REV", 12, 18):
        return ("REV", 13, 1)
    return ref


SCHEMES = ("eng", "org", "rso", "lxx", "vul", "rsc")


def detect_scheme(chapter_max):
    """Per chapter, the versification whose size matches the source's (many Bibles mix them: the Louis Segond
    follows the Hebrew numbering in Exodus 7-8 and the English one in the rest of the book). A chapter that
    matches the English size keeps its numbering; the others take the first scheme that fits, preferring the
    one most of that book uses. chapter_max: {(book, ch): max verse}.
    Returns ({(book, ch): scheme}, chapters matched, chapters)."""
    per_ch, matched = {}, 0
    for bk in {b for b, _ in chapter_max}:
        chs = {ch: mx for (b, ch), mx in chapter_max.items() if b == bk}
        sizes = {name: (app_counts() if name == "eng" else vrs(name)[0]).get(bk, {}) for name in SCHEMES}
        fits = {name: {ch for ch, mx in chs.items() if sizes[name].get(ch) == mx} for name in SCHEMES}
        # The book's own scheme is the one that fits most of its chapters (eng wins ties). A chapter keeps it when
        # it fits: in the Synodal Psalter every Psalm is shifted, and a chapter that happens to have the English
        # size must still be shifted. Only the chapters it doesn't fit try the English size, then the others.
        order = sorted(SCHEMES, key=lambda n: (-len(fits[n]), n != "eng"))
        dominant = order[0]
        for ch in chs:
            if ch in fits[dominant]:
                scheme = dominant
            elif ch in fits["eng"]:
                scheme = "eng"
            else:
                scheme = next((n for n in order if ch in fits[n]), dominant)
            per_ch[(bk, ch)] = scheme
            matched += ch in fits[scheme]
    return per_ch, matched, len(chapter_max)


# ---------------------------------------------------------------------------------------------- reading sources
def read_ebible(path):
    z = zipfile.ZipFile(path)
    name = next(n for n in z.namelist() if n.endswith("_vpl.txt"))
    verses, skipped = [], collections.Counter()
    for line in z.read(name).decode("utf-8-sig").split("\n"):
        m = re.match(r"^([1-4A-Z]{3}) (\d+):(\d+)\s?(.*)$", line.rstrip("\r"))
        if not m:
            continue
        b = ALIASES.get(m.group(1), m.group(1))
        if b not in BOOKNUM:
            skipped[b] += 1
            continue
        verses.append((b, int(m.group(2)), int(m.group(3)), m.group(4)))
    return verses, skipped


def read_getbible(path):
    """A whole translation from api.getbible.net/v2/<abbr>.json: books by KJV number (1-66), the rest dropped."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    verses, skipped = [], collections.Counter()
    for bk in d["books"]:
        nr = int(bk["nr"])
        for ch in bk["chapters"]:
            for v in ch["verses"]:
                if 1 <= nr <= 66:
                    text = re.sub(r"<note>.*?</note>", "", html.unescape(v["text"]), flags=re.S)  # editor's notes
                    verses.append((BOOKS[nr - 1], int(v["chapter"]), int(v["verse"]), text))
                else:
                    skipped[str(nr)] += 1
    return verses, skipped


def read_bss(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    verses, skipped = [], collections.Counter()
    for b, ch, v, t in con.execute("select book, chapter, verse, text from verses order by book, chapter, verse"):
        if not 1 <= b <= 66:
            skipped[str(b)] += 1
            continue
        verses.append((BOOKS[b - 1], ch, v, t or ""))
    con.close()
    return verses, skipped


CLEAN_RULES = [
    ("ref_marker", re.compile(r"[\[(]\d+[:\-]\d+[\])]\s*")),         # [3:19], (22:1), (50-2): original numbering
    ("usfm", re.compile(r"\\\+?[a-z]+\d*\*?\s?")),                    # \w, \f ... \f*
    ("html", re.compile(r"</?[a-zA-Z][^>]*>")),
    ("pilcrow", re.compile(r"[¶]")),
    ("control", re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u200b\ufeff]")),
]


def clean(text, stats):
    t = unicodedata.normalize("NFC", text)
    if t != text:
        stats["nfc"] += 1
    for name, rx in CLEAN_RULES:
        t2 = rx.sub("" if name != "usfm" else "", t)
        if t2 != t:
            stats[name] += 1
            t = t2
    if "{" in t or "}" in t or "\\" in t:  # the app renders verses as RTF: braces and backslashes would break it
        stats["rtf_chars"] += 1
        t = t.replace("{", "(").replace("}", ")").replace("\\", "/")
    t2 = re.sub(r"\s+([,.;:!?»”])", r"\1", re.sub(r"\s{2,}", " ", t)).strip()
    if t2 != t.strip():
        stats["spacing"] += 1
    return t2


# ---------------------------------------------------------------------------------------------- commands
def cmd_status(a):
    c = cfg()
    rows = tracker_rows(c)
    print(f"{'Código':10} {'Biblia en el tracker':48} {'pack':8} {'validación':12} {'aprobado':10} {'build':8}")
    for code, r in rows.items():
        d = pack_dir(c, code)
        p = json.loads((d / "pack.json").read_text(encoding="utf-8")) if (d / "pack.json").exists() else {}
        val = p.get("validation", {})
        print(f"{code:10} {r.get('Versión / Licencia', '')[:48]:48} {'sí' if p else '-':8} "
              f"{(str(val.get('errors')) + ' err') if val else '-':12} {'sí' if p.get('approval') else '-':10} "
              f"{p.get('build', {}).get('file', '-'):8}")


def cmd_init(a):
    c = cfg()
    rows = tracker_rows(c)
    if a.lang not in rows:
        fail(f"{a.lang} is not a code of the tracker. Codes: {', '.join(rows)}")
    manifest = json.loads((c["bibles_dir"] / "bibles-manifest.json").read_text(encoding="utf-8"))
    gone = eliminated_ids(c)
    cands = []
    for b in manifest["bibles"]:
        if b["tracker_code"] != a.lang:
            continue
        lic = (b.get("licence") or "") + " " + (b.get("copyright") or "")
        nc = bool(re.search(r"non-?commercial|noncommercial|no comercial|NC-ND|for profit", lic, re.I))
        books = b.get("books") or (b.get("ot_books", 0) + b.get("nt_books", 0))
        cands.append({
            "id": b["id"], "file": f'{b["folder"]}/{b["file"]}', "source": b["source"], "title": b["title"],
            "books": books, "licence": b.get("licence") or b.get("copyright", "")[:160], "non_commercial": nc,
            "include": False, "abbreviation": "", "description": b["title"], "attribution": b.get("copyright", "")[:400],
            "rejected": b["id"] in gone, "notes": b.get("notes", ""),
        })
    if not cands:
        fail(f"No Bibles of {a.lang} in bibles-manifest.json")
    # Default choice: complete, allowed with ads, not rejected; eBible before BSS when both have the same Bible.
    for x in sorted(cands, key=lambda x: (x["rejected"], x["non_commercial"], -x["books"], x["source"] != "eBible.org")):
        if not x["rejected"] and not x["non_commercial"] and x["books"] >= 66:
            x["include"] = True
            break
    d = pack_dir(c, a.lang)
    if (d / "pack.json").exists() and not a.force:
        fail(f"{d / 'pack.json'} exists (use --force to start over)")
    row = rows[a.lang]
    pack = {
        "lang": a.lang, "module_language": MODULE_LANGUAGE.get(a.lang, a.lang.lower()),
        "language_name": row["Idioma"], "script": row["Escritura"], "created": TODAY,
        "ads_allowed": row.get("¿Con anuncios?", "").startswith("✅"),
        "bibles": cands, "default_bible": None,
        "english_modules": ENGLISH_MODULES,
        "_help": "Mark include=true on the Bibles to ship (2-3 at most), fill abbreviation (e.g. 'LSG') and check "
                 "description and attribution. default_bible = the id of the main one. Then: pack.py import " + a.lang,
    }
    save_pack(c, a.lang, pack)
    print(f"Created {d / 'pack.json'}:")
    for x in cands:
        flag = "REJECTED" if x["rejected"] else ("NC" if x["non_commercial"] else "")
        print(f"  [{'x' if x['include'] else ' '}] {x['id']:22} {x['source'][:10]:10} {x['books']:>3} libros {flag:8} {x['title'][:50]}")
    print("Choose the Bibles (include, abbreviation, default_bible) and run  pack.py import " + a.lang)


def cmd_import(a):
    c = cfg()
    pack = load_pack(c, a.lang)
    chosen = [b for b in pack["bibles"] if b["include"]]
    if not chosen:
        fail("No Bible has include=true in pack.json")
    gone = eliminated_ids(c)
    target = app_counts()
    d = pack_dir(c, a.lang)
    db = d / "work.db"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.execute("create table verses (sid text, book text, chapter int, verse int, text text, raw text, "
                "primary key (sid, book, chapter, verse))")
    con.execute("create table log (sid text, kind text, detail text)")
    for b in chosen:
        if b["id"] in gone or b.get("rejected"):
            fail(f"{b['id']} was rejected in healthReport.md: it can't be imported")
        path = c["bibles_dir"] / b["file"]
        verses, skipped = {".zip": read_ebible, ".json": read_getbible}.get(path.suffix, read_bss)(path)
        maxv = collections.defaultdict(int)
        for bk, ch, v, _ in verses:
            maxv[(bk, ch)] = max(maxv[(bk, ch)], v)
        schemes, same, total = detect_scheme(maxv)
        forced = b.get("versification")  # pack.json can force it: "rso" (all), {"PSA": "rso"} (a book), {"EXO 8": "org"}
        if forced:
            for key in list(schemes):
                if isinstance(forced, str):
                    schemes[key] = forced
                elif f"{key[0]} {key[1]}" in forced or key[0] in forced:
                    schemes[key] = forced.get(f"{key[0]} {key[1]}", forced.get(key[0]))
        other = collections.defaultdict(list)
        for (bk, ch), sc in sorted(schemes.items(), key=lambda x: (BOOKNUM[x[0][0]], x[0][1])):
            if sc != "eng":
                other[(bk, sc)].append(ch)
        scheme = "eng" + ("; otra numeración en " + ", ".join(f"{bk} {','.join(map(str, chs))} ({sc})"
                                                              for (bk, sc), chs in other.items()) if other else "")
        stats = collections.Counter()
        out = collections.OrderedDict()  # app ref -> ([clean texts], [raw texts]), in reading order
        mapped = [to_app((bk, ch, v), schemes[(bk, ch)]) for bk, ch, v, _ in verses]
        dropped = collections.Counter((bk, ch) for (bk, ch, v, _), ref in zip(verses, mapped) if ref is None)
        for (bk, ch), n in dropped.items():
            skipped[f"{bk} {ch} (agregado deuterocanónico)"] += n
        verses = [x for x, ref in zip(verses, mapped) if ref is not None]
        mapped = [ref for ref in mapped if ref is not None]
        taken = set(mapped)
        order = [(bk, ch, v) for bk in BOOKS for ch in sorted(target[bk]) for v in range(1, target[bk][ch] + 1)]
        nxt = {order[i]: order[i + 1] for i in range(len(order) - 1)}
        for (bk, ch, v, t), ref in zip(verses, mapped):
            if ref[2] == 0:  # Psalm title: the app shows it at the start of verse 1, as the KJV module does
                ref = (ref[0], ref[1], 1)
                stats["title_merged"] += 1
            elif ref in out and nxt.get(ref) and nxt[ref] not in taken and nxt[ref][0] == ref[0]:
                # Two verses on one number (the tables split a verse the source keeps whole): the second
                # takes the next number nobody maps to, so no text is glued and no slot stays empty.
                ref = nxt[ref]
                taken.add(ref)
                stats["shifted"] += 1
            if ref in out:
                stats["merged"] += 1
            texts, raws = out.setdefault(ref, ([], []))
            t2 = clean(t, stats)
            if t2:
                texts.append(t2)
            raws.append(t)
        # Verses the app's numbering doesn't have (Septuagint additions such as JOS 24:34-36): pack.json decides.
        for ref in [r for r in out if r[2] > target.get(r[0], {}).get(r[1], 0)]:
            policy = (b.get("extra_verses_refs") or {}).get(f"{ref[0]} {ref[1]}:{ref[2]}", b.get("extra_verses", "error"))
            if policy == "drop":
                stats["extra_dropped"] += 1
                con.execute("insert into log values (?,?,?)", (b["id"], "extra_dropped", f"{ref[0]} {ref[1]}:{ref[2]} {' '.join(out[ref][0])[:200]}"))
                del out[ref]
            elif policy == "append":
                last = (ref[0], ref[1], target[ref[0]][ref[1]])
                out.setdefault(last, ([], []))[0].extend(out.pop(ref)[0])
                stats["extra_appended"] += 1
        # Renumbering decided in the criteria step: {"ISA 3:26": "ISA 3:25"} = the text of 3:25 goes to 3:26 (text unchanged).
        moves = b.get("criteria_moves") or {}
        if moves:
            snapshot = {k: (list(x[0]), list(x[1])) for k, x in out.items()}
            for dst, srcref in moves.items():
                sb, scv = srcref.split(" ")
                sch, sv = map(int, scv.split(":"))
                db_, dcv = dst.split(" ")
                dch, dv = map(int, dcv.split(":"))
                moved = snapshot.get((sb, sch, sv), ([], []))
                out[(db_, dch, dv)] = (list(moved[0]), list(moved[1]))
                if srcref not in moves:  # its own text did not move in from somewhere else: it is now empty
                    out[(sb, sch, sv)] = ([], [])
                con.execute("insert into log values (?,?,?)", (b["id"], "move", f"{dst} | texto de {srcref} (sin cambios)"))
        # Manual fixes from pack.json: {"ISA 3:23": "text", ...}. Logged, and shown in the report.
        for r, text in list((b.get("overrides") or {}).items()) + list((b.get("criteria_overrides") or {}).items()):
            bk, cv = r.split(" ")
            ch, v = map(int, cv.split(":"))
            before = " ".join(out.get((bk, ch, v), ([], []))[0])
            out[(bk, ch, v)] = ([clean(text, stats)] if text else [], [before])
            con.execute("insert into log values (?,?,?)", (b["id"], "override", f"{r} | antes: {before[:150]} | ahora: {text[:150]}"))
        rows = [(b["id"], bk, ch, v, " ".join(tx), "\n".join(rw)) for (bk, ch, v), (tx, rw) in out.items()]
        con.executemany("insert into verses values (?,?,?,?,?,?)", rows)
        con.execute("insert into log values (?,?,?)", (b["id"], "scheme", f"{scheme} ({same}/{total} chapters match)"))
        for k, n in stats.items():
            con.execute("insert into log values (?,?,?)", (b["id"], f"clean:{k}", str(n)))
        for k, n in skipped.items():
            con.execute("insert into log values (?,?,?)", (b["id"], "skipped_book", f"{k} ({n} verses)"))
        con.commit()
        print(f"  {b['id']}: {len(rows)} verses, versification {scheme} ({same}/{total} chapters match), "
              f"cleaned {dict(stats)}, skipped books {dict(skipped)}")
    con.close()
    pack.pop("validation", None)
    pack.pop("approval", None)
    pack["imported"] = TODAY
    save_pack(c, a.lang, pack)
    print(f"OK: {db}. Next: pack.py validate {a.lang}")


_KJV = {}


def kjv(c):
    if _KJV:
        return _KJV
    p = c["bibles_dir"] / "EN-English" / "king-james-version.bblx"
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    out = {}
    for b, ch, v, t in con.execute("select Book, Chapter, Verse, Scripture from Bible"):
        if 1 <= b <= 66:
            out[(BOOKS[b - 1], ch, v)] = re.sub(r"\{/?\w+\}|<[^>]*>", "", t or "")
    _KJV.update(out)
    return out


def script_of(ch):
    try:
        return unicodedata.name(ch).split(" ")[0]
    except ValueError:
        return "?"


def pearson(xs, ys):
    n = len(xs)
    if n < 8:
        return 1.0
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return 1.0 if sx == 0 or sy == 0 else sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def sample_refs(pack, sid, rows):
    """The random verses of the review: the same every time for a Bible (seeded with its id), only verses with text,
    none of the key passages. How many: pack.json review_sample, else review-verses.json random_sample (80)."""
    rv = json.loads((ASSETS / "review-verses.json").read_text(encoding="utf-8"))
    n = int(pack.get("review_sample") or rv.get("random_sample", 80))
    keys = {r for item in rv["verses"] for r in expand_ref(item["ref"])}
    pool = sorted(r for r, t in rows.items() if t and r not in keys)
    return sorted(random.Random(sid).sample(pool, min(n, len(pool))), key=lambda r: (BOOKNUM[r[0]], r[1], r[2]))


def norm_cmp(t):
    """Text for comparing two copies: same dashes, quotes, spacing and \u0451/\u0435, and without the brackets of words added by
    the translators (the Synodal marks them, some copies lost the marks): typography is not a typo."""
    t = re.sub(r"[\[\]]", "", t).replace("\u0451", "\u0435").replace("\u0401", "\u0415")
    t = re.sub(r"[\u2010-\u2015\u2212]", "-", t)
    t = re.sub(r"[\u00ab\u00bb\u201c\u201d\u201e\u2018\u2019\u201a\"']", "", t)
    t = re.sub(r"\s*([-,.;:!?()])\s*", r"\1", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def expand_ref(ref):
    m = re.match(r"^([1-4A-Z]{3}) (\d+):(\d+)(?:-(\d+))?$", ref)
    b, ch, v1, v2 = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4) or m.group(3))
    return [(b, ch, v) for v in range(v1, v2 + 1)]


def cmd_validate(a):
    c = cfg()
    pack = load_pack(c, a.lang)
    d = pack_dir(c, a.lang)
    if not (d / "work.db").exists():
        fail(f"Run  pack.py import {a.lang}  first")
    con = sqlite3.connect(d / "work.db")
    target = app_counts()
    ref_kjv = kjv(c)
    expected = SCRIPTS.get(pack["script"].lower(), ["LATIN"])
    issues = []  # (level, sid, check, ref, detail)

    def add(level, sid, check, ref, detail):
        issues.append((level, sid, check, ref, detail))

    gone = eliminated_ids(c)
    sids = [b for b in pack["bibles"] if b["include"]]
    texts = {}
    texts_all = {b["id"]: {(bk, ch, v): t for bk, ch, v, t in con.execute(
        "select book, chapter, verse, text from verses where sid=?", (b["id"],))} for b in sids}
    for b in sids:
        sid = b["id"]
        rows = {(bk, ch, v): t for bk, ch, v, t in con.execute("select book, chapter, verse, text from verses where sid=?", (sid,))}
        texts[sid] = rows
        if b.get("role") == "reference":
            add("I", sid, "referencia", "", "Solo de referencia (role: reference): se compara y se usa en el paso de criterio, no se publica")
            continue
        # --- health and licence
        if sid in gone or b.get("rejected"):
            add("E", sid, "salud", "", "Rechazada en healthReport.md")
        for n in health_notes(c, sid):
            add("W", sid, "salud", "", n[:300])
        if not (b.get("licence") or "").strip():
            add("E", sid, "licencia", "", "Sin licencia conocida")
        if b.get("non_commercial") and pack.get("ads_allowed"):
            add("W", sid, "licencia", "", "Licencia no comercial: este paquete no podrá usarse si la app tiene anuncios")
        if not (b.get("attribution") or "").strip():
            add("E", sid, "licencia", "", "Falta la atribución (créditos) en pack.json")
        if not (b.get("abbreviation") or "").strip():
            add("E", sid, "módulo", "", "Falta la abreviatura (abbreviation) en pack.json")
        # --- structure against the app's versification
        books_present = {bk for bk, _, _ in rows}
        nt_only = books_present and min(BOOKNUM[x] for x in books_present) >= NT_FIRST
        for bk in BOOKS:
            if bk not in books_present:
                if not (nt_only and BOOKNUM[bk] < NT_FIRST):
                    add("E", sid, "estructura", bk, "Falta el libro completo")
                continue
            for ch, mx in target[bk].items():
                missing = [v for v in range(1, mx + 1) if not rows.get((bk, ch, v), "").strip()]
                for v in missing:
                    r = f"{bk} {ch}:{v}"
                    prev, kprev = rows.get((bk, ch, v - 1), ""), ref_kjv.get((bk, ch, v - 1), "")
                    if r in OMITTED_OK:
                        add("W", sid, "estructura", r, "Versículo omitido por el texto crítico (normal en traducciones modernas)")
                    elif prev and kprev and len(prev) > 1.5 * len(kprev):
                        add("W", sid, "estructura", r, "Vacío: la traducción lo une al versículo anterior (versículos combinados)")
                    else:
                        add("E", sid, "estructura", r, "Versículo vacío o faltante")
        for (bk, ch, v), t in rows.items():
            if v > target.get(bk, {}).get(ch, 0) and t.strip():  # an emptied one (moved by the criteria step) is not built
                add("E", sid, "versificación", f"{bk} {ch}:{v}", "Versículo de más, fuera de la numeración de la app (no se mostraría). "
                    "Si es una adición de la Septuaginta: extra_verses \"drop\" en pack.json (\"append\" lo une al último versículo): "
                    + rows[(bk, ch, v)][:120])
        if nt_only:
            add("W", sid, "estructura", "", "Solo Nuevo Testamento: no puede ser la Biblia principal del idioma")
        # --- text
        script_bad, words = 0, collections.Counter()
        for ref, t in rows.items():
            r = f"{ref[0]} {ref[1]}:{ref[2]}"
            if re.search(r"Ã.|Â|â€|\ufffd|Ð[\u0080-\u00bf]", t):
                add("E", sid, "codificación", r, f"Texto mal decodificado: {t[:80]}")
            if re.search(r"\\[a-z]+|\|[a-z]+=|<|>|\{|\}", t):
                add("E", sid, "marcas", r, f"Quedan marcas de formato: {t[:80]}")
            letters = [script_of(ch) for ch in t if ch.isalpha()]
            if letters:
                ok = sum(1 for s in letters if s in expected)
                if ok / len(letters) < 0.85:
                    script_bad += 1
                    if script_bad <= 5:
                        add("W", sid, "escritura", r, f"Letras fuera de {pack['script']}: {t[:80]}")
            for blk in re.findall(r"\[[^\]]{150,}\]?", t):
                add("W", sid, "agregado", r, f"Texto largo entre corchetes ({len(blk)} letras): en la Sinodal marca un agregado de la "
                    f"Septuaginta o deuterocanónico (p. ej. las adiciones griegas de Ester): {blk[:120]}")
            if re.search(r"В Славянской Библии|по переводу 70-ти|Synodal note|note:", t):
                add("W", sid, "agregado", r, f"Nota del editor dentro del versículo (no es texto bíblico): {t[:120]}")
            rep_m = re.search(r"(?i)\b(\w{5,})\s+\1\b", t)  # short ones ("nous nous", "его его") are grammar
            if rep_m:
                add("W", sid, "repetición", r, f"Palabra repetida: {rep_m.group(0)}")
            if not set(expected) & NO_SPACES:
                words.update(w for w in re.findall(r"\w+", t.lower()) if not w.isdigit())
            k = ref_kjv.get(ref)
            if k and t and (len(t) < 0.2 * len(k) or len(t) > 5 * len(k)) and len(k) > 30:
                add("W", sid, "longitud", r, f"Largo anormal frente a la KJV ({len(t)} vs {len(k)}): {t[:80]}")
        paren = collections.Counter()
        for (bk, ch, v), t in rows.items():  # a parenthesis may close in the next verse: count per chapter
            paren[(bk, ch)] += t.count("(") - t.count(")") + t.count("[") - t.count("]")
        for (bk, ch), n in paren.items():
            if n:
                add("W", sid, "puntuación", f"{bk} {ch}", f"Paréntesis o corchetes sin cerrar en el capítulo ({n:+d})")
        if rows and script_bad / len(rows) > 0.01:
            add("E", sid, "escritura", "", f"{script_bad} versículos ({script_bad * 100 // len(rows)} %) no están en {pack['script']}")
        # merged words: a word seen once that is two frequent words glued together ("увероваливо" = "уверовали" + "во")
        if words:
            others = [set(re.findall(r"\w+", " ".join(texts_all[o].values()).lower())) for o in texts_all if o != sid]
            glued = []
            vocab = list(words)
            ends, starts = collections.Counter(), collections.Counter()
            for w in vocab:  # how often a piece is a common ending ("aient") or beginning ("pour"): grammar, not a typo
                for k in range(2, min(len(w), 8)):
                    ends[w[-k:]] += 1
                    starts[w[:k]] += 1
            for w, n in words.items():
                if n > 1 or len(w) < 7 or any(w in o for o in others):
                    continue  # a word the other copy of the same text also has is not a typo
                for i in range(2, len(w) - 2):
                    x, y = w[:i], w[i:]
                    fx, fy = words.get(x, 0), words.get(y, 0)
                    if not (fy >= 10 and len(y) >= 3 and (fx >= 300 or (len(x) >= 3 and fx >= 10))):
                        continue
                    if ends[y] - 1 >= 5 or (len(x) <= 4 and starts[x] - 1 >= 25):
                        continue
                    glued.append((w, x, y))
                    break
            for w, x, y in glued[:60]:
                ref = next((f"{bk} {ch}:{v}" for (bk, ch, v), t in rows.items() if re.search(rf"(?i)\b{re.escape(w)}\b", t)), "")
                add("W", sid, "errata", ref, f"¿Palabras pegadas? «{w}» = «{x}» + «{y}»")
            if len(glued) > 60:
                add("W", sid, "errata", "", f"... y {len(glued) - 60} posibles palabras pegadas más")
        # alignment: in a well numbered chapter verse lengths follow the KJV's
        by_ch = collections.defaultdict(list)
        for ref, t in rows.items():
            if ref in ref_kjv:
                by_ch[(ref[0], ref[1])].append((len(t), len(ref_kjv[ref])))
        bad = [(k, pearson([x for x, _ in v], [y for _, y in v])) for k, v in by_ch.items() if len(v) >= 10]
        for (bk, ch), r in sorted(bad, key=lambda x: x[1])[:15]:
            if r < 0.35:
                add("W", sid, "alineación", f"{bk} {ch}", f"Los largos de los versículos no siguen a la KJV (r={r:.2f}): ¿numeración corrida?")
        for kind, detail in con.execute("select kind, detail from log where sid=?", (sid,)):
            if kind == "scheme":
                add("I", sid, "versificación", "", f"Numeración de origen: {detail}")
            elif kind.startswith("clean:"):
                add("I", sid, "limpieza", "", f"{kind[6:]}: {detail} versículos corregidos")
            elif kind == "move":
                add("W", sid, "corrección manual", detail.split(" | ")[0], "Renumerado: " + detail.split(" | ", 1)[1])
            elif kind == "override":
                add("W", sid, "corrección manual", detail.split(" | ")[0], detail.split(" | ", 1)[1])
            elif kind == "extra_dropped":
                ref_part, text_part = " ".join(detail.split(" ", 2)[:2]), detail.split(" ", 2)[2]
                add("W", sid, "versificación", ref_part, "Versículo de más descartado (extra_verses=drop): " + text_part[:150])
            elif kind == "skipped_book":
                code = detail.split(" ")[0]
                if code in DEUTERO or code.isdigit() or "deuterocanónico" in detail:
                    add("I", sid, "canon", "", f"Libro fuera de los 66 descartado: {detail}")
                else:
                    add("E", sid, "canon", "", f"Código de libro desconocido, no importado: {detail} (agregarlo a ALIASES si es uno de los 66)")
    # --- two sources of the same text: the differences are digitisation errors of one of them
    ids = list(texts)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            A, B = texts[ids[i]], texts[ids[j]]
            common = [r for r in A if r in B and A[r] and B[r]]
            sample = random.Random(1).sample(common, min(400, len(common)))
            if not sample:
                continue
            sim = sum(difflib.SequenceMatcher(None, A[r], B[r]).ratio() for r in sample) / len(sample)
            if sim < 0.85:
                continue
            add("I", ids[i], "comparación", "", f"Mismo texto que {ids[j]} (similitud {sim:.2f}): se comparan versículo por versículo")
            n = 0
            for r in common:
                na, nb = norm_cmp(A[r]), norm_cmp(B[r])
                if na != nb:
                    s = difflib.SequenceMatcher(None, na, nb).ratio()
                    if 0.9 <= s < 0.995:
                        n += 1
                        if n <= 80:
                            add("W", ids[i], "comparación", f"{r[0]} {r[1]}:{r[2]}", f"{ids[i]}: «{A[r][:120]}» | {ids[j]}: «{B[r][:120]}»")
            if n > 80:
                add("W", ids[i], "comparación", "", f"... y {n - 80} diferencias pequeñas más con {ids[j]}")
    if set(expected) & RTL:
        add("W", "", "app", "", "Escritura de derecha a izquierda: comprobar en el teléfono que la app la muestra bien antes de publicar")
    if not pack.get("default_bible") or pack["default_bible"] not in [b["id"] for b in sids]:
        add("E", "", "módulo", "", "default_bible en pack.json debe ser el id de una Biblia incluida")
    # An error the criteria step accepted with a note (a combined verse, a book title printed as a heading) no longer
    # blocks: the report shows it as accepted, with the note.
    crit_path = d / "criteria.json"
    accepted = {}
    if crit_path.exists():
        for e in json.loads(crit_path.read_text(encoding="utf-8")).get("issues", []):
            dec = e.get("decision") or {}
            if dec.get("action") == "accept" and dec.get("note"):
                accepted[e["key"]] = dec["note"]
    errors = sum(1 for x in issues if x[0] == "E" and issue_key(x) not in accepted)
    warns = sum(1 for x in issues if x[0] == "W")
    (d / "issues.json").write_text(json.dumps([{"key": issue_key(x), "level": x[0], "bible": x[1], "check": x[2], "ref": x[3],
                                                "detail": x[4]} for x in issues], ensure_ascii=False, indent=1), encoding="utf-8")
    shown = [(x[0], x[1], x[2], x[3], x[4] + f" — ACEPTADO POR CRITERIO: {accepted[issue_key(x)]}") if x[0] == "E" and issue_key(x) in accepted
             else x for x in issues]
    write_report(c, pack, d, shown, texts, ref_kjv)
    pack["validation"] = {"date": TODAY, "errors": errors, "warnings": warns,
                          "report_sha256": sha256_file(d / "report.md"), "work_sha256": sha256_file(d / "work.db")}
    pack.pop("approval", None)
    save_pack(c, a.lang, pack)
    print(f"{errors} errors, {warns} warnings -> {d / 'report.md'} and {d / 'review.html'}")
    sys.exit(1 if errors else 0)


def issue_key(x):
    return f"{x[0]}|{x[1]}|{x[2]}|{x[3]}|{hashlib.sha1(x[4].encode('utf-8')).hexdigest()[:10]}"


def write_report(c, pack, d, issues, texts, ref_kjv):
    lines = [f"# Validación {pack['lang']} ({pack['language_name']})", "", f"Fecha: {TODAY}. Biblias: "
             + ", ".join(b["id"] for b in pack["bibles"] if b["include"]) + ".", "",
             f"**{sum(1 for x in issues if x[0] == 'E' and 'ACEPTADO POR CRITERIO' not in x[4])} errores** (bloquean el build; "
             f"{sum(1 for x in issues if x[0] == 'E' and 'ACEPTADO POR CRITERIO' in x[4])} más aceptados por criterio), "
             f"**{sum(1 for x in issues if x[0] == 'W')} advertencias** (revisarlas una por una), "
             f"{sum(1 for x in issues if x[0] == 'I')} notas.", ""]
    for level, title in (("E", "Errores"), ("W", "Advertencias"), ("I", "Notas")):
        group = [x for x in issues if x[0] == level]
        if not group:
            continue
        lines += [f"## {title}", "", "| Biblia | Control | Referencia | Detalle |", "|---|---|---|---|"]
        by = collections.Counter((x[1], x[2]) for x in group)
        shown = collections.Counter()
        for _, sid, check, ref, detail in group:
            shown[(sid, check)] += 1
            if shown[(sid, check)] > 40:
                continue
            lines.append(f"| {sid} | {check} | {ref} | {detail.replace('|', '/')} |")
        for (sid, check), n in by.items():
            if n > 40:
                lines.append(f"| {sid} | {check} | | ... {n - 40} más del mismo tipo |")
        lines.append("")
    (d / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # review sheet: key verses and a random sample next to the KJV
    rv = json.loads((ASSETS / "review-verses.json").read_text(encoding="utf-8"))["verses"]
    crit = json.loads((d / "criteria.json").read_text(encoding="utf-8")) if (d / "criteria.json").exists() else {}
    verdicts = {e["key"]: e for e in crit.get("key_verses", [])}
    decided = {e["key"]: e for e in crit.get("issues", [])}
    history = [e for e in crit.get("resolved", []) if e["key"] not in decided]
    rtl = bool(set(SCRIPTS.get(pack["script"].lower(), [])) & RTL)
    h = ["<!doctype html><meta charset='utf-8'><title>Revisión " + html.escape(pack["lang"]) + "</title>",
         "<style>body{font:15px/1.5 system-ui;margin:24px;max-width:1300px}table{border-collapse:collapse;width:100%}"
         "td,th{border:1px solid #ccc;padding:6px 8px;vertical-align:top}th{background:#f2f2f2}.ref{white-space:nowrap;font-weight:600}"
         ".doc{background:#fff6e0}.t{direction:" + ("rtl" if rtl else "ltr") + "}</style>",
         f"<h1>Revisión de {html.escape(pack['language_name'])} ({html.escape(pack['lang'])})</h1>",
         "<p>Leer cada versículo junto a la KJV. Las filas amarillas son los pasajes doctrinales del reporte de salud: "
         "marcar cada casilla solo si la traducción dice lo mismo que el original. Al terminar: "
         f"<code>pack.py approve {html.escape(pack['lang'])} --by &lt;nombre&gt;</code>.</p>"]
    for sid, rows in texts.items():
        if next((b for b in pack["bibles"] if b["id"] == sid), {}).get("role") == "reference":
            continue
        h.append(f"<h2>{html.escape(sid)}</h2><table><tr><th>✓</th><th>Ref.</th><th>{html.escape(sid)}</th><th>RV1960</th><th>KJV</th>"
                 "<th>Qué revisar</th><th>Bitácora de criterio</th></tr>")
        for item in rv:
            refs = expand_ref(item["ref"])
            t = " ".join(f"<sup>{v}</sup>{html.escape(rows.get((b, ch, v), '— FALTA —'))}" for b, ch, v in refs)
            k = " ".join(f"<sup>{v}</sup>{html.escape(ref_kjv.get((b, ch, v), ''))}" for b, ch, v in refs)
            rv60 = local_bible(c, "ES-Spanish/reina-valera-1960.bblx")
            es = " ".join(f"<sup>{v}</sup>{html.escape(rv60.get((b, ch, v), ''))}" for b, ch, v in refs)
            vd = verdicts.get(f"verse|{sid}|{item['ref']}", {})
            log = (f"<b>{html.escape(vd['verdict'])}</b>: {html.escape(vd.get('note', ''))}" if vd.get("verdict") else "<i>pendiente</i>")
            h.append(f"<tr class='{'doc' if item.get('doctrine') else ''}'><td><input type=checkbox></td><td class=ref>{item['ref']}</td>"
                     f"<td class=t>{t}</td><td>{es}</td><td>{k}</td><td>{html.escape(item['check'])}</td><td>{log}</td></tr>")
        sample = sample_refs(pack, sid, rows)
        h.append(f"</table><h3>Muestra al azar ({len(sample)} versículos)</h3><table><tr><th>✓</th><th>Ref.</th><th>Texto</th><th>RV1960</th>"
                 "<th>KJV</th><th>Bitácora de criterio</th></tr>")
        rv60 = local_bible(c, "ES-Spanish/reina-valera-1960.bblx")
        for r in sample:
            ref = f"{r[0]} {r[1]}:{r[2]}"
            vd = verdicts.get(f"sample|{sid}|{ref}", {})
            log = (f"<b>{html.escape(vd['verdict'])}</b>: {html.escape(vd.get('note', ''))}" if vd.get("verdict") else "<b>PENDIENTE</b>")
            h.append(f"<tr><td><input type=checkbox></td><td class=ref>{ref}</td><td class=t>{html.escape(rows[r])}</td>"
                     f"<td>{html.escape(rv60.get(r, ''))}</td><td>{html.escape(ref_kjv.get(r, ''))}</td><td>{log}</td></tr>")
        h.append("</table>")
    if decided:
        pend = sum(1 for e in decided.values() if not e.get("decision"))
        h.append(f"<h2>Problemas del reporte y cómo se resolvieron</h2><p>{len(decided)} problemas de la última validación, "
                 f"{pend} sin decisión.</p><table><tr><th>Nivel</th><th>Biblia</th><th>Control</th>"
                 "<th>Ref.</th><th>Problema</th><th>Bitácora de criterio</th><th>Evidencia</th></tr>")
        for e in sorted(decided.values(), key=lambda e: (e["level"], e["bible"], e["check"], e["ref"])):
            dec = e.get("decision") or {}
            log = (f"<b>{html.escape(dec.get('action', ''))}</b> — {html.escape(dec.get('note', ''))}") if dec else "<b>PENDIENTE DE DECISIÓN</b>"
            ev = "<br>".join(f"<a href='{html.escape(x.get('url', ''))}'>{html.escape(x['source'])}</a> v{x.get('verse', '')}: "
                             f"{html.escape((x.get('text') or '')[:160])}" for x in e.get("evidence", []))
            h.append(f"<tr><td>{e['level']}</td><td>{html.escape(e['bible'])}</td><td>{html.escape(e['check'])}</td>"
                     f"<td class=ref>{html.escape(e['ref'])}</td><td class=t>{html.escape(e['detail'][:300])}</td><td>{log}</td><td>{ev}</td></tr>")
        h.append("</table>")
    if history:
        h.append(f"<details><summary><b>Historial: {len(history)} problemas de pasadas anteriores que ya no aparecen</b></summary>"
                 "<p>Aparecieron en una validación anterior y desaparecieron solos al cambiar de copia o corregir la numeración: "
                 "no hay nada que decidir.</p><table><tr><th>Nivel</th><th>Biblia</th><th>Control</th><th>Ref.</th><th>Problema</th>"
                 "<th>Por qué ya no aplica</th></tr>")
        used = {b["id"] for b in pack["bibles"] if b["include"]}
        for e in sorted(history, key=lambda e: (e["bible"], e["check"], e["ref"])):
            dec = e.get("decision") or {}
            why = (f"<b>{html.escape(dec.get('action', ''))}</b> — {html.escape(dec.get('note', ''))}" if dec else
                   ("Esa copia ya no está en el paquete (descartada o solo de referencia)." if e["bible"] not in used or
                    next((b for b in pack["bibles"] if b["id"] == e["bible"]), {}).get("role") == "reference" else
                    "Se resolvió al corregir la conversión o con otra decisión (ya no aparece en la validación)."))
            h.append(f"<tr><td>{e['level']}</td><td>{html.escape(e['bible'])}</td><td>{html.escape(e['check'])}</td>"
                     f"<td class=ref>{html.escape(e['ref'])}</td><td class=t>{html.escape(e['detail'][:200])}</td><td>{why}</td></tr>")
        h.append("</table></details>")
    (d / "review.html").write_text("\n".join(h), encoding="utf-8")


def cmd_review(a):
    """Writes report.md and review.html again from issues.json and criteria.json: the validation, the approval and
    the build stay as they are (the text did not change)."""
    c = cfg()
    pack = load_pack(c, a.lang)
    d = pack_dir(c, a.lang)
    issues = [(x["level"], x["bible"], x["check"], x["ref"], x["detail"]) for x in json.loads((d / "issues.json").read_text(encoding="utf-8"))]
    crit = json.loads((d / "criteria.json").read_text(encoding="utf-8")) if (d / "criteria.json").exists() else {}
    accepted = {e["key"]: e["decision"]["note"] for e in crit.get("issues", [])
                if (e.get("decision") or {}).get("action") == "accept" and e["decision"].get("note")}
    shown = [(x[0], x[1], x[2], x[3], x[4] + f" — ACEPTADO POR CRITERIO: {accepted[issue_key(x)]}") if x[0] == "E" and issue_key(x) in accepted
             else x for x in issues]
    con = sqlite3.connect(d / "work.db")
    texts = {b["id"]: {(bk, ch, v): t for bk, ch, v, t in con.execute("select book, chapter, verse, text from verses where sid=?", (b["id"],))}
             for b in pack["bibles"] if b["include"]}
    write_report(c, pack, d, shown, texts, kjv(c))
    print(f"OK: {d / 'review.html'} and report.md written again")


def cmd_approve(a):
    c = cfg()
    pack = load_pack(c, a.lang)
    d = pack_dir(c, a.lang)
    v = pack.get("validation")
    if not v:
        fail(f"Run  pack.py validate {a.lang}  first")
    if v["errors"]:
        fail(f"The validation has {v['errors']} errors: fix them (pack.json or the source) and validate again")
    if sha256_file(d / "work.db") != v["work_sha256"]:
        fail("work.db changed after the validation: validate again")
    crit_path = d / "criteria.json"
    if not crit_path.exists():
        fail(f"No criteria step yet: run  pack.py criteria {a.lang}  and decide every problem")
    crit = json.loads(crit_path.read_text(encoding="utf-8"))
    current = {x["key"] for x in json.loads((d / "issues.json").read_text(encoding="utf-8")) if x["level"] in "EW"}
    known = {e["key"]: e for e in crit.get("issues", [])}
    pending = [k for k in current if not (known.get(k) or {}).get("decision")]
    if pending:
        fail(f"{len(pending)} problems without a decision in criteria.json (run  pack.py criteria {a.lang}  to add the new ones)")
    open_verses = [e["key"] for e in crit.get("key_verses", []) if not e.get("verdict")]
    if open_verses:
        fail(f"{len(open_verses)} key verses without a verdict in criteria.json")
    bad = [e["key"] for e in crit.get("key_verses", []) if e.get("verdict") == "problema"]
    if bad:
        fail("Key verses with a doctrinal problem: " + ", ".join(bad) + ". The text is not changed: reject that Bible (reject_bible) or ask the user")
    pack["approval"] = {"by": a.by, "date": TODAY, "notes": a.notes or "", "warnings_reviewed": v["warnings"],
                        "work_sha256": v["work_sha256"]}
    save_pack(c, a.lang, pack)
    tracker_set(c, a.lang, "Texto", "🟦", f"Biblia validada y revisada por {a.by} ({v['warnings']} advertencias revisadas)")
    print(f"OK: approved by {a.by}. Next: pack.py build {a.lang}")


def module_ids(c):
    p = c["app_repo"] / "cdn" / "bible" / "module-ids.json"
    if p.exists():
        return p, json.loads(p.read_text(encoding="utf-8"))
    # Seed with the ids already used by the published packs (Details.Id of every module).
    reg = {"_comment": "Details.Id of every module in the language packs. An id is never reused. "
                       "Written by the bible-language-pack skill.", "modules": []}
    for folder in ("EN-English", "ES-Spanish", "ES-Spanish-Lite"):
        for f in sorted((c["bibles_dir"] / folder).glob("*.*")):
            if f.suffix in (".bblx", ".cmtx", ".db", ".dev"):
                try:
                    con = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
                    i, lang, ab = con.execute("select Id, Language, Abbreviation from Details").fetchone()
                    con.close()
                    if not any(m["id"] == i for m in reg["modules"]):
                        reg["modules"].append({"id": i, "language": lang, "file": f.name, "abbreviation": ab, "pack": folder})
                except Exception:
                    pass
    reg["modules"].sort(key=lambda m: m["id"])
    return p, reg


def write_bblx(path, b, text_rows, lang, mid):
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE "Details" ("Description" NVARCHAR(255), "Abbreviation" NVARCHAR(50), "Comments" TEXT,
                                "Version" INT, "Language" TEXT, "Id" INTEGER);
        CREATE TABLE "Bible" ("id" INTEGER NOT NULL, "Book" INTEGER, "Chapter" INTEGER, "Verse" INTEGER,
                              "Scripture" TEXT, PRIMARY KEY("id"));
    """)
    con.execute("insert into Details values (?,?,?,?,?,?)", (b["description"], b["abbreviation"], b["attribution"], 1, lang, mid))
    rows = sorted(text_rows, key=lambda r: (BOOKNUM[r[0]], r[1], r[2]))
    con.executemany("insert into Bible values (?,?,?,?,?)",
                    [(i, BOOKNUM[bk], ch, v, t) for i, (bk, ch, v, t) in enumerate(rows, 1)])
    con.executescript("""
        CREATE INDEX "ix_verse_book_id" ON "Bible" ("Book");
        CREATE INDEX "ix_verse_chapter" ON "Bible" ("Chapter");
        CREATE INDEX "ix_verse_verse" ON "Bible" ("Verse");
    """)
    con.commit()
    con.execute("vacuum")
    con.close()


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "bible"


def cmd_build(a):
    c = cfg()
    pack = load_pack(c, a.lang)
    d = pack_dir(c, a.lang)
    ap = pack.get("approval")
    if not ap:
        fail(f"Not approved: read review.html and run  pack.py approve {a.lang} --by <name>")
    if sha256_file(d / "work.db") != ap["work_sha256"]:
        fail("work.db changed after the approval: validate and approve again")
    lang = pack["module_language"]
    reg_path, reg = module_ids(c)
    used = {m["id"] for m in reg["modules"]}
    out = d / "build"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    con = sqlite3.connect(d / "work.db")
    built = []
    for b in [x for x in pack["bibles"] if x["include"] and x.get("role") != "reference"]:
        prev = next((m for m in reg["modules"] if m.get("source") == b["id"] and m["language"] == lang), None)
        mid = prev["id"] if prev else max([FIRST_NEW_ID - 1] + [i for i in used if i >= FIRST_NEW_ID]) + 1
        used.add(mid)
        name = slug(b["abbreviation"] or "")
        fname = f"{lang}-{name if name != 'bible' else slug(b['id'])}.bblx"  # a Cyrillic abbreviation has no ASCII slug
        rows = list(con.execute("select book, chapter, verse, text from verses where sid=? and text<>''", (b["id"],)))
        write_bblx(out / fname, b, rows, lang, mid)
        built.append({"id": mid, "file": fname, "source": b["id"], "abbreviation": b["abbreviation"], "verses": len(rows)})
        if prev:
            prev["file"] = fname
        else:
            reg["modules"].append({"id": mid, "language": lang, "file": fname, "abbreviation": b["abbreviation"],
                                   "pack": a.lang, "source": b["id"], "added": TODAY})
    con.close()
    for f in pack.get("english_modules", ENGLISH_MODULES):
        src = c["bibles_dir"] / "EN-English" / f
        if not src.exists():
            fail(f"Missing English module {src}")
        shutil.copy2(src, out / f)
    # The archive: flat, like the English and Spanish packs. Version from the manifest (a new file never overwrites a published one).
    manifest = json.loads((c["app_repo"] / "cdn" / "bible" / "manifest.json").read_text(encoding="utf-8"))
    current = manifest.get("languages", {}).get(lang)
    ver = int(re.search(r"-v(\d+)\.obb$", current["url"]).group(1)) + 1 if current else 1
    obb = d / f"{lang}-v{ver}.obb"
    with zipfile.ZipFile(obb, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(out.iterdir()):
            z.write(f, f.name)
    # Verify the archive the way the app reads it (ModuleInitializer.saveModuleInformation).
    problems = verify_obb(obb, lang, {m["id"] for m in reg["modules"] if m["language"] != lang and m["id"] not in ENGLISH_DEFAULTS.values()})
    if problems:
        fail("The pack does not pass the check:\n  " + "\n  ".join(problems))
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg["modules"].sort(key=lambda m: m["id"])
    reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    default = next(x for x in built if x["source"] == pack["default_bible"])
    size, digest = obb.stat().st_size, sha256_file(obb)
    pack["build"] = {"date": TODAY, "file": obb.name, "size": size, "sha256": digest, "modules": built, "version": ver}
    save_pack(c, a.lang, pack)
    integ = app_integration(pack, default["id"], size, obb.name)
    (d / "app-integration.md").write_text(integ, encoding="utf-8")
    tracker_set(c, a.lang, "Texto", "✅", f"Paquete {obb.name} generado ({size / 1e6:.1f} MB): Biblia en el idioma, resto en inglés")
    print(f"OK: {obb} ({size / 1e6:.1f} MB, sha256 {digest[:12]}...)")
    for x in built:
        print(f"   module {x['id']}: {x['file']} ({x['verses']} verses)")
    print(f"   + English: {', '.join(pack.get('english_modules', ENGLISH_MODULES))}")
    print(f"Registry: {reg_path}\nApp changes needed: {d / 'app-integration.md'}\nNext: pack.py publish {a.lang}")


def verify_obb(obb, lang, foreign_ids):
    problems, ids = [], {}
    tmp = obb.parent / "_verify"
    if tmp.exists():
        shutil.rmtree(tmp)
    with zipfile.ZipFile(obb) as z:
        if z.testzip():
            return ["corrupt zip"]
        if any("/" in n for n in z.namelist()):
            problems.append("the archive must be flat (no folders): the app extracts it into the modules folder")
        z.extractall(tmp)
    for f in sorted(tmp.iterdir()):
        if f.suffix not in (".bblx", ".cmtx", ".db", ".dev"):
            problems.append(f"unexpected file {f.name}")
            continue
        if f.name.endswith("Plan.db"):
            continue
        con = sqlite3.connect(f)
        try:
            det = con.execute("select Id, Language, Abbreviation, Description from Details").fetchall()
        except sqlite3.Error as e:
            problems.append(f"{f.name}: no Details table ({e})")
            continue
        if len(det) != 1:
            problems.append(f"{f.name}: Details must have exactly one row")
            continue
        i, l, ab, desc = det[0]
        if i in ids:
            problems.append(f"{f.name}: id {i} repeated ({ids[i]})")
        if i in foreign_ids:
            problems.append(f"{f.name}: id {i} already belongs to another language")
        ids[i] = f.name
        if f.suffix == ".bblx":
            if l != lang:
                problems.append(f"{f.name}: Details.Language is {l}, expected {lang}")
            if not ab or not desc:
                problems.append(f"{f.name}: empty abbreviation or description")
            n, books = con.execute("select count(*), count(distinct Book) from Bible").fetchone()
            bad = con.execute("select count(*) from Bible where Scripture like '%{%' or Scripture like '%\\%' escape '!'").fetchone()[0]
            if n < 7000:
                problems.append(f"{f.name}: only {n} verses")
            if bad:
                problems.append(f"{f.name}: {bad} verses with RTF characters")
        con.close()
    shutil.rmtree(tmp)
    return problems


def app_integration(pack, default_id, size, obb_name):
    lang = pack["module_language"]
    return f"""# Integrar {pack['language_name']} ({lang}) en la app

El paquete `{obb_name}` ya está listo; la app todavía no conoce este idioma. Cambios en `D:\\Projects\\Android\\bible-versions`
(una versión nueva de la app, con el skill `android-release`):

1. `app/src/main/java/com/timeless/bible/ui/language/LanguageManager.java`:
   ```java
   public static final String LANGUAGE_{slug(lang).upper().replace('-', '_')} = "{lang}";
   // LANGUAGE_CONFIGS:
   new LanguageConfig("{lang}", null, {default_id}, {ENGLISH_DEFAULTS['commentary']}, {default_id}, {ENGLISH_DEFAULTS['daily_image']}, {ENGLISH_DEFAULTS['quiz']}, {ENGLISH_DEFAULTS['reference']}, {size}L),
   ```
   (Biblia principal {default_id}; comentario JFB 37, reflexión 43, quiz 44 y referencias 47 en inglés, como el paquete inglés.)
2. `getDisplayName`: un `case` con `R.string.language_{slug(lang).replace('-', '_')}` y ese texto en `res/values/strings.xml` y `values-en/strings.xml` (el nombre del idioma en su propio idioma: "{pack['language_name']}").
3. `getDefaultLanguageForDevice`: devolver "{lang}" cuando el idioma del teléfono es "{lang}" (hoy solo distingue es/en).
4. TTS (`singletons/TTS.java`): que lea la Biblia con la voz de "{lang}" si el teléfono la tiene.
5. La interfaz, el quiz, la reflexión y el comentario quedan en inglés: comprobar que la app no mezcla el idioma del módulo con el de la interfaz.
6. Probar en el teléfono (debug): descargar el idioma, abrir Génesis 1, Salmo 23 y Juan 3, la lectura paralela con la KJV, el quiz y el versículo del día.
{"7. **Escritura de derecha a izquierda**: revisar la lectura, la búsqueda y la imagen del día." if set(SCRIPTS.get(pack['script'].lower(), [])) & RTL else ""}
"""


# ---------------------------------------------------------------------------------------------- criteria (the pastor's step)
_SRC = {}


def sources():
    if not _SRC:
        _SRC.update(json.loads((ASSETS / "verify-sources.json").read_text(encoding="utf-8")))
    return _SRC


def plain(t):
    t = html.unescape(re.sub(r"<S>\d+</S>|<sup>.*?</sup>", "", t or ""))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()


class Fetcher:
    """Chapters from the sites of verify-sources.json: cached forever in packs/_cache, spaced by min_interval_s,
    at most `budget` network requests per command, and a site that answers 403/429 is not asked again."""

    def __init__(self, c, budget):
        self.c = c
        self.cache = c["packs_dir"] / "_cache"
        self.budget, self.last, self.blocked, self.requests = budget, {}, set(), 0

    def chapter(self, src, book, ch):
        site = src["site"]
        if site == "local":
            return None
        cfg_site = sources()["sites"][site]
        code = str(src.get("abbr") or src.get("vid"))
        path = self.cache / site / f"{code}_{book}_{ch}.json"
        if path.exists():
            return {int(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
        if site in self.blocked or self.budget <= 0:
            return None
        wait = cfg_site["min_interval_s"] - (time.time() - self.last.get(site, 0))
        if wait > 0:
            time.sleep(wait)
        url = cfg_site["chapter_url"].format(abbr=src.get("abbr"), vid=src.get("vid"), book=book, booknum=BOOKNUM[book], ch=ch)
        self.last[site] = time.time()
        self.budget -= 1
        self.requests += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bible-versions verification; low volume)"})
            raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                self.blocked.add(site)
                print(f"  {site}: HTTP {e.code}, not asked again in this run")
            return None
        except Exception as e:
            print(f"  {site}: {e}")
            return None
        verses = {}
        if site == "getbible":
            for x in json.loads(raw).get("verses", []):
                verses[int(x["verse"])] = plain(x["text"])
        elif site == "bolls":
            for x in json.loads(raw):
                verses[int(x["verse"])] = plain(x["text"])
        elif site == "biblecom":
            content = json.loads(raw).get("content", "")
            for seg in content.split('<span class="verse v')[1:]:
                m = re.match(r'(\d+)[^"]*" data-usfm="[^"]+"', seg)
                if not m:
                    continue
                v = int(m.group(1))
                text = " ".join(plain(x) for x in re.findall(r'<span class="content">(.*?)</span>', seg))
                verses[v] = (verses.get(v, "") + " " + text).strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(verses, ensure_ascii=False), encoding="utf-8")
        return verses


def page_url(src, book, ch):
    if src["site"] == "local":
        return ""
    return sources()["sites"][src["site"]]["page_url"].format(abbr=src.get("abbr"), vid=src.get("vid"), book=book,
                                                              booknum=BOOKNUM[book], ch=ch)


def sources_of(sid):
    """The online copies of the same version. A Bible downloaded with `fetch getbible:<abbr>` takes those of any
    Bible that lists that getBible text, without the getBible chapter itself (it is the same file)."""
    known = sources()["bibles"].get(sid)
    if known is not None or not sid.startswith("getbible_"):
        return known or []
    abbr = sid[len("getbible_"):]
    for lst in sources()["bibles"].values():
        if any(x["site"] == "getbible" and x.get("abbr") == abbr for x in lst):
            return [x for x in lst if not (x["site"] == "getbible" and x.get("abbr") == abbr)]
    return []


def evidence_for(fetcher, sid, ref, ours, max_sources=2, with_rv=True):
    """The verse in the same version online (same number, or the closest text in that chapter when the
    site numbers it differently) and in the RV1960 and the KJV."""
    m = re.match(r"^([1-4A-Z]{3}) (\d+)(?::(\d+))?", ref or "")
    if not m or not m.group(3):
        return []
    book, ch, v = m.group(1), int(m.group(2)), int(m.group(3))
    out = []
    for src in sorted(sources_of(sid), key=lambda x: x.get("match") != "exact")[:max_sources]:
        verses = fetcher.chapter(src, book, ch)
        if not verses:
            continue
        cand = verses.get(v, "")
        best_v, best_t, best_r = v, cand, difflib.SequenceMatcher(None, norm_cmp(ours), norm_cmp(cand)).ratio() if ours and cand else 0
        if ours and best_r < 0.8:
            for k, t in verses.items():
                r = difflib.SequenceMatcher(None, norm_cmp(ours), norm_cmp(t)).ratio()
                if r > best_r:
                    best_v, best_t, best_r = k, t, r
        out.append({"source": f"{src['site']}:{src.get('abbr') or src.get('vid')}", "match": src.get("match", ""),
                    "url": page_url(src, book, ch), "verse": best_v, "text": best_t, "similarity": round(best_r, 3)})
    if with_rv:  # the Reina-Valera 1960 of the Spanish pack, local: no request
        rv = local_bible(fetcher.c, "ES-Spanish/reina-valera-1960.bblx")
        out.append({"source": "RV1960", "match": "reference", "url": "", "verse": v, "text": rv.get((book, ch, v), "")})
    return out


_LOCAL = {}


def local_bible(c, rel):
    """A module of the app's own packs (RV1960, KJV) as {(book, ch, v): plain text}, without its RTF and tags."""
    if rel not in _LOCAL:
        con = sqlite3.connect(f"file:{c['bibles_dir'] / rel}?mode=ro", uri=True)
        out = {}
        for b, ch, v, t in con.execute("select Book, Chapter, Verse, Scripture from Bible"):
            if 1 <= b <= 66:
                t = re.sub(r"\{\\qc[^{}]*\}", "", t or "")  # section headings ({\qc \b La creación\par})
                t = re.sub(r"\\[a-z]+-?\d* ?", "", t)
                t = re.sub(r"\{/?\w+\}|<[^>]*>|[{}]", "", t)
                out[(BOOKS[b - 1], ch, v)] = re.sub(r"\s+", " ", t).strip()
        con.close()
        _LOCAL[rel] = out
    return _LOCAL[rel]


def kjv_text(c, ref):
    m = re.match(r"^([1-4A-Z]{3}) (\d+):(\d+)", ref or "")
    return kjv(c).get((m.group(1), int(m.group(2)), int(m.group(3))), "") if m else ""


def propose(e, texts):
    """A proposal for the pastor to confirm or change: never a decision by itself."""
    det, ref, sid = e["detail"], e["ref"], e["bible"]
    if e["check"] == "errata":
        m = re.search(r"«(.+?)» = «(.+?)» \+ «(.+?)»", det)
        if m:
            w, x, y = m.groups()
            evs = [ev for ev in e.get("evidence", []) if ev["match"] != "reference"]
            split = [ev["source"] for ev in evs if f"{x} {y}" in norm_cmp(ev.get("text", ""))]
            joined = [ev["source"] for ev in evs if w in norm_cmp(ev.get("text", "")).split()]
            if joined and not split:
                return {"action": "accept", "why": f"es una palabra real: {', '.join(joined)} la escribe igual"}
            return {"action": "split_words", "word": w, "into": [x, y],
                    "why": f"separado en {', '.join(split)}" if split else "sin evidencia: confirmar leyendo el contexto"}
    if e["check"] == "versificación" and e["level"] == "E":
        return {"action": "drop_extra", "why": "no existe en la RV1960 ni en la KJV (numeración de la app): adición de la Septuaginta o numeración propia; confirmar"}
    if e["check"] == "estructura" and e["level"] == "E":
        exact = [i for i, ev in enumerate(e.get("evidence", [])) if ev["match"] == "exact" and ev.get("text") and ev.get("similarity", 0) == 0]
        return {"action": "override", "evidence": exact[0], "why": "texto de la misma versión en línea"} if exact else \
            {"action": "accept", "why": "no se encontró el versículo en la misma versión: dejarlo vacío como en el original"}
    if e["check"] == "comparación":
        return {"action": "use_source", "why": "las dos copias difieren: elegir la correcta (con la misma versión en línea si hace falta)"}
    return {"action": "accept", "why": "advertencia informativa: confirmar leyendo el versículo"}


def cmd_fetch(a):
    """One request for the whole Bible (api.getbible.net/v2/<abbr>.json), never chapter by chapter."""
    c = cfg()
    site, _, abbr = a.source.partition(":")
    if site != "getbible" or not abbr:
        fail("Source like getbible:synodal (the abbreviation of api.getbible.net/v2/translations.json)")
    mpath = c["bibles_dir"] / "bibles-manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    folder = next((b["folder"] for b in manifest["bibles"] if b["tracker_code"] == a.lang), None)
    if not folder:
        fail(f"No folder for {a.lang} in bibles-manifest.json")
    dest = c["bibles_dir"] / folder / f"getbible_{abbr}.json"
    url = f"https://api.getbible.net/v2/{abbr}.json"
    if not dest.exists():
        print(f"Downloading {url} (one request)...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bible-versions; one download)"})
        dest.write_bytes(urllib.request.urlopen(req, timeout=300).read())
    d = json.loads(dest.read_text(encoding="utf-8"))
    canon = [b for b in d["books"] if 1 <= int(b["nr"]) <= 66]
    sid = f"getbible_{abbr}"
    entry = {"tracker_code": a.lang, "language": d.get("language", ""), "language_code": d.get("lang", ""), "folder": folder,
             "file": dest.name, "source": "getBible.net (CrossWire SWORD)", "id": sid,
             "title": d.get("description") or d.get("translation", ""), "short_title": d.get("translation", ""), "books": len(canon),
             "copyright": (d.get("distribution_about") or "")[:400], "licence": d.get("distribution_license", ""),
             "licence_url": f"https://getbible.net/{abbr}", "download_url": url,
             "format": "getBible v2 JSON: books[nr, chapters[verses[chapter, verse, text]]]", "bytes": dest.stat().st_size,
             "sha256": sha256_file(dest), "downloaded": TODAY,
             "notes": f"Source: {d.get('distribution_source', '')}; SWORD {d.get('distribution_abbreviation', '')} "
                      f"{d.get('distribution_version', '')} ({d.get('distribution_version_date', '')}); versification {d.get('distribution_versification', '')}"}
    manifest["bibles"] = [b for b in manifest["bibles"] if b["id"] != sid] + [entry]
    manifest["count"] = len(manifest["bibles"])
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    pack = load_pack(c, a.lang)
    if not any(b["id"] == sid for b in pack["bibles"]):
        pack["bibles"].append({"id": sid, "file": f"{folder}/{dest.name}", "source": entry["source"], "title": entry["title"],
                               "books": len(canon), "licence": entry["licence"], "non_commercial": False, "include": False,
                               "abbreviation": "", "description": entry["title"], "attribution": entry["copyright"],
                               "rejected": False, "notes": entry["notes"]})
        save_pack(c, a.lang, pack)
    print(f"OK: {dest} ({entry['bytes'] / 1e6:.1f} MB, {len(canon)} books of the 66, licence {entry['licence']}). "
          f"Added to bibles-manifest.json and to pack.json as {sid} (include=false: choose it there)")


def cmd_criteria(a):
    c = cfg()
    pack = load_pack(c, a.lang)
    d = pack_dir(c, a.lang)
    if not (d / "issues.json").exists():
        fail(f"Run  pack.py validate {a.lang}  first")
    issues = json.loads((d / "issues.json").read_text(encoding="utf-8"))
    path = d / "criteria.json"
    crit = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "_help": "Paso de criterio pastoral. Para cada problema: decision = {action, note} (y los datos de la acción). Acciones: "
                 "accept (sin cambio; note obligatoria), split_words (word, into: separar palabras pegadas: solo se agregan espacios), "
                 "use_source (source: tomar el versículo de la otra copia descargada de la misma versión), override (evidence: índice de "
                 "una evidencia 'exact' de la misma versión; o 'probable' si otra evidencia o la otra copia dice lo mismo), drop_extra / "
                 "append_extra (versículo de más), reject_bible. Versículos clave: verdict = ok | matiz | problema, con note. "
                 "bulk: [{check, bible ('*'), action, note}] para decidir de una vez los avisos de un tipo. Nunca escribir texto bíblico a mano.",
        "lang": a.lang, "issues": [], "resolved": [], "key_verses": [], "bulk": []}
    known = {e["key"]: e for e in crit["issues"]}
    current = {x["key"]: x for x in issues if x["level"] in "EW"}
    # problems fixed since the last run go to "resolved" with their log
    for k in [k for k in known if k not in current]:
        e = known.pop(k)
        e["status"] = f"ya no aparece en la validación del {TODAY}"
        crit["resolved"].append(e)
    con = sqlite3.connect(d / "work.db")
    texts = {b["id"]: {(bk, ch, v): t for bk, ch, v, t in con.execute("select book, chapter, verse, text from verses where sid=?", (b["id"],))}
             for b in pack["bibles"] if b["include"]}
    published = {b["id"] for b in pack["bibles"] if b["include"] and b.get("role") != "reference"}
    fetcher = Fetcher(c, a.fetch)
    need = {"errata", "comparación", "estructura", "versificación", "codificación", "escritura", "alineación"}
    for k, x in current.items():
        e = known.get(k) or dict(x, decision=None, evidence=[], proposal=None)
        if not e.get("evidence") and x["check"] in need and x["bible"] in texts:
            m = re.match(r"^([1-4A-Z]{3}) (\d+):(\d+)", x["ref"] or "")
            vref = (m.group(1), int(m.group(2)), int(m.group(3))) if m else None
            ours = texts[x["bible"]].get(vref, "") if vref else ""
            # The other downloaded copy of the same text comes first: when it settles the doubt, no web request.
            copies = [{"source": f"copia:{o}", "match": "copy", "url": "", "verse": vref[2], "text": t.get(vref, "")}
                      for o, t in texts.items() if o != x["bible"] and vref and t.get(vref)]
            settled = x["check"] in ("errata", "comparación") and copies
            e["evidence"] = copies + ([] if settled else evidence_for(
                fetcher, x["bible"], x["ref"], ours, with_rv=x["check"] in ("estructura", "versificación")))
            kj = kjv_text(c, x["ref"])
            if kj:
                e["evidence"].append({"source": "KJV", "match": "reference", "url": "", "verse": x["ref"].split(":")[-1], "text": kj})
        if not e.get("proposal"):
            e["proposal"] = propose(e, texts)
        known[k] = e
    for rule in crit.get("bulk", []):
        for e in known.values():
            if not e.get("decision") and e["check"] == rule["check"] and rule.get("bible", "*") in ("*", e["bible"]):
                e["decision"] = {"action": rule["action"], "note": rule["note"], "decided_by": "bulk"}
    crit["issues"] = sorted(known.values(), key=lambda e: (e["level"], e["bible"], e["check"], e["ref"]))
    # key verses: one verdict per Bible and passage, with the same version online as evidence
    rv = json.loads((ASSETS / "review-verses.json").read_text(encoding="utf-8"))["verses"]
    have = {e["key"]: e for e in crit["key_verses"]}
    for sid, rows in texts.items():
        if sid not in published:
            continue
        for item in rv:
            key = f"verse|{sid}|{item['ref']}"
            e = have.get(key) or {"key": key, "bible": sid, "ref": item["ref"], "doctrine": bool(item.get("doctrine")),
                                  "check": item["check"], "verdict": None, "note": "", "evidence": []}
            refs = expand_ref(item["ref"])
            e["text"] = " ".join(f"[{v}] {rows.get((b, ch, v), '— FALTA —')}" for b, ch, v in refs)
            e["kjv"] = " ".join(f"[{v}] {kjv(c).get((b, ch, v), '')}" for b, ch, v in refs)
            rv60 = local_bible(c, "ES-Spanish/reina-valera-1960.bblx")
            e["rv1960"] = " ".join(f"[{v}] {rv60.get((b, ch, v), '')}" for b, ch, v in refs)
            if not e["evidence"]:
                first = f"{refs[0][0]} {refs[0][1]}:{refs[0][2]}"
                e["evidence"] = evidence_for(fetcher, sid, first, rows.get(refs[0], ""), max_sources=1)
            have[key] = e
        rv60 = local_bible(c, "ES-Spanish/reina-valera-1960.bblx")
        for r in sample_refs(pack, sid, rows):
            ref = f"{r[0]} {r[1]}:{r[2]}"
            key = f"sample|{sid}|{ref}"
            e = have.get(key) or {"key": key, "bible": sid, "ref": ref, "doctrine": False, "sample": True,
                                  "check": "Muestra al azar: dice lo mismo que la RV1960 y la KJV, sin errores de digitalización",
                                  "verdict": None, "note": "", "evidence": []}
            e["text"], e["kjv"], e["rv1960"] = rows.get(r, ""), kjv(c).get(r, ""), rv60.get(r, "")
            have[key] = e
    current_keys = {f"verse|{sid}|{item['ref']}" for sid in published for item in rv} | \
                   {f"sample|{sid}|{r[0]} {r[1]}:{r[2]}" for sid in published for r in sample_refs(pack, sid, texts[sid])}
    crit["key_verses"] = [e for e in have.values() if e["key"] in current_keys]  # only the published Bibles and current lists
    path.write_text(json.dumps(crit, ensure_ascii=False, indent=1), encoding="utf-8")
    pend = sum(1 for e in crit["issues"] if not e.get("decision"))
    vpend = sum(1 for e in crit["key_verses"] if not e.get("verdict"))
    spend = sum(1 for e in crit["key_verses"] if e.get("sample") and not e.get("verdict"))
    print(f"{path}: {len(crit['issues'])} problems ({pend} without decision), {len(crit['key_verses'])} key and sample verses ({vpend} without "
          f"verdict, {spend} of them in the random sample), {len(crit['resolved'])} resolved. {fetcher.requests} web requests (cache in {fetcher.cache}).")
    if fetcher.budget <= 0:
        print(f"  The request budget ran out: run again (cached chapters are not asked again) or --fetch more")


def cmd_verify(a):
    c = cfg()
    pack = load_pack(c, a.lang)
    d = pack_dir(c, a.lang)
    con = sqlite3.connect(d / "work.db")
    ref = a.ref.upper()
    m = re.match(r"^([1-4A-Z]{3}) (\d+):(\d+)$", ref)
    if not m:
        fail("REF like 'JHN 3:16' (USFM book code)")
    key = (m.group(1), int(m.group(2)), int(m.group(3)))
    fetcher = Fetcher(c, 10)
    for b in [x for x in pack["bibles"] if x["include"] and (not a.bible or x["id"] == a.bible)]:
        row = con.execute("select text from verses where sid=? and book=? and chapter=? and verse=?", (b["id"], *key)).fetchone()
        ours = row[0] if row else ""
        print(f"\n{b['id']} (nuestra copia): {ours}")
        for ev in evidence_for(fetcher, b["id"], ref, ours, max_sources=3, with_rv=False):
            print(f"  {ev['source']} [{ev['match']}] v{ev['verse']} {('sim ' + str(ev['similarity'])) if 'similarity' in ev else ''}: {ev['text']}")
            print(f"     {ev['url']}")
    print(f"  RV1960: {local_bible(c, 'ES-Spanish/reina-valera-1960.bblx').get(key, '')}")
    print(f"  KJV: {kjv_text(c, ref)}")


def cmd_apply(a):
    c = cfg()
    pack = load_pack(c, a.lang)
    d = pack_dir(c, a.lang)
    crit = json.loads((d / "criteria.json").read_text(encoding="utf-8"))
    con = sqlite3.connect(d / "work.db")
    bibles = {b["id"]: b for b in pack["bibles"]}

    def verse(sid, ref):
        m = re.match(r"^([1-4A-Z]{3}) (\d+):(\d+)$", ref)
        row = con.execute("select text from verses where sid=? and book=? and chapter=? and verse=?",
                          (sid, m.group(1), int(m.group(2)), int(m.group(3)))).fetchone() if m else None
        return row[0] if row else ""

    applied, refused = 0, []
    for e in crit["issues"]:
        dec = e.get("decision") or {}
        # A chapter-level problem (punctuation, alignment) names the verse it fixes with "ref".
        act, sid, ref = dec.get("action"), e["bible"], dec.get("ref") or e["ref"]
        b = bibles.get(sid)
        if not act or act == "accept" or not b:
            if act == "accept" and not dec.get("note"):
                refused.append(f"{e['key']}: accept needs a note")
            continue
        if not dec.get("note"):
            refused.append(f"{e['key']}: every decision needs a note (the log)")
            continue
        co = b.setdefault("criteria_overrides", {})
        if act == "split_words":
            old = co.get(ref) or verse(sid, ref)
            w, (x, y) = dec.get("word") or e["proposal"]["word"], dec.get("into") or e["proposal"]["into"]
            m = re.search(rf"(?i)\b{re.escape(w)}\b", old)
            if not m:
                refused.append(f"{ref}: «{w}» is not in the verse")
                continue
            found = m.group(0)
            new = old[:m.start()] + found[:len(x)] + " " + found[len(x):] + old[m.end():]
            if new.replace(" ", "") != old.replace(" ", ""):
                refused.append(f"{ref}: split_words may only add spaces")
                continue
            co[ref] = new
        elif act == "use_source":
            other = dec.get("source")
            if other not in bibles or other == sid:
                refused.append(f"{ref}: use_source needs source = the id of the other copy")
                continue
            text = verse(other, ref)
            if not text:
                refused.append(f"{ref}: {other} has no text for this verse")
                continue
            co[ref] = text
        elif act == "override":
            evs = e.get("evidence", [])
            i = dec.get("evidence")
            if i is None or not 0 <= i < len(evs) or evs[i]["match"] == "reference":
                refused.append(f"{ref}: override needs evidence = the index of an online copy of the same version")
                continue
            ev = evs[i]
            agree = [x for j, x in enumerate(evs) if j != i and x["match"] != "reference" and norm_cmp(x.get("text", "")) == norm_cmp(ev["text"])]
            agree += [o for o in bibles if o != sid and bibles[o]["include"] and norm_cmp(verse(o, ref)) == norm_cmp(ev["text"])]
            if ev["match"] != "exact" and not agree:
                refused.append(f"{ref}: a '{ev['match']}' source alone is not enough: another source or the other copy must agree")
                continue
            if str(ev.get("verse")) != ref.split(":")[-1] and not dec.get("renumbered_ok"):
                refused.append(f"{ref}: the evidence is verse {ev.get('verse')} of the site; set renumbered_ok: true if that is the same verse")
                continue
            co[ref] = ev["text"]
        elif act == "move":
            # {"from": "ISA 3:25"} moves that verse to this one; {"moves": {"ISA 3:26": "ISA 3:25", ...}} several at once.
            pairs = dec.get("moves") or {ref: dec.get("from", "")}
            bad = False
            for dst, src in pairs.items():
                sm, tm = re.match(r"^([1-4A-Z]{3}) (\d+):(\d+)$", src), re.match(r"^([1-4A-Z]{3}) (\d+):(\d+)$", dst)
                if not sm or not tm or sm.group(1) != tm.group(1) or abs(int(sm.group(2)) - int(tm.group(2))) > 1:
                    refused.append(f"{dst}: move needs a verse of the same book (same or next chapter), not «{src}»")
                    bad = True
                elif not verse(sid, src):
                    refused.append(f"{dst}: {src} is empty")
                    bad = True
            if bad:
                continue
            b.setdefault("criteria_moves", {}).update(pairs)
        elif act in ("drop_extra", "append_extra"):
            b.setdefault("extra_verses_refs", {})[ref] = "drop" if act == "drop_extra" else "append"
        elif act == "reject_bible":
            b["include"] = False
            b["rejected_by_criteria"] = dec["note"]
            if pack.get("default_bible") == sid:
                refused.append(f"{sid}: it was the default Bible: choose another default_bible")
        else:
            refused.append(f"{e['key']}: unknown action {act}")
            continue
        applied += 1
    con.close()
    if refused:
        fail("Nothing applied. Refused decisions:\n  " + "\n  ".join(refused))
    save_pack(c, a.lang, pack)
    print(f"{applied} decisions applied to pack.json. Importing and validating again:")
    me = [sys.executable, str(Path(__file__).resolve())]
    subprocess.run(me + ["import", a.lang], check=True)
    r = subprocess.run(me + ["validate", a.lang])
    subprocess.run(me + ["criteria", a.lang, "--fetch", "0"])
    sys.exit(r.returncode)


def cred(target):
    class CRED(ctypes.Structure):
        _fields_ = [("Flags", ctypes.c_uint32), ("Type", ctypes.c_uint32), ("TargetName", ctypes.c_wchar_p),
                    ("Comment", ctypes.c_wchar_p), ("LastWritten", ctypes.c_uint64), ("CredentialBlobSize", ctypes.c_uint32),
                    ("CredentialBlob", ctypes.POINTER(ctypes.c_char)), ("Persist", ctypes.c_uint32),
                    ("AttributeCount", ctypes.c_uint32), ("Attributes", ctypes.c_void_p), ("TargetAlias", ctypes.c_wchar_p),
                    ("UserName", ctypes.c_wchar_p)]
    p = ctypes.POINTER(CRED)()
    if not ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(p)):
        fail(f"No credential '{target}' in the Windows Credential Manager (see scripts/publish-manifest.md of the app)")
    try:
        blob = ctypes.string_at(p.contents.CredentialBlob, p.contents.CredentialBlobSize)
        secret = blob.decode("utf-16-le") if b"\x00" in blob else blob.decode()
        return p.contents.UserName, secret
    finally:
        ctypes.windll.advapi32.CredFree(p)


def cmd_publish(a):
    c = cfg()
    pack = load_pack(c, a.lang)
    d = pack_dir(c, a.lang)
    b = pack.get("build")
    if not b:
        fail(f"Run  pack.py build {a.lang}  first")
    obb = d / b["file"]
    if sha256_file(obb) != b["sha256"]:
        fail("The .obb changed after the build: build again")
    lang = pack["module_language"]
    key = f"bible/modules/{b['file']}"
    url = f"https://cdn.timelesslabs.app/{key}"
    mpath = c["app_repo"] / "cdn" / "bible" / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    entry = {"url": f"modules/{b['file']}", "size": b["size"], "sha256": b["sha256"]}
    print(f"Plan:\n  1. Upload {obb} ({b['size'] / 1e6:.1f} MB) to R2 {c.get('bucket', 'timelesslabs-cdn')}/{key}")
    print(f"  2. Check {url} serves {b['size']} bytes")
    print(f"  3. cdn/bible/manifest.json: languages.{lang} = {json.dumps(entry)}"
          + (f" (replaces {manifest['languages'][lang]['url']})" if lang in manifest.get("languages", {}) else " (new)"))
    print("  4. Then the manifest goes live with  .\\scripts\\publish-manifest.ps1 -DryRun  and  .\\scripts\\publish-manifest.ps1")
    if not a.yes:
        print("Nothing changed. Run again with --yes to upload (the app only uses it once it knows the language: app-integration.md).")
        return
    account, token = cred(c.get("credential", "BibleVersions-Cloudflare"))
    env = {**os.environ, "CLOUDFLARE_API_TOKEN": token, "CLOUDFLARE_ACCOUNT_ID": account}
    r = subprocess.run(["npx", "--yes", "wrangler@4", "r2", "object", "put", f"{c.get('bucket', 'timelesslabs-cdn')}/{key}",
                        "--file", str(obb), "--content-type", "application/octet-stream", "--remote"], env=env, shell=True)
    if r.returncode:
        fail("wrangler upload failed")
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as resp:
        length = int(resp.headers.get("Content-Length", "0"))
    if length != b["size"]:
        fail(f"The CDN serves {length} bytes, expected {b['size']}")
    manifest.setdefault("languages", {})[lang] = entry
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pack["published"] = {"date": TODAY, "url": url}
    save_pack(c, a.lang, pack)
    tracker_log(c, a.lang, f"{b['file']} subido al CDN; falta publicar manifest.json y la versión de la app que conoce el idioma")
    print(f"OK: {url} ({length} bytes). manifest.json updated locally: run  .\\scripts\\publish-manifest.ps1 -DryRun  from {c['app_repo']}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("init"); p.add_argument("lang"); p.add_argument("--force", action="store_true")
    for name in ("import", "validate", "build"):
        sub.add_parser(name).add_argument("lang")
    p = sub.add_parser("approve"); p.add_argument("lang"); p.add_argument("--by", required=True); p.add_argument("--notes")
    p = sub.add_parser("criteria"); p.add_argument("lang"); p.add_argument("--fetch", type=int, default=150)
    p = sub.add_parser("verify"); p.add_argument("lang"); p.add_argument("ref"); p.add_argument("--bible")
    p = sub.add_parser("fetch"); p.add_argument("lang"); p.add_argument("source")
    sub.add_parser("review").add_argument("lang")
    sub.add_parser("apply").add_argument("lang")
    p = sub.add_parser("publish"); p.add_argument("lang"); p.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    {"status": cmd_status, "init": cmd_init, "import": cmd_import, "validate": cmd_validate, "approve": cmd_approve,
     "build": cmd_build, "publish": cmd_publish, "criteria": cmd_criteria, "verify": cmd_verify, "apply": cmd_apply, "fetch": cmd_fetch, "review": cmd_review}[a.cmd](a)


if __name__ == "__main__":
    main()
