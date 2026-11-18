"""Google Play Console from files: the store listing (texts, video, icon, feature graphic,
screenshots) and the releases (bundle, track, release notes, rollout) of any app, for several
developer accounts. Uses the Google Play Android Developer API v3 with a service account.

    python play.py auth     <service-account.json> --profile <name>      once per developer account
    python play.py register <data folder> [--package com.x.y] [--profile name]
    python play.py status   [--app <data folder>]
    python play.py versions [--app ...]                 every versionCode Play knows, as JSON
    python play.py pull     [--app ...] [--images]      the published listing -> files (start here)
    python play.py diff     [--app ...]                 what push-listing would change
    python play.py push-listing [--app ...] [--yes] [--only en-US,es-419] [--batch 5] [--parallel 8]
                                                        texts, video and images (only what changed)
    python play.py release  <app.aab> [--app ...] [--track internal] [--rollout 0.1] [--yes]
    python play.py promote  --from internal --to production [--rollout 0.1] [--draft] [--app ...] [--yes]
    python play.py retire   --track alpha [--app ...] [--yes]   halt a testing track's releases (never production)
    python play.py details  [--email ..] [--website ..] [--phone ..] [--language es-419] [--yes]   contact details
    python play.py data-safety <form.csv> [--yes]       the Data safety form (CSV exported from Play Console)
    python play.py testers  [--track alpha] [--groups a@googlegroups.com,..] [--yes]
    python play.py release-status [--track internal,alpha,beta,production] [--json]   review state of each release
    python play.py reviews  [--json] | --reply <reviewId> --text "..." --yes

Nothing is published without --yes: every change is built in an "edit" (a draft), validated by
Google and shown; without --yes the edit is deleted. Production also needs --yes.

Which app: --app <folder>, else the package of the Android project in the current folder
(applicationId in app/build.gradle) looked up in apps.json (next to this skill, per PC).
Data folder layout (play.json describes it; paths in it are relative to the folder or absolute):
    play.json
    listing/<lang>/title.txt, short.txt, full.txt, video.txt
    images/<lang>/icon.png, featureGraphic.png, phoneScreenshots/01.png ...
    changelogs/<lang>/<versionCode>.txt   (or default.txt)
Run without -I: the service account token is signed with the "cryptography" package.
"""
import argparse
import base64
import ctypes
import ctypes.wintypes as w
import hashlib
import http.client
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REGISTRY = SKILL / "apps.json"
API = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
UPLOAD = "https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
TEXTS = {"title": ("title", 30), "short": ("shortDescription", 80), "full": ("fullDescription", 4000)}
IMAGE_TYPES = ["icon", "featureGraphic", "phoneScreenshots", "sevenInchScreenshots", "tenInchScreenshots",
               "tvScreenshots", "wearScreenshots", "tvBanner"]
SINGLE = {"icon": (512, 512), "featureGraphic": (1024, 500), "tvBanner": (1280, 720)}
NOTES_MAX = 500


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


# --- service account keys: Windows Credential Manager, one per profile ------------------------------
# Only what the token needs (e-mail, private key, token URI), as UTF-8: ~1.8 KB, inside the
# Credential Manager's 2,560-byte limit (the whole JSON in UTF-16 would not fit). The Credential
# Manager encrypts it with DPAPI, readable only by this Windows user.

CRED_TARGET = "PlayConsole@{}"
CRED_MAX = 2560


class CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", w.DWORD), ("Type", w.DWORD), ("TargetName", w.LPWSTR), ("Comment", w.LPWSTR),
                ("LastWritten", w.FILETIME), ("CredentialBlobSize", w.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", w.DWORD),
                ("AttributeCount", w.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", w.LPWSTR), ("UserName", w.LPWSTR)]


def save_key(profile, key):
    if sys.platform != "win32":
        fail("On this system put the key JSON in the environment variable PLAY_KEY_<PROFILE>")
    blob = json.dumps({k: key[k] for k in ("client_email", "private_key", "token_uri")},
                      separators=(",", ":")).encode("utf-8")
    if len(blob) > CRED_MAX:
        fail(f"The key takes {len(blob)} bytes, over the Credential Manager's {CRED_MAX}")
    buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    cred = CREDENTIAL(Type=1, TargetName=CRED_TARGET.format(profile), CredentialBlobSize=len(blob),
                      CredentialBlob=buf, Persist=2, UserName=key["client_email"])  # 2 = LOCAL_MACHINE
    if not ctypes.windll.advapi32.CredWriteW(ctypes.byref(cred), 0):
        fail("Could not store the key in the Credential Manager")


def load_key(profile):
    env = os.environ.get(f"PLAY_KEY_{profile.upper()}")
    if env:
        return json.loads(env)
    pointer = ctypes.POINTER(CREDENTIAL)()
    if sys.platform != "win32" or not ctypes.windll.advapi32.CredReadW(CRED_TARGET.format(profile), 1, 0, ctypes.byref(pointer)):
        fail(f"No key for the profile '{profile}': python play.py auth <service-account.json> --profile {profile}")
    try:
        c = pointer.contents
        return json.loads(bytes(c.CredentialBlob[:c.CredentialBlobSize]).decode("utf-8"))
    finally:
        ctypes.windll.advapi32.CredFree(pointer)


# --- access token: a JWT signed by the service account ----------------------------------------------

_tokens = {}


_token_lock = threading.Lock()


def token(profile):
    with _token_lock:
        return _token(profile)


def _token(profile):
    if profile in _tokens and _tokens[profile][1] > time.time() + 60:
        return _tokens[profile][0]
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError:
        fail("Missing the 'cryptography' package: python -m pip install --user cryptography (and run without -I)")
    key = load_key(profile)
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
    now = int(time.time())
    header = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64(json.dumps({"iss": key["client_email"], "scope": SCOPE, "aud": key["token_uri"],
                             "iat": now, "exp": now + 3600}).encode())
    private = serialization.load_pem_private_key(key["private_key"].encode(), password=None)
    signature = b64(private.sign(header + b"." + claims, padding.PKCS1v15(), hashes.SHA256()))
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": (header + b"." + claims + b"." + signature).decode()}).encode()
    with urllib.request.urlopen(urllib.request.Request(key["token_uri"], data=body), timeout=60) as r:
        t = json.loads(r.read())
    _tokens[profile] = (t["access_token"], now + int(t.get("expires_in", 3600)))
    return t["access_token"]


# A flaky connection resets uploads now and then: each call retries, waiting up to a minute.
RETRIES = 10
# Resumable upload chunk: a multiple of 256 KB, as the protocol requires (except the last one).
UPLOAD_CHUNK = 256 * 1024

class Api:
    def __init__(self, profile, package):
        self.profile, self.package = profile, package
        self.edit = None

    def call(self, method, path, body=None, raw=None, content_type="application/json", upload=False, query=""):
        base = UPLOAD if upload else API
        url = f"{base}/{self.package}{path}{query}"
        data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
        headers = {"Authorization": f"Bearer {token(self.profile)}"}
        if data is not None:
            headers["Content-Type"] = content_type
        try:
            # A flaky connection (reset, SSL EOF, timeout) or a busy Google (HTTP 5xx) is retried;
            # any other HTTP answer is final.
            for attempt in range(RETRIES):
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers),
                                                timeout=900) as r:
                        text = r.read()
                        return json.loads(text) if text else {}
                except urllib.error.HTTPError as e:
                    if e.code < 500 or attempt == RETRIES - 1:
                        raise
                    print(f"  (HTTP {e.code} on {method} {path.split('?')[0]}; retrying)")
                    time.sleep(min(60, 5 * (attempt + 1)))
                except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
                    if attempt == RETRIES - 1:
                        raise
                    print(f"  (network error on {method} {path.split('?')[0]}: {e}; retrying)")
                    time.sleep(min(60, 5 * (attempt + 1)))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code == 403:
                detail += ("\nThe service account has no access to this app: invite it in Play Console"
                           " (Users and permissions) with permissions for this app.")
            if e.code == 404 and "edits" in path and not self.edit:
                detail += "\nThe app does not exist in Play Console, or it has no first release uploaded by hand yet."
            fail(f"{method} {path.split('?')[0]}: HTTP {e.code} {detail[:1200]}")

    def upload_resumable(self, path, data, mime, label=""):
        """Uploads a file with Google's resumable protocol (developers.google.com/android-publisher/upload):
        a session, then 256 KB chunks; after a cut connection it asks the session how many bytes Play
        already has and goes on from there, instead of sending the whole file again. Backoff 2^n s plus
        up to 1 s of jitter; a lost session (404/410) starts over. Keeps one connection per thread."""
        total = len(data)
        host = urllib.parse.urlsplit(UPLOAD).netloc
        local = self._conn if hasattr(self, "_conn") else None
        if local is None:
            self._conn = local = threading.local()

        def request(method, url, body=b"", headers=None):
            for attempt in range(RETRIES):
                try:
                    conn = getattr(local, "c", None)
                    if conn is None:
                        conn = local.c = http.client.HTTPSConnection(host, timeout=120)
                    conn.request(method, url, body=body, headers={"Authorization": f"Bearer {token(self.profile)}",
                                                                  **(headers or {})})
                    r = conn.getresponse()
                    return r.status, dict(r.getheaders()), r.read()
                except (OSError, http.client.HTTPException) as e:
                    if getattr(local, "c", None):
                        local.c.close()
                        local.c = None
                    if attempt == RETRIES - 1:
                        fail(f"{label}: upload failed after {RETRIES} tries: {e}")
                    wait = min(32, 2 ** attempt) + random.random()
                    print(f"  ({label}: {type(e).__name__} {e}; retrying in {wait:.1f} s)")
                    time.sleep(wait)
                    if method == "PUT" and body:
                        return 0, {}, b""  # the chunk loop asks the session where to go on

        while True:  # one session; a new one only if Play lost it
            base = urllib.parse.urlsplit(UPLOAD).path
            status, headers, body = request(
                "POST", f"{base}/{self.package}{path}?uploadType=resumable", b"",
                {"X-Upload-Content-Type": mime, "X-Upload-Content-Length": str(total), "Content-Length": "0"})
            if status != 200:
                fail(f"{label}: starting the upload: HTTP {status} {body[:400]!r}")
            session = {k.lower(): v for k, v in headers.items()}["location"]
            parts = urllib.parse.urlsplit(session)
            url = f"{parts.path}?{parts.query}"
            offset, resets = 0, 0
            while True:
                end = min(offset + UPLOAD_CHUNK, total) - 1
                status, headers, body = request("PUT", url, data[offset:end + 1], {
                    "Content-Type": mime, "Content-Range": f"bytes {offset}-{end}/{total}"})
                if status == 0:  # connection cut: ask how many bytes Play has
                    resets += 1
                    status, headers, body = request("PUT", url, b"", {"Content-Range": f"bytes */{total}",
                                                                      "Content-Length": "0"})
                if status in (200, 201):
                    return json.loads(body) if body else {}
                if status == 308:
                    rng = {k.lower(): v for k, v in headers.items()}.get("range")
                    offset = int(rng.split("-")[1]) + 1 if rng else 0
                    continue
                if status in (404, 410):
                    print(f"  ({label}: upload session lost (HTTP {status}); starting again)")
                    break
                if status >= 500:
                    wait = min(32, 2 ** min(resets, 5)) + random.random()
                    resets += 1
                    print(f"  ({label}: HTTP {status}; retrying in {wait:.1f} s)")
                    time.sleep(wait)
                    status, headers, body = request("PUT", url, b"", {"Content-Range": f"bytes */{total}",
                                                                      "Content-Length": "0"})
                    if status == 308:
                        rng = {k.lower(): v for k, v in headers.items()}.get("range")
                        offset = int(rng.split("-")[1]) + 1 if rng else 0
                        continue
                    if status in (200, 201):
                        return json.loads(body) if body else {}
                fail(f"{label}: HTTP {status} {body[:400]!r}")

    def open(self):
        self.edit = self.call("POST", "/edits", {})["id"]
        return self.edit

    def e(self, path=""):
        return f"/edits/{self.edit}{path}"

    def discard(self):
        if self.edit:
            self.call("DELETE", self.e())
            self.edit = None

    def commit(self):
        self.call("POST", self.e(":validate"))
        result = self.call("POST", self.e(":commit"))
        self.edit = None
        return result


