"""From an approved language pack to a language ready to publish in Bible Versions (everything except the Play
release, the website deploy and the commits). One stage at a time, with its state in packs/<lang>/ship.json, so it
can run unattended (a /loop) until every language of the tracker is done.

  ship.py status                     every language and its stages
  ship.py next                       the next stage to do (first language of the tracker with work left)
  ship.py check <lang> [stage]       runs the automatic checks and marks the stages that pass
  ship.py cdn <lang>                 uploads the validated .obb, adds it to the manifest and publishes the manifest
  ship.py strings <lang>             checks values-<xx>/strings.xml against values/ (English: keys, placeholders, plurals, arrays)
  ship.py about                      writes assets/legal/bible_modules_<ui>.md for every UI language from module-credits.json
  ship.py web <lang>                 checks the website texts of the language (keys, site.json) and builds it (no deploy)
  ship.py play <lang>                checks the Play listing, changelog and screenshots of the language
  ship.py flows <lang>               writes the Maestro flows of the language (key verses + the 8 screenshots)
  ship.py device <lang> prep|restore backs up the phone, sets the app's language (per-app locale) / restores it
  ship.py shots <lang>               takes the raw Maestro screenshots to play/images/<locale>/phoneScreenshots (1080x2340)
  ship.py feature <lang>             the Play feature graphic of the language (play-feature-graphic skill) from those screenshots
  ship.py mark <lang> <stage> [--note ...]   records a stage done by hand (Claude's work: translations, device checks)
  ship.py report <lang>              what is ready and what is missing to publish the language

Paths: config.json next to this script (see SETUP.md).
"""
import argparse, datetime, glob, hashlib, json, os, re, shutil, sqlite3, subprocess, sys, time, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
TODAY = datetime.date.today().isoformat()
PACKAGE = "com.timeless.bible"
ADB = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"

STAGES = [
    ("pack", "Biblia validada, revisada con criterio y paquete armado (skill bible-language-pack)"),
    ("cdn", "El .obb en Cloudflare y en el manifiesto publicado, con el mismo sha256"),
    ("app_core", "Una sola vez para todos los idiomas: idiomas en assets/languages.json, voz con aviso amable, 'Biblias y comentarios' en Acerca de, localeConfig por app"),
    ("app_language", "El idioma en assets/languages.json (paquete, Biblia por defecto, voces)"),
    ("strings", "Interfaz traducida: values-<xx>/strings.xml completo y válido"),
    ("legal", "Documentos de Acerca de en inglés: no se traducen (las cadenas *_file del idioma no existen o apuntan a los *_en.md)"),
    ("about", "Biblias y comentarios: la Biblia nueva en module-credits.json y bible_modules_en.md / _es.md regenerados"),
    ("web", "La interfaz de la web en el idioma (textos de i18n, idioma en site.json, build sin deploy); los documentos legales quedan en inglés"),
    ("play", "Ficha de Play en el idioma (título, descripción corta y completa, notas de versión)"),
    ("unit", "Tests unitarios y build debug sin errores"),
    ("tts", "Voz probada en el teléfono: lee en el idioma, o muestra el aviso amable si no hay voz"),
    ("device_text", "Maestro: los versículos clave se ven igual que en el módulo, sin caracteres raros"),
    ("screenshots", "Las 8 capturas de teléfono de Play en el idioma (las de tablet quedan las inglesas)"),
    ("feature", "La imagen destacada de Play en el idioma (1024x500, skill play-feature-graphic)"),
    ("ready", "Todo listo para publicar (falta solo: release en Play, deploy de la web y commits)"),
]
AUTO = {"pack", "cdn", "app_language", "strings", "legal", "about", "web", "play", "screenshots", "feature"}
UI_DOCS = ["privacy", "terms", "licenses", "photo_credits", "bible_modules"]


# ---------------------------------------------------------------------------------------------- basics
def cfg():
    p = Path(os.environ.get("BIBLE_SHIP_CONFIG") or HERE / "config.json")
    if not p.exists():
        fail(f"Missing {p}: see SETUP.md")
    c = json.loads(p.read_text(encoding="utf-8"))
    for k in ("app_repo", "packs_dir", "play_dir", "website_site", "tracker", "pack_script", "web_script"):
        c[k] = Path(c[k])
    return c


def fail(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def locales():
    return json.loads((ASSETS / "locales.json").read_text(encoding="utf-8"))["languages"]


def pack_of(c, lang):
    p = c["packs_dir"] / lang.replace(" / ", "-") / "pack.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def state_path(c, lang):
    return c["packs_dir"] / lang.replace(" / ", "-") / "ship.json"


def load_state(c, lang):
    p = state_path(c, lang)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"lang": lang, "stages": {}}


def save_state(c, lang, st):
    p = state_path(c, lang)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mark(c, lang, stage, note="", ok=True):
    st = load_state(c, lang)
    if ok:
        st["stages"][stage] = {"done": TODAY, "note": note}
    else:
        st["stages"].pop(stage, None)
    save_state(c, lang, st)


def global_state(c):
    p = c["packs_dir"] / "_ship_global.json"
    return p, (json.loads(p.read_text(encoding="utf-8")) if p.exists() else {})


def module_lang(c, lang):
    pk = pack_of(c, lang)
    return (pk or {}).get("module_language") or lang.lower()


