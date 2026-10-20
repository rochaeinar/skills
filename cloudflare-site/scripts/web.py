"""Static websites for apps, one per subdomain, in one monorepo, published to Cloudflare Pages
(Direct Upload with wrangler) on several Cloudflare accounts.

    python web.py init <repo>                          monorepo scaffold (once), remembers the repo on this PC
    python web.py auth --profile <name>                guided API token for one Cloudflare account -> Credential Manager
    python web.py new <slug> --profile <p> --domain <host> [--package com.x] [--name "App"]
                         [--app-project <folder>] [--assets <folder>]
    python web.py assets <slug>                        inventory of the external images/videos folder
    python web.py import <slug> <file>... [--to screens] [--name x]   copy into the site (videos are compressed)
    python web.py capture <slug> shot <name> | record <name> [--seconds 20]   from the connected phone
    python web.py build <slug> | --all                 npm build + checks (sizes, SEO tags, links, alt texts)
    python web.py qa <slug> [--lighthouse]             screenshots desktop/phone of every page (+ Lighthouse)
    python web.py preview <slug>                       local server of the built site
    python web.py deploy <slug> [--prod --yes] | --changed [--prod --yes]
    python web.py domain <slug> [--yes]                custom domain on the Pages project + CNAME in the zone
    python web.py status                               every site: account, project, last deploy, domain

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
        data[args.profile] = {"account_id": account, "zones": zones}
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
    (folder / "site.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    pkg = folder / "package.json"
    pkg.write_text(pkg.read_text(encoding="utf-8").replace("__SLUG__", slug), encoding="utf-8")
    print(f"OK: sites/{slug}. Next: npm install (in {root}), then the analysis (SKILL.md step 1)")


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
    if not cname:
        if records:
            fail(f"{host} already has other DNS records ({', '.join(r['type'] for r in records)}): resolve it by hand")
        plan.append(f"DNS {zone['name']}: CNAME {host} -> {target} (proxied)")
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
