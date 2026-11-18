"""Static websites for apps, one per subdomain, in one monorepo, published to Cloudflare Pages
(Direct Upload with wrangler) on several Cloudflare accounts.

    python web.py init <repo>                          monorepo scaffold (once), remembers the repo on this PC
    python web.py auth --profile <name>                guided API token for one Cloudflare account -> Credential Manager
    python web.py new <slug> --profile <p> --domain <host> [--package com.x] [--name "App"]
                         [--app-project <folder>] [--assets <folder>]
    python web.py assets <slug>                        inventory of the external images/videos folder
    python web.py import <slug> <file>... [--to screens] [--name x]   copy into the site (videos are compressed)
    python web.py capture <slug> shot <name> | record <name> [--seconds 20]   from the connected phone
    python web.py licenses <slug> [--module app]        open-source inventory of the app's release dependencies
    python web.py legal <slug> [--check] [--online]    app documents -> website, app links to the site, Play links file
    python web.py build <slug> | --all                 npm build + checks (sizes, SEO tags, links, alt texts)
    python web.py qa <slug> [--lighthouse]             screenshots desktop/phone of every page (+ Lighthouse)
    python web.py preview <slug>                       local server of the built site
    python web.py deploy <slug> [--prod --yes] | --changed [--prod --yes]
    python web.py domain <slug> [--yes]                custom domain on the Pages project + CNAME in the zone
    python web.py status                               every site: account, project, last deploy, domain
    python web.py link <slug> [--yes]                  the main site of the domain lists the app; the app links back
    python web.py video <slug> [--format vertical]     the app's published promo videos (app-promo-video) -> the site

Without --prod a deploy goes to the "preview" branch (a *.pages.dev URL, not the domain). Production
and domain changes need --yes. Each site names its account profile in site.json; the token of that
profile is read from the Windows Credential Manager (CloudflarePages@<profile>) only for that call.
"""
import argparse
import contextlib
import ctypes
import io
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
LOCAL = SKILL / "config.json"  # per PC: where the monorepo is
CF = "https://api.cloudflare.com/client/v4"
CRED = "CloudflarePages@{}"
MAX_FILE = 25 * 1024 * 1024  # Pages: 25 MiB per file
MAX_FILES = 20000  # Pages free plan
NPX = "npx.cmd" if os.name == "nt" else "npx"
NPM = "npm.cmd" if os.name == "nt" else "npm"
ADB = Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"
BADGES = {"en": "https://play.google.com/intl/en_us/badges/static/images/badges/en_badge_web_generic.png",
          "es": "https://play.google.com/intl/en_us/badges/static/images/badges/es-419_badge_web_generic.png"}


def tool(name):
    """ffmpeg/ffprobe: on PATH, or where winget installs them (not always added to PATH)."""
    found = shutil.which(name)
    if found:
        return found
    import glob
    pattern = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg_*", "ffmpeg-*", "bin")
    for d in sorted(glob.glob(pattern), reverse=True):
        if Path(d, name + ".exe").exists():
            return str(Path(d, name + ".exe"))
    fail(f"{name} not found: winget install Gyan.FFmpeg")


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def run(cmd, cwd=None, env=None, check=True, capture=False):
    r = subprocess.run(cmd, cwd=cwd, env=env, text=True, encoding="utf-8", errors="replace",
                       capture_output=capture)
    if check and r.returncode != 0:
        if capture:
            print((r.stdout or "")[-4000:], (r.stderr or "")[-4000:])
        fail(f"{' '.join(map(str, cmd))} failed (exit {r.returncode})")
    return r


# --- Windows Credential Manager: one token per Cloudflare account -----------------------------------
# UserName = Account ID, blob = token in UTF-16 (readable by the PowerShell CredentialManager module too).

if os.name == "nt":
    import ctypes.wintypes as w

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [("Flags", w.DWORD), ("Type", w.DWORD), ("TargetName", w.LPWSTR), ("Comment", w.LPWSTR),
                    ("LastWritten", w.FILETIME), ("CredentialBlobSize", w.DWORD),
                    ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", w.DWORD),
                    ("AttributeCount", w.DWORD), ("Attributes", ctypes.c_void_p),
                    ("TargetAlias", w.LPWSTR), ("UserName", w.LPWSTR)]


def save_token(profile, account_id, token):
    blob = token.encode("utf-16-le")
    buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    cred = CREDENTIAL(Type=1, TargetName=CRED.format(profile), CredentialBlobSize=len(blob),
                      CredentialBlob=buf, Persist=2, UserName=account_id)
    if not ctypes.windll.advapi32.CredWriteW(ctypes.byref(cred), 0):
        fail("Could not store the token in the Credential Manager")


def load_token(profile):
    """(account_id, token). Elsewhere: CLOUDFLARE_ACCOUNT_ID_<PROFILE> and CLOUDFLARE_API_TOKEN_<PROFILE>."""
    env_t = os.environ.get(f"CLOUDFLARE_API_TOKEN_{profile.upper()}")
    if env_t:
        return os.environ.get(f"CLOUDFLARE_ACCOUNT_ID_{profile.upper()}", ""), env_t
    pointer = ctypes.POINTER(CREDENTIAL)() if os.name == "nt" else None
    if os.name != "nt" or not ctypes.windll.advapi32.CredReadW(CRED.format(profile), 1, 0, ctypes.byref(pointer)):
        fail(f"No token for the Cloudflare profile '{profile}': python web.py auth --profile {profile}")
    try:
        c = pointer.contents
        return c.UserName, bytes(c.CredentialBlob[:c.CredentialBlobSize]).decode("utf-16-le")
    finally:
        ctypes.windll.advapi32.CredFree(pointer)


class Cloudflare:
    def __init__(self, profile, account_id=None, token=None):
        if token is None:
            account_id, token = load_token(profile)
        self.profile, self.account, self.token = profile, account_id, token

    def call(self, method, path, body=None, ok404=False):
        req = urllib.request.Request(CF + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read()).get("result")
        except urllib.error.HTTPError as e:
            if ok404 and e.code == 404:
                return None
            detail = e.read().decode("utf-8", "replace")[:800]
            hint = {401: "The token is invalid or expired: web.py auth --profile " + self.profile,
                    403: "The token lacks a permission (SETUP.md: Pages Edit, Zone Read, DNS Edit) or this account/zone"}
            fail(f"{method} {path}: HTTP {e.code} {detail}\n{hint.get(e.code, '')}")

    def env(self):
        return {**os.environ, "CLOUDFLARE_API_TOKEN": self.token, "CLOUDFLARE_ACCOUNT_ID": self.account}

    def project(self, name):
        return self.call("GET", f"/accounts/{self.account}/pages/projects/{name}", ok404=True)

    def zone(self, host):
        """The zone of the account that holds host (bible.example.com -> example.com)."""
        for z in self.call("GET", f"/zones?account.id={self.account}&per_page=50") or []:
            if host == z["name"] or host.endswith("." + z["name"]):
                return z
        return None


# --- monorepo and sites ----------------------------------------------------------------------------

def repo(arg=None):
    if arg:
        return Path(arg).resolve()
    for d in [Path.cwd(), *Path.cwd().parents]:
        if (d / "accounts.json").exists() and (d / "sites").is_dir():
            return d
    if LOCAL.exists():
        return Path(json.loads(LOCAL.read_text(encoding="utf-8"))["repo"])
    fail("Which monorepo? python web.py init <folder>")


def accounts(root):
    p = root / "accounts.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def site(root, slug):
    folder = root / "sites" / slug
    if not (folder / "site.json").exists():
        fail(f"No site '{slug}' (sites/{slug}/site.json). Sites: {', '.join(all_sites(root)) or 'none'}")
    cfg = json.loads((folder / "site.json").read_text(encoding="utf-8"))
    cfg["_dir"] = folder
    return cfg