def tracker_codes(c):
    codes, header = [], None
    for line in c["tracker"].read_text(encoding="utf-8").split("\n"):
        cells = [x.strip() for x in line.split("|")]
        if "Código" in cells and "Idioma" in cells:
            header = cells
        elif header and len(cells) == len(header) and cells[1].isdigit():
            codes.append(cells[header.index("Código")])
    return codes


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bible-versions ship)"})
    return urllib.request.urlopen(req, timeout=60).read()


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------- checks
def check_pack(c, lang):
    pk = pack_of(c, lang)
    if not pk:
        return False, "No packs/<lang>/pack.json: run the bible-language-pack skill first"
    if not pk.get("approval") or not pk.get("build"):
        return False, "Pack not approved and built (bible-language-pack: criteria, approve, build)"
    obb = c["packs_dir"] / lang.replace(" / ", "-") / pk["build"]["file"]
    if not obb.exists() or sha256(obb) != pk["build"]["sha256"]:
        return False, f"{obb.name} missing or changed after the build"
    return True, f"{pk['build']['file']} ({pk['build']['size'] / 1e6:.1f} MB)"


def check_cdn(c, lang):
    pk = pack_of(c, lang)
    if not pk or not pk.get("build"):
        return False, "no build"
    try:
        manifest = json.loads(get("https://cdn.timelesslabs.app/bible/manifest.json"))
    except Exception as e:
        return False, f"manifest not readable: {e}"
    entry = manifest.get("languages", {}).get(pk["module_language"])
    if not entry:
        return False, f"languages.{pk['module_language']} is not in the published manifest"
    if entry["sha256"] != pk["build"]["sha256"]:
        return False, "the published manifest points to another build (run  ship.py cdn)"
    return True, entry["url"]


def app_languages(c):
    p = c["app_repo"] / "app" / "src" / "main" / "assets" / "languages.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def check_app_language(c, lang):
    data = app_languages(c)
    if data is None:
        return False, "assets/languages.json does not exist yet: stage app_core (one time)"
    code = module_lang(c, lang)
    e = next((x for x in data.get("languages", []) if x.get("code") == code), None)
    if not e:
        return False, f"{code} is not in assets/languages.json"
    # LanguageCatalog leaves out an entry without these (the app would not show the language).
    missing = [k for k in ("nativeName", "defaultBible", "defaultCommentary", "dailyImage", "quiz", "reference", "tts")
               if not e.get(k)]
    if missing:
        return False, f"{code} in assets/languages.json lacks {missing}"
    ids = {m["id"] for m in (pack_of(c, lang) or {}).get("build", {}).get("modules", [])}
    own = {e.get(k) for k in ("defaultCommentary", "dailyImage", "quiz", "reference")}
    if not own <= ids and "en" not in (e.get("requires") or []):
        return False, f"{code} uses English modules (commentary, quiz, images, references) but does not require \"en\""
    pk = pack_of(c, lang)
    ids = {m["id"] for m in (pk or {}).get("build", {}).get("modules", [])}
    if pk and e.get("defaultBible") not in ids:
        return False, f"defaultBible {e.get('defaultBible')} is not a module of the build {sorted(ids)}"
    if pk and int(e.get("sizeInBytes", 0)) != pk["build"]["size"]:
        return False, "sizeInBytes differs from the build"
    return True, f"defaultBible {e['defaultBible']}"


def parse_strings(path):
    root = ET.parse(path).getroot()
    out = {"string": {}, "plurals": {}, "array": {}}
    for el in root:
        name = el.get("name")
        if el.tag == "string":
            out["string"][name] = ("".join(el.itertext()), el.get("translatable"))
        elif el.tag == "plurals":
            out["plurals"][name] = {i.get("quantity"): "".join(i.itertext()) for i in el.findall("item")}
        elif el.tag in ("string-array", "array"):
            out["array"][name] = ["".join(i.itertext()) for i in el.findall("item")]
    return out


PH = re.compile(r"%(?:\d+\$)?[sdf]|\{\d\}")


# Strings that are the same in every language: the brand, addresses, templates with no words.
SAME_IN_EVERY_LANGUAGE = {"app_name", "web", "web_url", "subject", "copyright", "privacy_link", "according"}


def ui_of(c, lang):
    """The interface language from assets/languages.json ("ui"), when the pack has no translation of
    its own (Quechua and Guarani show Spanish: decided by the user, 2026-10-22). None otherwise."""
    data = app_languages(c) or {}
    code = module_lang(c, lang)
    e = next((x for x in data.get("languages", []) if x.get("code") == code), None)
    ui = (e or {}).get("ui")
    return ui if ui and ui != code else None


