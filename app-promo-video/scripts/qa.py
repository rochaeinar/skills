"""Checks a rendered promo video before it is delivered.

Usage:
    python qa.py <video.mp4> [--format vertical|horizontal]

Checks: size and frame rate of the format, H.264 + AAC, duration (TikTok 9-60 s, YouTube/Play
30 s - 2 min), loudness (-14 LUFS +-1, true peak <= -1 dBTP), no black frames and no frozen
picture longer than 1.5 s (an editing pause), audio not cut off at the end (the last 0.5 s
quieter than the 3 s before). Writes <video>.qa.jpg: the first frame, 1.5 s (the hook), and one
frame every few seconds, with the platform's safe zones drawn over the vertical ones, to look at
with Read. Exits 1 if a check fails.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ffmpeg_paths, run  # noqa: E402

SPEC = {"vertical": {"size": (1080, 1920), "seconds": (9, 60)},
        "horizontal": {"size": (1920, 1080), "seconds": (30, 120)}}


def probe(ffprobe, path):
    out = run([ffprobe, "-v", "error", "-show_entries",
               "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration", "-of", "json", str(path)]).stdout
    return json.loads(out)


def mean_db(ffmpeg, path, start, length):
    log = run([ffmpeg, "-hide_banner", "-ss", f"{max(0, start):.2f}", "-t", f"{length:.2f}", "-i", str(path),
               "-vn", "-af", "volumedetect", "-f", "null", "-"], check=False).stderr
    m = re.search(r"mean_volume: (-?[\d.]+)", log)
    return float(m.group(1)) if m else -91.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--format", default=None, choices=list(SPEC))
    args = parser.parse_args()
    path = Path(args.video)
    ffmpeg, ffprobe = ffmpeg_paths()
    info = probe(ffprobe, path)
    streams = {s["codec_type"]: s for s in info["streams"]}
    v, a = streams.get("video", {}), streams.get("audio")
    fmt = args.format or ("vertical" if v.get("height", 0) > v.get("width", 0) else "horizontal")
    spec = SPEC[fmt]
    duration = float(info["format"]["duration"])
    results = []

    def check(name, ok, detail):
        results.append((ok, name, detail))

    check("tamaño", (v.get("width"), v.get("height")) == spec["size"], f"{v.get('width')}x{v.get('height')} (esperado {spec['size'][0]}x{spec['size'][1]})")
    num, den = (int(x) for x in v.get("r_frame_rate", "0/1").split("/"))
    check("fps", den and abs(num / den - 30) < 0.01, f"{num / den if den else 0:.2f}")
    check("códecs", v.get("codec_name") == "h264" and a and a.get("codec_name") == "aac",
          f"{v.get('codec_name')} / {a.get('codec_name') if a else 'sin audio'}")
    lo, hi = spec["seconds"]
    check("duración", lo <= duration <= hi, f"{duration:.1f} s (rango {lo}-{hi} s)")

    if a:
        log = run([ffmpeg, "-hide_banner", "-i", str(path), "-af", "loudnorm=print_format=json", "-vn", "-f", "null", "-"],
                  check=False).stderr
        m = json.loads(log[log.rindex("{"):log.rindex("}") + 1])
        i, tp = float(m["input_i"]), float(m["input_tp"])
        check("volumen", abs(i + 14) <= 1.0 and tp <= -1.0, f"{i:.1f} LUFS, pico {tp:.1f} dBTP")
        tail, before = mean_db(ffmpeg, path, duration - 0.5, 0.5), mean_db(ffmpeg, path, duration - 3.5, 3.0)
        check("final del audio", tail <= before - 3, f"últimos 0,5 s {tail:.0f} dB vs. 3 s antes {before:.0f} dB")

    log = run([ffmpeg, "-hide_banner", "-i", str(path), "-vf", "blackdetect=d=0.2:pix_th=0.05,freezedetect=n=0.001:d=1.5",
               "-an", "-f", "null", "-"], check=False).stderr
    blacks = re.findall(r"black_start:([\d.]+)", log)
    freezes = re.findall(r"freeze_start: ([\d.]+)", log)
    check("sin cuadros negros", not blacks, ", ".join(f"{float(t):.1f} s" for t in blacks) or "ninguno")
    # The outro holds a still logo on purpose: freezes in its last 3 s are fine.
    freezes = [t for t in freezes if float(t) < duration - 3]
    check("sin pausas congeladas", not freezes, ", ".join(f"{float(t):.1f} s" for t in freezes) or "ninguna")

    # Frames to look at: 0 s, the hook at 1.5 s, then every few seconds; safe zones on vertical.
    times = [0.05, 1.5] + [t for t in range(4, int(duration), max(3, int(duration // 14)))]
    sheet = path.with_suffix(".qa.jpg")
    draw = ""
    if fmt == "vertical":
        draw = (",drawbox=y=0:w=iw:h=ih*0.08:color=red@0.7:t=5,drawbox=y=ih*0.80:w=iw:h=ih*0.20:color=red@0.7:t=5,"
                "drawbox=x=iw*0.86:y=ih*0.35:w=iw*0.14:h=ih*0.45:color=red@0.7:t=5")
    select = "+".join(f"lt(prev_t\\,{t})*gte(t\\,{t})" for t in times)
    run([ffmpeg, "-v", "error", "-y", "-i", str(path), "-vf",
         f"select='{select}'{draw},scale={360 if fmt == 'vertical' else 480}:-1,tile={min(8, len(times))}x{(len(times) + 7) // 8}",
         "-frames:v", "1", "-fps_mode", "vfr", str(sheet)])

    failed = 0
    for ok, name, detail in results:
        print(f"{'OK   ' if ok else 'FALLA'} {name}: {detail}")
        failed += not ok
    print(f"Cuadros para revisar: {sheet}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