def all_sites(root):
    return sorted(p.parent.name for p in (root / "sites").glob("*/site.json"))


def cmd_init(args):
    root = Path(args.repo).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for src in (TEMPLATES / "monorepo").rglob("*"):
        dst = root / src.relative_to(TEMPLATES / "monorepo")
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        elif not dst.exists():  # never overwrite what the repo already has
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  + {dst.relative_to(root)}")
    (root / "sites").mkdir(exist_ok=True)
    badges = root / "packages/ui/src/assets"
    badges.mkdir(parents=True, exist_ok=True)
    for lang, url in BADGES.items():  # the official Google Play badges (Google's brand guidelines)
        target = badges / f"google-play-badge-{lang}.png"
        if not target.exists():
            run(["curl", "-sSfL", "-o", str(target), url])
            print(f"  + {target.relative_to(root)}")
    LOCAL.write_text(json.dumps({"repo": str(root)}, indent=2), encoding="utf-8")
    print(f"OK: monorepo at {root}. Next: cd {root} && npm install")


def cmd_auth(args):
    """Opens a separate console window: the token is typed there (hidden), never in the chat."""
    if args.store:
        import getpass
        print(f"Cloudflare account profile '{args.profile}'\n")
        account = input("Account ID (dashboard -> the account -> Overview, right column): ").strip()
        token = getpass.getpass("API token (hidden, paste with right click): ").strip()
        if not re.fullmatch(r"[0-9a-f]{32}", account) or len(token) < 30:
            fail("That does not look like an Account ID (32 hex characters) and a token")
        cf = Cloudflare(args.profile, account, token)
        cf.call("GET", f"/accounts/{account}/pages/projects")  # Pages permission on that account
        zones = [z["name"] for z in cf.call("GET", f"/zones?account.id={account}&per_page=50") or []]
        save_token(args.profile, account, token)
        root = repo(args.repo)
        data = accounts(root)
        data.setdefault(args.profile, {}).update({"account_id": account, "zones": zones})  # keeps "developer"
        (root / "accounts.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"\nOK: saved as {CRED.format(args.profile)}. Zones the token sees: {', '.join(zones) or 'none'}")
        input("Enter to close this window.")
        return
    cmd = [sys.executable, str(Path(__file__).resolve())]
    cmd += ["--repo", str(repo(args.repo))]  # --repo is a global option: before the command
    cmd += ["auth", "--profile", args.profile, "--store"]
    subprocess.Popen(cmd, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    print("A new window asks for the Account ID and the token (SETUP.md step 3). Check afterwards with: web.py status")


def cmd_new(args):
    root = repo(args.repo)
    slug = args.slug
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", slug):
        fail("slug: lowercase letters, digits and dashes")
    folder = root / "sites" / slug
    if folder.exists():
        fail(f"sites/{slug} already exists")
    if args.profile not in accounts(root):
        print(f"WARNING: profile '{args.profile}' is not in accounts.json yet (web.py auth --profile {args.profile})")
    shutil.copytree(TEMPLATES / "site", folder)
    cfg = json.loads((folder / "site.json").read_text(encoding="utf-8"))
    cfg.update({"slug": slug, "name": args.name or slug.replace("-", " ").title(), "profile": args.profile,
                "project": args.project or slug, "domain": args.domain})
    cfg["play"]["package"] = args.package or ""
    cfg["app_project"] = args.app_project or ""
    cfg["assets_dir"] = args.assets or ""
    cfg["play_dir"] = args.play_dir or default_play_dir(cfg)
    (folder / "site.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    pkg = folder / "package.json"
    pkg.write_text(pkg.read_text(encoding="utf-8").replace("__SLUG__", slug), encoding="utf-8")
    cfg["_dir"] = folder
    plan, changes = link_plan(root, cfg)
    if plan:  # the main site of the domain lists the new app, and the app links back
        apply_link(root, cfg, plan)
        print("Linked with the main site:\n" + "\n".join(f"  - {c}" for c in changes))
    for other in all_sites(root):  # a new main site: it lists the app sites of its domain
        child = site(root, other)
        child_plan, child_changes = link_plan(root, child)
        if child_plan and child_plan[0]["slug"] == slug and child_changes:
            apply_link(root, child, child_plan)
            print(f"Linked {other} with this main site:\n" + "\n".join(f"  - {c}" for c in child_changes))
    print(f"OK: sites/{slug}. Next: npm install (in {root}), then the analysis (SKILL.md step 1)")


# --- the app and its website: documents, About, Google Play (references/app-integration.md) -------

PLAY_APPS = SKILL.parent / "play-console" / "apps.json"  # play-console: package -> its play folder
WEB_DOCS = ("privacy", "terms")  # published on the website; licenses stay in the app
APP_DOCS = ("privacy", "terms", "licenses")
LINKS_START, LINKS_END = "<!-- web.py:links -->", "<!-- /web.py:links -->"


def default_play_dir(cfg):
    package = cfg.get("play", {}).get("package")
    if package and PLAY_APPS.exists():
        known = json.loads(PLAY_APPS.read_text(encoding="utf-8")).get(package)
        if known:
            return Path(known).as_posix()
    assets = cfg.get("assets_dir")
    return (Path(assets).parent / "play").as_posix() if assets else ""


def app_module(cfg, module):
    project = cfg.get("app_project") or fail("site.json has no app_project (the Android project folder)")
    folder = Path(project) / module
    if not folder.is_dir():
        fail(f"No module '{module}' in {project} (--module)")
    return Path(project), folder


def page_url(cfg, lang, path):
    prefix = "" if lang == cfg["default_locale"] else f"/{lang}"
    return f"https://{cfg['domain']}{prefix}{path}"


def unfinished(text):
    """Template leftovers in a document: placeholders, guidance comments, TODO."""
    return [m for m in ("{{", "<!--", "TODO") if m in text]


POM_REPOS = ("https://dl.google.com/dl/android/maven2", "https://repo1.maven.org/maven2")
_pom_cache = {}


def pom_text(cache, group, artifact, version):
    """The POM from Gradle's cache; Gradle skips it when the artifact has module metadata (.module),
    so then from Google Maven or Maven Central (public, read only)."""
    key = (group, artifact, version)
    if key in _pom_cache:
        return _pom_cache[key]
    text = None
    local = sorted((cache / group / artifact / version).glob("*/*.pom"))
    if local:
        text = local[0].read_text(encoding="utf-8", errors="replace")
    else:
        for base in POM_REPOS:
            url = f"{base}/{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.pom"
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cloudflare-site-licenses"}), timeout=20) as r:
                    text = r.read().decode("utf-8", "replace")
                break
            except Exception:  # noqa: BLE001 - not in this repository: try the next one
                continue
    _pom_cache[key] = text
    return text


def pom_licenses(cache, group, artifact, version, depth=0):
    """Licenses declared in a Maven POM, following <parent> POMs (AndroidX, Google and Square declare
    them there). Returns [(name, url)] or []."""
    import xml.etree.ElementTree as ET
    text = pom_text(cache, group, artifact, version) if version and depth <= 6 else None
    if not text:
        return []
    try:
        tree = ET.fromstring(text)
    except ET.ParseError:
        return []
    for el in tree.iter():  # drop the Maven namespace
        el.tag = el.tag.split("}")[-1]
    found = [((l.findtext("name") or "").strip(), (l.findtext("url") or "").strip()) for l in tree.findall("./licenses/license")]
    if found:
        return found
    parent = tree.find("./parent")
    if parent is not None:
        return pom_licenses(cache, parent.findtext("groupId"), parent.findtext("artifactId"), parent.findtext("version"), depth + 1)
    return []


def license_family(name, url):
    s = f"{name} {url}".lower()
    for family, keys in (("Apache 2.0", ("apache",)), ("MIT", ("mit license", "opensource.org/licenses/mit", " mit")),
                         ("BSD 3-Clause", ("bsd-3", "bsd 3", "new bsd", "revised bsd")), ("BSD 2-Clause", ("bsd-2", "bsd 2", "simplified bsd")),
                         ("BSD", ("bsd",)), ("ISC", ("isc",)), ("EPL", ("eclipse public",)), ("MPL 2.0", ("mozilla",)),
                         ("LGPL", ("lgpl", "lesser general")), ("GPL", ("gpl", "general public")), ("CC0", ("cc0",)),
                         ("Unicode", ("unicode",)), ("OFL", ("open font", "ofl"))):
        if any(k in s for k in keys):
            return family
    return name or "?"


def cmd_licenses(args):
    """Every artifact on the app's release runtime classpath with the license its POM declares, plus
    what Gradle does not see (local modules, jars/aars in libs/, fonts) -> content/licenses-inventory.md.
    It is the evidence for assets/legal/licenses.md, written by hand from it."""
    root = repo(args.repo)
    cfg = site(root, args.slug)
    project, module = app_module(cfg, args.module)
    wrapper = project / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if not wrapper.exists():
        fail(f"No Gradle wrapper in {project}")
    print(f"> gradle :{args.module}:dependencies --configuration {args.configuration}", flush=True)
    out = run([str(wrapper), f":{args.module}:dependencies", "--configuration", args.configuration, "-q"],
              cwd=project, capture=True).stdout
    line_re = re.compile(r"--- (project \S+|[\w.\-]+:[\w.\-]+(?::[^\s]+)?)(?: -> ([^\s]+))?(?: \(([*cn])\))?\s*$")
    artifacts, modules = {}, set()
    for line in out.splitlines():
        m = line_re.search(line)
        if not m or m.group(3) in ("c", "n"):  # constraints and unresolved entries do not ship
            continue
        coord, arrow = m.group(1), m.group(2)
        if coord.startswith("project "):
            modules.add(coord.split(" ", 1)[1])
            continue
        parts = coord.split(":")
        version = arrow or (parts[2] if len(parts) > 2 else None)
        if parts[1].endswith("-bom") or not version:
            continue
        artifacts[(parts[0], parts[1])] = version
    if not artifacts:
        fail(f"Gradle listed no dependencies for {args.configuration}: check the module and the configuration name")
    cache = Path(os.environ.get("GRADLE_USER_HOME", Path.home() / ".gradle")) / "caches" / "modules-2" / "files-2.1"
    rows, unknown = [], []
    for (group, artifact), version in sorted(artifacts.items()):
        lic = pom_licenses(cache, group, artifact, version)
        family = ", ".join(sorted({license_family(n, u) for n, u in lic})) if lic else "?"
        urls = " ".join(sorted({u for _, u in lic if u}))
        rows.append((family, group, artifact, version, urls))
        if family == "?":
            unknown.append(f"{group}:{artifact}:{version}")
    extra = []
    for folder, kinds in ((module / "libs", (".jar", ".aar")), (module / "src/main/res/font", (".ttf", ".otf", ".xml")),
                          (module / "src/main/assets/fonts", (".ttf", ".otf"))):
        if folder.is_dir():
            extra += [f"`{p.relative_to(project).as_posix()}`" for p in sorted(folder.iterdir()) if p.suffix.lower() in kinds]
    by_family = {}
    for row in rows:
        by_family.setdefault(row[0], []).append(row)
    md = [f"# Open-source inventory — {cfg['name']}", "",
          f"`{args.module}` · `{args.configuration}` (what ships in the release). Generated by `web.py licenses`; "
          "the evidence for `assets/legal/licenses.md` (references/app-integration.md §2). Not published.", "",
          "| License | Components |", "| --- | --- |"]
    md += [f"| {fam} | {len(items)} |" for fam, items in sorted(by_family.items(), key=lambda kv: -len(kv[1]))]
    for fam, items in sorted(by_family.items(), key=lambda kv: -len(kv[1])):
        md += ["", f"## {fam}", "", "| Component | Version | License URL |", "| --- | --- | --- |"]
        md += [f"| `{g}:{a}` | {v} | {u} |" for _, g, a, v, u in items]
    md += ["", "## Not seen by Gradle: check each one by hand", ""]
    md += [f"- Local module `{m}`: its own license (its LICENSE file or the author's)" for m in sorted(modules)] or []
    md += [f"- {e}" for e in extra]
    if not modules and not extra:
        md.append("- (nothing)")
    if unknown:
        md += ["", "## No license in the POM", "", "Find it in the project's repository (LICENSE file) before writing the document:", ""]
        md += [f"- `{u}`" for u in unknown]
    target = cfg["_dir"] / "content" / "licenses-inventory.md"
    target.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"  {len(rows)} components: " + ", ".join(f"{f} {len(i)}" for f, i in sorted(by_family.items(), key=lambda kv: -len(kv[1]))))
    copyleft = [r for r in rows if r[0] in ("GPL", "LGPL")]
    for r in copyleft:
        print(f"  WARNING copyleft: {r[1]}:{r[2]} ({r[0]}) — tell the user before publishing")
    if unknown:
        print(f"  WARNING {len(unknown)} without a license in the POM (listed in the inventory)")
    print(f"OK: {target.relative_to(root)}. Next: write assets/legal/licenses.md from it")


def play_links_block(cfg):
    rows = [("Política de privacidad (Contenido de la app › Política de privacidad)", page_url(cfg, cfg["default_locale"], "/privacy/")),
            ("Sitio web (Ficha de Play Store › Detalles de contacto)", f"https://{cfg['domain']}/"),
            ("Términos y condiciones", page_url(cfg, cfg["default_locale"], "/terms/"))]
    return "\n".join([LINKS_START, "| Campo de Play Console | Valor |", "| --- | --- |"]
                     + [f"| {k} | {v} |" for k, v in rows] + [LINKS_END])


def cmd_legal(args):
    """The app's documents (assets/legal/privacy.md, terms.md, licenses.md) are the single source, in
    ENGLISH ONLY (never translated): privacy and terms are copied to the website, which shows the same
    English text in every site language; the app must link the site and open the documents; the Play
    folder gets the links (app-content.md). --check verifies without writing; --online fetches the
    live privacy page."""
    root = repo(args.repo)
    cfg = site(root, args.slug)
    project, module = app_module(cfg, args.module)
    src = module / "src" / "main" / "assets" / "legal"
    problems, done, notes = [], [], []

    # 1. The documents in the app: one English file each (legacy <doc>_en.md accepted as the source)
    clean = {}
    for doc in APP_DOCS:
        f = next((c for c in (src / f"{doc}.md", src / f"{doc}_en.md") if c.exists()), None)
        if not f:
            problems.append(f"app: no assets/legal/{doc}.md (English only)")
            continue
        left = unfinished(f.read_text(encoding="utf-8"))
        if left:
            problems.append(f"app: {f.name} still has template leftovers ({', '.join(left)})")
        else:
            clean[doc] = f
    translated = sorted(f.name for f in src.glob("*_*.md") if not f.name.endswith("_en.md")) if src.is_dir() else []
    if translated:
        problems.append(f"app: translated legal documents ({', '.join(translated[:6])}…): legal documents are English only, remove them")

    # 2. Website: src/legal/<doc>.md, the same English text for every site language
    legal_dir = cfg["_dir"] / "src" / "legal"
    for doc in WEB_DOCS:
        target = legal_dir / f"{doc}.md"
        source = clean.get(doc)
        if not source:
            problems.append(f"web: {target.relative_to(root).as_posix()} is not the app's document yet")
            continue
        text = source.read_text(encoding="utf-8")
        if target.exists() and target.read_text(encoding="utf-8") == text:
            continue
        if args.check:
            problems.append(f"web: {target.relative_to(root).as_posix()} differs from the app's {source.name}")
        else:
            target.write_text(text, encoding="utf-8")
            done.append(f"web: {target.relative_to(root).as_posix()} <- {source.name}")
    if not args.check:  # template documents the site does not use (no image credits, old per-language copies)
        for f in sorted(legal_dir.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            if text.startswith("TODO: copy the app's own") or (f.stem.count(".") and f.stem.split(".")[0] in WEB_DOCS):
                f.unlink()
                done.append(f"web: removed {f.relative_to(root).as_posix()}")
        if not list(legal_dir.glob("credits*.md")):
            for page in (cfg["_dir"] / "src/pages/credits.astro", cfg["_dir"] / "src/pages/[lang]/credits.astro"):
                if page.exists():
                    page.unlink()
                    done.append(f"web: removed {page.relative_to(root).as_posix()} (the app has no image credits)")

    # 3. The app links the website and shows the documents
    strings = " ".join(p.read_text(encoding="utf-8", errors="replace") for p in (module / "src/main/res").glob("values*/*.xml"))
    if f"https://{cfg['domain']}" not in strings:
        problems.append(f"app: no string with https://{cfg['domain']} (About › website: about_web_url)")
    if not re.search(rf"https://{re.escape(cfg['domain'])}(/[a-z\-]+)?/privacy", strings):
        problems.append(f"app: no string with the privacy URL https://{cfg['domain']}/privacy/ (privacy_policy_url)")
    code = " ".join(p.read_text(encoding="utf-8", errors="replace") for p in (module / "src/main").rglob("*")
                    if p.suffix in (".kt", ".java")) + strings
    for doc in APP_DOCS:  # LegalDocs.Doc.PRIVACY (templates) or an asset path "legal/privacy…"
        if not re.search(rf"Doc\.{doc.upper()}\b|legal/{doc}", code):
            problems.append(f"app: nothing opens the {doc} document (About › documents: LegalDocs.Doc.{doc.upper()})")

    # 4. Google Play: the links (and the app-content declarations to complete from the analysis)
    pdir = Path(cfg.get("play_dir") or default_play_dir(cfg) or fail("site.json has no play_dir"))
    play_file = pdir / "app-content.md"
    block = play_links_block(cfg)
    if play_file.exists():
        text = play_file.read_text(encoding="utf-8")
    else:
        text = (TEMPLATES / "play" / "app-content.md").read_text(encoding="utf-8")
        text = text.replace("{{APP}}", cfg["name"]).replace("{{SLUG}}", cfg["slug"])
    if LINKS_START in text and LINKS_END in text:
        new = re.sub(re.escape(LINKS_START) + r".*?" + re.escape(LINKS_END), lambda _: block, text, flags=re.S)
    else:
        new = text.rstrip() + "\n\n## Enlaces\n\n" + block + "\n"
    if new != text or not play_file.exists():
        if args.check:
            problems.append(f"play: {play_file} does not have the current links (run without --check)")
        else:
            pdir.mkdir(parents=True, exist_ok=True)
            play_file.write_text(new, encoding="utf-8")
            done.append(f"play: {play_file} (links)")
    left = [l.strip() for l in new.splitlines() if "{{" in l]
    if left:
        problems.append(f"play: {play_file.name} has {len(left)} answers to complete from the analysis ({{{{…}}}})")

    # 5. Live page
    if args.online:
        url = page_url(cfg, cfg["default_locale"], "/privacy/")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cloudflare-site-check"})
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", "replace")
            first = clean.get("privacy")
            heading = next((l[3:].strip() for l in first.read_text(encoding="utf-8").splitlines() if l.startswith("## ")), "") if first else ""
            if heading and heading.split(". ", 1)[-1] not in html:
                problems.append(f"online: {url} does not show the app's current policy (deploy again)")
            else:
                done.append(f"online: {url} OK")
        except Exception as e:  # noqa: BLE001 - report any network/HTTP error as a problem
            problems.append(f"online: {url} -> {e}")

    for d in done:
        print(f"  {d}")
    for n in notes:
        print(f"  NOTE {n}")
    for p in problems:
        print(f"  PROBLEM {p}")
    if problems:
        fail(f"{len(problems)} things left to integrate the app and its website (references/app-integration.md)")
    print("OK: app documents, website and Play links are consistent")


# --- assets ----------------------------------------------------------------------------------------

IMG = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".avif"}
VID = {".mp4", ".mov", ".webm", ".mkv"}


def probe(path):
    if path.suffix.lower() in VID:
        r = run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                 "stream=width,height:format=duration", "-of", "json", str(path)], check=False, capture=True)
        try:
            d = json.loads(r.stdout)
            s = d["streams"][0]
            return f"{s['width']}x{s['height']} {float(d['format']['duration']):.0f}s"
        except Exception:
            return "video"
    if path.suffix.lower() == ".svg":
        return "svg"
    try:
        from PIL import Image
        with Image.open(path) as im:
            return f"{im.width}x{im.height}"
    except Exception:
        return ""