def check_strings(c, lang, verbose=True):
    ui = ui_of(c, lang)
    if ui:
        return True, f"interface in {ui} (\"ui\" in languages.json): no values folder of its own"
    loc = locales().get(module_lang(c, lang))
    if not loc:
        return False, f"{module_lang(c, lang)} is not in assets/locales.json"
    res = c["app_repo"] / "app" / "src" / "main" / "res"
    # values/ is English (the fallback, stage app_core); Spanish is in values-es/.
    en, tgt = res / "values" / "strings.xml", res / loc["values"] / "strings.xml"
    if not tgt.exists():
        return False, f"{tgt} does not exist (translate values/strings.xml, the English texts)"
    try:
        E, T = parse_strings(en), parse_strings(tgt)
    except ET.ParseError as e:
        return False, f"invalid XML: {e}"
    problems = []
    raw = tgt.read_text(encoding="utf-8")
    # Words that are the same in the language ("Menu", "Quiz" in Portuguese), declared in the file itself:
    # <!-- same-as-english: menu quiz -->
    same_ok = set(" ".join(re.findall(r"<!--\s*same-as-english:([^>]*?)-->", raw)).split())
    for n, (text, tr) in E["string"].items():
        if tr == "false" or n.endswith("_file"):
            continue  # documents are not translated: the English fallback (values/) points to the English files
        if n not in T["string"]:
            problems.append(f"missing string {n}")
            continue
        t = T["string"][n][0]
        if sorted(PH.findall(text)) != sorted(PH.findall(t)):
            problems.append(f"{n}: placeholders {PH.findall(text)} -> {PH.findall(t)}")
        if t.strip() == text.strip() and len(text) > 3 and not re.match(r"^[\W\d_]*$", PH.sub("", text)) \
                and n not in SAME_IN_EVERY_LANGUAGE and n not in same_ok:
            problems.append(f"{n}: still in English: {text[:60]}")
    for n, items in E["plurals"].items():
        if n not in T["plurals"]:
            problems.append(f"missing plurals {n}")
            continue
        need = set(loc["plurals"])
        have = set(T["plurals"][n])
        if not need <= have:
            problems.append(f"plurals {n}: needs {sorted(need)}, has {sorted(have)}")
        for q, t in T["plurals"][n].items():
            if sorted(set(PH.findall(items.get("other", "")))) != sorted(set(PH.findall(t))) and PH.findall(items.get("other", "")):
                problems.append(f"plurals {n}/{q}: placeholders differ")
    for n, items in E["array"].items():
        if n in T["array"] and len(T["array"][n]) != len(items):
            problems.append(f"array {n}: {len(T['array'][n])} items, English has {len(items)}")
        elif n not in T["array"] and not re.search(r"(count|value|ids?)$", n):
            problems.append(f"missing array {n}")
    if re.search(r"(?<!\\)'", re.sub(r"<!--.*?-->", "", raw, flags=re.S).replace("&apos;", "")) and "'" in raw:
        bad = [m.group(0) for m in re.finditer(r"<string[^>]*>[^<]*(?<!\\)'[^<]*</string>", raw)][:3]
        if bad:
            problems.append(f"unescaped apostrophes (use \\'): {bad}")
    if verbose and problems:
        print("\n".join("  - " + p for p in problems[:80]))
        if len(problems) > 80:
            print(f"  ... {len(problems) - 80} more")
    return (not problems), (f"{len(T['string'])} strings OK" if not problems else f"{len(problems)} problems")


def check_legal(c, lang):
    ui = ui_of(c, lang)
    if ui:
        return True, f"documents of the {ui} interface (its values folder)"
    loc = locales().get(module_lang(c, lang))
    res = c["app_repo"] / "app" / "src" / "main" / "res" / loc["values"] / "strings.xml"
    if not res.exists():
        return False, "no strings yet"
    T = parse_strings(res)["string"]
    default = c["app_repo"] / "app" / "src" / "main" / "res" / "values" / "strings.xml"
    D = parse_strings(default)["string"] if default.exists() else {}
    problems = []
    for key in ("privacy_file", "legal_file", "licence_file", "image_credits_file", "bible_modules_file"):
        own = T.get(key, (None,))[0]
        path = own if own is not None else D.get(key, ("",))[0]
        if own is not None and not re.search(r"_en\.md$", own):
            problems.append(f"{key} -> {own}: the documents stay in English (remove it from {loc['values']})")
        elif not path or not re.search(r"_en\.md$", path):
            problems.append(f"{key}: the fallback (values/) does not point to the English document ({path or 'missing'}): stage app_core")
        elif not (c["app_repo"] / "app" / "src" / "main" / "assets" / path).exists():
            problems.append(f"{key}: {path} does not exist")
    return (not problems), ("documents in English, as decided" if not problems else "; ".join(problems))


def credits_path(c):
    return c["app_repo"] / "cdn" / "bible" / "module-credits.json"


def check_about(c, lang):
    p = credits_path(c)
    if not p.exists():
        return False, "module-credits.json does not exist yet (stage app_core)"
    credits = json.loads(p.read_text(encoding="utf-8"))
    pk = pack_of(c, lang) or {}
    ids = [m["id"] for m in pk.get("build", {}).get("modules", [])]
    have = {m["id"] for m in credits["modules"]}
    missing = [i for i in ids if i not in have]
    if missing:
        return False, f"module ids {missing} are not in module-credits.json"
    md = sorted((c["app_repo"] / "app" / "src" / "main" / "assets" / "legal").glob("bible_modules_*.md"))
    if not md:
        return False, "no bible_modules_<ui>.md: run  ship.py about"
    # Hidden modules (publisher copyright, permission pending) are never listed in the documents.
    hidden = {m["id"] for m in credits["modules"] if m.get("status") == "hidden"}
    abbr = [m["abbreviation"] for m in pk.get("build", {}).get("modules", []) if m["id"] not in hidden]
    stale = [f.name for f in md if any(a not in f.read_text(encoding="utf-8") for a in abbr)]
    return (not stale), ("credits and documents up to date" if not stale else f"regenerate (ship.py about): {stale}")


def check_web(c, lang):
    ui = ui_of(c, lang)
    if ui:
        return True, f"no page of its own: its readers use the {ui} page"
    code = module_lang(c, lang)
    site = c["website_site"]
    en = site / "src" / "i18n" / "en.json"
    tgt = site / "src" / "i18n" / f"{code}.json"
    if not tgt.exists():
        return False, f"{tgt} does not exist (translate en.json)"

    def keys(d, prefix=""):
        out = set()
        if isinstance(d, dict):
            for k, v in d.items():
                out |= keys(v, f"{prefix}{k}.")
        elif isinstance(d, list):
            out.add(f"{prefix}[{len(d)}]")
            for i, v in enumerate(d):
                out |= keys(v, f"{prefix}{i}.")
        else:
            out.add(prefix.rstrip("."))
        return out
    E, T = json.loads(en.read_text(encoding="utf-8")), json.loads(tgt.read_text(encoding="utf-8"))
    diff = sorted(keys(E) ^ keys(T))
    if diff:
        return False, f"keys differ from en.json: {diff[:8]}"
    sj = json.loads((site / "site.json").read_text(encoding="utf-8"))
    if code not in sj.get("locales", []):
        return False, f"{code} is not in site.json locales"
    return True, "texts and locales OK (run the build with  ship.py web)"


def play_locale(c, lang):
    return locales().get(module_lang(c, lang), {}).get("play")


