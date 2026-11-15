"""play-launch: publish an Android app on Google Play in three stages that never mix -
GENERATE everything (no Play Console), the user REVIEWS it (texts first) and approves, then EXECUTE
exactly what was approved (after the user signs in). Fail-closed: anything without evidence stops.

    python launch.py init     <app data folder>            play/launch/ with expediente.json and state.json
    python launch.py analyze  [--app F] [--apk app-release.apk]   facts from the release build -> derived answers
    python launch.py check    [--app F]                    stage-1 gate: texts, images, declarations, consistency
    python launch.py review-export [--app F ...] --out <dir>  page data (items.json) + images for the review page
    python launch.py review-import --from <dir> [--app F ...] edits, notes and approvals read back from the page
    python launch.py approval [--app F]                    is the approval still valid (files unchanged)?
    python launch.py set-state <state> [--app F] [--note ..]  move an app along the pipeline (after a verified step)
    python launch.py status                                every app in the pipeline and what it waits for
    python launch.py next     [--app F]                    what comes next, in words for the user (where to review, what to do)
    python launch.py review-published <url> [--app F ...]  remember the review page link and print the message for the user
    python launch.py tick                                  daily: review states by API, closed-test days, reminders
    python launch.py verify-signing --version-code N [--app F]   Play's signing certificate == the app's own key?
    python launch.py policies fetch|diff                   dated copies of Google's policy pages; what changed

App data folder: D:/Documents/Apps/<App>/ (app.json from app-init, play/ from play-console). The pipeline
lives in <folder>/play/launch/. Shared policy copies live next to this skill (policies/).
"""
import argparse
import csv
import datetime as dt
import difflib
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
PLAY_SCRIPTS = Path.home() / ".claude" / "skills" / "play-console" / "scripts"
SDK = Path.home() / "AppData" / "Local" / "Android" / "Sdk"
TEMPLATE = SKILL / "templates" / "expediente.json"
RULES = json.loads((SKILL / "rules" / "metadata.json").read_text(encoding="utf-8"))
SOURCES = SKILL / "policies" / "sources.json"
SNAPSHOTS = SKILL / "policies" / "snapshots"

STATES = ["new", "generated", "in-review", "approved", "waiting-sign-in", "app-created", "signing-and-first-aab",
          "content-declared", "listing-uploaded", "closed-test", "production-requested", "in-review-by-google",
          "published", "rollout-100", "stopped"]
NEEDS_USER = {"generated": "review the generated texts, images and declarations (review page) and approve",
              "in-review": "finish the review on the page and approve",
              "approved": "sign in to Play Console in the dedicated browser (console.py open) and tell Claude",
              "waiting-sign-in": "sign in to Play Console in the dedicated browser (console.py open)",
              "stopped": "read the reason and decide"}
TEXT_FILES = {"title": 30, "short": 80, "full": 4000}
MIN_SCREENSHOTS, MAX_SCREENSHOTS = 2, 8
MAX_PENDING_FOR_REVIEW = 3
VIDEO_HOSTS = ["drive.google.com", "youtube.com", "youtu.be"]   # where Google's reviewer can watch a declaration video   # the review can start with a few items still pending (shown in red, they block approval)


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def today():
    return dt.date.today().isoformat()


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --- the app -------------------------------------------------------------------------------------------

class App:
    def __init__(self, folder):
        self.dir = Path(folder).resolve()
        self.meta = read_json(self.dir / "app.json") or fail(f"No app.json in {self.dir} (run app-init first)")
        self.play = self.dir / "play"
        self.launch = self.play / "launch"
        self.exp_path = self.launch / "expediente.json"
        self.state_path = self.launch / "state.json"

    @property
    def slug(self):
        return self.meta.get("slug") or self.dir.name.lower()

    @property
    def repo(self):
        return Path(self.meta.get("repo", {}).get("path", ""))

    def expediente(self):
        return read_json(self.exp_path) or fail(f"No expediente: python launch.py init {self.dir}")

    def save_expediente(self, exp):
        write_json(self.exp_path, exp)

    def state(self):
        return read_json(self.state_path, {"state": "new", "history": []})

    def set_state(self, state, note=""):
        if state not in STATES:
            fail(f"Unknown state '{state}'. States: {', '.join(STATES)}")
        s = self.state()
        s["history"].append({"at": now(), "from": s["state"], "to": state, "note": note})
        s["state"] = state
        write_json(self.state_path, s)
        print(f"  {self.slug}: {s['history'][-1]['from']} -> {state}" + (f" ({note})" if note else ""))

    def rel(self, value):
        p = Path(value)
        return p if p.is_absolute() else (self.play / p).resolve()


def registered_apps():
    """Every app data folder with a play/launch/ pipeline, found through play-console's apps.json."""
    registry = read_json(PLAY_SCRIPTS.parent / "apps.json", {})
    folders = {Path(v).resolve().parent if Path(v).name == "play" else Path(v).resolve() for v in registry.values()}
    return [App(f) for f in sorted(folders) if (f / "play" / "launch" / "state.json").exists()]


def pick(args):
    if getattr(args, "app", None):
        return [App(a) for a in args.app]
    apps = registered_apps()
    return apps or fail("No app in the pipeline: python launch.py init <app data folder>")


# --- init ----------------------------------------------------------------------------------------------