def cmd_assets(args):
    root = repo(args.repo)
    cfg = site(root, args.slug)
    folder = Path(args.folder or cfg.get("assets_dir") or fail("No assets_dir in site.json (or pass --folder)"))
    if not folder.exists():
        fail(f"{folder} does not exist")
    rows = []
    for p in sorted(folder.rglob("*")):
        skip = {"node_modules", "work", "remotion", "upload", ".git"}  # build folders of other skills
        if p.is_file() and p.suffix.lower() in IMG | VID and not skip & set(p.parts) and ".proxy." not in p.name:
            rows.append((p.relative_to(folder).as_posix(), probe(p), p.stat().st_size))
    out = cfg["_dir"] / "content" / "assets-inventory.md"
    out.parent.mkdir(exist_ok=True)
    lines = [f"# Assets in {folder}", "", "| File | Size | KB |", "|---|---|---|"]
    lines += [f"| {r} | {d} | {s // 1024} |" for r, d, s in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} images/videos -> {out}")


def cmd_import(args):
    """Images go to src/assets/<to>/ (Astro makes AVIF/WebP at build); videos are re-encoded small
    for the web (H.264, no sound, <= 1080 px, faststart) into public/media/."""
    root = repo(args.repo)
    cfg = site(root, args.slug)
    for i, f in enumerate(map(Path, args.files)):
        if not f.exists():
            fail(f"{f} does not exist")
        name = (args.name if len(args.files) == 1 and args.name else f.stem)
        name = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
        if f.suffix.lower() in VID:
            target = cfg["_dir"] / "public" / "media" / f"{name}.mp4"
            target.parent.mkdir(parents=True, exist_ok=True)
            run([tool("ffmpeg"), "-y", "-loglevel", "error", "-i", str(f), "-an", "-vf",
                 "scale='min(1080,iw)':-2,fps=30", "-c:v", "libx264", "-crf", "28", "-preset", "slow",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)])
            poster = target.with_suffix(".jpg")
            run([tool("ffmpeg"), "-y", "-loglevel", "error", "-i", str(target), "-frames:v", "1", "-q:v", "3", str(poster)])
            size = target.stat().st_size
            print(f"  video {f.name} -> {target.relative_to(root)} ({size / 1048576:.1f} MB) + poster")
            if size > MAX_FILE:
                fail(f"{target.name} is over 25 MiB: cut it shorter or use the YouTube video")
        else:
            target = cfg["_dir"] / "src" / "assets" / args.to / f"{name}{f.suffix.lower().replace('.jpeg', '.jpg')}"
            target.parent.mkdir(parents=True, exist_ok=True)
            if args.trim:
                trim_phone(f, target)
            else:
                shutil.copy2(f, target)
            print(f"  image {f.name} -> {target.relative_to(root)}" + (" (trimmed)" if args.trim else ""))