def check_play(c, lang):
    pl = play_locale(c, lang)
    if pl is None:
        return True, "Play has no listing language for it: the English listing is used (add keywords there)"
    d = c["play_dir"] / "listing" / pl
    limits = {"title.txt": 30, "short.txt": 80, "full.txt": 4000}
    problems = []
    for f, n in limits.items():
        p = d / f
        if not p.exists():
            problems.append(f"missing {p}")
        elif len(p.read_text(encoding="utf-8").strip()) > n:
            problems.append(f"{f} has {len(p.read_text(encoding='utf-8').strip())} characters (max {n})")
    en_logs = sorted((c["play_dir"] / "changelogs" / "en-US").glob("*.txt"), key=lambda p: int(p.stem))
    if en_logs:
        latest = en_logs[-1].name
        p = c["play_dir"] / "changelogs" / pl / latest
        if not p.exists():
            problems.append(f"missing changelog {pl}/{latest} (same version as en-US)")
        elif len(p.read_text(encoding="utf-8")) > 500:
            problems.append(f"changelog {latest} over 500 characters")
    pj = json.loads((c["play_dir"] / "play.json").read_text(encoding="utf-8"))
    if pl not in pj.get("languages", []):
        problems.append(f"{pl} is not in play.json languages")
    return (not problems), ("listing OK" if not problems else "; ".join(problems))


def check_screenshots(c, lang):
    pl = play_locale(c, lang) or None
    if pl is None:
        return True, "no Play listing language: screenshots not needed"
    d = c["play_dir"] / "images" / pl / "phoneScreenshots"
    files = sorted(d.glob("0[1-8].png")) if d.exists() else []
    if len(files) < 8:
        return False, f"{len(files)}/8 screenshots in {d}"
    from PIL import Image
    bad = [f.name for f in files if Image.open(f).size != (1080, 2340)]
    return (not bad), ("8 screenshots 1080x2340" if not bad else f"wrong size: {bad}")


def check_feature(c, lang):
    pl = play_locale(c, lang)
    if pl is None:
        return True, "no Play listing language: the English feature graphic is used"
    f = c["play_dir"] / "images" / pl / "featureGraphic.png"
    if not f.exists():
        return False, f"missing {f} (ship.py feature)"
    from PIL import Image
    im = Image.open(f)
    if im.size != (1024, 500) or im.mode != "RGB":
        return False, f"{f.name} is {im.size} {im.mode}: must be 1024x500 RGB without alpha"
    return True, "feature graphic 1024x500"


CHECKS = {"feature": check_feature, "pack": check_pack, "cdn": check_cdn, "app_language": check_app_language, "strings": check_strings,
          "legal": check_legal, "about": check_about, "web": check_web, "play": check_play, "screenshots": check_screenshots}


def run_checks(c, lang, only=None):
    st = load_state(c, lang)
    for name, _ in STAGES:
        if only and name != only:
            continue
        if name == "app_core":
            _, g = global_state(c)
            ok = bool(g.get("app_core"))
            print(f"  {'✓' if ok else '·'} app_core: {'done ' + g['app_core'] if ok else 'pending (one time)'}")
            continue
        if name in CHECKS:
            ok, msg = CHECKS[name](c, lang)
            print(f"  {'✓' if ok else '✗'} {name}: {msg}")
            if ok:
                st["stages"][name] = {"done": st["stages"].get(name, {}).get("done", TODAY), "note": msg}
            else:
                st["stages"].pop(name, None)
        else:
            s = st["stages"].get(name)
            print(f"  {'✓' if s else '·'} {name}: {s['note'] if s else 'by hand: ' + dict(STAGES)[name]}")
    save_state(c, lang, st)
    return st


# ---------------------------------------------------------------------------------------------- commands
def cmd_status(a):
    c = cfg()
    _, g = global_state(c)
    print(f"app_core (one time): {'done ' + g['app_core'] if g.get('app_core') else 'pending'}")
    for lang in tracker_codes(c):
        st = load_state(c, lang)
        done = [n for n, _ in STAGES if n in st["stages"] or (n == "app_core" and g.get("app_core"))]
        if pack_of(c, lang) or st["stages"]:
            print(f"{lang:10} {len(done):2}/{len(STAGES)}  next: {next((n for n, _ in STAGES if n not in done), '-')}")


def next_stage(c, lang):
    _, g = global_state(c)
    st = load_state(c, lang)
    for n, desc in STAGES:
        if n == "app_core":
            if not g.get("app_core"):
                return n, desc
        elif n not in st["stages"]:
            return n, desc
    return None, None


def cmd_next(a):
    c = cfg()
    codes = tracker_codes(c)
    # Languages already started go first, so one language is finished before the next one begins.
    order = [a.lang] if a.lang else [x for x in codes if pack_of(c, x)] + [x for x in codes if not pack_of(c, x)]
    for lang in order:
        if lang in ("en", "es"):
            continue
        pk = pack_of(c, lang)
        if not pk:
            print(f"NEXT: {lang} — bible-language-pack (no pack yet): pack.py init {lang}")
            return
        run_checks(c, lang)
        n, desc = next_stage(c, lang)
        if n:
            print(f"NEXT: {lang} — {n}: {desc}")
            return
    print("NEXT: nothing — every language of the tracker is ready")


def cmd_check(a):
    c = cfg()
    run_checks(c, a.lang, a.stage)