def cmd_init(args):
    app = App(args.folder)
    if app.exp_path.exists():
        print(f"{app.exp_path} already exists: nothing to do.")
        return
    exp = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    exp["package"] = app.meta["package"]
    exp["name"] = app.meta["name"]
    web = app.meta.get("web", {}).get("domain")
    if web:
        exp["contact"]["website"] = f"https://{web}/"
        exp["privacy_url"] = f"https://{web}/privacy/"
    if not (app.play / "play.json").exists():
        profile = app.meta.get("profiles", {}).get("play") or fail("app.json has no profiles.play")
        out = run([sys.executable, PLAY_SCRIPTS / "play.py", "register", app.play, "--package", exp["package"],
                   "--profile", profile])
        print(out.stdout.strip() or out.stderr.strip())
    play_cfg = read_json(app.play / "play.json", {})
    if play_cfg:
        exp["default_language"] = play_cfg.get("default_language", exp["default_language"])
        exp["languages"] = play_cfg.get("languages", exp["languages"])
    app.save_expediente(exp)
    (app.launch / "texts").mkdir(parents=True, exist_ok=True)
    write_json(app.state_path, {"state": "new", "history": [{"at": now(), "from": None, "to": "new", "note": "init"}]})
    print(f"OK: {app.exp_path}\nNext: build the release (assembleRelease) and run analyze.")


# --- analyze: facts from the release build ---------------------------------------------------------------

def aapt2():
    tools = sorted((SDK / "build-tools").glob("*/aapt2.exe")) + sorted((SDK / "build-tools").glob("*/aapt2"))
    return tools[-1] if tools else fail(f"aapt2 not found under {SDK / 'build-tools'}")


def run(cmd):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")


def manifest_facts(apk):
    badging = run([aapt2(), "dump", "badging", apk])
    if badging.returncode:
        fail(f"aapt2 badging failed: {badging.stderr[:500]}")
    tree = run([aapt2(), "dump", "xmltree", "--file", "AndroidManifest.xml", apk]).stdout
    b = badging.stdout
    facts = {
        "package": re.search(r"package: name='([^']+)'", b).group(1),
        "versionCode": int(re.search(r"versionCode='(\d+)'", b).group(1)),
        "versionName": re.search(r"versionName='([^']*)'", b).group(1),
        "minSdk": int((re.search(r"(?:minSdkVersion|sdkVersion):'(\d+)'", b) or [0, 0])[1]),
        "targetSdk": int((re.search(r"targetSdkVersion:'(\d+)'", b) or [0, 0])[1]),
        "permissions": sorted(set(re.findall(r"uses-permission(?:-sdk-23)?: name='([^']+)'", b))),
        "locales": sorted(set(re.findall(r"locales: (.*)", b)[0].replace("'", "").split())) if "locales:" in b else [],
    }
    # Foreground service types: every <service> with android:foregroundServiceType.
    services, current = [], None
    for line in tree.splitlines():
        if re.search(r"E: service\b", line):
            current = {"name": None, "types": None}
            services.append(current)
        elif re.search(r"E: (activity|receiver|provider|activity-alias)\b", line):
            current = None
        elif current is not None and "android:name(" in line and current["name"] is None:
            m = re.search(r'="([^"]+)"', line)
            current["name"] = m.group(1) if m else None
        elif current is not None and "foregroundServiceType" in line:
            m = re.search(r"\)=(0x[0-9a-f]+|\d+)", line) or re.search(r'="([^"]+)"', line)
            current["types"] = m.group(1) if m else line.strip()
    facts["foreground_services"] = [s for s in services if s["types"]]
    facts["fgs_permissions"] = [p for p in facts["permissions"] if p.startswith("android.permission.FOREGROUND_SERVICE_")]
    facts["exported_components"] = len(re.findall(r"android:exported\(0x[0-9a-f]+\)=\(type 0x12\)0xffffffff", tree))
    return facts


def dependency_facts(app):
    """Release dependencies from cloudflare-site's licence inventory (web.py licenses), if it exists."""
    inventory = None
    for root in (Path("D:/Projects/websites"),):
        p = root / "sites" / app.slug / "content" / "licenses-inventory.md"
        if p.exists():
            inventory = p
    if not inventory:
        return {"inventory": None, "dependencies": [], "flags": {}}
    text = inventory.read_text(encoding="utf-8")
    deps = sorted(set(re.findall(r"`?([a-z0-9_.\-]+:[a-zA-Z0-9_.\-]+)(?::[\w.\-]+)?`?", text)))
    flags = {}
    for flag, patterns in RULES["sdk_flags"].items():
        hits = [d for d in deps if any(p in d for p in patterns)]
        if hits:
            flags[flag] = hits
    return {"inventory": str(inventory), "dependencies": deps, "flags": flags}


def default_apk(app):
    return app.repo / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"


def derive(exp, facts):
    """Answers that follow mechanically from the build. Everything else stays 'ask' for Claude to answer
    with evidence (archivo:línea) and the rule it follows."""
    d = exp["declarations"]
    perms = set(facts["permissions"])
    flags = facts["deps"]["flags"]

    def setd(key, value, evidence):
        item = d[key]
        if item.get("status") == "answered":   # an answer written by Claude with evidence wins
            return
        item.update({"value": value, "evidence": evidence, "status": "derived"})

    setd("advertising_id", "com.google.android.gms.permission.AD_ID" in perms,
         f"release manifest permissions ({len(perms)}): AD_ID {'present' if 'com.google.android.gms.permission.AD_ID' in perms else 'absent'}")
    if "ads" in flags:
        d["ads"].update({"value": None, "status": "ask", "evidence": f"ad SDKs in the release: {flags['ads']}"})
    elif facts["deps"]["inventory"]:
        setd("ads", False, f"no ad SDK in {facts['deps']['inventory']}")
    fgs = facts["fgs_permissions"]
    setd("foreground_services", [p.replace("android.permission.FOREGROUND_SERVICE_", "") for p in fgs],
         f"release manifest: {fgs or 'no FOREGROUND_SERVICE_* permission'}; services {facts['foreground_services']}")
    sensitive = sorted(perms & set(RULES["sensitive_permissions"]))
    setd("sensitive_permissions", sensitive, f"release manifest: {sensitive or 'none of the sensitive list'}")
    internet = "android.permission.INTERNET" in perms
    exp["facts_summary"] = {"internet": internet, "targetSdk": facts["targetSdk"], "versionCode": facts["versionCode"],
                            "sdk_flags": flags}