def trim_phone(src, target):
    """A phone screenshot without the system bars: the black band at the top (status bar hidden or
    camera cutout) and the navigation bar at the bottom (48 dp, the width taken as ~411 dp)."""
    from PIL import Image
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        top = 0
        while top < h // 8 and max(max(im.getpixel((x, top))) for x in range(0, w, max(1, w // 24))) < 14:
            top += 1
        nav = round(48 * w / 411)
        im.crop((0, top, w, h - nav)).save(target, quality=92)


def adb(*a, capture=True):
    if not ADB.exists():
        fail(f"adb not found at {ADB} (Android SDK platform-tools)")
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    return subprocess.run([str(ADB), *a], capture_output=capture, env=env)


def cmd_capture(args):
    root = repo(args.repo)
    cfg = site(root, args.slug)
    devices = [l for l in adb("devices").stdout.decode().splitlines()[1:] if l.strip().endswith("device")]
    if not devices:
        fail("No phone: connect it by USB, unlock it, enable USB debugging (Settings > Developer options) "
             "and accept the 'Allow USB debugging' prompt. Check with: adb devices")
    raw = Path(cfg.get("assets_dir") or cfg["_dir"]) / "web-captures"
    raw.mkdir(parents=True, exist_ok=True)
    if args.kind == "shot":
        target = raw / f"{args.name}.png"
        target.write_bytes(adb("exec-out", "screencap", "-p").stdout)
    else:
        remote = f"/sdcard/{args.name}.mp4"
        print(f"Recording {args.seconds}s: do the action on the phone now...")
        adb("shell", "screenrecord", "--time-limit", str(args.seconds), "--bit-rate", "12000000", remote, capture=False)
        target = raw / f"{args.name}.mp4"
        adb("pull", remote, str(target))
        adb("shell", "rm", remote)
    print(f"OK: {target}  ({probe(target)}). Review it, then: web.py import {args.slug} \"{target}\"")