# --- apps: data folder, registry ---------------------------------------------------------------------

def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}


def package_of_cwd():
    for gradle in (Path.cwd() / "app" / "build.gradle", Path.cwd() / "app" / "build.gradle.kts"):
        if gradle.exists():
            m = re.search(r"applicationId\s*=?\s*[\"']([\w.]+)[\"']", gradle.read_text(encoding="utf-8", errors="replace"))
            if m:
                return m.group(1)
    return None


def find_app(app_arg):
    if app_arg:
        folder = Path(app_arg).resolve()
    else:
        package = package_of_cwd()
        apps = registry()
        if package and package in apps:
            folder = Path(apps[package])
        elif len(apps) == 1 and not package:
            folder = Path(next(iter(apps.values())))
        else:
            fail(f"Which app? Use --app <data folder>, or register it: python play.py register <folder>"
                 + (f" --package {package}" if package else "") + f"\nRegistered: {apps or 'none'}")
    cfg_path = folder / "play.json"
    if not cfg_path.exists():
        fail(f"No play.json in {folder}: python play.py register {folder}")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["_dir"] = folder
    return cfg


def rel(cfg, value):
    p = Path(value)
    return p if p.is_absolute() else (cfg["_dir"] / p).resolve()


def languages(cfg):
    """The listing languages to publish: play.json "languages" without those in "hold" (kept locally,
    e.g. while a licence is pending, but never pushed)."""
    hold = set(cfg.get("hold") or [])
    return [l for l in (cfg.get("languages") or [cfg.get("default_language", "en-US")]) if l not in hold]


# --- local listing ---------------------------------------------------------------------------------------

def local_texts(cfg, lang):
    folder = cfg["_dir"] / "listing" / lang
    out = {}
    for name, (field, limit) in TEXTS.items():
        f = folder / f"{name}.txt"
        if f.exists():
            text = f.read_text(encoding="utf-8").strip()
            if len(text) > limit:
                fail(f"{f}: {len(text)} characters, Play allows {limit}")
            out[field] = text
    video = local_video(cfg, lang)
    if video is not None:
        out["video"] = video
    return out


def local_video(cfg, lang):
    """listing/<lang>/video.txt, or the YouTube link publish.py saved in the promo video.json, of the
    format in play.json "video": {"format": "vertical"} (default horizontal)."""
    f = cfg["_dir"] / "listing" / lang / "video.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    conf = cfg.get("video") or {}
    src = conf.get("from")
    if src and rel(cfg, src).exists():
        promo = json.loads(rel(cfg, src).read_text(encoding="utf-8"))
        uploaded = (promo.get("publish", {}).get(lang) or {}).get("uploaded", {})
        fmt = conf.get("format", "horizontal")
        matching = [v for k, v in uploaded.items() if f"-{fmt}" in k]
        if matching:
            return matching[-1]["url"]
    return None


def local_images(cfg, lang):
    """{imageType: [files]} from play.json "images" (per type and language) or images/<lang>/."""
    out = {}
    conf = cfg.get("images") or {}
    base = cfg["_dir"] / "images" / lang
    for t in IMAGE_TYPES:
        src = (conf.get(t) or {}).get(lang)
        files = []
        if src:
            p = rel(cfg, src)
            files = sorted(x for x in p.iterdir() if x.suffix.lower() in (".png", ".jpg", ".jpeg")) if p.is_dir() else [p]
        elif (base / f"{t}.png").exists():
            files = [base / f"{t}.png"]
        elif (base / t).is_dir():
            files = sorted(x for x in (base / t).iterdir() if x.suffix.lower() in (".png", ".jpg", ".jpeg"))
        if files:
            check_images(t, files)
            out[t] = files
    return out