def cmd_analyze(args):
    for app in pick(args):
        exp = app.expediente()
        apk = Path(args.apk) if args.apk else default_apk(app)
        if not apk.exists():
            fail(f"No release APK at {apk}: ./gradlew :app:assembleRelease in {app.repo} (or --apk)")
        facts = manifest_facts(apk)
        if facts["package"] != exp["package"]:
            fail(f"The APK is {facts['package']}, the expediente is {exp['package']}")
        facts["apk"] = str(apk)
        facts["apk_sha256"] = sha256(apk)
        facts["deps"] = dependency_facts(app)
        facts["analyzed"] = now()
        write_json(app.launch / "facts.json", facts)
        derive(exp, facts)
        app.save_expediente(exp)
        ask = [k for k, v in exp["declarations"].items() if v.get("status") not in ("derived", "answered")]
        print(f"{app.slug}: v{facts['versionCode']} ({facts['versionName']}), targetSdk {facts['targetSdk']}, "
              f"{len(facts['permissions'])} permissions, FGS {facts['fgs_permissions'] or 'none'}, "
              f"internet {'yes' if 'android.permission.INTERNET' in facts['permissions'] else 'no'}")
        print(f"  derived: {[k for k, v in exp['declarations'].items() if v.get('status') == 'derived']}")
        print(f"  Claude must answer with evidence + rule ({len(ask)}): {ask}")


# --- check: the stage-1 gate ---------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.errors, self.warnings, self.ok = [], [], []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def good(self, msg):
        self.ok.append(msg)


def listing_dir(app, lang):
    return app.play / "listing" / lang


def check_texts(app, exp, r):
    everywhere = [w.lower() for w in RULES["banned_everywhere"]]
    title_short = [w.lower() for w in RULES["banned_in_title_short"]]
    for lang in exp["languages"]:
        for name, limit in TEXT_FILES.items():
            f = listing_dir(app, lang) / f"{name}.txt"
            if not f.exists() or not f.read_text(encoding="utf-8").strip():
                r.err(f"{lang}: missing listing/{lang}/{name}.txt")
                continue
            text = f.read_text(encoding="utf-8").strip()
            if len(text) > limit:
                r.err(f"{lang}/{name}: {len(text)} characters, the limit is {limit}")
            low = text.lower()
            for w in everywhere + (title_short if name in ("title", "short") else []):
                if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", low):
                    r.err(f"{lang}/{name}: '{w}' is not allowed in the listing (metadata policy)")
            if name == "title" and re.search(r"[\U0001F300-\U0001FAFF]", text):
                r.err(f"{lang}/title: no emoji in the app name")
            if name == "full":
                words = re.findall(r"\w{4,}", low)
                common = max((words.count(w) for w in set(words)), default=0)
                if len(words) >= 150 and common / len(words) > RULES["max_keyword_share"]:
                    r.warn(f"{lang}/full: one word is {common}/{len(words)} of the text (keyword stuffing?)")
        notes = sorted((app.play / "changelogs" / lang).glob("*.txt")) if (app.play / "changelogs" / lang).exists() else []
        for n in notes:
            if len(n.read_text(encoding="utf-8").strip()) > 500:
                r.err(f"{lang}: {n.name} over 500 characters")
        if not notes:
            r.err(f"{lang}: no release notes in changelogs/{lang}/ (default.txt or <versionCode>.txt)")
    for key, item in exp.get("texts", {}).items():
        f = app.rel(item["file"])
        empty = not f.exists() or not f.read_text(encoding="utf-8").strip()
        if empty and item.get("optional"):
            continue
        if empty:
            r.err(f"text '{key}': missing {f}")
        elif item.get("limit") and len(f.read_text(encoding="utf-8").strip()) > item["limit"]:
            r.err(f"text '{key}': over {item['limit']} characters")


def image_size(path):
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(path) as im:
        return im.size, im.mode