# --- build and checks ------------------------------------------------------------------------------

def check_dist(dist, cfg):
    problems, files, total = [], 0, 0
    pages = []
    for p in dist.rglob("*"):
        if p.is_file():
            files += 1
            total += p.stat().st_size
            if p.stat().st_size > MAX_FILE:
                problems.append(f"{p.relative_to(dist)} is over 25 MiB (Pages limit)")
            if p.suffix == ".html":
                pages.append(p)
    if files > MAX_FILES:
        problems.append(f"{files} files, Pages allows {MAX_FILES}")
    for page in pages:
        html = page.read_text(encoding="utf-8", errors="replace")
        rel = page.relative_to(dist).as_posix()
        if page.name == "404.html":
            continue
        for what, pattern in (("<html lang>", r"<html[^>]+lang="), ("<title>", r"<title>[^<]{5,}</title>"),
                              ("meta description", r'<meta[^>]+name="description"'),
                              ("og:image", r'<meta[^>]+property="og:image"'),
                              ("canonical", r'<link[^>]+rel="canonical"')):
            if not re.search(pattern, html):
                problems.append(f"{rel}: no {what}")
        visible = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)
        if "TODO" in visible:
            problems.append(f"{rel}: placeholder text (TODO) left in the page")
        if "{{" in visible:
            problems.append(f"{rel}: template placeholder ({{{{…}}}}) left in the page")
        for img in re.findall(r"<img\b[^>]*>", html):
            if not re.search(r'\salt(=|\s|/?>)', img):  # alt="" may be minified to a bare alt
                problems.append(f"{rel}: <img> without alt: {img[:90]}")
        for href in re.findall(r'(?:href|src)="(/[^"#?]*)', html):
            target = dist / href.lstrip("/")
            if not (target.exists() or (target / "index.html").exists() or target.with_suffix(".html").exists()):
                problems.append(f"{rel}: broken link {href}")
    return problems, files, total, len(pages)


def build(root, slug):
    cfg = site(root, slug)
    print(f"> build {slug}", flush=True)
    out = run([NPM, "run", "build", "-w", f"sites/{slug}"], cwd=root, capture=True)
    warnings = sorted({l.strip() for l in (out.stdout + out.stderr).splitlines() if re.search(r"\bwarn|\[WARN\]", l, re.I)})
    for w in warnings:
        print(f"  WARNING {w}")
    dist = cfg["_dir"] / "dist"
    problems, files, total, pages = check_dist(dist, cfg)
    linked, notes = link_problems(root, cfg, dist)
    problems += linked
    for w in notes:
        print(f"  WARNING {w}")
    print(f"  {pages} pages, {files} files, {total / 1048576:.1f} MB")
    for p in sorted(set(problems)):
        print(f"  PROBLEM {p}")
    if problems:
        fail(f"{slug}: {len(set(problems))} problems in the build")
    return cfg, dist


def cmd_build(args):
    root = repo(args.repo)
    for slug in (all_sites(root) if args.all else [args.slug or fail("build <slug> or --all")]):
        build(root, slug)
    print("OK: built and checked")



# --- the main site of the domain and the promo video (web.py link / web.py video) --------------------

APPS_FILE = "src/apps.json"  # the main site's list of apps (its Home shows one card per entry)
PROMO_FORMATS = ("horizontal", "vertical")
SCRIPT_REGIONS = {"zh-hans": "zh-cn", "zh-hant": "zh-tw"}  # site path (script) -> video locale (region)
POSTER_WIDTH = 1080
HOOK_SECOND = 1.8  # the frame publish.py uses for the YouTube thumbnail