def cmd_cdn(a):
    c = cfg()
    ok, msg = check_pack(c, a.lang)
    if not ok:
        fail(msg)
    ok, msg = check_cdn(c, a.lang)
    if ok:
        print(f"Already live: {msg}")
        mark(c, a.lang, "cdn", msg)
        return
    r = subprocess.run([sys.executable, str(c["pack_script"]), "publish", a.lang, "--yes"])
    if r.returncode:
        fail("pack.py publish failed")
    ps = c["app_repo"] / "scripts" / "publish-manifest.ps1"
    for extra in (["-DryRun"], []):
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps), *extra], cwd=c["app_repo"])
        if r.returncode:
            fail(f"publish-manifest.ps1 {' '.join(extra)} failed: nothing else published")
    ok, msg = check_cdn(c, a.lang)
    if not ok:
        fail(msg)
    mark(c, a.lang, "cdn", msg)
    print(f"OK: {msg} is live in the manifest (the current app ignores languages it does not know)")


def cmd_strings(a):
    c = cfg()
    ok, msg = check_strings(c, a.lang)
    print(("OK: " if ok else "NOT OK: ") + msg)
    mark(c, a.lang, "strings", msg, ok)
    sys.exit(0 if ok else 1)


ABOUT_TEXT = {
    "_comment": "Titles of bible_modules_<ui>.md. A UI language without an entry gets its translation by Claude in the 'legal' stage (add it here).",
    "es": {"title": "Biblias y comentarios", "intro": "Estos son los textos bíblicos y comentarios de dominio público o de licencia libre que incluye la app. Agradecemos a los traductores, editores y organizaciones que los pusieron al alcance de todos.",
           "bibles": "Biblias", "commentaries": "Comentarios", "year": "Año", "by": "Traducción", "author": "Autor", "licence": "Licencia", "source": "Fuente", "notes": "Notas",
           "footer": "Si encuentras un error en algún texto, escríbenos desde la app."},
    "en": {"title": "Bibles and commentaries", "intro": "These are the public-domain and openly licensed Bible texts and commentaries included in the app. We thank the translators, publishers and organizations who made them available to everyone.",
           "bibles": "Bibles", "commentaries": "Commentaries", "year": "Year", "by": "Translation", "author": "Author", "licence": "Licence", "source": "Source", "notes": "Notes",
           "footer": "If you find a mistake in a text, write to us from the app."},
}