def check_images(app, exp, r):
    for lang in exp["languages"]:
        base = app.play / "images" / lang
        for name, size in (("icon.png", (512, 512)), ("featureGraphic.png", (1024, 500))):
            f = base / name
            if not f.exists():
                r.err(f"{lang}: missing images/{lang}/{name}")
                continue
            info = image_size(f)
            if info and info[0] != size:
                r.err(f"{lang}/{name}: {info[0][0]}x{info[0][1]}, must be {size[0]}x{size[1]}")
            if info and name == "featureGraphic.png" and info[1] in ("RGBA", "LA", "P"):
                r.err(f"{lang}/{name}: has transparency (must be 24-bit, no alpha)")
        for kind in ("phoneScreenshots", "sevenInchScreenshots", "tenInchScreenshots"):
            shots = sorted((base / kind).glob("*.png")) + sorted((base / kind).glob("*.jpg")) if (base / kind).exists() else []
            if kind == "phoneScreenshots" and len(shots) < MIN_SCREENSHOTS:
                r.err(f"{lang}: {len(shots)} phone screenshots, Play needs at least {MIN_SCREENSHOTS}")
            if len(shots) > MAX_SCREENSHOTS:
                r.err(f"{lang}/{kind}: {len(shots)} screenshots, at most {MAX_SCREENSHOTS}")
            for s in shots:
                info = image_size(s)
                ratio = max(info[0]) / min(info[0]) if info else 0
                if info and not (320 <= min(info[0]) and max(info[0]) <= 3840 and abs(ratio - 16 / 9) < 0.01):
                    r.err(f"{lang}/{kind}/{s.name}: {info[0]} - Play needs 16:9 or 9:16, each side 320-3840 px")
            if kind != "phoneScreenshots" and not shots:
                r.warn(f"{lang}: no {kind} (needed to appear as a tablet app)")


def check_declarations(app, exp, r):
    for key, item in exp["declarations"].items():
        status = item.get("status")
        if status not in ("derived", "answered"):
            r.err(f"declaration '{key}': not answered ({item.get('question', '')})")
            continue
        if not item.get("evidence"):
            r.err(f"declaration '{key}': answer without evidence")
        if not item.get("rule"):
            r.err(f"declaration '{key}': answer without the Google rule it follows (URL)")
    facts = read_json(app.launch / "facts.json")
    if not facts:
        r.err("no facts.json: run analyze")
        return
    d = exp["declarations"]
    # Consistency between what the build does and what is declared.
    collects = d.get("data_safety", {}).get("value")
    if facts["deps"]["flags"].get("analytics") and collects is False:
        r.err(f"data safety says no data collected, but analytics SDKs ship: {facts['deps']['flags']['analytics']}")
    if d.get("ads", {}).get("value") is False and facts["deps"]["flags"].get("ads"):
        r.err("ads declared 'no' but an ad SDK ships")
    declared_fgs = set(d.get("foreground_services", {}).get("value") or [])
    for fgs in declared_fgs:
        video = exp.get("videos", {}).get(f"fgs_{fgs}")
        why = exp.get("texts", {}).get(f"fgs_{fgs}")
        if not video:
            r.err(f"foreground service {fgs}: no video link (videos.fgs_{fgs})")
        if not why:
            r.err(f"foreground service {fgs}: no explanation text (texts.fgs_{fgs})")
    if facts["targetSdk"] < RULES["min_target_sdk"]:
        r.err(f"targetSdk {facts['targetSdk']} is below Play's current minimum {RULES['min_target_sdk']}")
    if not exp.get("data_safety_csv") or not app.rel(exp["data_safety_csv"]).exists():
        r.err("no Data safety CSV (data_safety_csv): export the template from Play Console once and fill it")
    aab = exp.get("aab")
    if not aab or not Path(aab).exists():
        r.err("no signed AAB (aab): ./gradlew :app:bundleRelease")
    for field in ("privacy_url", "category"):
        if not exp.get(field):
            r.err(f"missing {field}")
    if not exp.get("contact", {}).get("email"):
        r.err("missing the public contact e-mail (contact.email)")


def check_online(exp, r):
    url = exp.get("privacy_url")
    if not url:
        return
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "play-launch"}), timeout=20) as resp:
            body = resp.read().decode("utf-8", "replace")
        if resp.status != 200:
            r.err(f"privacy policy {url}: HTTP {resp.status}")
        elif exp["name"].split()[0].lower() not in body.lower():
            r.warn(f"privacy policy {url} does not name the app")
        else:
            r.good(f"privacy policy online: {url}")
    except Exception as e:
        r.err(f"privacy policy {url}: {e}")


def cmd_check(args):
    worst = 0
    for app in pick(args):
        exp = app.expediente()
        r = Report()
        check_texts(app, exp, r)
        check_images(app, exp, r)
        check_declarations(app, exp, r)
        if not args.offline:
            check_online(exp, r)
        write_json(app.launch / "check.json", {"at": now(), "errors": r.errors, "warnings": r.warnings})
        print(f"{app.slug}: {len(r.errors)} errors, {len(r.warnings)} warnings")
        for m in r.errors:
            print(f"  ERROR {m}")
        for m in r.warnings:
            print(f"  warn  {m}")
        if not r.errors and app.state()["state"] == "new":
            app.set_state("generated", "stage 1 complete: every check passed")
        worst = max(worst, 1 if r.errors else 0)
    sys.exit(worst)


# --- review: page data out, edits and approvals in ------------------------------------------------------

