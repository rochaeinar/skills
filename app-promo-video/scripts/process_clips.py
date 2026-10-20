"""Cleans the raw recordings: crops the real system bars (the video draws its own clean status
bar), converts the variable frame rate of screenrecord to a constant 30 fps, and finds the parts
where something moves, so the editor never shows Maestro's pauses.

Usage:
    python process_clips.py <video.json> [--locale es-419] [--scene home,parallel]

For each recordings/<locale>/<scene>.raw.mp4 writes:
    <scene>.mp4    cropped, 30 fps, H.264 high quality
    <scene>.proxy.mp4  540 px wide, fast to decode: what render.py previews and stills use (the
                   phone on screen is at most ~510 px wide there); --final uses <scene>.mp4
    <scene>.json   duration and "active" segments [start, end] in seconds (motion, padded)
    <scene>.sheet.jpg  one frame per second with its time: look at it (Read) to choose the part
                   of each scene the video uses ("in"/"out" in video.json)

Options per scene in video.json capture.scenes: "freeze_noise" (default 0.003). Lower it for
scenes whose motion is subtle, like a highlight moving through the text (audio: 0.0003).
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import fail, ffmpeg_paths, load_video_json, resolve, run, write_json  # noqa: E402

FPS = 30
FREEZE_NOISE = 0.003   # frame difference below this counts as "not moving"
FREEZE_MIN = 0.5       # seconds without motion to count as a pause
PAD = 0.25             # seconds kept before and after each motion
MIN_ACTIVE = 0.4       # shorter motions are ignored (cursor blinks, clock ticks)


def duration(ffprobe, path):
    out = run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout
    return float(out.strip())


def contact_sheet(ffmpeg, path, out, total, columns=10):
    """One frame per second, labeled with its time, in a grid."""
    import tempfile
    from PIL import Image, ImageDraw, ImageFont
    with tempfile.TemporaryDirectory() as tmp:
        run([ffmpeg, "-v", "error", "-i", str(path), "-vf", "fps=1,scale=216:-2", f"{tmp}/f%04d.jpg"])
        frames = sorted(Path(tmp).glob("f*.jpg"))
        if not frames:
            return
        w, h = Image.open(frames[0]).size
        rows = (len(frames) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * w, rows * (h + 26)), "#000000")
        draw = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except OSError:
            font = ImageFont.load_default()
        for i, frame in enumerate(frames):
            x, y = (i % columns) * w, (i // columns) * (h + 26)
            sheet.paste(Image.open(frame), (x, y + 26))
            draw.text((x + 6, y + 2), f"{i}s", fill="#FFD54A", font=font)
        sheet.save(out, quality=85)


def active_segments(ffmpeg, path, total, noise=FREEZE_NOISE):
    """Complement of the frozen intervals reported by freezedetect, padded and merged."""
    log = run([ffmpeg, "-hide_banner", "-i", str(path), "-vf",
               f"freezedetect=n={noise}:d={FREEZE_MIN}", "-an", "-f", "null", "-"], check=False).stderr
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", log)]
    if len(ends) < len(starts):
        ends.append(total)
    frozen = list(zip(starts, ends))
    active, cursor = [], 0.0
    for a, b in frozen:
        if a - cursor > 0:
            active.append([cursor, a])
        cursor = b
    if total - cursor > 0:
        active.append([cursor, total])
    padded = [[max(0.0, a - PAD), min(total, b + PAD)] for a, b in active if b - a >= MIN_ACTIVE]
    merged = []
    for seg in padded:
        if merged and seg[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], seg[1])
        else:
            merged.append(seg)
    return [[round(a, 2), round(b, 2)] for a, b in merged]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_json")
    parser.add_argument("--locale", default=None)
    parser.add_argument("--scene", default="")
    args = parser.parse_args()

    config = load_video_json(args.video_json)
    locale = args.locale or next(iter(config["locales"]))
    rec_dir = resolve(config, "recordings") / locale
    meta_path = rec_dir / "capture.json"
    if not meta_path.exists():
        fail(f"No recordings for {locale}: run capture.py first.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    top, bottom = meta["device"]["status_bar"], meta["device"]["navigation_bar"]
    width, height = (int(v) for v in meta["device"]["size"].split("x"))
    wanted = [s.strip() for s in args.scene.split(",") if s.strip()] or list(meta["scenes"])

    ffmpeg, ffprobe = ffmpeg_paths()
    crop_h = height - top - bottom
    crop_h -= crop_h % 2  # H.264 needs even sizes
    for scene in wanted:
        raw = rec_dir / f"{scene}.raw.mp4"
        if not raw.exists():
            fail(f"Missing {raw}")
        out = rec_dir / f"{scene}.mp4"
        run([ffmpeg, "-v", "error", "-y", "-i", str(raw),
             "-vf", f"crop={width}:{crop_h}:0:{top},fps={FPS},format=yuv420p",
             "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-movflags", "+faststart", "-an", str(out)])
        # Proxy: half size, a keyframe every 10 frames and fastdecode, so seeking a clip is cheap.
        run([ffmpeg, "-v", "error", "-y", "-i", str(out), "-vf", "scale=540:-2", "-c:v", "libx264",
             "-preset", "veryfast", "-tune", "fastdecode", "-crf", "20", "-g", "10", "-movflags", "+faststart",
             "-an", str(rec_dir / f"{scene}.proxy.mp4")])
        total = duration(ffprobe, out)
        options = config["capture"]["scenes"].get(scene, {})
        noise = options.get("freeze_noise", FREEZE_NOISE) if isinstance(options, dict) else FREEZE_NOISE
        segments = active_segments(ffmpeg, out, total, noise)
        contact_sheet(ffmpeg, out, rec_dir / f"{scene}.sheet.jpg", total)
        write_json(rec_dir / f"{scene}.json", {
            "scene": scene, "file": out.name, "width": width, "height": crop_h, "fps": FPS,
            "duration": round(total, 2), "freeze_noise": noise, "active": segments,
        })
        print(f"OK {scene}: {total:.1f} s, {len(segments)} active segments "
              f"({sum(b - a for a, b in segments):.1f} s with motion)")


if __name__ == "__main__":
    main()
