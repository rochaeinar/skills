"""Interstitial web ads (custom_web) for Android apps, made from the app's vertical promo video
(app-promo-video): the same hook, feature lines, recordings and outro, as one light HTML page with
CSS animations that a fullscreen WebView shows.

    python ad.py config --ads-root <folder>          once per PC: where the ads are written (<root>/<guid>/)
    python ad.py init <promo-video/video.json> [--guid <uuid>] [--features 6]   -> <app>/ad/ad.json
    python ad.py build <ad.json>                     frames, hook, logo, badges -> <root>/<guid>/index.html + img/
    python ad.py qa <ad.json> [--sizes 360x780,412x915]   screenshots of every scene per language -> <app>/ad/qa/
    python ad.py serve <ad.json>                     local preview (?lang=es, ?t=<seconds>)

ad.json is the source (texts, scenes, frame times, colors); index.html is generated from
templates/index.html. Images get content-hashed names, so a changed image is a new file (the server
caches img/ for a year). See SKILL.md and references/format.md.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
LOCAL = SKILL / "config.json"  # per PC: {"ads_root": "..."}; not in the skills backup
TEMPLATE = SKILL / "templates" / "index.html"
BADGES = {"en": SKILL / "assets" / "google-play-badge-en.png", "es": SKILL / "assets" / "google-play-badge-es.png"}
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

FRAME_WIDTH = 360        # px of each phone frame (css ~300 px wide on a phone, x1.2)
HOOK_SIZE = (540, 960)
ICON_SIZE = 192
LOGO_SIZE = 400
BADGE_WIDTH = 480
WEBP_QUALITY = 80
FRAME_POINTS = (0.12, 0.5, 0.88)   # where in the chosen part of the clip each of the 3 frames is taken
HOOK_SECOND = 1.8                  # the hook's key action (app-promo-video: within the first 1.5 s)
DURATION = {"hook": 3.4, "first": 3.2, "feature": 2.8, "outro": 3.6}
MANDATORY = 5.0                    # seconds before the close button works: hook + first feature fit
MAX_FEATURES = 6
TEXT_LIMIT = {"hook": 60, "feature": 34}
UI = {  # the ad's own words; other languages fall back to English (the app only sends es/en)
    "en": {"ad": "Ad", "badge": "Get it on Google Play", "free": "Free on Google Play"},
    "es": {"ad": "Anuncio", "badge": "Disponible en Google Play", "free": "Gratis en Google Play"},
}


def fail(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def tool(name):
    found = shutil.which(name)
    if found:
        return found
    import glob
    import os
    for d in sorted(glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages",
                                           "Gyan.FFmpeg_*", "ffmpeg-*", "bin")), reverse=True):
        if Path(d, name + ".exe").exists():
            return str(Path(d, name + ".exe"))
    fail(f"{name} not found (winget install Gyan.FFmpeg)")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ads_root(arg=None):
    if arg:
        return Path(arg)
    if LOCAL.exists():
        return Path(read_json(LOCAL)["ads_root"])
    fail("Where are the ads written on this PC? python ad.py config --ads-root <folder> (ask the user)")


# --- colors ---------------------------------------------------------------------------------------

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    """a mixed with b, t = share of b."""
    ra, rb = hex_rgb(a), hex_rgb(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ra, rb))


def colors_from(palette):
    base = palette.get("background") or palette.get("primary") or "#1b2a26"
    text = palette.get("text", "#f1f6f4")
    bg = mix(base, "#000000", 0.62)
    return {"bg": bg, "bg2": mix(base, "#000000", 0.25), "accent": palette.get("accent", "#4fd49a"),
            "text": text, "sub": mix(text, bg, 0.28)}


# --- init -----------------------------------------------------------------------------------------

def lang_of(locale):
    return locale.split("-")[0].lower()


def ad_dir_for(promo):
    """<app folder>/ad: next to promo-video (Apps/<App>/promo-video) or above Images (Images/promo-video)."""
    parent = promo.parent
    return (parent.parent if parent.name.lower() == "images" else parent) / "ad"


def first_existing(*paths):
    return next((p for p in paths if p and Path(p).exists()), None)


def cmd_config(args):
    LOCAL.write_text(json.dumps({"ads_root": str(Path(args.ads_root))}, indent=2), encoding="utf-8")
    print(f"OK: ads are written to {args.ads_root}/<guid>/ on this PC")


def cmd_init(args):
    video_json = Path(args.video_json).resolve()
    promo = video_json.parent
    v = read_json(video_json)
    fmt = "vertical"
    locales = [loc for loc, d in v.get("locales", {}).items() if fmt in d]
    if not locales:
        fail(f"{video_json} has no {fmt} scenes: the ad follows the vertical video")
    langs = {}
    for loc in locales:  # one locale per language (es-419 for es)
        langs.setdefault(lang_of(loc), loc)
    default_lang = "en" if "en" in langs else next(iter(langs))
    scenes_of = {l: v["locales"][loc][fmt]["scenes"] for l, loc in langs.items()}
    main = scenes_of[default_lang]

    hook = next((s for s in main if s["type"] == "hook"), None)
    features = [s for s in main if s["type"] == "feature"]
    picked = features[:args.features]
    text = {}
    for l, scenes in scenes_of.items():
        ui = UI.get(l, UI["en"])
        h = next((s for s in scenes if s["type"] == "hook"), {})
        outro = next((s for s in scenes if s["type"] == "outro"), {})
        text[l] = {"ad": ui["ad"], "badge": ui["badge"], "free": outro.get("text") or ui["free"],
                   "tagline": outro.get("tagline", ""), "hook": [h.get("text", ""), h.get("keyword", "")]}
        by_clip = {s.get("clip"): s for s in scenes if s["type"] == "feature"}
        for f in picked:
            s = by_clip.get(f["clip"], {})
            text[l][scene_id(f["clip"])] = [s.get("text", f["text"]), s.get("keyword", f.get("keyword", ""))]

    variant = (hook or {}).get("variant_broll") or (hook or {}).get("variant") or "A"
    broll = read_json(promo / "broll" / f"{fmt}.json").get(variant, {}) if (promo / "broll" / f"{fmt}.json").exists() else {}
    hook_src = next((broll[k] for k in ("final", "draft", "placeholder") if broll.get(k)), "")

    scenes = [{"type": "hook", "seconds": DURATION["hook"], "source": hook_src, "second": HOOK_SECOND}]
    for i, f in enumerate(picked):
        scenes.append({"type": "feature", "id": scene_id(f["clip"]), "clip": f["clip"],
                       "seconds": DURATION["first" if i == 0 else "feature"],
                       "times": {l: frame_times(promo, loc, f["clip"], scenes_of[l]) for l, loc in langs.items()}})
    scenes.append({"type": "outro", "seconds": DURATION["outro"]})

    app_dir = ad_dir_for(promo).parent
    package = (v.get("capture", {}).get("app_id") or v.get("app_id") or "").removesuffix(".debug")
    parts = list((v.get("logo_parts") or {}).values())
    logo = parts[0] if parts else v.get("logo", "")
    ad = {
        "app": v.get("app_name", app_dir.name), "package": package,
        "play": f"https://play.google.com/store/apps/details?id={package}",
        "guid": args.guid or str(uuid.uuid4()), "promo_video": str(video_json),
        "langs": langs, "default_lang": default_lang, "colors": colors_from(v.get("palette", {})),
        "icon": str(first_existing(app_dir / "Images/icon/icon.png", promo / "assets/logo_square.png",
                                   promo / v.get("logo", "_")) or ""),
        "logo": {"base": logo, "parts": parts[1:], "name": not v.get("logo_includes_name", False)},
        "scenes": scenes, "text": text,
    }
    out = ad_dir_for(promo) / "ad.json"
    if out.exists() and not args.force:
        fail(f"{out} exists (--force to make it again; it keeps nothing)")
    write_json(out, ad)
    print(f"OK: {out}  (guid {ad['guid']})")
    print(f"  languages: {', '.join(f'{l} <- {loc}' for l, loc in langs.items())}; hook: {hook_src or 'NONE (add one)'}")
    print(f"  features ({len(picked)} of {len(features)} in the video): " + ", ".join(f["clip"] for f in picked))
    if len(features) > len(picked):
        print("  Review which features go (the strongest first; the first one is seen in the mandatory 5 s).")
    print(f"Next: review ad.json (texts short, frame times), then ad.py build {out}")


def scene_id(clip):
    return re.sub(r"[^a-z0-9]+", "-", clip.lower().removesuffix("_cut")).strip("-")


def frame_times(promo, locale, clip, scenes):
    """3 moments of the part of the recording the video uses (in/out of that language's scene)."""
    s = next((x for x in scenes if x.get("clip") == clip), None) or {}
    meta = promo / "recordings" / locale / f"{clip}.json"
    length = read_json(meta).get("duration", 0) if meta.exists() else 0
    start = float(s.get("in", 0))
    end = float(s.get("out", length or start + 3))
    return [round(start + (end - start) * p, 2) for p in FRAME_POINTS]


# --- build ----------------------------------------------------------------------------------------

def hashed(name, data, ext):
    return f"{name}.{hashlib.sha1(data).hexdigest()[:8]}{ext}"


def webp_bytes(img, quality=WEBP_QUALITY):
    import io
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=quality, method=6)
    return buf.getvalue()