def check_images(kind, files):
    from PIL import Image
    if kind in SINGLE:
        if len(files) != 1:
            fail(f"{kind}: one image, found {len(files)}")
        im = Image.open(files[0])
        if im.size != SINGLE[kind]:
            fail(f"{files[0]}: {im.size[0]}x{im.size[1]}, Play wants {SINGLE[kind][0]}x{SINGLE[kind][1]}")
        if kind == "featureGraphic" and im.mode in ("RGBA", "LA"):
            fail(f"{files[0]}: the feature graphic must have no alpha channel")
        return
    if not 2 <= len(files) <= 8:
        fail(f"{kind}: Play wants 2 to 8 screenshots, found {len(files)}")
    for f in files:
        x, y = Image.open(f).size
        # Only the sizes: Play accepts screenshots longer than 2:1 (1080x2340 is published), and the
        # edit's validation by Google catches anything else before publishing.
        if min(x, y) < 320 or max(x, y) > 3840:
            fail(f"{f}: {x}x{y}; screenshots: each side between 320 and 3840 px")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- commands ----------------------------------------------------------------------------------------------

def cmd_auth(args):
    data = json.loads(Path(args.key).read_text(encoding="utf-8"))
    if data.get("type") != "service_account":
        fail("That JSON is not a service account key (Google Cloud -> IAM -> Service accounts -> Keys -> JSON)")
    save_key(args.profile, data)
    token(args.profile)  # checks the key works
    print(f"OK: profile '{args.profile}' = {data['client_email']}\n"
          f"Invite that e-mail in Play Console -> Users and permissions, with access to its apps.\n"
          f"Then delete the downloaded JSON: the key is in the Windows Credential Manager as {CRED_TARGET.format(args.profile)}")