def user_inputs(app, exp):
    """Things only the user can provide (a link, an e-mail): one field each on the review page, with the steps
    to get it. `path` is where review-import writes the value in the expediente; `covers` is the check error the
    field resolves (it is not repeated as a red pending line)."""
    out = []
    video_file = app.dir / "Images" / "play-declarations"
    for fgs in exp["declarations"].get("foreground_services", {}).get("value") or []:
        key = f"fgs_{fgs}"
        if exp.get("videos", {}).get(key):
            continue
        local = sorted(video_file.glob("foreground-service-*.mp4")) if video_file.exists() else []
        out.append({
            "key": key, "path": f"videos.{key}", "type": "url", "required": True,
            "label": f"Enlace del video del servicio en primer plano ({fgs.lower().replace('_', ' ')})",
            "help": [
                f"Sube a Google Drive el video: {local[0] if local else '(Claude todavía no lo grabó)'}",
                "En Drive: clic derecho > Compartir > Acceso general: 'Cualquier persona con el enlace' (Lector)",
                "Copiar vínculo y pegarlo aquí. Google lo usa para revisar la declaración.",
            ],
            "placeholder": "https://drive.google.com/file/d/.../view?usp=sharing",
            "hosts": VIDEO_HOSTS,
            "covers": f"foreground service {fgs}: no video link"})
    if not exp.get("contact", {}).get("email"):
        out.append({"key": "contact_email", "path": "contact.email", "type": "email", "required": True,
                    "label": "Correo público de contacto (se ve en la ficha de Play)",
                    "help": ["Un correo que revises: Google y los usuarios escriben ahí."],
                    "placeholder": "support@tu-dominio.app", "covers": "missing the public contact e-mail"})
    return out


def set_path(data, path, value):
    cur = data
    parts = path.split(".")
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def review_items(app, exp, img_root):
    """One document per reviewable thing, texts first. Images are copied under img_root."""
    items, order = [], 0
    base_lang = exp["default_language"]

    def add(**kw):
        nonlocal order
        order += 1
        kw.update({"app": app.slug, "order": order})
        kw.setdefault("reviewed", False)
        items.append(kw)

    def text_item(key, label, path, limit, section, lang=None, base=None):
        value = path.read_text(encoding="utf-8").strip() if path.exists() else ""
        add(id=f"{app.slug}--{key}", kind="text", section=section, label=label, lang=lang, limit=limit,
            file=str(path), original=value, value=value, base=base)

    for lang in exp["languages"]:
        for name, limit in TEXT_FILES.items():
            base_text = None
            if lang != base_lang:
                bf = listing_dir(app, base_lang) / f"{name}.txt"
                base_text = bf.read_text(encoding="utf-8").strip() if bf.exists() else None
            text_item(f"listing-{lang}-{name}", {"title": "App name", "short": "Short description",
                                                   "full": "Full description"}[name],
                      listing_dir(app, lang) / f"{name}.txt", limit, "Store listing", lang, base_text)
        notes = app.play / "changelogs" / lang
        for n in sorted(notes.glob("*.txt")) if notes.exists() else []:
            text_item(f"notes-{lang}-{n.stem}", f"Release notes ({n.stem})", n, 500, "Release notes", lang)
    for key, item in exp.get("texts", {}).items():
        if item.get("optional") and not app.rel(item["file"]).exists():
            continue
        text_item(f"text-{key}", item.get("label", key), app.rel(item["file"]), item.get("limit"),
                  "Declaration texts", item.get("lang"))
    for lang in exp["languages"]:
        base = app.play / "images" / lang
        for kind in ("icon", "featureGraphic", "phoneScreenshots", "sevenInchScreenshots", "tenInchScreenshots"):
            files = [base / f"{kind}.png"] if kind in ("icon", "featureGraphic") else \
                (sorted((base / kind).glob("*.png")) + sorted((base / kind).glob("*.jpg")) if (base / kind).exists() else [])
            files = [f for f in files if f.exists()]
            if not files:
                continue
            published = []
            for f in files:
                rel = f"img/{app.slug}/{lang}/{kind}-{f.name}"
                (img_root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, img_root / rel)
                published.append(rel)
            add(id=f"{app.slug}--img-{lang}-{kind}", kind="images", section="Images", label=kind, lang=lang,
                files=published)
    for field in user_inputs(app, exp):
        add(id=f"{app.slug}--input-{field['key']}", kind="input", section="From you", value="", **{
            k: v for k, v in field.items() if k != "key"})
    for key, url in exp.get("videos", {}).items():
        add(id=f"{app.slug}--video-{key}", kind="link", section="Videos", label=key, url=url)
    for key, item in exp["declarations"].items():
        add(id=f"{app.slug}--decl-{key}", kind="declaration", section="Declarations", label=item.get("question", key),
            value=json.dumps(item.get("value"), ensure_ascii=False), evidence=item.get("evidence"),
            rule=item.get("rule"), status=item.get("status"))
    plan = {k: exp.get(k) for k in ("category", "tags", "contact", "privacy_url", "countries", "testers_groups",
                                    "production_criteria")}
    add(id=f"{app.slug}--plan", kind="plan", section="Setup and tracks", label="Setup and tracks",
        value=json.dumps(plan, ensure_ascii=False, indent=1))
    return items


def approval_hash(app, exp):
    """Hash of everything that will be sent: the expediente and every file it or the listing uses."""
    files = [app.exp_path]
    for sub in ("listing", "images", "changelogs"):
        if (app.play / sub).exists():
            files += [f for f in (app.play / sub).rglob("*") if f.is_file()]
    files += [app.rel(t["file"]) for t in exp.get("texts", {}).values()]
    if exp.get("data_safety_csv"):
        files.append(app.rel(exp["data_safety_csv"]))
    if exp.get("aab"):
        files.append(Path(exp["aab"]))
    h = hashlib.sha256()
    for f in sorted({Path(f).resolve() for f in files if Path(f).exists()}):
        h.update(str(f).encode())
        h.update(sha256(f).encode())
    return h.hexdigest()