def cmd_about(a):
    c = cfg()
    p = credits_path(c)
    if not p.exists():
        fail("module-credits.json does not exist: stage app_core copies assets/module-credits.seed.json there")
    credits = json.loads(p.read_text(encoding="utf-8"))
    review = [m for m in credits["modules"] if m.get("status") == "review"]
    hidden = [m for m in credits["modules"] if m.get("status") == "hidden"]
    texts_path = c["app_repo"] / "cdn" / "bible" / "about-texts.json"
    texts = json.loads(texts_path.read_text(encoding="utf-8")) if texts_path.exists() else ABOUT_TEXT
    if not texts_path.exists():
        texts_path.write_text(json.dumps(ABOUT_TEXT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shown = [m for m in credits["modules"] if m.get("status") == "ok" and m.get("pack") != "es"]  # never the full Spanish pack
    missing = [m for m in shown for f in ("language", "name", "abbreviation") if not m.get(f)]
    if missing:
        fail("module-credits.json: entries without language, name or abbreviation: "
             + ", ".join(sorted({str(m.get("id")) for m in missing})))

    def loc(value, ui):
        # A plain string is the same in every document; else {"en": ..., "es": ...}.
        if isinstance(value, dict):
            return value.get(ui) or value.get("en") or ""
        return value or ""

    # The English pack first, then lite Spanish, then the new languages in the order they were added.
    packs = []
    for m in shown:
        if m["pack"] not in packs:
            packs.append(m["pack"])
    packs.sort(key=lambda x: (x != "en", x != "esp"))
    out_dir = c["app_repo"] / "app" / "src" / "main" / "assets" / "legal"
    for ui in ("en", "es"):  # the documents are only in English and Spanish (user's decision 2026-10-21)
        t = texts[ui]
        lines = [f"# {t['title']}", "", t["intro"], ""]
        for pack in packs:
            in_pack = [m for m in shown if m["pack"] == pack]
            lines += [f"## {loc(in_pack[0]['language'], ui)}", ""]
            for kind, label in (("bible", t["bibles"]), ("commentary", t["commentaries"])):
                mods = [m for m in in_pack if m["type"] == kind]
                if not mods:
                    continue
                lines += [f"### {label}", ""]
                for m in mods:
                    lines.append(f"**{m['name']}** ({m['abbreviation']})")
                    lines.append("")
                    by_label = t.get("author", t["by"]) if kind == "commentary" else t["by"]
                    rows = [(t["year"], loc(m.get("year"), ui)), (by_label, loc(m.get("by"), ui)),
                            (t["licence"], loc(m.get("licence"), ui)), (t["source"], loc(m.get("source"), ui)),
                            (t["notes"], loc(m.get("notes"), ui))]
                    lines += [f"- {k}: {v}" for k, v in rows if v]
                    lines.append("")
            lines += ["---", ""]
        lines += [f"*{t['footer']}*", ""]
        (out_dir / f"bible_modules_{ui}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
        print(f"  wrote assets/legal/bible_modules_{ui}.md ({len(shown)} modules)")
    for m in hidden:
        print(f"  hidden (editorial copyright or permission needed, never shown): {m['id']} {m['name']}")
    if review:
        print("NOT SHOWN until the user confirms the licence (status review):")
        for m in review:
            print(f"  - {m['id']} {m['name']}: {m.get('review_note', '')}")


def cmd_web(a):
    c = cfg()
    ok, msg = check_web(c, a.lang)
    print(("OK: " if ok else "NOT OK: ") + msg)
    if not ok:
        mark(c, a.lang, "web", msg, False)
        sys.exit(1)
    r = subprocess.run([sys.executable, str(c["web_script"]), "build", c.get("website_slug", "bibleversions")], cwd=c["website_site"].parent.parent)
    mark(c, a.lang, "web", "texts OK, build OK (not deployed)" if r.returncode == 0 else "build failed", r.returncode == 0)
    sys.exit(r.returncode)


def cmd_play(a):
    c = cfg()
    ok, msg = check_play(c, a.lang)
    print(("OK: " if ok else "NOT OK: ") + msg)
    mark(c, a.lang, "play", msg, ok)
    sys.exit(0 if ok else 1)


KEY_VERSES = [("GEN", 1, 1), ("PSA", 23, 1), ("ISA", 53, 5), ("MAT", 1, 21), ("MAT", 1, 25), ("LUK", 1, 28), ("JHN", 1, 1),
              ("JHN", 3, 16), ("ROM", 3, 28), ("ROM", 5, 1), ("EPH", 2, 8), ("1TI", 2, 5), ("HEB", 9, 27), ("REV", 22, 21)]
BOOKS = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZK DAN HOS "
         "JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM "
         "HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()


def maestro_regex(text):
    """A regex that matches the start of the verse as the app shows it (the first words, escaped). The brackets
    stay: the app shows them, as the Synodal's mark of the words added by the translators ("[Как]", Mt 1:25)."""
    words = re.sub(r"\s+", " ", text).strip().split(" ")[:6]
    # Python's \s matches the ideographic space (U+3000, "起初，　神" in the Chinese Union Version);
    # Maestro's regex (Java) does not, so the gaps take it explicitly.
    return ".*" + re.escape(" ".join(words)).replace("\\ ", "[\\s\\u3000]+") + ".*"


def cmd_flows(a):
    c = cfg()
    pk = pack_of(c, a.lang)
    if not pk or not pk.get("build"):
        fail("No build")
    code = pk["module_language"]
    loc = locales()[code]
    # A pack shown in another interface language ("ui") uses that language's book names.
    ui = ui_of(c, a.lang)
    values = (locales().get(ui) or {}).get("values", f"values-{ui}") if ui else loc["values"]
    strings = c["app_repo"] / "app" / "src" / "main" / "res" / values / "strings.xml"
    names = parse_strings(strings)["array"].get("book_names") if strings.exists() else None
    if not names or len(names) != 66:
        fail(f"book_names (66) missing in {strings}: translate the UI first (stage strings)")
    default = next(m for m in pk["build"]["modules"] if m["source"] == pk["default_bible"])
    d = c["app_repo"] / ".maestro" / "languages" / code
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("verify_*.yaml"):
        old.unlink()
    # One flow per Bible of the pack, opened by its module id (short names repeat across languages:
    # "ULB", "IRV"), and verify_text.yaml that runs them all.
    per_module = []
    for mod in pk["build"]["modules"]:
        bblx = c["packs_dir"] / a.lang.replace(" / ", "-") / "build" / mod["file"]
        con = sqlite3.connect(f"file:{bblx}?mode=ro", uri=True)
        lines = [f"# Generated by bible-language-ship: the key verses of {mod['abbreviation']} (module {mod['id']}, {code}) look",
                 "# exactly as in the module (first words), and no verse on screen shows RTF/HTML/markup or replacement characters.",
                 f"appId: {PACKAGE}", f"name: Verse text in {code} module {mod['id']}", "tags:", "  - language", "---",
                 "- runFlow: ../../subflows/launch.yaml"]
        count = 0
        for bk, ch, v in KEY_VERSES:
            row = con.execute("select Scripture from Bible where Book=? and Chapter=? and Verse=?", (BOOKS.index(bk) + 1, ch, v)).fetchone()
            if not row or not row[0].strip():
                continue
            count += 1
            lines += ["- runFlow:", "    file: ../../subflows/open_passage.yaml", "    env:",
                      f"      BOOK_NUMBER: {BOOKS.index(bk) + 1}", f"      BOOK: \"{names[BOOKS.index(bk)]}\"",
                      f"      CHAPTER: {ch}", f"      VERSE: {v}", f"      VERSION: {json.dumps(mod['abbreviation'], ensure_ascii=False)}",
                      f"      MODULE_ID: {mod['id']}",
                      "- assertVisible:", f"    text: {json.dumps(maestro_regex(row[0]), ensure_ascii=False)}",
                      "- assertNotVisible:", "    text: \".*(\\\\[a-z]+[0-9]*|\\\\{|\\\\}|\\ufffd|&lt;|&#[0-9]+;|\\\\|strong=).*\""]
        con.close()
        name = f"verify_{mod['id']}.yaml"
        (d / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        per_module.append((name, mod, count))
    lines = [f"# Generated by bible-language-ship: the key verses of every Bible of the {code} pack, module by module.",
             f"appId: {PACKAGE}", "name: Verse text in " + code, "tags:", "  - language", "---"]
    for name, mod, _ in per_module:
        lines += ["- runFlow:", f"    file: {name}"]
    (d / "verify_text.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # The 8 Play screenshots with this language's Bible and book name. The values go in the flow, not on
    # the command line: PowerShell 5.1 garbles non-ASCII arguments (Cyrillic, accents) for native programs.
    shots = sorted(p.name for p in (c["app_repo"] / ".maestro" / "screenshots").glob("0[1-8]_*.yaml"))
    if len(shots) != 8:
        fail(f"{len(shots)}/8 flows in .maestro/screenshots (stage app_core)")
    wrapper = [f"# Generated by bible-language-ship: the 8 Play phone screenshots in {code}, saved to",
               f"# build/maestro/screenshots/{code}/ (then  ship.py shots {a.lang}).",
               f"appId: {PACKAGE}", "name: Screenshots " + code, "env:", f"  LANG: \"{code}\"",
               f"  BIBLE: \"{default['abbreviation']}\"", f"  BIBLE_ID: \"{default['id']}\"",
               # right to left: the line starts on the right (subflows/select_verse.yaml)
               f"  RTL: \"{'true' if loc.get('rtl') else 'false'}\"",
               f"  GENESIS: \"{names[0]}\"", "---"]
    for name in shots:
        wrapper += ["- runFlow:", f"    file: ../../screenshots/{name}"]
    (d / "screenshots.yaml").write_text("\n".join(wrapper) + "\n", encoding="utf-8")
    for name, mod, count in per_module:
        print(f"  {name}: {mod['abbreviation']} ({count} key verses)")
    print(f"OK: {d / 'verify_text.yaml'} ({len(per_module)} modules) and {d / 'screenshots.yaml'}")


def adb(*args, check=True):
    r = subprocess.run([str(ADB), *args], capture_output=True, text=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    if check and r.returncode:
        fail(f"adb {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def cmd_device(a):
    c = cfg()
    code = module_lang(c, a.lang)
    loc = locales()[code]
    backup = c["packs_dir"] / "_device_backup"
    if a.action == "prep":
        if not adb("devices").count("\tdevice"):
            fail("No phone: connect it, unlock it and accept USB debugging")
        backup.mkdir(parents=True, exist_ok=True)
        for name, path in (("data.db", "files/data.db"), ("general_settings.xml", "shared_prefs/general_settings.xml")):
            data = subprocess.run([str(ADB), "exec-out", "run-as", PACKAGE, "cat", path], capture_output=True).stdout
            if data:
                (backup / name).write_bytes(data)
        # The app's language through the debug test link (AppCompat): works on Android 12 too, where
        # `cmd locale set-app-locales` does not exist. Needs the debug build. With the app stopped,
        # AppCompat (Android 12) never stores the language: open the app first.
        # A pack shown in another interface language ("ui": Quechua in Spanish) gets that language,
        # with the pack's country (es-PE).
        ui = ui_of(c, a.lang)
        tag = f"{ui}-{loc['adb'].split('-')[-1]}" if ui else loc["adb"]
        adb("shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(7)
        adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d",
            f"timelessbible-test://locale?tag={tag}")
        # AppCompat writes the language to its file in the background: stopping the app before that
        # loses it. Wait for the file (up to 10 s).
        record = "files/androidx.appcompat.app.AppCompatDelegate.application_locales_record_file"
        for _ in range(20):
            if tag in adb("shell", "run-as", PACKAGE, "cat", record, check=False):
                break
            time.sleep(0.5)
        else:
            fail("the app did not store its language: is the debug build installed?")
        adb("shell", "am", "force-stop", PACKAGE)
        print(f"OK: app data backed up in {backup}, app language = {tag} (per-app locale). Restore with  ship.py device {a.lang} restore")
    elif a.action == "install":
        # Downloads and installs the pack from the real CDN with the app's own LanguageDownloader, through the
        # debug link timelessbible-test://install (no scrolling through the language cards), and waits for it.
        flag = f'name="language_downloaded_{code}" value="true"'
        if flag in adb("exec-out", "run-as", PACKAGE, "cat", "shared_prefs/general_settings.xml", check=False):
            print(f"OK: {code} is already installed")
            return
        adb("shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(7)
        adb("logcat", "-c", check=False)
        adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", f"timelessbible-test://install?lang={code}")
        for _ in range(180):
            time.sleep(2)
            log = adb("logcat", "-d", "-s", "TestInstall:I", check=False)
            if f"{code} -> " in log:
                if f"{code} -> true" not in log:
                    fail(f"the app could not install {code} (logcat: adb logcat -d | grep LanguageDownloader)")
                print(f"OK: {code} downloaded from the CDN and installed")
                return
        fail(f"{code} was not installed within 6 minutes")
    else:
        # Back to the phone's language (an empty tag), through the debug test link as in prep.
        adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d",
            "timelessbible-test://locale?tag=", check=False)
        adb("shell", "am", "force-stop", PACKAGE)
        for name, path in (("data.db", "files/data.db"), ("general_settings.xml", "shared_prefs/general_settings.xml")):
            f = backup / name
            if f.exists():
                adb("push", str(f), f"/data/local/tmp/{name}")
                adb("shell", "run-as", PACKAGE, "cp", f"/data/local/tmp/{name}", path)
        print("OK: app language and data restored (the downloaded language pack stays installed)")


def cmd_shots(a):
    c = cfg()
    pl = play_locale(c, a.lang)
    if not pl:
        print("Play has no listing language for it: no screenshots needed")
        mark(c, a.lang, "screenshots", "no Play listing language")
        return
    from PIL import Image
    # ui-test.ps1 runs Maestro with --test-output-dir, so takeScreenshot lands inside the run's folder:
    # build/maestro/<run>/.../takeScreenshot/build/maestro/screenshots/<code>/0N.png. The newest of each.
    code = module_lang(c, a.lang)
    newest = {}
    for f in glob.glob(str(c["app_repo"] / "build" / "maestro" / "**" / "screenshots" / code / "0[1-8].png"), recursive=True):
        name = os.path.basename(f)
        if name not in newest or os.path.getmtime(f) > os.path.getmtime(newest[name]):
            newest[name] = f
    raw = [newest[n] for n in sorted(newest)]
    if len(raw) < 8:
        fail(f"{len(raw)}/8 raw screenshots in build/maestro/screenshots/{module_lang(c, a.lang)}: run the screenshot flow")
    out = c["play_dir"] / "images" / pl / "phoneScreenshots"
    out.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(raw[:8], 1):
        im = Image.open(f).convert("RGB")
        if im.size != (1080, 2340):
            im = im.resize((1080, int(im.height * 1080 / im.width)))
            im = im.crop((0, 0, 1080, 2340)) if im.height >= 2340 else im
            canvas = Image.new("RGB", (1080, 2340), (0, 0, 0))
            canvas.paste(im, (0, 0))
            im = canvas
        im.save(out / f"{i:02d}.png")
    ok, msg = check_screenshots(c, a.lang)
    mark(c, a.lang, "screenshots", msg, ok)
    print(("OK: " if ok else "NOT OK: ") + msg + f" -> {out}")


def cmd_feature(a):
    """Adds the language to the feature-graphic config (screens: home in the centre, reading and plans at the sides,
    taken from the language's own Play screenshots) and builds it with the play-feature-graphic skill. The texts
    (title, tagline, chips) are Claude's translation of the English ones: they must be in the config first."""
    c = cfg()
    pl = play_locale(c, a.lang)
    if pl is None:
        mark(c, a.lang, "feature", "no Play listing language")
        print("Play has no listing language for it: the English feature graphic is used")
        return
    fg = Path(c["feature_config"])
    conf = json.loads(fg.read_text(encoding="utf-8"))
    shots = c["play_dir"] / "images" / pl / "phoneScreenshots"
    if not (shots / "03.png").exists():
        fail("Take the 8 screenshots first (stage screenshots)")
    loc = conf["locales"].get(pl)
    if not loc or not loc.get("tagline_html") or not loc.get("chips"):
        en = conf["locales"].get("en-US") or next(iter(conf["locales"].values()))
        fail(f"Add the translated texts of {pl} to {fg} (title_lines, tagline_html, chips, hero_chip), like en-US: "
             f"{json.dumps({k: en.get(k) for k in ('title_lines', 'tagline_html', 'chips', 'hero_chip')}, ensure_ascii=False)}")
    loc["screens"] = {"center": str(shots / "03.png"), "left": str(shots / "01.png"), "right": str(shots / "05.png")}
    conf["locales"][pl] = loc
    fg.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    script = Path(c["feature_script"])
    r = subprocess.run([sys.executable, str(script), str(fg), "--locale", pl])
    if r.returncode:
        fail("build_feature_graphic.py failed")
    out = Path(conf.get("output_dir", "."))
    out = (fg.parent / out).resolve() if not out.is_absolute() else out
    built = out / f"feature-graphic-{pl}.png"
    dest = c["play_dir"] / "images" / pl / "featureGraphic.png"
    shutil.copy2(built, dest)
    ok, msg = check_feature(c, a.lang)
    mark(c, a.lang, "feature", msg, ok)
    print(("OK: " if ok else "NOT OK: ") + f"{msg} -> {dest} (look at it with Read)")


def cmd_mark(a):
    c = cfg()
    if a.stage == "app_core":
        p, g = global_state(c)
        g["app_core"] = TODAY
        g["note"] = a.note or ""
        p.write_text(json.dumps(g, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        if a.stage not in dict(STAGES):
            fail(f"Unknown stage. Stages: {', '.join(n for n, _ in STAGES)}")
        if a.stage in AUTO:
            fail(f"{a.stage} is checked automatically: run  ship.py check {a.lang} {a.stage}")
        mark(c, a.lang, a.stage, a.note or "")
    print(f"OK: {a.lang} {a.stage}")


def tracker_ready(c, lang):
    """The language's row of the tracker: UI, Fuente/Layout and Ficha Play done, and a note (Publicado stays for the user)."""
    path = c["tracker"]
    raw = path.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(nl)
    header = next((x for x in lines if x.startswith("| #") and "Código" in x), None)
    if not header:
        print("  tracker: no header row, not updated")
        return
    names = [x.strip() for x in header.split("|")]
    code = module_lang(c, lang)
    for i, line in enumerate(lines):
        cells = line.split("|")
        # The tracker's code is the pack's ("pt-BR", "tl / fil") or the module language's ("ru").
        if len(cells) != len(names) or cells[names.index("Código")].strip() not in (code, lang):
            continue
        for col in ("UI", "Fuente/Layout", "Ficha Play"):
            if col in names:
                cells[names.index(col)] = " ✅ "
        if "Notas" in names and "Listo para publicar" not in cells[names.index("Notas")]:
            cells[names.index("Notas")] = f" Listo para publicar ({TODAY}): falta el release en Play y el deploy de la web. {cells[names.index('Notas')].strip()} "
        lines[i] = "|".join(cells)
        path.write_text(nl.join(lines), encoding="utf-8", newline="")
        print(f"  tracker: {code} marked ready")
        return
    print(f"  tracker: no row with code {code}, not updated")


def cmd_report(a):
    c = cfg()
    st = run_checks(c, a.lang)
    _, g = global_state(c)
    missing = [n for n, _ in STAGES if n not in st["stages"] and not (n == "app_core" and g.get("app_core")) and n != "ready"]
    if not missing:
        mark(c, a.lang, "ready", "listo para publicar")
        tracker_ready(c, a.lang)
        print(f"\n{a.lang} is READY. Left for the user: the Play release (android-release) and the website deploy (cloudflare-site).")
    else:
        print(f"\n{a.lang} is not ready: {', '.join(missing)}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = ap.add_subparsers(dest="cmd", required=True)
    s.add_parser("status")
    p = s.add_parser("next"); p.add_argument("--lang")
    p = s.add_parser("check"); p.add_argument("lang"); p.add_argument("stage", nargs="?")
    for n in ("cdn", "strings", "web", "play", "flows", "shots", "feature", "report"):
        s.add_parser(n).add_argument("lang")
    s.add_parser("about")
    p = s.add_parser("device"); p.add_argument("lang"); p.add_argument("action", choices=["prep", "install", "restore"])
    p = s.add_parser("mark"); p.add_argument("lang"); p.add_argument("stage"); p.add_argument("--note")
    a = ap.parse_args()
    {"status": cmd_status, "next": cmd_next, "check": cmd_check, "cdn": cmd_cdn, "strings": cmd_strings, "about": cmd_about,
     "web": cmd_web, "play": cmd_play, "flows": cmd_flows, "device": cmd_device, "shots": cmd_shots, "feature": cmd_feature, "mark": cmd_mark,
     "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
