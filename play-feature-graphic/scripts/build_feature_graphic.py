"""Build Google Play feature graphics (1024x500) from real app screenshots.

Usage:
    python build_feature_graphic.py <config.json> [--locale es-419]

For every locale in the config it writes, in output_dir:
    feature-graphic-<locale>.png   final image: 1024x500, 24-bit PNG without alpha
    work/<locale>/                 cropped screenshots, logo and the HTML it rendered

Needs Python 3 with Pillow, and Microsoft Edge or Google Chrome (headless render).
See ../SKILL.md for the config format and the design rules.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from string import Template

from PIL import Image

WIDTH, HEIGHT = 1024, 500
SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "templates" / "feature.html"

DEFAULT_PALETTE = {
    "bg": "#12181A",          # canvas background (usually the app's dark background)
    "accent": "#49CC87",      # bright brand color: highlighted chip, logo tone
    "accent_soft": "#82BFAB", # softer accent: emphasized word in the tagline
    "deep": "#1E6B57",        # dark brand tone for the corner glow
    "text": "#EEF3F1",
    "muted": "#9AA8A4",
    "on_accent": "#0D1F17",   # text on the highlighted chip
}
DEFAULT_FONTS = {"title": "Cormorant Garamond", "title_weight": 600, "body": "Inter"}

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/microsoft-edge",
]


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def find_browser(config):
    candidates = [config.get("browser")] + BROWSERS
    for path in candidates:
        if path and Path(path).exists():
            return path
    fail("No Edge or Chrome found. Set \"browser\" in the config to its executable.")


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def crop_screen(src, dst, crop):
    """Removes the status bar (top) and the navigation bar (bottom), in px of the original."""
    image = Image.open(src).convert("RGB")
    top = crop.get("top", 0)
    bottom = crop.get("bottom", 0)
    image.crop((0, top, image.width, image.height - bottom)).save(dst, quality=95)
    return image.width / (image.height - top - bottom)


def prepare_logo(logo, dst):
    """Crops the logo and, if remove_bg is set, turns that solid background transparent."""
    image = Image.open(logo["path"]).convert("RGBA")
    if logo.get("crop"):
        image = image.crop(tuple(logo["crop"]))
    if logo.get("remove_bg"):
        br, bg, bb = hex_to_rgb(logo["remove_bg"])
        tolerance = logo.get("tolerance", 12)
        pixels = image.load()
        for y in range(image.height):
            for x in range(image.width):
                r, g, b, a = pixels[x, y]
                distance = abs(r - br) + abs(g - bg) + abs(b - bb)
                alpha = 0 if distance < tolerance else min(a, distance * 6)
                pixels[x, y] = (r, g, b, alpha)
    image.save(dst)


def render(browser, html_path, png_path):
    url = html_path.resolve().as_uri()
    command = [
        browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", f"--window-size={WIDTH},{HEIGHT}",
        "--virtual-time-budget=6000", "--allow-file-access-from-files",
        f"--screenshot={png_path}", url,
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    if not png_path.exists():
        fail(f"The browser did not write {png_path}")


def build_locale(config, locale, data, browser, output_dir):
    work = output_dir / "work" / locale
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    crop = data.get("screen_crop", config.get("screen_crop", {}))
    screens = data["screens"]
    ratio = None
    for slot in ("center", "left", "right"):
        if slot not in screens:
            fail(f"{locale}: screens.{slot} is missing")
        path = screens[slot]
        if not Path(path).exists():
            fail(f"{locale}: screenshot not found: {path}")
        ratio = crop_screen(path, work / f"{slot}.jpg", crop)

    prepare_logo(config["logo"], work / "logo.png")

    palette = {**DEFAULT_PALETTE, **config.get("palette", {})}
    fonts = {**DEFAULT_FONTS, **config.get("fonts", {})}
    chips = data.get("chips", [])
    hero = data.get("hero_chip", 0)
    chips_html = "\n      ".join(
        f'<span class="chip{" hero" if i == hero else ""}">{chip}</span>' for i, chip in enumerate(chips)
    )

    # Phone sizes keep the screenshot's aspect ratio (after the crop) plus the 7 px bezel.
    center_h, side_h = 457, 393
    values = {
        **{f"c_{k}": v for k, v in palette.items()},
        "font_title": fonts["title"],
        "font_title_weight": fonts["title_weight"],
        "font_body": fonts["body"],
        "font_query": "family=" + fonts["title"].replace(" ", "+") + f":wght@{fonts['title_weight']}"
                      + "&family=" + fonts["body"].replace(" ", "+") + ":wght@400;500;600",
        "lang": locale.split("-")[0],
        "title_html": "<br>".join(data["title_lines"]),
        "title_size": data.get("title_size", 64),
        "tagline_html": data["tagline_html"],
        "chips_html": chips_html,
        "center_w": round((center_h - 14) * ratio + 14),
        "center_h": center_h,
        "side_w": round((side_h - 14) * ratio + 14),
        "side_h": side_h,
    }
    html = Template(TEMPLATE.read_text(encoding="utf-8")).substitute(values)
    html_path = work / "feature.html"
    html_path.write_text(html, encoding="utf-8")

    raw = work / "render.png"
    render(browser, html_path, raw)
    image = Image.open(raw).convert("RGB")  # Play rejects feature graphics with alpha
    if image.size != (WIDTH, HEIGHT):
        fail(f"{locale}: rendered {image.size}, expected {WIDTH}x{HEIGHT}")
    out = output_dir / f"feature-graphic-{locale}.png"
    image.save(out, optimize=True)
    size_mb = out.stat().st_size / 1024 / 1024
    if size_mb > 15:
        fail(f"{locale}: {out} is {size_mb:.1f} MB, the limit is 15 MB")
    print(f"OK {locale}: {out} ({WIDTH}x{HEIGHT}, {out.stat().st_size // 1024} KB)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("--locale", help="Build only this locale")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    os.chdir(config_path.parent)  # relative paths in the config are relative to it
    output_dir = Path(config["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    browser = find_browser(config)

    locales = config["locales"]
    if args.locale:
        if args.locale not in locales:
            fail(f"Locale {args.locale} is not in the config")
        locales = {args.locale: locales[args.locale]}
    for locale, data in locales.items():
        build_locale(config, locale, data, browser, output_dir)


if __name__ == "__main__":
    main()