def grab(video, second, work):
    out = work / f"g{abs(hash((str(video), second)))}.png"
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", str(second), "-i", str(video), "-frames:v", "1", str(out)],
                   check=True)
    from PIL import Image
    return Image.open(out).convert("RGB")


def cover(img, size):
    from PIL import Image
    w, h = size
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def logo_file(path, name):
    """SVG stays SVG (sharp and small); a bitmap becomes WebP."""
    from PIL import Image
    p = Path(path)
    if p.suffix.lower() == ".svg":
        data = p.read_bytes()
        return hashed(name, data, ".svg"), data
    img = Image.open(p).convert("RGBA")
    img.thumbnail((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
    data = webp_bytes(img, 90)
    return hashed(name, data, ".webp"), data


def cmd_build(args):
    from PIL import Image
    ad_json = Path(args.ad_json).resolve()
    ad = read_json(ad_json)
    promo = Path(ad["promo_video"]).parent
    out = ads_root(args.ads_root) / ad["guid"]
    img_dir = out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp())
    files, warnings = {}, []

    def put(key, name, data):
        files[key] = name
        target = img_dir / name
        if not target.exists():
            target.write_bytes(data)

    for scene in ad["scenes"]:
        if scene["type"] == "hook":
            src = promo / scene["source"] if scene.get("source") else None
            if not src or not src.exists():
                fail(f"hook source not found: {scene.get('source')!r} (a frame or image of the video's AI hook)")
            img = Image.open(src).convert("RGB") if src.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") \
                else grab(src, scene.get("second", HOOK_SECOND), work)
            data = webp_bytes(cover(img, HOOK_SIZE))
            put("hook", hashed("hook", data, ".webp"), data)
        elif scene["type"] == "feature":
            scene["frames"] = {}
            for lang, times in scene["times"].items():
                clip = promo / "recordings" / ad["langs"][lang] / f"{scene['clip']}.mp4"
                if not clip.exists():
                    warnings.append(f"{lang}: no recording {clip.name}: the scene is left out in {lang}")
                    continue
                for k, second in enumerate(times, 1):
                    frame = grab(clip, second, work)
                    frame = frame.resize((FRAME_WIDTH, round(FRAME_WIDTH * frame.height / frame.width)), Image.LANCZOS)
                    ad["_frame"] = [frame.width, frame.height]
                    data = webp_bytes(frame)
                    put(f"{lang}-{scene['id']}-{k}", hashed(f"{lang}-{scene['id']}-{k}", data, ".webp"), data)
                scene["frames"][lang] = len(times)

    if not ad.get("icon") or not Path(ad["icon"]).exists():
        fail(f"icon not found: {ad.get('icon')!r} (the app icon, square PNG)")
    icon = Image.open(ad["icon"]).convert("RGBA").resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    data = webp_bytes(icon, 90)
    put("icon", hashed("icon", data, ".webp"), data)
    for lang in ad["text"]:
        badge = Image.open(BADGES.get(lang, BADGES["en"])).convert("RGBA")
        badge = badge.crop(badge.getchannel("A").getbbox())  # the official file has a transparent margin
        badge = badge.resize((BADGE_WIDTH, round(BADGE_WIDTH * badge.height / badge.width)), Image.LANCZOS)
        data = webp_bytes(badge, 90)
        put(f"badge-{lang}", hashed(f"badge-{lang}", data, ".webp"), data)
    logo = {"base": "", "parts": [], "name": ad["logo"].get("name", True)}
    for i, part in enumerate([ad["logo"]["base"], *ad["logo"].get("parts", [])]):
        path = promo / part
        if not path.exists():
            fail(f"logo not found: {path}")
        name, data = logo_file(path, f"logo-{i}")
        put(f"logo-{i}", name, data)
        if i == 0:
            logo["base"] = name
        else:
            logo["parts"].append(name)

    for old in img_dir.iterdir():  # images of earlier builds that no scene uses any more
        if old.name not in files.values():
            old.unlink()
    width, height = ad.get("_frame", [FRAME_WIDTH, 698])
    config = {"app": ad["app"], "play": ad["play"], "default_lang": ad["default_lang"], "text": ad["text"],
              "frame": [width, height], "img": files, "logo": logo,
              "scenes": [{k: s[k] for k in ("type", "id", "seconds", "frames", "tap", "at") if k in s} for s in ad["scenes"]]}
    c = ad["colors"]
    page = (TEMPLATE.read_text(encoding="utf-8")
            .replace("__TITLE__", ad["app"]).replace("__BG__", c["bg"]).replace("__BG2__", c["bg2"])
            .replace("__ACCENT__", c["accent"]).replace("__TEXT__", c["text"]).replace("__SUB__", c["sub"])
            .replace("__RATIO__", f"{width / height:.4f}")
            .replace("/*__CONFIG__*/null", json.dumps(config, ensure_ascii=False).replace("</", "<\\/")))
    (out / "index.html").write_text(page, encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)

    for lang, t in ad["text"].items():
        if len(t["hook"][0]) > TEXT_LIMIT["hook"]:
            warnings.append(f"{lang}: hook over {TEXT_LIMIT['hook']} characters (it wraps into many lines)")
        for s in ad["scenes"]:
            if s["type"] == "feature" and len(t.get(s["id"], [""])[0]) > TEXT_LIMIT["feature"]:
                warnings.append(f"{lang}: '{t[s['id']][0]}' over {TEXT_LIMIT['feature']} characters (two lines max)")
            if s["type"] == "feature" and t.get(s["id"], ["", ""])[1] and t[s["id"]][1] not in t[s["id"]][0]:
                warnings.append(f"{lang}: keyword '{t[s['id']][1]}' is not in '{t[s['id']][0]}'")
    first = ad["scenes"][0]["seconds"] + (ad["scenes"][1]["seconds"] if len(ad["scenes"]) > 2 else 0)
    if first < MANDATORY:
        warnings.append(f"hook + first feature last {first:.1f} s: the mandatory {MANDATORY:.0f} s show the second feature empty-loading")
    total = sum(p.stat().st_size for p in img_dir.iterdir()) + (out / "index.html").stat().st_size
    upfront = sum((img_dir / files[k]).stat().st_size for k in files
                  if k in ("hook", "icon") or k.startswith("badge-") or k.startswith(f"{ad['default_lang']}-{ad['scenes'][1].get('id')}-"))
    for w in warnings:
        print(f"  WARNING {w}")
    print(f"OK: {out / 'index.html'}  ({len(files)} images, {total // 1024} KB; before the ad shows ~{upfront // 1024} KB;"
          f" loop {sum(s['seconds'] for s in ad['scenes']):.1f} s)")
    print(f"Next: ad.py qa {ad_json}")


# --- preview and qa -------------------------------------------------------------------------------

def serve(folder):
    import functools
    import http.server
    import threading
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(Quiet, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def moments(ad):
    """(label, second) of each scene: the hook's question in full, each feature on its last frame, the outro settled."""
    out, start = [], 0.0
    for i, s in enumerate(ad["scenes"]):
        at = {"hook": 2.2, "feature": min(s["seconds"] - 0.3, 2.2), "outro": 2.6}[s["type"]]
        out.append((f"{i:02d}-{s.get('id', s['type'])}", round(start + at, 2)))
        start += s["seconds"]
    return out


def cmd_qa(args):
    from PIL import Image, ImageDraw
    from playwright.sync_api import sync_playwright
    ad_json = Path(args.ad_json).resolve()
    ad = read_json(ad_json)
    folder = ads_root(args.ads_root) / ad["guid"]
    if not (folder / "index.html").exists():
        fail("build first")
    qa = ad_json.parent / "qa"
    qa.mkdir(exist_ok=True)
    server, base = serve(folder)
    sizes = [tuple(int(x) for x in s.split("x")) for s in args.sizes.split(",")]
    problems = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=EDGE if Path(EDGE).exists() else None)
        for lang in ad["text"]:
            for w, h in sizes:
                shots = []
                for label, second in moments(ad):
                    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2)
                    page = ctx.new_page()
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.on("requestfailed", lambda r: errors.append(f"failed {r.url}"))
                    page.goto(f"{base}/index.html?lang={lang}&t={second}", wait_until="networkidle")
                    page.wait_for_timeout(400)
                    path = qa / f"{lang}-{w}x{h}-{label}.png"
                    page.screenshot(path=str(path))
                    href = page.get_attribute("#ctaButton", "href")
                    if href != ad["play"]:
                        problems.append(f"{lang}: #ctaButton goes to {href}")
                    problems += [f"{lang} {label}: {e}" for e in errors]
                    shots.append((label, path))
                    ctx.close()
                thumbs = [Image.open(p).convert("RGB").resize((w // 2, h // 2)) for _, p in shots]
                sheet = Image.new("RGB", (len(thumbs) * (w // 2 + 12) + 12, h // 2 + 44), "#202020")
                draw = ImageDraw.Draw(sheet)
                for i, (thumb, (label, _)) in enumerate(zip(thumbs, shots)):
                    x = 12 + i * (w // 2 + 12)
                    sheet.paste(thumb, (x, 32))
                    draw.text((x, 10), label, fill="#ffffff")
                sheet_path = qa / f"sheet-{lang}-{w}x{h}.jpg"
                sheet.save(sheet_path, quality=85)
                print(f"  {sheet_path}")
        browser.close()
    server.shutdown()
    for p in sorted(set(problems)):
        print(f"  PROBLEM {p}")
    print("OK: review the sheets with Read (texts that wrap badly, the top-right corner empty for the close button,"
          " frames of the right language, the CTA not covering the phone)" if not problems else "Fix the problems above")


def cmd_serve(args):
    import time
    ad = read_json(args.ad_json)
    server, base = serve(ads_root(args.ads_root) / ad["guid"])
    print(f"{base}/index.html?lang={ad['default_lang']}  (Ctrl+C to stop; ?t=<seconds> freezes a moment)")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ads-root", dest="ads_root_global", help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("config"); s.add_argument("--ads-root", required=True)
    s = sub.add_parser("init"); s.add_argument("video_json"); s.add_argument("--guid")
    s.add_argument("--features", type=int, default=MAX_FEATURES); s.add_argument("--force", action="store_true")
    for name in ("build", "qa", "serve"):
        s = sub.add_parser(name); s.add_argument("ad_json"); s.add_argument("--ads-root")
        if name == "qa":
            s.add_argument("--sizes", default="360x780,412x915")
    args = ap.parse_args()
    {"config": cmd_config, "init": cmd_init, "build": cmd_build, "qa": cmd_qa, "serve": cmd_serve}[args.cmd](args)


if __name__ == "__main__":
    main()
