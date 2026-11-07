"""app-init: sets up a new Android app, or puts an existing one in order, so every other skill
(app-screen-design, app-design-implementation, cloudflare-site, play-console, android-release,
play-feature-graphic, app-promo-video) finds what it needs.

Nothing is changed without --yes: without it every command that writes shows its plan and stops.

Usage (python, Windows):
    appinit.py detect <repo>                       what the project has (language, signing, libs, folders...)
    appinit.py profiles                            Play / Cloudflare / YouTube / Bitbucket profiles on this PC
    appinit.py candidates "<App name>"             folders that may already hold the app's data
    appinit.py refs <old folder> [--repo <repo>]   every file that names a folder (before moving it)
    appinit.py appdir <D:/Documents/Apps/X> --name "App" --package com.x.y [--brand erasoft] [--yes]
    appinit.py scaffold <repo> --app-dir <dir> --name "App" --package com.x.y [--libs dal,restlog] [--yes]
    appinit.py wire <repo> --app-dir <dir> [--yes]  signing (signing.gradle, setup-signing.ps1, SIGNING.md),
                                                   pointer to the app folder, .gitignore, CLAUDE.md, .claude/
    appinit.py keystore <repo>                     opens a separate window to create (or register) the key
    appinit.py bitbucket auth                      opens a separate window to store the Bitbucket API token
    appinit.py bitbucket check
    appinit.py bitbucket create <repo> --workspace W --slug S [--project KEY] [--public] [--yes]
    appinit.py check <repo>                        final checks (OK / warnings)
    appinit.py summary <repo>                      the final summary in Markdown
"""
import argparse
import base64
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL / "templates"
APPS_ROOT = Path(os.environ.get("APP_INIT_APPS_ROOT", "D:/Documents/Apps"))
PROJECTS_ROOT = Path(os.environ.get("APP_INIT_PROJECTS_ROOT", "D:/Projects/Android"))
DOCUMENTS_ROOT = APPS_ROOT.parent
BITBUCKET_CRED = "Bitbucket-API"

# Own libraries: module name -> (source folder, package). See references/librerias.md.
LIBS = {
    "dal": (PROJECTS_ROOT / "data-access/DataAccessLayer/dal", "com.erc.dal"),
    "restlog": (PROJECTS_ROOT / "RestLog4Android/RestLog", "com.erc.log"),
    "synchronizer": (PROJECTS_ROOT / "synchronizer/app", "com.erasoft.synchronizer"),
    "custom-ads": (PROJECTS_ROOT / "custom-ads", "com.erc.customads"),
}
# A library that needs another one built from source too.
LIB_NEEDS = {"restlog": ["dal"], "synchronizer": ["dal"]}

BRANDS = {
    "erasoft": {"package_prefix": "com.erasoft", "web_zone": "era-soft.app", "developer": "Erasoft"},
    "timeless": {"package_prefix": "com.timeless", "web_zone": "timelesslabs.app", "developer": "Timeless Labs"},
}

APP_SUBFOLDERS = ["KeyStore", "Images", "Images/icon", "Images/screens", "play", "Docs"]

GITIGNORE_LINES = [
    "# Signing: keystores and their passwords never go in the repo (see SIGNING.md)",
    "keystore.properties", "*.jks", "*.keystore", "*.p12", "*.pem",
    "# Personal Claude Code permissions",
    ".claude/settings.local.json",
    "__pycache__/",
]


# --------------------------------------------------------------------------------------------
# helpers

