"""Google Play Console from files: the store listing (texts, video, icon, feature graphic,
screenshots) and the releases (bundle, track, release notes, rollout) of any app, for several
developer accounts. Uses the Google Play Android Developer API v3 with a service account.

    python play.py auth     <service-account.json> --profile <name>      once per developer account
    python play.py register <data folder> [--package com.x.y] [--profile name]
    python play.py status   [--app <data folder>]
    python play.py pull     [--app ...] [--images]      the published listing -> files (start here)
    python play.py diff     [--app ...]                 what push-listing would change
    python play.py push-listing [--app ...] [--yes]     texts, video and images (only what changed)
    python play.py release  <app.aab> [--app ...] [--track internal] [--rollout 0.1] [--yes]
    python play.py promote  --from internal --to production [--rollout 0.1] [--app ...] [--yes]
    python play.py retire   --track alpha [--app ...] [--yes]   halt a testing track's releases (never production)

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
import json
import os
import re
import sys
import time
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


def token(profile):
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
            with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers), timeout=900) as r:
                text = r.read()
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code == 403:
                detail += ("\nThe service account has no access to this app: invite it in Play Console"
                           " (Users and permissions) with permissions for this app.")
            if e.code == 404 and "edits" in path and not self.edit:
                detail += "\nThe app does not exist in Play Console, or it has no first release uploaded by hand yet."
            fail(f"{method} {path.split('?')[0]}: HTTP {e.code} {detail[:1200]}")

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
    return cfg.get("languages") or [cfg.get("default_language", "en-US")]


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
    """listing/<lang>/video.txt, or the YouTube link publish.py saved in the promo video.json."""
    f = cfg["_dir"] / "listing" / lang / "video.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    src = (cfg.get("video") or {}).get("from")
    if src and rel(cfg, src).exists():
        promo = json.loads(rel(cfg, src).read_text(encoding="utf-8"))
        uploaded = (promo.get("publish", {}).get(lang) or {}).get("uploaded", {})
        horizontal = [v for k, v in uploaded.items() if "-horizontal" in k]
        if horizontal:
            return horizontal[-1]["url"]
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
            have = {}
        for field, value in want.items():
            if (have.get(field) or "") != value:
                changes.append(("text", lang, field, have.get(field) or "", value))
        for t, files in local_images(cfg, lang).items():
            remote = api.call("GET", api.e(f"/listings/{lang}/{t}")).get("images", [])
            if [i.get("sha256") for i in remote] != [sha256(f) for f in files]:
                changes.append(("images", lang, t, len(remote), files))
    return changes


def show(changes):
    if not changes:
        print("Nothing to change: the files match what is published.")
    for c in changes:
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


def cmd_push_listing(args):
    cfg = find_app(args.app)
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        changes = plan_listing(api, cfg)
        show(changes)
        if not changes:
            return
        texts = {}
        for c in changes:
            if c[0] == "text":
                texts.setdefault(c[1], {})[c[2]] = c[4]
        for lang, fields in texts.items():
            api.call("PATCH", api.e(f"/listings/{lang}"), {"language": lang, **fields})
        for c in changes:
            if c[0] == "images":
                _, lang, t, _, files = c
                api.call("DELETE", api.e(f"/listings/{lang}/{t}"))
                for f in files:
                    mime = "image/png" if f.suffix.lower() == ".png" else "image/jpeg"
                    api.call("POST", api.e(f"/listings/{lang}/{t}"), raw=f.read_bytes(), content_type=mime, upload=True)
        api.call("POST", api.e(":validate"))
        if not args.yes:
            print("\nValidated by Google, NOT published (dry run). Run again with --yes to publish.")
            return
        api.commit()
        print("\nOK: listing published.")
    finally:
        api.discard()


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


def cmd_release(args):
    cfg = find_app(args.app)
    aab = Path(args.bundle)
    if not aab.exists() or aab.suffix != ".aab":
        fail(f"Not an .aab: {aab}")
    api = Api(cfg["profile"], cfg["package"])
    api.open()
    try:
        print(f"Uploading {aab.name} ({aab.stat().st_size // 1048576} MB) to {cfg['package']}...")
        bundle = api.call("POST", api.e("/bundles"), raw=aab.read_bytes(), content_type="application/octet-stream",
                          upload=True, query="?uploadType=media")
        vc = bundle["versionCode"]
        notes = release_notes(cfg, vc)
        if not notes:
            print(f"  (no release notes: add changelogs/<lang>/{vc}.txt or default.txt)")
        api.call("PUT", api.e(f"/tracks/{args.track}"),
                 {"track": args.track, "releases": [track_release([vc], notes, args.rollout, args.name)]})
        api.call("POST", api.e(":validate"))
        rollout = f"{args.rollout * 100:g}%" if args.rollout and args.rollout < 1 else "100%"
        print(f"versionCode {vc} -> {args.track} ({rollout}), notes in {', '.join(n['language'] for n in notes) or 'none'}")
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


def main():
    # Windows consoles default to cp1252: print accents and any Unicode from the API safely.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("auth"); a.add_argument("key"); a.add_argument("--profile", required=True)
    r = sub.add_parser("register"); r.add_argument("folder"); r.add_argument("--package"); r.add_argument("--profile")
    for name in ("status", "pull", "diff", "push-listing"):
        s = sub.add_parser(name); s.add_argument("--app")
        if name == "pull":
            s.add_argument("--images", action="store_true")
        if name == "push-listing":
            s.add_argument("--yes", action="store_true")
    rl = sub.add_parser("release"); rl.add_argument("bundle"); rl.add_argument("--app")
    rl.add_argument("--track", default="internal"); rl.add_argument("--rollout", type=float, default=None)
    rl.add_argument("--name"); rl.add_argument("--yes", action="store_true")
    pr = sub.add_parser("promote"); pr.add_argument("--app")
    pr.add_argument("--from", dest="source", required=True); pr.add_argument("--to", dest="target", required=True)
    pr.add_argument("--rollout", type=float, default=None); pr.add_argument("--yes", action="store_true")
    rt = sub.add_parser("retire"); rt.add_argument("--track", required=True); rt.add_argument("--app")
    rt.add_argument("--yes", action="store_true")
    args = p.parse_args()
    {"retire": cmd_retire, "auth": cmd_auth, "register": cmd_register, "status": cmd_status, "pull": cmd_pull, "diff": cmd_diff,
     "push-listing": cmd_push_listing, "release": cmd_release, "promote": cmd_promote}[args.cmd](args)


if __name__ == "__main__":
    main()