def cmd_review_export(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    all_items, apps = [], []
    for app in pick(args):
        exp = app.expediente()
        check = read_json(app.launch / "check.json") or fail(f"{app.slug}: run check first")
        covered = [f["covers"] for f in user_inputs(app, exp)]
        pending = [e for e in check.get("errors", []) if not any(c in e for c in covered)]
        if len(pending) > MAX_PENDING_FOR_REVIEW:
            fail(f"{app.slug}: stage 1 is far from complete ({len(pending)} errors in check.json): finish it first")
        all_items += review_items(app, exp, out)
        apps.append({"id": app.slug, "name": exp["name"], "package": exp["package"],
                     "languages": exp["languages"], "hash": approval_hash(app, exp),
                     "warnings": check.get("warnings", []), "pending": pending, "exported": now()})
        if app.state()["state"] in ("new", "generated"):
            app.set_state("in-review", "review page exported" + (f" ({len(pending)} items still pending)" if pending else ""))
    # One file per document, and the ArtifactData batches (≤ 50 writes each) that load them into the page.
    writes = []
    for coll, docs in (("apps", apps), ("items", all_items)):
        shutil.rmtree(out / "db" / coll, ignore_errors=True)
        for doc in docs:
            path = out / "db" / coll / f"{doc['id']}.json"
            write_json(path, doc)
            writes.append({"op": "set", "collection": coll, "doc_id": doc["id"], "file_path": str(path)})
    batches = [writes[i:i + 50] for i in range(0, len(writes), 50)]
    write_json(out / "batches.json", batches)
    images = sorted(str(p.relative_to(out)).replace("\\", "/") for p in (out / "img").rglob("*") if p.is_file()) \
        if (out / "img").exists() else []
    write_json(out / "files.json", {p: str(out / p) for p in images})
    print(f"OK: {len(all_items)} items for {len(apps)} apps in {out}")
    print(f"  page: {SKILL / 'templates' / 'review.html'}  files: {out / 'files.json'} ({len(images)} images)")
    print(f"  data: {out / 'batches.json'} ({len(batches)} ArtifactData batches)")


def cmd_review_import(args):
    """Reads the page's documents (ArtifactData list ... out_dir=<dir>): <dir>/items/*.json, <dir>/apps/*.json,
    <dir>/approvals/*.json. Applies edited texts to their files, saves notes, and records approvals."""
    src = Path(args.source)

    def body(doc):
        # ArtifactData may save the document alone or wrapped with its id and version.
        return doc.get("data") if isinstance(doc.get("data"), dict) and "version" in doc else doc

    def docs(coll):
        return [body(read_json(p)) for p in sorted((src / coll).glob("*.json"))] if (src / coll).exists() else []
    items = docs("items")
    approvals = {a.get("app"): a for a in docs("approvals")}
    for app in pick(args):
        exp = app.expediente()
        mine = [i for i in items if i.get("app") == app.slug]
        changed, notes = 0, []
        for i in mine:
            if i.get("kind") == "text" and i.get("value") is not None and i["value"].strip() != (i.get("original") or "").strip():
                Path(i["file"]).parent.mkdir(parents=True, exist_ok=True)
                Path(i["file"]).write_text(i["value"].strip() + "\n", encoding="utf-8")
                changed += 1
                print(f"  {app.slug}: edited {i['label']} [{i.get('lang') or '-'}]")
            if i.get("kind") == "input" and (i.get("value") or "").strip():
                value = i["value"].strip()
                host = urllib.parse.urlparse(value).hostname or ""
                if i.get("type") == "url" and (not re.match(r"https://\S+$", value) or
                                               (i.get("hosts") and not any(host == h or host.endswith("." + h) for h in i["hosts"]))):
                    print(f"  {app.slug}: '{i['label']}' is not a valid link ({value!r}; allowed: {i.get('hosts')}): not applied")
                else:
                    set_path(exp, i["path"], value)
                    app.save_expediente(exp)
                    changed += 1
                    print(f"  {app.slug}: {i['label']} = {value}")
            if i.get("note"):
                notes.append(f"- **{i['label']}** [{i.get('lang') or '-'}]: {i['note']}")
        if notes:
            (app.launch / "review-notes.md").write_text(f"# Review notes ({now()})\n\n" + "\n".join(notes) + "\n",
                                                       encoding="utf-8")
            print(f"  {app.slug}: {len(notes)} notes -> {app.launch / 'review-notes.md'}")
        approval = approvals.get(app.slug)
        r = Report()
        check_texts(app, exp, r); check_images(app, exp, r); check_declarations(app, exp, r)
        write_json(app.launch / "check.json", {"at": now(), "errors": r.errors, "warnings": r.warnings})
        pending = r.errors
        if approval and approval.get("approved") and pending:
            print(f"  {app.slug}: approval ignored, stage 1 still has pending items: {pending}")
            continue
        if not approval or not approval.get("approved"):
            print(f"  {app.slug}: not approved yet ({changed} texts edited)")
            continue
        unreviewed = [i["label"] for i in mine if i.get("kind") == "text" and not i.get("reviewed")]
        if unreviewed:
            print(f"  {app.slug}: approval ignored, texts not marked reviewed: {unreviewed}")
            continue
        if notes:
            print(f"  {app.slug}: approved with notes: Claude must act on review-notes.md first; approval not recorded")
            continue
        r = Report()
        check_texts(app, exp, r)
        if r.errors:
            print(f"  {app.slug}: the edited texts fail the checks, approval not recorded: {r.errors}")
            continue
        write_json(app.launch / "approval.json", {"approved_at": approval.get("at"), "recorded": now(),
                                                  "hash": approval_hash(app, exp), "texts_edited_on_page": changed})
        app.set_state("approved", "approved on the review page")


def cmd_review_published(args):
    """Records the review page's link in each app of the lot (state.json) and prints what to tell the user."""
    for app in pick(args):
        st = app.state()
        st["review_url"] = args.url
        write_json(app.state_path, st)
    print(f"Recorded. Tell the user (review page: {args.url}):")
    print("\n".join(next_steps_lines(pick(args))))


def approval_valid(app):
    a = read_json(app.launch / "approval.json")
    if not a:
        return False, "no approval"
    current = approval_hash(app, app.expediente())
    return (True, "valid") if current == a["hash"] else (False, "files changed after the approval")


def cmd_approval(args):
    bad = 0
    for app in pick(args):
        ok, why = approval_valid(app)
        print(f"{app.slug}: {'OK' if ok else 'NOT VALID'} ({why})")
        bad |= not ok
    sys.exit(1 if bad else 0)


def cmd_set_state(args):
    for app in pick(args):
        if STATES.index(args.state) >= STATES.index("waiting-sign-in") and args.state != "stopped":
            ok, why = approval_valid(app)
            if not ok:
                fail(f"{app.slug}: cannot move to '{args.state}': approval {why}")
        app.set_state(args.state, args.note or "")


# --- what comes next, in words for the user ----------------------------------------------------------

STAGE = {"new": 1, "generated": 2, "in-review": 2, "approved": 3, "waiting-sign-in": 3, "app-created": 3,
         "signing-and-first-aab": 3, "content-declared": 3, "listing-uploaded": 3, "closed-test": 4,
         "production-requested": 4, "in-review-by-google": 4, "published": 5, "rollout-100": 5, "stopped": 0}


def next_steps_lines(apps):
    lines = []
    for app in apps:
        st = app.state()
        s, url = st["state"], st.get("review_url")
        pending = (read_json(app.launch / "check.json") or {}).get("errors", [])
        head = f"{app.meta.get('name', app.slug)} - stage {STAGE.get(s, '?')}/4 ({s})"
        if s == "new":
            todo = [f"Claude: finish stage 1 ({len(pending)} pending)"] + [f"  - {p}" for p in pending]
        elif s in ("generated", "in-review"):
            todo = [f"YOU: open the review page {url or '(not published yet: Claude publishes it)'}",
                    "  read every text (they are editable), mark each one 'Revisado', leave notes for Claude if needed",
                    "  when everything is reviewed, press 'Aprobar esta app' and tell Claude"]
            todo += [f"  BLOCKING until done: {p}" for p in pending]
        elif s in ("approved", "waiting-sign-in"):
            profile = app.meta.get("profiles", {}).get("play", "<profile>")
            todo = [f"YOU: python {SKILL / 'scripts' / 'console.py'} open --profile {profile}",
                    "  sign in by hand to Play Console in that window, then tell Claude 'listo'"]
        elif s == "closed-test":
            todo = [f"Closed test day {closed_test_day(app)}/14: the testers use the app; nothing for you unless asked"]
        elif s == "stopped":
            todo = [f"YOU: read why it stopped: {app.state_path}"]
        else:
            todo = [NEEDS_USER.get(s, "Claude continues; nothing for you now")]
        lines.append(head)
        lines += [f"  {t}" for t in todo]
    return lines


def cmd_next(args):
    print("\n".join(next_steps_lines(pick(args))))


# --- signing: the certificate Play delivers must be the app's own key -------------------------------

def norm_fp(value):
    return re.sub(r"[^0-9a-f]", "", (value or "").lower())


def cmd_verify_signing(args):
    """Compares the certificate of the APKs Google Play generates for a versionCode (API generatedapks) with the
    app's own key (app.json signing.sha256). Run it after the first AAB is processed. A mismatch means Play signs
    with a Google-generated key (the default for new apps): fix it on the Play app signing page before the app
    reaches open testing or production, where the key can no longer be changed."""
    play = play_module()
    bad = 0
    for app in pick(args):
        own = norm_fp(app.meta.get("signing", {}).get("sha256")) or fail(f"{app.slug}: app.json has no signing.sha256")
        cfg = play.find_app(str(app.play))
        data = play.Api(cfg["profile"], cfg["package"]).call("GET", f"/generatedApks/{args.version_code}")
        certs = sorted({norm_fp(g.get("certificateSha256Hash")) for g in data.get("generatedApks", [])} - {""})
        if not certs:
            print(f"{app.slug}: Play has not generated APKs for versionCode {args.version_code} yet (try again later)")
            bad = 1
            continue
        for c in certs:
            ok = c == own
            bad |= not ok
            print(f"{app.slug}: Play signs v{args.version_code} with {c[:16]}... {'= the app key (OK)' if ok else '!= the app key ' + own[:16] + '... (WRONG)'}")
    sys.exit(1 if bad else 0)


# --- status and the daily tick --------------------------------------------------------------------------

def play_module():
    sys.path.insert(0, str(PLAY_SCRIPTS))
    import play  # noqa: E402
    return play


def closed_test_day(app):
    s = app.state()
    start = next((h["at"] for h in s["history"] if h["to"] == "closed-test"), None)
    return (dt.datetime.now() - dt.datetime.fromisoformat(start)).days if start else None


def cmd_status(args):
    for app in pick(args):
        s = app.state()["state"]
        extra = ""
        if s == "closed-test":
            extra = f" day {closed_test_day(app)}/14"
        print(f"  {app.slug:<20} {s:<22}{extra}  {NEEDS_USER.get(s, '')}")


def cmd_tick(args):
    """API-only daily pass: never touches Play Console screens. Moves states that the API proves, lists what
    needs the user, and what Claude must run in the browser next."""
    play = None
    report = []
    for app in pick(args):
        s = app.state()["state"]
        if s in ("production-requested", "in-review-by-google", "published", "closed-test"):
            play = play or play_module()
            cfg = play.find_app(str(app.play))
            try:
                rows = play.release_states(cfg, "production")
            except SystemExit:
                rows = []
            states = {r["state"] for r in rows}
            if s == "production-requested" and "in-review" in states:
                app.set_state("in-review-by-google", "API: production release in review")
            elif s in ("production-requested", "in-review-by-google") and "published" in states:
                app.set_state("published", "API: production release published")
            elif "not-approved" in states:
                app.set_state("stopped", "API: production release NOT approved - read the e-mail / Inbox")
        if s == "closed-test":
            day = closed_test_day(app)
            if day is not None and day >= 14:
                report.append(f"{app.slug}: closed test day {day}: Claude checks the opted-in count in the console "
                              f"and drafts the production request")
        s = app.state()["state"]
        if s in NEEDS_USER:
            report.append(f"{app.slug}: {NEEDS_USER[s]}")
    write_json(SKILL / "last-tick.json", {"at": now(), "report": report})
    print("\n".join(report) or "Nothing needs you today.")
    if report and sys.platform == "win32" and args.notify:
        msg = "; ".join(report)[:250].replace("'", "")
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
                        f"[System.Windows.Forms.MessageBox]::Show('{msg}','play-launch')"], capture_output=True)