def write_site_json(cfg):
    data = {k: v for k, v in cfg.items() if not k.startswith("_")}
    (cfg["_dir"] / "site.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parent_site(root, cfg):
    """The site of the domain's main host: a site whose domain is a suffix of this one's
    (era-soft.app for forevernote.era-soft.app). None for a main site or when there is none."""
    best = None
    for slug in all_sites(root):
        other = site(root, slug)
        if slug != cfg["slug"] and cfg["domain"].endswith("." + other["domain"]):
            if best is None or len(other["domain"]) > len(best["domain"]):
                best = other
    return best


def parent_entry(parent):
    return {"slug": parent["slug"], "name": parent["name"], "url": f"https://{parent['domain']}/",
            "locales": parent["locales"], "default_locale": parent["default_locale"]}


def load_apps(parent):
    path = parent["_dir"] / APPS_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def i18n_text(cfg, lang, *keys):
    path = cfg["_dir"] / "src/i18n" / f"{lang}.json"
    if not path.exists():
        return ""
    node = json.loads(path.read_text(encoding="utf-8"))
    for k in keys:
        node = node.get(k, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, str) else ""


def app_card(cfg, parent, old):
    """The card of an app on the main site: keeps what is already written (descriptions, icon, play)."""
    card = dict(old or {})
    card.update({"slug": cfg["slug"], "website": f"https://{cfg['domain']}/",
                 "locales": cfg["locales"], "default_locale": cfg["default_locale"]})
    card.setdefault("name", cfg["name"])
    card.setdefault("icon", f"/brand/{cfg['slug']}.svg")
    card.setdefault("tile", False)
    card.setdefault("play", cfg.get("play", {}).get("package", ""))
    descriptions = dict(card.get("description") or {})
    for lang in parent["locales"]:
        if not descriptions.get(lang):
            text = i18n_text(cfg, lang, "meta", "description") or i18n_text(cfg, cfg["default_locale"], "meta", "description")
            if text:
                descriptions[lang] = text
    card["description"] = descriptions
    return card


def link_plan(root, cfg):
    parent = parent_site(root, cfg)
    if not parent:
        return None, []
    apps = load_apps(parent)
    own = f"https://{cfg['domain']}"
    old = next((a for a in apps if a.get("slug") == cfg["slug"] or a.get("website", "").rstrip("/") == own), None)
    card = app_card(cfg, parent, old)
    changes = []
    if cfg.get("parent") != parent_entry(parent):
        changes.append(f"sites/{cfg['slug']}/site.json: parent = {parent['name']} (https://{parent['domain']}/)")
    if old != card:
        changes.append(f"sites/{parent['slug']}/{APPS_FILE}: {'update' if old else 'add'} the card of {cfg['name']}")
    icon = parent["_dir"] / "public" / card["icon"].lstrip("/")
    logo = cfg["_dir"] / "src/assets/logo.svg"
    if not icon.exists():
        changes.append(f"sites/{parent['slug']}/public{card['icon']}: copy of sites/{cfg['slug']}/src/assets/logo.svg"
                       if logo.exists() else f"sites/{parent['slug']}/public{card['icon']}: MISSING, add the app icon by hand")
    return (parent, apps, old, card, icon, logo), changes


def apply_link(root, cfg, plan):
    parent, apps, old, card, icon, logo = plan
    cfg["parent"] = parent_entry(parent)
    write_site_json(cfg)
    apps = [card if a is old else a for a in apps] if old else apps + [card]
    path = parent["_dir"] / APPS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(apps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not icon.exists() and logo.exists():
        icon.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(logo, icon)


def cmd_link(args):
    """An app's site and the main site of its domain link each other: the main site lists the app
    (src/apps.json, with its website) and the app's site links back (site.json parent -> ParentLink)."""
    root = repo(args.repo)
    cfg = site(root, args.slug)
    plan, changes = link_plan(root, cfg)
    if plan is None:
        print(f"{args.slug}: no main site for {cfg['domain']} in the monorepo (a site whose domain is its parent domain). Nothing to link.")
        return
    if not changes:
        print(f"OK: {args.slug} and {plan[0]['slug']} already link each other")
        return
    print("Plan:\n" + "\n".join(f"  - {c}" for c in changes))
    if not args.yes:
        print("Nothing written. Run again with --yes.")
        return
    apply_link(root, cfg, plan)
    print(f"OK: linked. Check the descriptions in sites/{plan[0]['slug']}/{APPS_FILE} (natural text per language),"
          f" then build and deploy both sites: {args.slug} and {plan[0]['slug']}")


def promo_project(cfg):
    """app-promo-video's folder of the app: <app folder>/promo-video or <assets_dir>/promo-video."""
    assets = cfg.get("assets_dir")
    if not assets:
        return None
    for folder in (Path(assets).parent / "promo-video", Path(assets) / "promo-video"):
        if (folder / "video.json").exists():
            return folder
    return None


def published_videos(folder):
    """{video locale (lowercase): {format: (upload name, id)}} of the public or unlisted uploads."""
    data = json.loads((folder / "video.json").read_text(encoding="utf-8"))
    out = {}
    for locale, pub in (data.get("publish") or {}).items():
        for name, up in ((pub or {}).get("uploaded") or {}).items():
            if not isinstance(up, dict) or not up.get("id") or up.get("privacy") == "private":
                continue
            fmt = next((f for f in PROMO_FORMATS if f"-{f}" in name), "horizontal")
            out.setdefault(locale.lower(), {}).setdefault(fmt, (name, up["id"]))
    return out


def video_for(videos, lang):
    lang = SCRIPT_REGIONS.get(lang, lang).lower()
    if lang in videos:
        return videos[lang]
    base = lang.split("-")[0]
    return next((v for loc, v in sorted(videos.items()) if loc.split("-")[0] == base), None)


def make_poster(folder, name, vertical, target):
    """The video's own thumbnail when it has the video's shape, else its hook frame."""
    from PIL import Image
    up = folder / "upload" / name
    thumb = up / "thumbnail.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    if thumb.exists():
        with Image.open(thumb) as im:
            if (im.height > im.width) == vertical:
                img = im.convert("RGB")
                img.thumbnail((POSTER_WIDTH, POSTER_WIDTH * 2), Image.LANCZOS)
                img.save(target, quality=90)
                return "thumbnail"
    video = up / "video.mp4"
    if not video.exists():
        return None
    run([tool("ffmpeg"), "-v", "error", "-y", "-ss", str(HOOK_SECOND), "-i", str(video), "-frames:v", "1",
         "-vf", f"scale='min({POSTER_WIDTH},iw)':-2", "-q:v", "2", str(target)])
    return "hook frame"


def video_plan(cfg, fmt=None):
    folder = promo_project(cfg)
    if not folder:
        return None, None, {}
    videos = published_videos(folder)
    per_lang = {lang: video_for(videos, lang) for lang in cfg["locales"]}
    if not fmt:  # the format published for the most languages of the site (a tie: horizontal)
        fmt = max(PROMO_FORMATS, key=lambda f: (sum(1 for v in per_lang.values() if v and f in v), f == "horizontal"))
    chosen = {lang: v[fmt] for lang, v in per_lang.items() if v and fmt in v}
    return folder, fmt, chosen


def shows_video(cfg):
    return any("YouTube" in p.read_text(encoding="utf-8", errors="replace") for p in (cfg["_dir"] / "src").rglob("*.astro"))


def cmd_video(args):
    """The app's promo videos (app-promo-video, published on YouTube) -> site.json youtube.<lang> and
    youtube_vertical, with a poster per language in src/assets/video/poster-<lang>.jpg."""
    root = repo(args.repo)
    cfg = site(root, args.slug)
    folder, fmt, chosen = video_plan(cfg, args.format)
    if not folder:
        print(f"{args.slug}: the app has no promo-video/video.json next to {cfg.get('assets_dir') or '(no assets_dir)'}. Nothing to add.")
        return
    if not chosen:
        print(f"{args.slug}: no public or unlisted {fmt} upload in {folder / 'video.json'} for {', '.join(cfg['locales'])}.")
        return
    youtube = {lang: vid for lang, (_, vid) in chosen.items()}
    changed = cfg.get("youtube") != youtube or bool(cfg.get("youtube_vertical")) != (fmt == "vertical")
    cfg["youtube"], cfg["youtube_vertical"] = youtube, fmt == "vertical"
    write_site_json(cfg)
    print(f"{'Updated' if changed else 'Unchanged'}: site.json youtube ({fmt}) = {json.dumps(youtube)}")
    missing = [l for l in cfg["locales"] if l not in youtube]
    if missing:
        print(f"  no video for {', '.join(missing)}: those pages show the {cfg['default_locale']} one")
    for lang, (name, _) in chosen.items():
        poster = cfg["_dir"] / "src/assets/video" / f"poster-{lang}.jpg"
        if poster.exists() and not args.posters:
            print(f"  poster-{lang}.jpg kept (--posters to make it again)")
            continue
        how = make_poster(folder, name, fmt == "vertical", poster)
        print(f"  poster-{lang}.jpg from the {how}" if how else f"  poster-{lang}.jpg: no thumbnail or video in upload/{name}")
    if not shows_video(cfg):
        print("  WARNING: no component shows a YouTube video yet: add the video section to src/components/Home.astro"
              " (promoVideo(site, lang) from @sites/ui/links.ts, SKILL.md step 5)")
    print(f"Next: web.py build {args.slug}, qa, deploy")


def link_problems(root, cfg, dist):
    """Problems (the build fails) and warnings about the main site link and the promo video."""
    problems, warnings = [], []
    home = dist / "index.html"
    html = home.read_text(encoding="utf-8", errors="replace") if home.exists() else ""
    parent = parent_site(root, cfg)
    if parent:
        if not cfg.get("parent"):
            problems.append(f"not linked with its main site {parent['domain']}: web.py link {cfg['slug']} --yes")
        elif f"https://{parent['domain']}/" not in html:
            problems.append(f"the home page has no link to https://{parent['domain']}/ (ParentLink in the Layout footer)")
        if not any(a.get("website", "").rstrip("/") == f"https://{cfg['domain']}" for a in load_apps(parent)):
            problems.append(f"the main site {parent['slug']} does not list this site: web.py link {cfg['slug']} --yes")
    if (cfg["_dir"] / APPS_FILE).exists():
        for slug in all_sites(root):
            child = site(root, slug)
            if (child.get("parent") or {}).get("slug") == cfg["slug"] and f"https://{child['domain']}/" not in html:
                problems.append(f"the home page has no link to the app site https://{child['domain']}/ ({slug})")
    _, _, chosen = video_plan(cfg)
    if chosen and not cfg.get("youtube"):
        warnings.append(f"the app has a published promo video: web.py video {cfg['slug']}")
    elif chosen and any(cfg["youtube"].get(l) != v for l, (_, v) in chosen.items()):
        warnings.append(f"site.json youtube differs from the published promo videos: web.py video {cfg['slug']}")
    if cfg.get("youtube") and "lite-youtube" not in html:
        problems.append("site.json has a promo video but the home page does not show it (YouTube section in Home.astro)")
    return problems, warnings


BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome"]


def serve(dist):
    """The built site on a local port, with Pages-like directory URLs."""
    import functools
    import http.server
    import threading
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            # /__frame/<w>/<h>/<page>: the page inside an iframe of that size (phone screenshots)
            m = re.match(r"/__frame/(\d+)/(\d+)(/.*)", self.path)
            if not m:
                return super().do_GET()
            body = (f"<!doctype html><body style='margin:0'><iframe src='{m.group(3)}' style='border:0;"
                    f"width:{m.group(1)}px;height:{m.group(2)}px;display:block'></iframe>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    handler = functools.partial(Handler, directory=str(dist))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.handle_error = lambda *a: None  # the headless browser drops connections when it is done
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def cmd_qa(args):
    """Screenshots of every page (desktop 1440 px and phone 390 px, whole page) to review with Read,
    and optionally the Lighthouse scores (performance, accessibility, best practices, SEO)."""
    root = repo(args.repo)
    cfg = site(root, args.slug)
    dist = cfg["_dir"] / "dist"
    if not dist.exists():
        fail(f"Build first: web.py build {args.slug}")
    browser = next((b for b in BROWSERS if Path(b).exists()), None) or fail("Needs Microsoft Edge or Google Chrome")
    out = cfg["_dir"] / "content" / "qa"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    server, base = serve(dist)
    pages = sorted("/" + p.parent.relative_to(dist).as_posix().strip(".") for p in dist.rglob("index.html"))
    pages = [p.replace("//", "/").rstrip("/") + "/" for p in pages]
    if args.pages:
        wanted = {p.strip() if p.strip().endswith("/") else p.strip() + "/" for p in args.pages.split(",")}
        pages = [p for p in pages if p in wanted]
    try:
        for page in pages:
            name = page.strip("/").replace("/", "_") or "home"
            themes = ["light", "dark"] if args.theme == "both" else [args.theme]
            shots = []
            for theme in themes:
                for label, (w, h) in {"desktop": (1440, args.height), "phone": (390, args.height)}.items():
                    target = out / f"{name}-{label}-{theme}.png"
                    url = base + page
                    if w < 600:  # headless windows are never narrower than ~500 px: lay the page out in an iframe
                        url = f"{base}/__frame/{w}/{h}{page}"
                    # prefers-color-scheme for the page: Blink's preferredColorScheme 0 = dark, 1 = light
                    scheme = "0" if theme == "dark" else "1"
                    run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={max(w, 800)},{h}",
                         "--force-device-scale-factor=1", f"--blink-settings=preferredColorScheme={scheme}",
                         f"--screenshot={target}", "--virtual-time-budget=4000", url], capture=True, check=False)
                    if w < 600 and target.exists():
                        from PIL import Image
                        with Image.open(target) as im:
                            im.crop((0, 0, w, h)).save(target)
                    shots.append(target.name)
            print(f"  {page} -> {', '.join(shots)}")
        if args.lighthouse:
            env = {**os.environ, "CHROME_PATH": browser}
            for page in pages[: args.lighthouse_pages]:
                report = out / f"lighthouse-{page.strip('/').replace('/', '_') or 'home'}.json"
                r = run([NPX, "--yes", "lighthouse@13", base + page, "--quiet", "--output=json", f"--output-path={report}",
                         "--only-categories=performance,accessibility,best-practices,seo", "--form-factor=mobile",
                         "--chrome-flags=--headless=new"], env=env, capture=True, check=False)
                if not report.exists():
                    print(f"  lighthouse {page}: failed\n{(r.stderr or r.stdout)[-1500:]}")
                    continue
                data = json.loads(report.read_text(encoding="utf-8"))
                print(f"  lighthouse {page}: " + ", ".join(f"{k} {round((v['score'] or 0) * 100)}" for k, v in data["categories"].items()))
                a = data["audits"]
                print("    " + ", ".join(f"{k} {a[k]['displayValue']}" for k in ("first-contentful-paint", "largest-contentful-paint",
                                                                            "cumulative-layout-shift", "total-blocking-time")))
                # The local server sends no compression or cache headers: those audits are fine on Pages.
                weak = [v["title"] for k, v in a.items() if v.get("score") is not None and v["score"] < 0.9
                        and k not in ("cache-insight", "document-latency-insight", "uses-long-cache-ttl", "uses-text-compression")]
                if weak:
                    print("    to improve: " + "; ".join(weak[:8]))
    finally:
        server.shutdown()
    print(f"OK: {out}  (review the screenshots with Read; content/ is not published)")


def cmd_preview(args):
    root = repo(args.repo)
    site(root, args.slug)
    run([NPM, "run", "preview", "-w", f"sites/{args.slug}"], cwd=root)


# --- deploy, domain, status ------------------------------------------------------------------------

def git(root, *a):
    r = subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip() if r.returncode == 0 else ""


def last_deploy(cf, cfg):
    deps = cf.call("GET", f"/accounts/{cf.account}/pages/projects/{cfg['project']}/deployments?env=production&per_page=1", ok404=True)
    return deps[0] if deps else None


def changed_sites(root):
    """Sites whose files (or the shared packages) changed since their last production deploy."""
    out = []
    for slug in all_sites(root):
        cfg = site(root, slug)
        cf = Cloudflare(cfg["profile"])
        dep = last_deploy(cf, cfg) if cf.project(cfg["project"]) else None
        sha = ((dep or {}).get("deployment_trigger") or {}).get("metadata", {}).get("commit_hash")
        if not sha or not git(root, "cat-file", "-t", sha):
            out.append(slug)
            continue
        diff = git(root, "diff", "--name-only", sha, "--", f"sites/{slug}", "packages", "package-lock.json")
        dirty = git(root, "status", "--porcelain", "--", f"sites/{slug}", "packages")
        if diff or dirty:
            out.append(slug)
    return out


def deploy(root, slug, prod, yes):
    cfg, dist = build(root, slug)
    cf = Cloudflare(cfg["profile"])
    branch = "main" if prod else "preview"
    proj = cf.project(cfg["project"])
    if not proj:
        print(f"  the Pages project '{cfg['project']}' does not exist in account '{cfg['profile']}': it will be created")
    if prod and not yes:
        print(f"  {slug}: would publish {dist} to PRODUCTION of '{cfg['project']}' ({cfg['domain']}). Add --yes.")
        return
    if not proj:
        cf.call("POST", f"/accounts/{cf.account}/pages/projects", {"name": cfg["project"], "production_branch": "main"})
    sha = git(root, "rev-parse", "HEAD")
    msg = git(root, "log", "-1", "--format=%s") or "deploy"
    dirty = bool(git(root, "status", "--porcelain", "--", f"sites/{slug}", "packages"))
    cmd = [NPX, "wrangler", "pages", "deploy", str(dist), "--project-name", cfg["project"], "--branch", branch,
           "--commit-message", msg[:300]]
    if sha:
        cmd += ["--commit-hash", sha] + (["--commit-dirty=true"] if dirty else [])
    run(cmd, cwd=root, env=cf.env())
    proj = cf.project(cfg["project"])
    where = f"https://{cfg['domain']}" if prod else f"https://{branch}.{proj['subdomain']}"
    print(f"OK: {slug} -> {where}" + ("  (uncommitted changes deployed: commit them)" if dirty else ""))


def cmd_deploy(args):
    root = repo(args.repo)
    slugs = changed_sites(root) if args.changed else [args.slug or fail("deploy <slug> or --changed")]
    if args.changed:
        print(f"Changed since their last production deploy: {', '.join(slugs) or 'none'}")
    for slug in slugs:
        deploy(root, slug, args.prod, args.yes)


# Record types that may share the zone apex with the flattened Pages CNAME.
APEX_COMPATIBLE = {"MX", "TXT", "CAA", "NS", "SRV", "HTTPS", "SVCB"}


def cmd_domain(args):
    root = repo(args.repo)
    cfg = site(root, args.slug)
    cf = Cloudflare(cfg["profile"])
    host = cfg["domain"]
    proj = cf.project(cfg["project"]) or fail(f"Deploy '{args.slug}' once first (the Pages project does not exist)")
    target = proj["subdomain"]  # <project>.pages.dev, sometimes with a suffix if the name was taken
    zone = cf.zone(host) or fail(f"No zone for {host} in account '{cfg['profile']}' (or the token lacks Zone Read on it)")
    domains = {d["name"]: d for d in cf.call("GET", f"/accounts/{cf.account}/pages/projects/{cfg['project']}/domains") or []}
    records = cf.call("GET", f"/zones/{zone['id']}/dns_records?name={host}") or []
    plan = []
    if host not in domains:
        plan.append(f"add {host} as a custom domain of the Pages project {cfg['project']}")
    cname = [r for r in records if r["type"] == "CNAME"]
    # At the zone apex Cloudflare flattens the CNAME, so it lives next to the zone's mail and verification
    # records (MX, TXT...: e.g. Email Routing for support@<domain>), which are left untouched.
    apex = host == zone["name"]
    blocking = [r for r in records if r["type"] != "CNAME" and not (apex and r["type"] in APEX_COMPATIBLE)]
    if not cname:
        if blocking:
            fail(f"{host} already has other DNS records ({', '.join(r['type'] for r in blocking)}): resolve it by hand")
        kept = sorted({r["type"] for r in records})
        plan.append(f"DNS {zone['name']}: CNAME {host} -> {target} (proxied" + (", flattened at the apex" if apex else "") + ")"
                    + (f"; keeps its {', '.join(kept)} records" if kept else ""))
    elif cname[0]["content"] != target:
        fail(f"{host} is a CNAME to {cname[0]['content']}, not {target}: change it by hand if that is intended")
    if not plan:
        d = domains[host]
        print(f"{host}: {d.get('status')} (certificate {d.get('validation_data', {}).get('status', d.get('status'))})")
        return
    print("\n".join("  " + p for p in plan))
    if not args.yes:
        print("Not applied: run again with --yes")
        return
    if host not in domains:
        cf.call("POST", f"/accounts/{cf.account}/pages/projects/{cfg['project']}/domains", {"name": host})
    if not cname:
        cf.call("POST", f"/zones/{zone['id']}/dns_records", {"type": "CNAME", "name": host, "content": target,
                                                              "proxied": True, "comment": f"Pages {cfg['project']}"})
    print(f"OK: {host} -> {target}. The certificate takes a few minutes: web.py domain {args.slug}")


def cmd_status(args):
    root = repo(args.repo)
    print(f"monorepo {root}")
    for name, a in accounts(root).items():
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                load_token(name)
            ok = "token OK"
        except SystemExit:
            ok = "NO TOKEN"
        print(f"  account {name:12} {a['account_id']}  {ok}  zones: {', '.join(a.get('zones', []))}")
    for slug in all_sites(root):
        cfg = site(root, slug)
        line = f"  site {slug:16} {cfg['profile']:10} {cfg['domain']:32}"
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                cf = Cloudflare(cfg["profile"])
            proj = cf.project(cfg["project"])
            if not proj:
                print(line + " (not deployed yet)")
                continue
            dep = last_deploy(cf, cfg)
            when = (dep or {}).get("created_on", "")[:16].replace("T", " ")
            doms = {d["name"]: d.get("status") for d in cf.call("GET", f"/accounts/{cf.account}/pages/projects/{cfg['project']}/domains") or []}
            print(line + f" {proj['subdomain']}  last prod {when or '-'}  domain {doms.get(cfg['domain'], 'not added')}")
        except SystemExit:
            print(line + " (no token for its profile)")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="the monorepo (default: the current folder's, else the one from init)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("repo")
    s = sub.add_parser("auth"); s.add_argument("--profile", required=True); s.add_argument("--store", action="store_true", help=argparse.SUPPRESS)
    s = sub.add_parser("new"); s.add_argument("slug"); s.add_argument("--profile", required=True); s.add_argument("--domain", required=True)
    s.add_argument("--package"); s.add_argument("--name"); s.add_argument("--project"); s.add_argument("--app-project"); s.add_argument("--assets")
    s.add_argument("--play-dir", help="the app's Google Play folder (default: play-console's, else <app folder>/play)")
    s = sub.add_parser("licenses"); s.add_argument("slug"); s.add_argument("--module", default="app")
    s.add_argument("--configuration", default="releaseRuntimeClasspath")
    s = sub.add_parser("legal"); s.add_argument("slug"); s.add_argument("--module", default="app")
    s.add_argument("--check", action="store_true", help="only verify, write nothing")
    s.add_argument("--online", action="store_true", help="also fetch the published privacy page")
    s = sub.add_parser("assets"); s.add_argument("slug"); s.add_argument("--folder")
    s = sub.add_parser("import"); s.add_argument("slug"); s.add_argument("files", nargs="+"); s.add_argument("--to", default="screens"); s.add_argument("--name")
    s.add_argument("--trim", action="store_true", help="phone screenshots: cut the status and navigation bars")
    s = sub.add_parser("capture"); s.add_argument("slug"); s.add_argument("kind", choices=["shot", "record"]); s.add_argument("name")
    s.add_argument("--seconds", type=int, default=20)
    s = sub.add_parser("build"); s.add_argument("slug", nargs="?"); s.add_argument("--all", action="store_true")
    s = sub.add_parser("preview"); s.add_argument("slug")
    s = sub.add_parser("qa"); s.add_argument("slug"); s.add_argument("--height", type=int, default=5200)
    s.add_argument("--theme", choices=["light", "dark", "both"], default="both")
    s.add_argument("--pages", help="only these pages, comma separated (e.g. /,/es/)")
    s.add_argument("--lighthouse", action="store_true"); s.add_argument("--lighthouse-pages", type=int, default=2)
    s = sub.add_parser("deploy"); s.add_argument("slug", nargs="?"); s.add_argument("--changed", action="store_true")
    s.add_argument("--prod", action="store_true"); s.add_argument("--yes", action="store_true")
    s = sub.add_parser("domain"); s.add_argument("slug"); s.add_argument("--yes", action="store_true")
    sub.add_parser("status")
    s = sub.add_parser("link"); s.add_argument("slug"); s.add_argument("--yes", action="store_true")
    s = sub.add_parser("video"); s.add_argument("slug"); s.add_argument("--format", choices=PROMO_FORMATS)
    s.add_argument("--posters", action="store_true", help="make the posters again even if they exist")
    if "--store" in sys.argv:  # the separate auth window: keep it open on any error so it can be read
        try:
            args = ap.parse_args()
            return cmd_auth(args)
        except BaseException as e:
            if not isinstance(e, (KeyboardInterrupt, SystemExit)):  # fail() already printed its message
                import traceback
                traceback.print_exc()
            input("\nEnter to close this window.")
            raise
    args = ap.parse_args()
    if args.cmd == "init":
        return cmd_init(args)
    globals()["cmd_" + args.cmd](args)


if __name__ == "__main__":
    main()