def cmd_register(args):
    folder = Path(args.folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    cfg_path = folder / "play.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    cfg["package"] = args.package or cfg.get("package") or package_of_cwd() or fail("Give --package com.x.y")
    cfg["profile"] = args.profile or cfg.get("profile") or fail("Give --profile <developer account profile>")
    cfg.setdefault("default_language", "en-US")
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    apps = registry()
    apps[cfg["package"]] = str(folder)
    REGISTRY.write_text(json.dumps(apps, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {cfg['package']} (profile {cfg['profile']}) -> {folder}")


def cmd_status(args):
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        details = api.call("GET", api.e("/details"))
        tracks = api.call("GET", api.e("/tracks")).get("tracks", [])
        listings = api.call("GET", api.e("/listings")).get("listings", [])
    finally:
        api.discard()
    print(f"{cfg['package']}  profile {cfg['profile']}  default language {details.get('defaultLanguage')}")
    print(f"listings: {', '.join(l['language'] for l in listings)}")
    for t in tracks:
        for r in t.get("releases", []):
            frac = f" {r['userFraction'] * 100:g}%" if r.get("userFraction") else ""
            print(f"  {t['track']:12} {r.get('status')}{frac}  versions {r.get('versionCodes')}  {r.get('name', '')}")


def cmd_versions(args):
    """Every versionCode Play knows (releases of every track, uploaded bundles and APKs) as JSON, so a
    new build can take a code Play has never seen: a code once uploaded can never be reused."""
    print(json.dumps(known_versions(find_app(args.app)), indent=2, ensure_ascii=False))


def known_versions(cfg):
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        tracks = api.call("GET", api.e("/tracks")).get("tracks", [])
        uploaded = [int(b["versionCode"]) for b in api.call("GET", api.e("/bundles")).get("bundles", [])]
        uploaded += [int(a["versionCode"]) for a in api.call("GET", api.e("/apks")).get("apks", [])]
    finally:
        api.discard()
    releases = [{"track": t["track"], "status": r.get("status"), "versionCodes": [int(v) for v in r.get("versionCodes", [])],
                 "name": r.get("name", ""), "userFraction": r.get("userFraction")}
                for t in tracks for r in t.get("releases", [])]
    codes = uploaded + [v for r in releases for v in r["versionCodes"]]
    return {"package": cfg["package"], "maxVersionCode": max(codes, default=0), "releases": releases}


def cmd_pull(args):
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        details = api.call("GET", api.e("/details"))
        listings = api.call("GET", api.e("/listings")).get("listings", [])
        langs = [l["language"] for l in listings]
        for l in listings:
            folder = cfg["_dir"] / "listing" / l["language"]
            folder.mkdir(parents=True, exist_ok=True)
            for name, (field, _) in TEXTS.items():
                (folder / f"{name}.txt").write_text(l.get(field, ""), encoding="utf-8")
            if l.get("video"):
                (folder / "video.txt").write_text(l["video"], encoding="utf-8")
            if args.images:
                for t in IMAGE_TYPES:
                    imgs = api.call("GET", api.e(f"/listings/{l['language']}/{t}")).get("images", [])
                    for i, img in enumerate(imgs, 1):
                        target = cfg["_dir"] / "images" / l["language"] / (f"{t}.png" if t in SINGLE else f"{t}/{i:02}.png")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        urllib.request.urlretrieve(img["url"] + "=w4000", target)
    finally:
        api.discard()
    path = cfg["_dir"] / "play.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["default_language"] = details.get("defaultLanguage", data.get("default_language"))
    data["languages"] = langs
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {len(langs)} languages ({', '.join(langs)}) -> {cfg['_dir'] / 'listing'}"
          + (" and images" if args.images else " (add --images to download the images too)"))


def plan_listing(api, cfg):
    """What push-listing would change, per language: texts and image types."""
    changes = []
    for lang in languages(cfg):
        want = local_texts(cfg, lang)
        try:
            have = api.call("GET", api.e(f"/listings/{lang}"))
        except SystemExit:
            have = None  # a language that is not on Play yet (fail() already printed the 404)
            print(f"  ({lang}: new language on Play)")
            changes.append(("new", lang))
        for field, value in want.items():
            if ((have or {}).get(field) or "") != value:
                changes.append(("text", lang, field, (have or {}).get(field) or "", value))
        locked = set(cfg.get("lock_images") or [])
        for t, files in local_images(cfg, lang).items():
            if f"{lang}/{t}" in locked:
                continue  # made by hand in Play Console: never replaced from the files
            remote = [] if have is None else api.call("GET", api.e(f"/listings/{lang}/{t}")).get("images", [])
            if [i.get("sha256") for i in remote] != [sha256(f) for f in files]:
                changes.append(("images", lang, t, len(remote), files))
    return changes


def show(changes):
    if not changes:
        print("Nothing to change: the files match what is published.")
    for c in changes:
        if c[0] == "new":
            continue
        if c[0] == "text":
            _, lang, field, old, new = c
            print(f"[{lang}] {field}:\n   - {old[:160]!r}\n   + {new[:160]!r}")
        else:
            _, lang, t, n_old, files = c
            print(f"[{lang}] {t}: {n_old} published -> {len(files)} ({', '.join(f.name for f in files)})")


def cmd_diff(args):
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        show(plan_listing(api, cfg))
    finally:
        api.discard()


def apply_listing(api, cfg):
    """Puts every listing change into the open edit. Returns the changes."""
    changes = plan_listing(api, cfg)
    show(changes)
    texts = {}
    for c in changes:
        if c[0] == "text":
            texts.setdefault(c[1], {})[c[2]] = c[4]
    new = {c[1] for c in changes if c[0] == "new"}
    for lang, fields in texts.items():
        # PATCH only updates an existing listing; a new language is created with PUT.
        api.call("PUT" if lang in new else "PATCH", api.e(f"/listings/{lang}"), {"language": lang, **fields})
    # Images: several languages at once (each upload waits for Play to process the image), and one
    # language's images in order, since Play keeps them in the order they were uploaded.
    by_lang = {}
    for c in changes:
        if c[0] == "images":
            by_lang.setdefault(c[1], []).append(c)
    if by_lang:
        with ThreadPoolExecutor(max_workers=PARALLEL_LANGUAGES) as pool:
            for future in [pool.submit(upload_images, api, lang, items) for lang, items in by_lang.items()]:
                future.result()
    return changes


# Languages whose images are uploaded at the same time (push-listing --parallel).
PARALLEL_LANGUAGES = 8


def upload_images(api, lang, items):
    start = time.time()
    for _, _, t, _, files in items:
        want = [sha256(f) for f in files]
        # A retried upload whose first try did reach Play leaves a duplicate: check and redo.
        for attempt in range(3):
            api.call("DELETE", api.e(f"/listings/{lang}/{t}"))
            for k, f in enumerate(files, 1):
                mime = "image/png" if f.suffix.lower() == ".png" else "image/jpeg"
                t1 = time.time()
                api.upload_resumable(api.e(f"/listings/{lang}/{t}"), f.read_bytes(), mime, f"{lang} {t} {f.name}")
                print(f"  [{lang}] {t} {k}/{len(files)} {f.name} ({f.stat().st_size // 1024} KB) in {time.time() - t1:.1f} s")
            got = [i.get("sha256") for i in api.call("GET", api.e(f"/listings/{lang}/{t}")).get("images", [])]
            if got == want:
                break
            print(f"  ({lang} {t}: {len(got)} images on Play instead of {len(want)}; uploading again)")
        else:
            fail(f"{lang} {t}: the images on Play don't match the files after 3 tries")
    n = sum(len(i[4]) for i in items)
    print(f"  [{lang}] {n} images uploaded in {time.time() - start:.0f} s")


def cmd_push_listing(args):
    global PARALLEL_LANGUAGES
    PARALLEL_LANGUAGES = max(1, args.parallel)
    cfg = find_app(args.app)
    langs = languages(cfg)
    if args.only:
        only = [x.strip() for x in args.only.split(",") if x.strip()]
        unknown = [x for x in only if x not in langs]
        if unknown:
            fail(f"Not languages of the listing: {', '.join(unknown)}")
        langs = only
    # Batches: a network cut only loses its own batch; the batches already committed stay published.
    size = args.batch if args.batch > 0 else len(langs)
    batches = [langs[i:i + size] for i in range(0, len(langs), size)]
    started = time.time()
    for n, batch in enumerate(batches, 1):
        part = {**cfg, "languages": batch, "hold": []}
        label = f"batch {n}/{len(batches)} ({', '.join(batch)})" if len(batches) > 1 else ", ".join(batch)
        print(f"\n== {label}: opening an edit")
        t0 = time.time()
        api = Api(cfg["profile"], cfg["package"])
        api.open()
        try:
            if not apply_listing(api, part):
                print(f"== {label}: nothing to change")
                continue
            api.call("POST", api.e(":validate"))
            if not args.yes:
                print(f"== {label}: validated by Google, NOT published (dry run)")
                continue
            api.commit()
            print(f"== {label}: published in {time.time() - t0:.0f} s (total {time.time() - started:.0f} s)")
        finally:
            api.discard()
    print("\nOK: listing published." if args.yes else "\nDry run: run again with --yes to publish.")


def release_notes(cfg, version_code):
    notes = []
    for lang in languages(cfg):
        folder = cfg["_dir"] / "changelogs" / lang
        for name in (f"{version_code}.txt", "default.txt"):
            f = folder / name
            if f.exists():
                text = f.read_text(encoding="utf-8").strip()
                if len(text) > NOTES_MAX:
                    fail(f"{f}: {len(text)} characters, Play allows {NOTES_MAX}")
                notes.append({"language": lang, "text": text})
                break
    return notes


def track_release(version_codes, notes, rollout, name=None):
    r = {"versionCodes": [str(v) for v in version_codes], "releaseNotes": notes}
    if name:
        r["name"] = name
    if rollout and rollout < 1:
        r.update({"status": "inProgress", "userFraction": rollout})
    else:
        r["status"] = "completed"
    return r


def confirm_production(track, yes):
    if track == "production" and not yes:
        print("Production: shown only. Run again with --yes to publish.")


def apply_release(api, cfg, args):
    """Uploads the bundle into the open edit and puts it on the track with its notes."""
    aab = Path(args.bundle)
    if not aab.exists() or aab.suffix != ".aab":
        fail(f"Not an .aab: {aab}")
    print(f"Uploading {aab.name} ({aab.stat().st_size // 1048576} MB) to {cfg['package']}...")
    bundle = api.call("POST", api.e("/bundles"), raw=aab.read_bytes(), content_type="application/octet-stream",
                      upload=True, query="?uploadType=media")
    vc = bundle["versionCode"]
    if getattr(args, "version_code", None) and int(vc) != int(args.version_code):
        fail(f"The bundle has versionCode {vc}, expected {args.version_code}: rebuild it")
    notes = release_notes(cfg, vc)
    if not notes:
        print(f"  (no release notes: add changelogs/<lang>/{vc}.txt or default.txt)")
    api.call("PUT", api.e(f"/tracks/{args.track}"),
             {"track": args.track, "releases": [track_release([vc], notes, args.rollout, args.name)]})
    rollout = f"{args.rollout * 100:g}%" if args.rollout and args.rollout < 1 else "100%"
    print(f"versionCode {vc} -> {args.track} ({rollout}), notes in {', '.join(n['language'] for n in notes) or 'none'}")


def edit_has_version(api, track, version_code):
    """Whether the open edit already puts this versionCode on the track (a resumed publish)."""
    try:
        releases = api.call("GET", api.e(f"/tracks/{track}")).get("releases", [])
    except SystemExit:
        return False
    return any(str(version_code) in r.get("versionCodes", []) for r in releases)


def cmd_publish(args):
    """The bundle, its notes and every listing change in ONE edit, so Google reviews them together.
    On a failure (a slow or flaky connection) the edit is KEPT and its id printed: --edit <id> resumes
    it, skipping the bundle already on the track and every listing that already matches the files."""
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    if args.edit:
        api.edit = args.edit
        print(f"Resuming edit {args.edit}")
    else:
        api.open()
        print(f"Edit {api.edit} (to resume after a failure: --edit {api.edit})")
    done = False
    try:
        if args.edit and args.version_code and edit_has_version(api, args.track, args.version_code):
            print(f"versionCode {args.version_code} is already on {args.track} in this edit")
        else:
            apply_release(api, cfg, args)
        print()
        apply_listing(api, cfg)
        api.call("POST", api.e(":validate"))
        if not args.yes:
            print("\nValidated by Google, NOT published (dry run). Run again with --yes to publish.")
            done = True
            return
        api.commit()
        done = True
        print("\nOK: release and listing sent for review together.")
    finally:
        if done:
            api.discard()
        elif api.edit:
            print(f"\nFAILED: the edit is kept on Play. Resume with: publish ... --edit {api.edit}")


def cmd_release(args):
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        apply_release(api, cfg, args)
        api.call("POST", api.e(":validate"))
        if not args.yes:
            print("Validated by Google, NOT published (dry run). Run again with --yes to publish.")
            return
        api.commit()
        print("OK: release published.")
    finally:
        api.discard()


def cmd_promote(args):
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        src = api.call("GET", api.e(f"/tracks/{args.source}"))
        releases = [r for r in src.get("releases", []) if r.get("status") in ("completed", "inProgress")]
        if not releases:
            fail(f"No release on {args.source} to promote")
        r = releases[0]
        new = track_release(r["versionCodes"], r.get("releaseNotes", []), args.rollout, r.get("name"))
        if args.draft:
            # An app that was never reviewed only accepts draft releases on its tracks: Play Console then
            # rolls them out when the user (or play-launch) sends the changes for review.
            new.pop("userFraction", None)
            new["status"] = "draft"
        api.call("PUT", api.e(f"/tracks/{args.target}"), {"track": args.target, "releases": [new]})
        api.call("POST", api.e(":validate"))
        print(f"versions {r['versionCodes']} {args.source} -> {args.target} ({new.get('userFraction', 1) * 100:g}%)")
        if not args.yes:
            print("Validated by Google, NOT published (dry run). Run again with --yes to publish.")
            return
        api.commit()
        print("OK: promoted.")
    finally:
        api.discard()


def cmd_retire(args):
    """Halts every release of a testing track (internal, alpha, beta, a closed track): its testers stop
    getting that version (Play ignores an empty list of releases). Only the track's current release can
    be halted: Play then shows the previous one again, and refuses to halt that one ("no matching in
    progress release") - harmless, since users get the highest versionCode of every track they are in
    (production is usually higher). To close the track itself: Play Console -> Closed testing -> the
    track -> remove its testers. Never production: replace it with a new release, or halt it in Play
    Console."""
    if args.track == "production":
        fail("retire does not touch production: publish a new release, or halt its rollout in Play Console")
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        track = api.call("GET", api.e(f"/tracks/{args.track}"))
        releases = track.get("releases", [])
        if not releases:
            print(f"{args.track} has no releases.")
            return
        # An empty list of releases is ignored by Play; a release is withdrawn by halting it.
        live = [r for r in releases if r.get("status") != "halted"]
        if not live:
            print(f"{args.track}: every release is already halted.")
            return
        for r in live:
            print(f"{args.track}: {r.get('status')} versions {r.get('versionCodes')} {r.get('name', '')} -> halted")
            r["status"] = "halted"
        api.call("PUT", api.e(f"/tracks/{args.track}"), {"track": args.track, "releases": releases})
        api.call("POST", api.e(":validate"))
        if not args.yes:
            print("Validated by Google, NOT published (dry run). Run again with --yes to publish.")
            return
        api.commit()
        print(f"OK: {args.track} halted.")
    finally:
        api.discard()


# --- app details, data safety, testers, review status, reviews ---------------------------------------
# Used by the play-launch skill. Every write is built in an edit and validated; nothing changes in Play
# without --yes (data safety has no edit: without --yes it only shows what would be sent).

DETAIL_FIELDS = {"email": "contactEmail", "website": "contactWebsite", "phone": "contactPhone",
                 "language": "defaultLanguage"}


def cmd_details(args):
    """Contact details of the store listing (e-mail, website, phone) and the default language."""
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        current = api.call("GET", api.e("/details"))
        wanted = {DETAIL_FIELDS[k]: v for k, v in vars(args).items() if k in DETAIL_FIELDS and v is not None}
        changes = {k: v for k, v in wanted.items() if current.get(k) != v}
        for field in DETAIL_FIELDS.values():
            mark = f"  -> {changes[field]}" if field in changes else ""
            print(f"  {field}: {current.get(field, '')}{mark}")
        if not changes:
            print("No changes." if wanted else "")
            return
        api.call("PATCH", api.e("/details"), changes)
        api.call("POST", api.e(":validate"))
        if not args.yes:
            print("Validated by Google, NOT saved (dry run). Run again with --yes.")
            return
        api.commit()
        print("OK: details saved.")
    finally:
        api.discard()


def cmd_data_safety(args):
    """Writes the Data safety form from the CSV that Play Console exports (Policy > App content > Data
    safety > Export to CSV): the file must keep Play's question ids. Google validates it on upload."""
    cfg = find_app(args.app)
    csv = Path(args.csv).read_text(encoding="utf-8")
    import csv as csvlib
    rows = [r for r in csvlib.reader(csv.splitlines()) if any(c.strip() for c in r)]
    answered = [r for r in rows[1:] if len(r) > 2 and r[2].strip()]
    print(f"  {args.csv}: {len(rows) - 1} rows, {len(answered)} with a response value")
    if not args.yes:
        print("NOT sent (dry run). Run again with --yes to write the Data safety form.")
        return
    Api(cfg["profile"], cfg["package"]).call("POST", "/dataSafety", {"safetyLabels": csv})
    print("OK: Data safety form written. Check it in Play Console > App content > Data safety.")


def cmd_testers(args):
    """The Google Groups (and e-mails) that may join a testing track."""
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        current = api.call("GET", api.e(f"/testers/{args.track}"))
        print(f"  {args.track}: groups {current.get('googleGroups', [])}")
        if args.groups is None:
            return
        groups = [g.strip() for g in args.groups.split(",") if g.strip()]
        if sorted(groups) == sorted(current.get("googleGroups", [])):
            print("No changes.")
            return
        api.call("PUT", api.e(f"/testers/{args.track}"), {"googleGroups": groups})
        api.call("POST", api.e(":validate"))
        print(f"  -> groups {groups}")
        if not args.yes:
            print("Validated by Google, NOT saved (dry run). Run again with --yes.")
            return
        api.commit()
        print("OK: testers saved.")
    finally:
        api.discard()


REVIEW_STATES = {
    "RELEASE_LIFECYCLE_STATE_DRAFT": "draft",
    "RELEASE_LIFECYCLE_STATE_NOT_SENT_FOR_REVIEW": "not-sent-for-review",
    "RELEASE_LIFECYCLE_STATE_IN_REVIEW": "in-review",
    "RELEASE_LIFECYCLE_STATE_APPROVED_NOT_PUBLISHED": "approved-not-published",
    "RELEASE_LIFECYCLE_STATE_NOT_APPROVED": "not-approved",
    "RELEASE_LIFECYCLE_STATE_PUBLISHED": "published",
}


def release_states(cfg, track):
    """Review state of the releases of a track (applications.tracks.releases.list)."""
    data = Api(cfg["profile"], cfg["package"]).call("GET", f"/tracks/{track}/releases")
    out = []
    for r in data.get("releases", []):
        codes = [a.get("versionCode") for a in r.get("activeArtifacts", []) if a.get("versionCode")]
        out.append({"track": track, "name": r.get("releaseName", ""), "versionCodes": codes,
                    "state": REVIEW_STATES.get(r.get("releaseLifecycleState"), r.get("releaseLifecycleState", "?"))})
    return out


def cmd_release_status(args):
    cfg = find_app(args.app)
    rows = [s for t in args.track.split(",") for s in release_states(cfg, t.strip())]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    for s in rows or [{"track": args.track, "name": "", "versionCodes": [], "state": "no releases"}]:
        print(f"  {s['track']:<12} {s['state']:<24} {s['versionCodes']} {s['name']}")


def cmd_reviews(args):
    """Recent reviews (the API returns those of the last week with text) and their replies."""
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    if args.reply:
        if not args.yes:
            print(f"Would reply to {args.reply}: {args.text!r}. Run again with --yes.")
            return
        api.call("POST", f"/reviews/{args.reply}:reply", {"replyText": args.text})
        print("OK: reply posted.")
        return
    data = api.call("GET", "/reviews", query=f"?maxResults={args.max}")
    rows = []
    for r in data.get("reviews", []):
        user = next((c["userComment"] for c in r.get("comments", []) if "userComment" in c), {})
        dev = next((c["developerComment"] for c in r.get("comments", []) if "developerComment" in c), None)
        rows.append({"id": r.get("reviewId"), "stars": user.get("starRating"), "lang": user.get("reviewerLanguage"),
                     "version": user.get("appVersionCode"), "text": (user.get("text") or "").strip(),
                     "replied": bool(dev)})
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    for r in rows or []:
        print(f"  {r['stars']}* [{r['lang']}] v{r['version']} {'(replied) ' if r['replied'] else ''}{r['id']}\n    {r['text']}")
    if not rows:
        print("No recent reviews.")


def main():
    # Windows consoles default to cp1252: print accents and any Unicode from the API safely.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("auth"); a.add_argument("key"); a.add_argument("--profile", required=True)
    r = sub.add_parser("register"); r.add_argument("folder"); r.add_argument("--package"); r.add_argument("--profile")
    for name in ("status", "versions", "pull", "diff", "push-listing"):
        s = sub.add_parser(name); s.add_argument("--app")
        if name == "pull":
            s.add_argument("--images", action="store_true")
        if name == "push-listing":
            s.add_argument("--yes", action="store_true")
            s.add_argument("--only", help="comma-separated languages: push only these")
            s.add_argument("--batch", type=int, default=0,
                           help="languages per edit: each batch is validated and committed on its own (with --yes)")
            s.add_argument("--parallel", type=int, default=PARALLEL_LANGUAGES,
                           help="languages uploading images at the same time")
    for name in ("release", "publish"):
        rl = sub.add_parser(name); rl.add_argument("bundle"); rl.add_argument("--app")
        rl.add_argument("--track", default="internal"); rl.add_argument("--rollout", type=float, default=None)
        rl.add_argument("--name"); rl.add_argument("--yes", action="store_true")
        rl.add_argument("--version-code", type=int, help="fail unless the bundle has this versionCode")
        if name == "publish":
            rl.add_argument("--edit", help="resume this edit (printed by a publish that failed)")
    pr = sub.add_parser("promote"); pr.add_argument("--app")
    pr.add_argument("--from", dest="source", required=True); pr.add_argument("--to", dest="target", required=True)
    pr.add_argument("--rollout", type=float, default=None); pr.add_argument("--yes", action="store_true")
    pr.add_argument("--draft", action="store_true", help="create the release as a draft (required while the app was never reviewed)")
    rt = sub.add_parser("retire"); rt.add_argument("--track", required=True); rt.add_argument("--app")
    rt.add_argument("--yes", action="store_true")
    d = sub.add_parser("details"); d.add_argument("--app"); d.add_argument("--yes", action="store_true")
    for k in DETAIL_FIELDS:
        d.add_argument(f"--{k}")
    ds = sub.add_parser("data-safety"); ds.add_argument("csv"); ds.add_argument("--app"); ds.add_argument("--yes", action="store_true")
    ts = sub.add_parser("testers"); ts.add_argument("--app"); ts.add_argument("--track", default="alpha")
    ts.add_argument("--groups", help="comma-separated Google Groups; omit to only show them"); ts.add_argument("--yes", action="store_true")
    rs = sub.add_parser("release-status"); rs.add_argument("--app")
    rs.add_argument("--track", default="internal,alpha,beta,production"); rs.add_argument("--json", action="store_true")
    rv = sub.add_parser("reviews"); rv.add_argument("--app"); rv.add_argument("--max", type=int, default=50)
    rv.add_argument("--json", action="store_true"); rv.add_argument("--reply"); rv.add_argument("--text")
    rv.add_argument("--yes", action="store_true")
    args = p.parse_args()
    {"details": cmd_details, "data-safety": cmd_data_safety, "testers": cmd_testers,
     "release-status": cmd_release_status, "reviews": cmd_reviews, "retire": cmd_retire, "auth": cmd_auth, "register": cmd_register, "status": cmd_status, "versions": cmd_versions,
     "pull": cmd_pull, "diff": cmd_diff,
     "push-listing": cmd_push_listing, "release": cmd_release, "publish": cmd_publish,
     "promote": cmd_promote}[args.cmd](args)


if __name__ == "__main__":
    main()