def fail(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def read(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def fwd(path):
    return str(path).replace("\\", "/")


def slug_of(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def pascal_of(name):
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", name) if w)


def env_prefix(name):
    return slug_of(name).upper()


def plan(changes, yes):
    """Prints the planned changes; returns True when they must be applied."""
    if not changes:
        print("Nothing to change.")
        return False
    print("Plan:")
    for c in changes:
        print(f"  - {c}")
    if not yes:
        print("\n(dry run: repeat with --yes to apply)")
    return yes


class Cred:
    """Generic credentials of the Windows Credential Manager (the same ones New-StoredCredential makes)."""

    @staticmethod
    def _struct():
        import ctypes
        import ctypes.wintypes as w

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [("Flags", w.DWORD), ("Type", w.DWORD), ("TargetName", w.LPWSTR), ("Comment", w.LPWSTR),
                        ("LastWritten", w.FILETIME), ("CredentialBlobSize", w.DWORD),
                        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", w.DWORD),
                        ("AttributeCount", w.DWORD), ("Attributes", ctypes.c_void_p),
                        ("TargetAlias", w.LPWSTR), ("UserName", w.LPWSTR)]
        return ctypes, CREDENTIAL

    @classmethod
    def get(cls, target):
        """(user, secret) or None."""
        if sys.platform != "win32":
            return None
        ctypes, CREDENTIAL = cls._struct()
        pointer = ctypes.POINTER(CREDENTIAL)()
        if not ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(pointer)):
            return None
        try:
            c = pointer.contents
            return c.UserName, bytes(c.CredentialBlob[:c.CredentialBlobSize]).decode("utf-16-le")
        finally:
            ctypes.windll.advapi32.CredFree(pointer)

    @classmethod
    def exists(cls, target):
        return cls.get(target) is not None

    @classmethod
    def put(cls, target, user, secret):
        import ctypes
        import ctypes.wintypes as w

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [("Flags", w.DWORD), ("Type", w.DWORD), ("TargetName", w.LPWSTR), ("Comment", w.LPWSTR),
                        ("LastWritten", w.FILETIME), ("CredentialBlobSize", w.DWORD),
                        ("CredentialBlob", ctypes.c_void_p), ("Persist", w.DWORD),
                        ("AttributeCount", w.DWORD), ("Attributes", ctypes.c_void_p),
                        ("TargetAlias", w.LPWSTR), ("UserName", w.LPWSTR)]
        blob = secret.encode("utf-16-le")
        buf = ctypes.create_string_buffer(blob, len(blob))
        cred = CREDENTIAL(Type=1, TargetName=target, CredentialBlobSize=len(blob),
                          CredentialBlob=ctypes.cast(buf, ctypes.c_void_p), Persist=2, UserName=user)
        if not ctypes.windll.advapi32.CredWriteW(ctypes.byref(cred), 0):
            fail(f"Could not store the credential {target}")

    @staticmethod
    def targets():
        """Names of all generic credentials (cmdkey /list)."""
        if sys.platform != "win32":
            return []
        out = subprocess.run(["cmdkey", "/list"], capture_output=True, text=True, errors="replace").stdout
        names = []
        for line in out.splitlines():
            m = re.search(r"(?:target|Destino)\s*[:=]\s*(?:LegacyGeneric:target=)?(.+)$", line.strip(), re.I)
            if m:
                names.append(m.group(1).strip())
        return names


# --------------------------------------------------------------------------------------------
# project inspection

def gradle_files(repo):
    repo = Path(repo)
    app = next((p for p in [repo / "app/build.gradle.kts", repo / "app/build.gradle"] if p.exists()), None)
    settings = next((p for p in [repo / "settings.gradle.kts", repo / "settings.gradle"] if p.exists()), None)
    return app, settings


def count_sources(repo):
    java = kt = 0
    for base in Path(repo).glob("*/src"):
        for p in base.rglob("*"):
            if p.suffix == ".java":
                java += 1
            elif p.suffix == ".kt":
                kt += 1
    return java, kt


def language_of(java, kt):
    if java == 0 and kt == 0:
        return "new"
    if kt == 0:
        return "java"
    if java == 0:
        return "kotlin"
    return "hybrid"


def pointer_of(repo):
    """The app folder named in gradle.properties (appDataDir)."""
    props = Path(repo) / "gradle.properties"
    if props.exists():
        m = re.search(r"^appDataDir\s*=\s*(.+)$", read(props), re.M)
        if m:
            return Path(m.group(1).strip())
    return None


def load_app_json(app_dir):
    p = Path(app_dir) / "app.json"
    return json.loads(read(p)) if p.exists() else None


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, errors="replace")
    return r.stdout.strip() if r.returncode == 0 else None


def detect(repo):
    repo = Path(repo)
    info = {"repo": fwd(repo), "exists": repo.exists()}
    if not repo.exists():
        return info
    app, settings = gradle_files(repo)
    info["gradle_dsl"] = None if not app else ("kts" if app.suffix == ".kts" else "groovy")
    text = read(app) if app else ""
    stext = read(settings) if settings else ""
    m = re.search(r"applicationId\s*=?\s*[\"']([\w.]+)[\"']", text)
    info["package"] = m.group(1) if m else None
    m = re.search(r"namespace\s*=?\s*[\"']([\w.]+)[\"']", text)
    info["namespace"] = m.group(1) if m else None
    java, kt = count_sources(repo)
    info["sources"] = {"java": java, "kotlin": kt}
    info["language"] = language_of(java, kt)
    info["compose"] = bool(re.search(r"compose\s*(=\s*)?true|kotlin\.compose|plugin\.compose", text))
    info["version_catalog"] = (repo / "gradle/libs.versions.toml").exists()
    info["libs"] = {name: (f"':{name}'" in stext or f'":{name}"' in stext) for name in LIBS}
    info["signing"] = {
        "signing_gradle": (repo / "gradle/signing.gradle").exists() and "signing.gradle" in text,
        "credential_manager": "Get-StoredCredential" in text or "signing.gradle" in text,
        "keystore_properties": (repo / "keystore.properties").exists(),
        "plaintext_password": bool(re.search(r"storePassword\s*=?\s*[\"'][^\"'$]+[\"']", text)),
        "setup_script": (repo / "setup-signing.ps1").exists(),
    }
    m = re.search(r"defaultReleaseKeystore\s*=\s*[\"']([^\"']+)[\"']", text)
    info["signing"]["keystore_in_build"] = m.group(1) if m else None
    info["claude_md"] = (repo / "CLAUDE.md").exists()
    info["claude_dir"] = sorted(p.name for p in (repo / ".claude").glob("*")) if (repo / ".claude").exists() else []
    info["maestro"] = (repo / ".maestro").exists()
    info["git"] = (repo / ".git").exists()
    info["remote"] = git(repo, "remote", "get-url", "origin") if info["git"] else None
    info["branch"] = git(repo, "branch", "--show-current") if info["git"] else None
    info["dirty"] = bool(git(repo, "status", "--porcelain")) if info["git"] else None
    ptr = pointer_of(repo)
    info["app_dir"] = fwd(ptr) if ptr else None
    info["app_json"] = bool(ptr and (ptr / "app.json").exists())
    gi = read(repo / ".gitignore") if (repo / ".gitignore").exists() else ""
    info["gitignore_keys"] = all(x in gi for x in ["*.jks", "keystore.properties"])
    tracked = git(repo, "ls-files", "*.jks", "*.keystore", "keystore.properties") if info["git"] else ""
    info["tracked_secrets"] = tracked.splitlines() if tracked else []
    info["google_services"] = (repo / "app/google-services.json").exists()
    return info


def print_detect(info):
    print(json.dumps(info, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------------------------
# profiles and folders

def profiles():
    targets = Cred.targets()
    out = {
        "play": sorted(t.split("@", 1)[1] for t in targets if t.startswith("PlayConsole@")),
        "cloudflare": sorted(t.split("@", 1)[1] for t in targets if t.startswith("CloudflarePages@")),
        "youtube": sorted({t.split("@", 1)[1] if "@" in t else "(default)"
                           for t in targets if t.startswith("PromoVideo-YouTube") and "Client" not in t}),
        "bitbucket": BITBUCKET_CRED in targets,
    }
    cf = SKILL.parent / "cloudflare-site/config.json"
    if cf.exists():
        accounts = Path(json.loads(read(cf)).get("repo", "")) / "accounts.json"
        if accounts.exists():
            out["cloudflare_zones"] = {k: v.get("zones", []) for k, v in json.loads(read(accounts)).items()}
    apps = SKILL.parent / "play-console/apps.json"
    if apps.exists():
        out["play_apps"] = json.loads(read(apps))
    return out


def candidates(name):
    """Folders under Documents (and Apps) whose name looks like the app's."""
    key = slug_of(name)
    words = [w for w in re.split(r"[^a-z0-9]+", name.lower()) if len(w) > 3]
    found = []
    for root in [APPS_ROOT, DOCUMENTS_ROOT]:
        if not root.exists():
            continue
        for p in root.iterdir():
            if not p.is_dir():
                continue
            s = slug_of(p.name)
            if s == key or (key and key in s) or (s and s in key and len(s) > 4) or any(w in s for w in words):
                found.append({"path": fwd(p), "in_apps": root == APPS_ROOT,
                              "items": sorted(x.name for x in p.iterdir())[:30]})
    return found


def refs(old, repo=None):
    """Files that mention a folder: the repo, the skills' configs, the websites monorepo, the app folder."""
    old = fwd(Path(old)).rstrip("/")
    variants = {old, old.replace("/", "\\"), old.replace("/", "\\\\")}
    roots = []
    if repo:
        roots.append(Path(repo))
    roots.append(SKILL.parent)  # every skill: configs and docs that name data folders
    cf = SKILL.parent / "cloudflare-site/config.json"
    if cf.exists():
        roots.append(Path(json.loads(read(cf)).get("repo", "")) / "sites")
    roots.append(Path(old))
    skip = {".git", "node_modules", "build", ".gradle", ".idea", "__pycache__", "dist", ".astro"}
    exts = {".json", ".gradle", ".kts", ".md", ".ps1", ".py", ".properties", ".yaml", ".yml", ".txt", ".toml", ".xml"}
    hits = []
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for f in filenames:
                p = Path(dirpath) / f
                if p.suffix.lower() not in exts or p.stat().st_size > 2_000_000:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if any(v.lower() in line.lower() for v in variants):
                        hits.append(f"{fwd(p)}:{i}: {line.strip()[:160]}")
    return hits


# --------------------------------------------------------------------------------------------
# app folder (D:/Documents/Apps/<App>/)

def cmd_appdir(a):
    app_dir = Path(a.app_dir)
    existing = load_app_json(app_dir) or {}
    brand = a.brand or existing.get("brand")
    data = {
        "schema": 1,
        "name": a.name or existing.get("name"),
        "slug": a.slug or existing.get("slug")
        or (slug_of(a.package.rsplit(".", 1)[-1]) if a.package else slug_of(a.name or app_dir.name)),
        "package": a.package or existing.get("package"),
        "brand": brand,
        "repo": existing.get("repo", {}),
        "language": existing.get("language"),
        "ui": existing.get("ui"),
        "signing": existing.get("signing", {}),
        "libs": existing.get("libs", {}),
        "profiles": existing.get("profiles", {}),
        "web": existing.get("web", {}),
        "created": existing.get("created") or datetime.date.today().isoformat(),
    }
    if a.repo:
        data["repo"]["path"] = fwd(Path(a.repo))
    for key in ["language", "ui"]:
        if getattr(a, key):
            data[key] = getattr(a, key)
    if a.libs is not None:
        data["libs"] = {k: k in a.libs.split(",") for k in LIBS}
    for k in ["play", "cloudflare", "youtube"]:
        v = getattr(a, f"{k}_profile")
        if v:
            data["profiles"][k] = v
    if a.domain:
        data["web"]["domain"] = a.domain
    if brand in BRANDS and not data["web"].get("zone"):
        data["web"]["zone"] = BRANDS[brand]["web_zone"]
    data["signing"].setdefault("keystore", "KeyStore/upload.jks")
    data["signing"].setdefault("alias", "upload")
    data["signing"].setdefault("credential", f"{data['slug']}-release-signing")
    data["signing"].setdefault("env_prefix", env_prefix(data["slug"]))
    if not data["package"]:
        fail("Give --package")

    changes = []
    if not app_dir.exists():
        changes.append(f"create {fwd(app_dir)}")
    for sub in APP_SUBFOLDERS:
        if not (app_dir / sub).exists():
            changes.append(f"create {sub}/")
    new_json = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if not (app_dir / "app.json").exists() or read(app_dir / "app.json") != new_json:
        changes.append("write app.json:\n" + new_json)
    if not (app_dir / "README.md").exists():
        changes.append("write README.md (what goes in each folder)")
    if not plan(changes, a.yes):
        return
    for sub in APP_SUBFOLDERS:
        (app_dir / sub).mkdir(parents=True, exist_ok=True)
    write(app_dir / "app.json", new_json)
    if not (app_dir / "README.md").exists():
        tpl = read(TEMPLATES / "app-folder/README.md")
        write(app_dir / "README.md", tpl.replace("{{APP_NAME}}", data["name"] or app_dir.name)
              .replace("{{PACKAGE}}", data["package"]))
    print(f"OK: {fwd(app_dir)}")


def update_app_json(app_dir, **fields):
    data = load_app_json(app_dir)
    if data is None:
        return
    for k, v in fields.items():
        if isinstance(v, dict):
            data.setdefault(k, {}).update(v)
        else:
            data[k] = v
    write(Path(app_dir) / "app.json", json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------------------------
# new project (Kotlin + Compose)

def newest_wrapper():
    """The gradle wrapper (jar + properties + scripts) of the newest local project."""
    best = None
    for props in PROJECTS_ROOT.glob("*/gradle/wrapper/gradle-wrapper.properties"):
        m = re.search(r"gradle-([\d.]+)-", read(props))
        jar = props.with_name("gradle-wrapper.jar")
        if m and jar.exists() and (props.parent.parent.parent / "gradlew").exists():
            v = tuple(int(x) for x in m.group(1).split("."))
            if not best or v > best[0]:
                best = (v, props.parent.parent.parent)
    return best[1] if best else None


def substitute(text, values):
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def cmd_scaffold(a):
    repo = Path(a.repo)
    if repo.exists() and any(p for p in repo.iterdir() if p.name != ".git"):
        fail(f"{fwd(repo)} is not empty: for an existing project use detect/wire (references/repo-existente.md).")
    libs = [x for x in (a.libs or "").split(",") if x]
    for lib in list(libs):
        for need in LIB_NEEDS.get(lib, []):
            if need not in libs:
                libs.insert(0, need)
    for lib in libs:
        if lib not in LIBS:
            fail(f"Unknown library {lib}: {', '.join(LIBS)}")
    pkg = a.package
    values = {
        "APP_NAME": a.name, "PACKAGE": pkg, "PACKAGE_PATH": pkg.replace(".", "/"),
        "ROOT_NAME": pascal_of(a.name), "THEME": pascal_of(a.name), "APP_DIR": fwd(Path(a.app_dir)),
        "MIN_SDK": str(a.min_sdk),
    }
    include_lines, dep_lines = [], []
    for lib in libs:
        path, _ = LIBS[lib]
        include_lines.append(f'include(":{lib}")\nproject(":{lib}").projectDir = file("{fwd(path)}")')
        dep_lines.append(f'    implementation(project(":{lib}"))')
    values["LIB_INCLUDES"] = ("\n// Own libraries built from source (references/librerias.md in the app-init skill).\n"
                              + "\n".join(include_lines)) if include_lines else ""
    values["LIB_DEPENDENCIES"] = "\n".join(dep_lines)
    wrapper = newest_wrapper()
    src = TEMPLATES / "project-kotlin"
    files = [p for p in src.rglob("*") if p.is_file()]
    changes = [f"create {fwd(repo)} ({len(files)} files from templates/project-kotlin)",
               f"package {pkg}, libs: {', '.join(libs) or 'none'}",
               f"gradle wrapper copied from {fwd(wrapper)}" if wrapper else "no local gradle wrapper found: "
               "open the project in Android Studio once, or run `gradle wrapper`"]
    if not plan(changes, a.yes):
        return
    from xml.sax.saxutils import escape
    xml_values = {**values, "APP_NAME": escape(a.name).replace("'", "\\'")}
    for p in files:
        rel = substitute(fwd(p.relative_to(src)), values).replace(".tmpl", "")
        write(repo / rel, substitute(read(p), xml_values if p.suffix == ".xml" else values))
    sdk = Path(os.environ.get("ANDROID_HOME") or Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk")
    if sdk.exists():  # local.properties is per PC and ignored by git
        write(repo / "local.properties", "sdk.dir=" + fwd(sdk) + "\n")
    if wrapper:
        for rel in ["gradlew", "gradlew.bat", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties"]:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(wrapper / rel, repo / rel)
    print(f"OK: project at {fwd(repo)}. Next: wire, keystore.")


# --------------------------------------------------------------------------------------------
# wiring an existing (or freshly scaffolded) project

def apply_line(dsl):
    return ('apply(from = rootProject.file("gradle/signing.gradle"))' if dsl == "kts"
            else "apply from: rootProject.file('gradle/signing.gradle')")


def cmd_wire(a):
    repo = Path(a.repo)
    app_dir = Path(a.app_dir)
    info = detect(repo)
    if not info.get("gradle_dsl"):
        fail("No app/build.gradle(.kts): is this an Android project?")
    data = load_app_json(app_dir) or fail(f"No app.json in {fwd(app_dir)}: run appdir first.")
    sign = data["signing"]
    values = {"APP_NAME": data["name"], "SLUG": data["slug"], "PACKAGE": data["package"],
              "APP_DIR": fwd(app_dir), "KEYSTORE": sign["keystore"], "ALIAS": sign["alias"],
              "CREDENTIAL": sign["credential"], "ENV_PREFIX": sign["env_prefix"],
              "KEYSTORE_PATH": fwd(app_dir / sign["keystore"]),
              "DEVELOPER": BRANDS.get(data.get("brand") or "", {}).get("developer", data["name"])}
    changes, actions = [], []

    def add_file(rel, template, force=False):
        dest = repo / rel
        text = substitute(read(TEMPLATES / template), values)
        if dest.exists() and not force:
            if read(dest) != text:
                changes.append(f"{rel} exists and differs: left as is (compare with templates/{template})")
            return
        changes.append(f"write {rel}")
        if dest.suffix == ".ps1":  # Windows PowerShell 5.1 reads a file without BOM as ANSI
            actions.append(lambda: dest.parent.mkdir(parents=True, exist_ok=True) or
                           dest.write_text(text, encoding="utf-8-sig"))
        else:
            actions.append(lambda: write(dest, text))

    add_file("gradle/signing.gradle", "signing/signing.gradle", force=a.update_signing)
    add_file("setup-signing.ps1", "signing/setup-signing.ps1", force=a.update_signing)
    add_file("SIGNING.md", "signing/SIGNING.md", force=a.update_signing)

    # gradle.properties: the pointer to the app folder and the signing names (no secrets)
    props_path = repo / "gradle.properties"
    props = read(props_path) if props_path.exists() else ""
    wanted = {"appDataDir": fwd(app_dir), "signing.keystore": sign["keystore"],
              "signing.credential": sign["credential"], "signing.envPrefix": sign["env_prefix"],
              "signing.signDebug": "true" if a.sign_debug else "false"}
    new_props = props
    block = []
    for k, v in wanted.items():
        if re.search(rf"^{re.escape(k)}\s*=", new_props, re.M):
            new_props = re.sub(rf"^{re.escape(k)}\s*=.*$", f"{k}={v}", new_props, flags=re.M)
        else:
            block.append(f"{k}={v}")
    if block:
        new_props = new_props.rstrip("\n") + ("\n\n" if new_props.strip() else "") + \
            "# App data folder (images, Play, keystore) and signing names. No secrets here: see SIGNING.md.\n" + \
            "\n".join(block) + "\n"
    if new_props != props:
        changes.append("gradle.properties: " + ", ".join(f"{k}={v}" for k, v in wanted.items()))
        actions.append(lambda: write(props_path, new_props))

    # app/build.gradle(.kts): apply the signing script at the end
    app, _ = gradle_files(repo)
    app_text = read(app)
    line = apply_line(info["gradle_dsl"])
    if "signing.gradle" not in app_text:
        old_signing = info["signing"]["credential_manager"] or info["signing"]["keystore_properties"]
        changes.append(f"{app.relative_to(repo)}: append `{line}`" +
                       (" (the old signing block stays until you remove it: see references/repo-existente.md)"
                        if old_signing else ""))
        actions.append(lambda: write(app, app_text.rstrip("\n") + "\n\n// Release signing from the Windows "
                                     "Credential Manager (SIGNING.md)\n" + line + "\n"))

    # .gitignore
    gi_path = repo / ".gitignore"
    gi = read(gi_path) if gi_path.exists() else ""
    missing = [l for l in GITIGNORE_LINES if not l.startswith("#") and l not in gi.splitlines()]
    if missing:
        changes.append(".gitignore: add " + ", ".join(missing))
        actions.append(lambda: write(gi_path, gi.rstrip("\n") + "\n\n# Added by app-init: keystores, their "
                                     "passwords and personal Claude Code settings never go in the repo\n"
                                     + "\n".join(missing) + "\n"))

    # Claude Code: CLAUDE.md (only if missing) and shared settings
    if not (repo / "CLAUDE.md").exists():
        changes.append("write CLAUDE.md from templates/CLAUDE.md (then fill in the project sections)")
        tpl = substitute(read(TEMPLATES / "claude/CLAUDE.md"), {**values, "LANGUAGE": a.language or info["language"],
                                                                 "UI": a.ui or ("compose" if info["compose"] else "views")})
        actions.append(lambda: write(repo / "CLAUDE.md", tpl))
    else:
        changes.append("CLAUDE.md exists: compare it with templates/claude/CLAUDE.md and add the missing rules by hand")
    if not (repo / ".claude/settings.json").exists():
        changes.append("write .claude/settings.json (shared permissions: gradle, adb, maestro, git read-only)")
        actions.append(lambda: write(repo / ".claude/settings.json", read(TEMPLATES / "claude/settings.json")))

    if info["tracked_secrets"]:
        changes.append("WARNING: tracked secret files (remove them from git history with the user): "
                       + ", ".join(info["tracked_secrets"]))
    if not plan(changes, a.yes):
        return
    for act in actions:
        act()
    update_app_json(app_dir, repo={"path": fwd(repo)}, language=a.language or data.get("language") or info["language"],
                    ui=a.ui or data.get("ui") or ("compose" if info["compose"] else "views"))
    print("OK: wired. Next: appinit.py keystore", fwd(repo))


# --------------------------------------------------------------------------------------------
# keystore and bitbucket token: separate windows, secrets never pass through the chat

def cmd_keystore(a):
    repo = Path(a.repo)
    script = repo / "setup-signing.ps1"
    if not script.exists():
        fail("No setup-signing.ps1 in the repo: run wire first.")
    mode = "-Register" if a.register else "-Create"
    cmd = ["cmd", "/c", "start", "Firma de la app", "powershell", "-NoExit", "-ExecutionPolicy", "Bypass",
           "-File", str(script), mode]
    subprocess.Popen(cmd, cwd=str(repo))
    print(f"Opened a separate PowerShell window ({mode}). The passwords are typed there, hidden.")


def bitbucket_request(method, url, body=None):
    cred = Cred.get(BITBUCKET_CRED)
    if not cred:
        fail(f"No Bitbucket token: run `appinit.py bitbucket auth` (SETUP.md, Bitbucket).")
    email, token = cred
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode())
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read() or b"{}")
        except ValueError:
            detail = {}
        return e.code, detail


def cmd_bitbucket(a):
    if a.action == "auth":
        if not a.here:
            subprocess.Popen(["cmd", "/c", "start", "Bitbucket", sys.executable, str(Path(__file__)), "bitbucket", "auth",
                              "--here"])
            print("Opened a separate window: type the Atlassian e-mail and the API token there (hidden).")
            return
        import getpass
        email = input("Atlassian account e-mail: ").strip()
        token = getpass.getpass("Bitbucket API token (hidden): ").strip()
        Cred.put(BITBUCKET_CRED, email, token)
        status, me = bitbucket_request("GET", "https://api.bitbucket.org/2.0/user")
        print(f"Stored {BITBUCKET_CRED}. Check: HTTP {status} {me.get('username', me.get('error', ''))}")
        input("Enter to close")
        return
    if a.action == "check":
        status, me = bitbucket_request("GET", "https://api.bitbucket.org/2.0/user")
        if status != 200:
            fail(f"HTTP {status}: {me}. Token expired or without read:user:bitbucket (SETUP.md).")
        print(f"OK: {me.get('username')} ({me.get('display_name')})")
        status, ws = bitbucket_request("GET", "https://api.bitbucket.org/2.0/user/permissions/workspaces?pagelen=50")
        if status == 200:
            for v in ws.get("values", []):
                print(f"  workspace {v['workspace']['slug']} ({v.get('permission')})")
        return
    # create
    repo = Path(a.repo)
    url = f"https://api.bitbucket.org/2.0/repositories/{a.workspace}/{a.slug}"
    status, existing = bitbucket_request("GET", url)
    remote = f"https://bitbucket.org/{a.workspace}/{a.slug}.git"
    changes = []
    if status == 200:
        changes.append(f"repository {a.workspace}/{a.slug} already exists: only set it as origin")
    else:
        changes.append(f"create {'public' if a.public else 'private'} repository {a.workspace}/{a.slug}"
                       + (f" in project {a.project}" if a.project else ""))
    if not (repo / ".git").exists():
        changes.append("git init -b master")
    current = git(repo, "remote", "get-url", "origin") if (repo / ".git").exists() else None
    if current and current != remote:
        fail(f"origin is already {current}: decide with the user before changing it.")
    if not current:
        changes.append(f"git remote add origin {remote}")
    changes.append("no commit and no push: those only when the user asks")
    if not plan(changes, a.yes):
        return
    if status != 200:
        body = {"scm": "git", "is_private": not a.public, "fork_policy": "no_public_forks"}
        if a.project:
            body["project"] = {"key": a.project}
        status, created = bitbucket_request("POST", url, body)
        if status not in (200, 201):
            fail(f"HTTP {status}: {created}. A 403 means the token lacks admin:repository:bitbucket "
                 "(or admin:project:bitbucket for a project): SETUP.md.")
        print(f"Created {created.get('links', {}).get('html', {}).get('href', url)}")
    if not (repo / ".git").exists():
        subprocess.run(["git", "-C", str(repo), "init", "-b", "master"], check=True)
    if not current:
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote], check=True)
    app_dir = pointer_of(repo)
    if app_dir:
        update_app_json(app_dir, repo={"remote": remote, "workspace": a.workspace, "slug": a.slug})
    print(f"OK: origin = {remote}")


# --------------------------------------------------------------------------------------------
# checks and summary

def checks(repo):
    info = detect(repo)
    res = []

    def add(ok, what, fix=""):
        res.append(("OK" if ok is True else "WARN" if ok is None else "FAIL", what, fix))

    app_dir = Path(info["app_dir"]) if info.get("app_dir") else None
    data = load_app_json(app_dir) if app_dir else None
    add(bool(app_dir), "repo points to the app folder (gradle.properties appDataDir)", "appinit.py wire")
    add(bool(app_dir) and fwd(app_dir).lower().startswith(fwd(APPS_ROOT).lower()),
        f"app folder is under {fwd(APPS_ROOT)}", "move it (references/carpeta-app.md)")
    add(bool(data), "app.json exists", "appinit.py appdir")
    if data:
        add(data.get("package") == info.get("package"), f"app.json package = applicationId ({info.get('package')})")
        ks = app_dir / data["signing"]["keystore"]
        add(ks.exists(), f"keystore {fwd(ks)}", "appinit.py keystore <repo>")
        add(Cred.exists(data["signing"]["credential"]), f"credential {data['signing']['credential']}",
            "setup-signing.ps1 -Register")
        info_path = ks.parent / "keystore-info.json"
        ks_info = json.loads(info_path.read_text(encoding="utf-8-sig")) if info_path.exists() else {}
        if ks_info.get("sha256") and data["signing"].get("sha256") != ks_info["sha256"]:
            update_app_json(app_dir, signing={"sha256": ks_info["sha256"], "sha1": ks_info.get("sha1")})
            data["signing"]["sha256"] = ks_info["sha256"]
        add(True if ks_info.get("sha256") else None, "public fingerprints (KeyStore/keystore-info.json)",
            "setup-signing.ps1 writes them")
        add(True if data["signing"].get("backup", {}).get("bitwarden") else None,
            "backup in Bitwarden confirmed", "references/firma.md, step 4")
        for k in ["play", "cloudflare", "youtube"]:
            add(True if data.get("profiles", {}).get(k) else None, f"{k} profile chosen")
        play_dir = app_dir / "play" / "play.json"
        add(True if play_dir.exists() else None, "play/play.json (play-console register)")
    add(info["signing"]["signing_gradle"], "build applies gradle/signing.gradle")
    add(not info["signing"]["plaintext_password"], "no plaintext password in the build")
    add(not info["tracked_secrets"], "no keystore tracked by git", ", ".join(info["tracked_secrets"]))
    add(info["gitignore_keys"], ".gitignore covers keystores")
    add(info["claude_md"], "CLAUDE.md")
    add(True if info["remote"] else None, f"git remote ({info['remote'] or 'none'})", "appinit.py bitbucket create")
    return info, data, res


def cmd_check(a):
    _, _, res = checks(a.repo)
    for state, what, fix in res:
        print(f"[{state:4}] {what}" + (f"  -> {fix}" if fix and state != "OK" else ""))
    if any(s == "FAIL" for s, _, _ in res):
        sys.exit(2)


def cmd_summary(a):
    info, data, res = checks(a.repo)
    d = data or {}
    p = d.get("profiles", {})
    s = d.get("signing", {})
    libs = [k for k, v in d.get("libs", {}).items() if v] or [k for k, v in info.get("libs", {}).items() if v]
    lines = [
        f"# {d.get('name', Path(a.repo).name)}: inicialización",
        "",
        "| | |", "|---|---|",
        f"| Paquete | `{info.get('package')}` |",
        f"| Lenguaje / UI | {d.get('language', info.get('language'))} / {d.get('ui', '-')} |",
        f"| Repo | `{info['repo']}` ({info.get('branch') or '-'}) |",
        f"| Remoto | {info.get('remote') or 'sin remoto'} |",
        f"| Carpeta de la app | `{info.get('app_dir')}` |",
        f"| Firma | `{s.get('keystore')}` alias `{s.get('alias')}`, credencial `{s.get('credential')}` |",
        f"| SHA-256 (subida) | `{s.get('sha256', 'pendiente')}` |",
        f"| Librerías | {', '.join(libs) or 'ninguna'} |",
        f"| Perfiles | Play `{p.get('play', '-')}`, Cloudflare `{p.get('cloudflare', '-')}`, YouTube `{p.get('youtube', '-')}` |",
        f"| Web | {d.get('web', {}).get('domain') or d.get('web', {}).get('zone') or '-'} |",
        "", "## Controles", "",
    ]
    for state, what, fix in res:
        mark = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}[state]
        lines.append(f"- {mark} {what}" + (f" → {fix}" if fix and state != "OK" else ""))
    lines += ["", "## Siguientes skills", "", read(TEMPLATES / "next-steps.md").strip()]
    print("\n".join(lines))


# --------------------------------------------------------------------------------------------

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("detect"); s.add_argument("repo")
    sub.add_parser("profiles")
    s = sub.add_parser("candidates"); s.add_argument("name")
    s = sub.add_parser("refs"); s.add_argument("old"); s.add_argument("--repo")
    s = sub.add_parser("appdir"); s.add_argument("app_dir"); s.add_argument("--name"); s.add_argument("--package")
    s.add_argument("--brand"); s.add_argument("--repo"); s.add_argument("--language", choices=["kotlin", "java", "hybrid"])
    s.add_argument("--ui", choices=["compose", "views"]); s.add_argument("--libs")
    s.add_argument("--play-profile"); s.add_argument("--cloudflare-profile"); s.add_argument("--youtube-profile")
    s.add_argument("--domain"); s.add_argument("--slug", help="default: last part of the package")
    s.add_argument("--yes", action="store_true")
    s = sub.add_parser("scaffold"); s.add_argument("repo"); s.add_argument("--app-dir", required=True)
    s.add_argument("--name", required=True); s.add_argument("--package", required=True); s.add_argument("--libs")
    s.add_argument("--min-sdk", type=int, default=26); s.add_argument("--yes", action="store_true")
    s = sub.add_parser("wire"); s.add_argument("repo"); s.add_argument("--app-dir", required=True)
    s.add_argument("--language", choices=["kotlin", "java", "hybrid"]); s.add_argument("--ui", choices=["compose", "views"])
    s.add_argument("--no-sign-debug", dest="sign_debug", action="store_false")
    s.add_argument("--update-signing", action="store_true", help="overwrite signing.gradle / setup-signing.ps1 / SIGNING.md")
    s.add_argument("--yes", action="store_true")
    s = sub.add_parser("keystore"); s.add_argument("repo"); s.add_argument("--register", action="store_true")
    s = sub.add_parser("bitbucket"); s.add_argument("action", choices=["auth", "check", "create"])
    s.add_argument("repo", nargs="?"); s.add_argument("--workspace"); s.add_argument("--slug"); s.add_argument("--project")
    s.add_argument("--public", action="store_true"); s.add_argument("--here", action="store_true")
    s.add_argument("--yes", action="store_true")
    s = sub.add_parser("check"); s.add_argument("repo")
    s = sub.add_parser("summary"); s.add_argument("repo")
    a = ap.parse_args()

    if a.cmd == "detect":
        print_detect(detect(a.repo))
    elif a.cmd == "profiles":
        print(json.dumps(profiles(), indent=2, ensure_ascii=False))
    elif a.cmd == "candidates":
        print(json.dumps(candidates(a.name), indent=2, ensure_ascii=False))
    elif a.cmd == "refs":
        hits = refs(a.old, a.repo)
        print("\n".join(hits) if hits else "No references.")
    elif a.cmd == "appdir":
        cmd_appdir(a)
    elif a.cmd == "scaffold":
        cmd_scaffold(a)
    elif a.cmd == "wire":
        cmd_wire(a)
    elif a.cmd == "keystore":
        cmd_keystore(a)
    elif a.cmd == "bitbucket":
        if a.action == "create" and not (a.repo and a.workspace and a.slug):
            fail("bitbucket create <repo> --workspace W --slug S")
        cmd_bitbucket(a)
    elif a.cmd == "check":
        cmd_check(a)
    elif a.cmd == "summary":
        cmd_summary(a)


if __name__ == "__main__":
    main()
