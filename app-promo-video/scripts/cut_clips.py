"""Joins several pieces of one recording into a compact clip, so a scene can show three actions
that were 60 s apart (pick a photo, crop it, attach a PDF) without the waits in between.

    python cut_clips.py video.json --locale es-419 [--cut images_cut]

In video.json:
    "capture": {"cuts": {"es-419": {
        "images_cut": {"from": "images", "ranges": [[44.8, 47.0], [63.0, 70.0, 2.0], [98.5, 103.5]]}
    }}}
Each range is [start, end] or [start, end, speed] in seconds of recordings/<locale>/<from>.mp4
(speed > 1 plays that piece faster: typing, slow dialogs). Writes <name>.mp4, <name>.proxy.mp4,
<name>.json and <name>.sheet.jpg next to it; a scene then uses "clip": "<name>" with in 0 and
out = the duration printed here. Run process_clips.py first (it makes <from>.mp4).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import fail, ffmpeg_paths, load_video_json, resolve, run, write_json  # noqa: E402
from process_clips import FPS, contact_sheet, duration  # noqa: E402


def build(ffmpeg, ffprobe, rec_dir, name, spec):
    src = rec_dir / f"{spec['from']}.mp4"
    if not src.exists():
        fail(f"Missing {src}: run process_clips.py first.")
    parts, labels = [], []
    for i, r in enumerate(spec["ranges"]):
        start, end = r[0], r[1]
        speed = r[2] if len(r) > 2 else 1.0
        if end <= start:
            fail(f"{name}: range {r} ends before it starts")
        parts.append(f"[0:v]trim=start={start}:end={end},setpts=(PTS-STARTPTS)/{speed},fps={FPS}[v{i}]")
        labels.append(f"[v{i}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=1:a=0,format=yuv420p[out]"
    out = rec_dir / f"{name}.mp4"
    run([ffmpeg, "-v", "error", "-y", "-i", str(src), "-filter_complex", graph, "-map", "[out]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-movflags", "+faststart", "-an", str(out)])
    run([ffmpeg, "-v", "error", "-y", "-i", str(out), "-vf", "scale=540:-2", "-c:v", "libx264",
         "-preset", "veryfast", "-tune", "fastdecode", "-crf", "20", "-g", "10", "-movflags", "+faststart",
         "-an", str(rec_dir / f"{name}.proxy.mp4")])
    total = duration(ffprobe, out)
    meta = json.loads((rec_dir / f"{spec['from']}.json").read_text(encoding="utf-8"))
    contact_sheet(ffmpeg, out, rec_dir / f"{name}.sheet.jpg", total)
    write_json(rec_dir / f"{name}.json", {
        "scene": name, "file": out.name, "width": meta["width"], "height": meta["height"], "fps": FPS,
        "duration": round(total, 2), "from": spec["from"], "ranges": spec["ranges"], "active": [[0, round(total, 2)]],
    })
    print(f"OK {name}: {total:.2f} s from {spec['from']} ({len(spec['ranges'])} pieces)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_json")
    parser.add_argument("--locale", default=None)
    parser.add_argument("--cut", default="", help="Comma separated names; defaults to all of the locale")
    args = parser.parse_args()
    config = load_video_json(args.video_json)
    locale = args.locale or next(iter(config["locales"]))
    cuts = config.get("capture", {}).get("cuts", {}).get(locale, {})
    wanted = [c.strip() for c in args.cut.split(",") if c.strip()] or list(cuts)
    if not wanted:
        fail(f"No capture.cuts.{locale} in video.json")
    ffmpeg, ffprobe = ffmpeg_paths()
    rec_dir = resolve(config, "recordings") / locale
    for name in wanted:
        if name not in cuts:
            fail(f"No cut {name} for {locale}")
        build(ffmpeg, ffprobe, rec_dir, name, cuts[name])


if __name__ == "__main__":
    main()