# --- policies: dated copies and what changed ------------------------------------------------------------

def page_text(url):
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + "hl=en", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8", "replace")
    m = re.search(r"<article.*?</article>", raw, re.S) or re.search(r"<main.*?</main>", raw, re.S)
    body = m.group(0) if m else raw
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S)
    body = re.sub(r"<br\s*/?>|</(p|li|h\d|tr|div)>", "\n", body)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    return "\n".join(l.strip() for l in text.splitlines() if l.strip())


def cmd_policies(args):
    sources = read_json(SOURCES)
    changes = []
    for src in sources:
        folder = SNAPSHOTS / src["id"]
        folder.mkdir(parents=True, exist_ok=True)
        previous = sorted(folder.glob("*.txt"))
        if args.action == "fetch":
            try:
                text = page_text(src["url"])
            except Exception as e:
                print(f"  {src['id']:<28} ERROR {e}")
                continue
            if previous and previous[-1].read_text(encoding="utf-8") == text:
                print(f"  {src['id']:<28} unchanged since {previous[-1].stem}")
                continue
            (folder / f"{today()}.txt").write_text(text, encoding="utf-8")
            previous = sorted(folder.glob("*.txt"))
            print(f"  {src['id']:<28} {'NEW COPY' if len(previous) == 1 else 'CHANGED'} ({len(text)} chars)")
        if len(previous) >= 2:
            a, b = previous[-2].read_text(encoding="utf-8"), previous[-1].read_text(encoding="utf-8")
            if a != b:
                diff = list(difflib.unified_diff(a.splitlines(), b.splitlines(), previous[-2].stem, previous[-1].stem,
                                                 lineterm="", n=1))
                changes.append({"id": src["id"], "url": src["url"], "affects": src.get("affects", []),
                                "from": previous[-2].stem, "to": previous[-1].stem, "diff": diff[:200]})
    write_json(SKILL / "policies" / "changes.json", {"at": now(), "changes": changes})
    if changes:
        print("Changed policies (Claude reviews each and re-checks the answers that depend on it):")
        for c in changes:
            print(f"  {c['id']} {c['from']} -> {c['to']}  affects {c['affects']}")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init"); i.add_argument("folder")
    for name in ("analyze", "check", "approval", "status", "tick"):
        s = sub.add_parser(name); s.add_argument("--app", action="append")
        if name == "analyze":
            s.add_argument("--apk")
        if name == "check":
            s.add_argument("--offline", action="store_true")
        if name == "tick":
            s.add_argument("--notify", action="store_true", help="show a Windows message when something needs you")
    e = sub.add_parser("review-export"); e.add_argument("--app", action="append"); e.add_argument("--out", required=True)
    m = sub.add_parser("review-import"); m.add_argument("--app", action="append"); m.add_argument("--from", dest="source", required=True)
    vs = sub.add_parser("verify-signing"); vs.add_argument("--app", action="append")
    vs.add_argument("--version-code", type=int, required=True)
    nx = sub.add_parser("next"); nx.add_argument("--app", action="append")
    rp = sub.add_parser("review-published"); rp.add_argument("url"); rp.add_argument("--app", action="append")
    st = sub.add_parser("set-state"); st.add_argument("state"); st.add_argument("--app", action="append"); st.add_argument("--note")
    po = sub.add_parser("policies"); po.add_argument("action", choices=["fetch", "diff"])
    args = p.parse_args()
    {"init": cmd_init, "analyze": cmd_analyze, "check": cmd_check, "review-export": cmd_review_export,
     "review-import": cmd_review_import, "approval": cmd_approval, "set-state": cmd_set_state,
     "status": cmd_status, "tick": cmd_tick, "policies": cmd_policies,
     "next": cmd_next, "verify-signing": cmd_verify_signing, "review-published": cmd_review_published}[args.cmd](args)


if __name__ == "__main__":
    main()
