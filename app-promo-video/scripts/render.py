"""Renders a promo video with Remotion from video.json.

Usage:
    python render.py <video.json> [--locale es-419] [--format vertical] [--variant A] [--final] [--still SECONDS]

Builds the composition props from:
  - video.json: locales.<locale>.<format>.scenes (texts, clip names and the in/out seconds chosen
    from the contact sheets), logo, transition length;
  - the app's feature-graphic config ("app_config"): palette;
  - audio/<locale>-<format>.json from audio.py, when it exists: the voice of each scene (a scene
    lasts as long as its sentence needs; the clip slows down to cover it), the captions, the
    music (lower while the voice speaks) and the transition sound.
Every asset path is relative to the folder of video.json.

Writes output/promo-<locale>-<format>[-<variant>].mp4 with --final, or ...-preview.mp4 for a
preview (never the final's name), with music, loudness normalized to
-14 LUFS (TikTok / YouTube), and the props next to it. While the video is being tuned only that
version is rendered, as a quick 540p preview (--scale, faster encoding: the recordings, audio
and layout are the same, only fewer pixels are drawn); --final renders in full 1080p and also -voz.mp4 (voice only, to
pick a song in TikTok's own library), and refuses while the hook still has a placeholder or a
draft AI scene. --still renders one frame (PNG) at that second instead, to check a layout quickly.
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import fail, ffmpeg_paths, load_video_json, resolve, run, write_json  # noqa: E402

REMOTION_DIR = Path(__file__).resolve().parent.parent / "remotion"
FORMATS = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
FPS = 30
VOICE_OFFSET = 5      # frames from the start of a scene to its voice
VOICE_TAIL = 8        # frames of silence after the voice, before the next transition starts
CAPTION_WORDS = 4     # words per caption at most
FISH_FRAMES = 27      # the green fish swimming into the logo
FISH_HOLD = 24        # the whole logo, still, before the end
LOUDNESS = {"I": -14.0, "TP": -1.5, "LRA": 11.0}


def theme_from(config):
    palette = {}
    if config.get("app_config"):
        app = json.loads(resolve(config, config["app_config"]).read_text(encoding="utf-8"))
        palette = app.get("palette", {})
    p = {**palette, **config.get("palette", {})}
    return {
        "bg": p.get("bg", "#12181A"), "accent": p.get("accent", "#49CC87"),
        "accentSoft": p.get("accent_soft", "#82BFAB"), "deep": p.get("deep", "#1E6B57"),
        "text": p.get("text", "#EEF3F1"), "muted": p.get("muted", "#9AA8A4"),
        "onAccent": p.get("on_accent", "#0D1F17"), "screenBg": p.get("screen_bg", p.get("bg", "#12181A")),
    }


def captions_for(words, start_frame):
    """Splits a sentence into captions of a few words (breaking after punctuation)."""
    chunks, current = [], []
    for w in words:
        current.append(w)
        if len(current) >= CAPTION_WORDS or w["text"][-1:] in ",.;:?!":
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    # A word alone ("Drive.") joins the previous caption instead of flashing by itself.
    merged = []
    for chunk in chunks:
        if len(chunk) == 1 and merged and len(merged[-1]) <= CAPTION_WORDS:
            merged[-1] = merged[-1] + chunk
        else:
            merged.append(chunk)
    chunks = merged
    out = []
    for chunk in chunks:
        out.append({
            "from": start_frame + int(chunk[0]["start"] * FPS),
            "to": start_frame + math.ceil(chunk[-1]["end"] * FPS) + 4,
            "words": [{"text": w["text"], "from": start_frame + int(w["start"] * FPS),
                       "to": start_frame + math.ceil(w["end"] * FPS)} for w in chunk],
        })
    # A caption ends where the next one starts, so two never overlap.
    for a, b in zip(out, out[1:]):
        a["to"] = min(a["to"], b["from"])
    return out


def script_scenes(config, locale, fmt, variant=None):
    """The scenes of the script; with a hook variant, the hook takes that variant's text and voice
    (locales.<locale>.hook_variants) and its AI scene (broll/<format>.json: the final video, else
    the draft, else the placeholder image)."""
    loc = config["locales"].get(locale) or fail(f"No locale {locale} in video.json")
    script = loc.get(fmt) or fail(f"No {fmt} script for {locale} in video.json")
    scenes = [dict(s) for s in script["scenes"]]
    if variant:
        texts = (loc.get("hook_variants") or {}).get(variant) or fail(f"No hook variant {variant} for {locale}")
        broll_path = resolve(config, f"broll/{fmt}.json")
        broll = json.loads(broll_path.read_text(encoding="utf-8")).get(variant, {}) if broll_path.exists() else {}
        for s in scenes:
            if s["type"] == "hook":
                s.update({"text": texts["text"], "keyword": texts.get("keyword"), "voice": texts.get("voice", texts["text"])})
                for stage in ("final", "draft", "placeholder"):
                    if broll.get(stage):
                        s["broll"], s["brollStage"] = broll[stage], stage
                        break
    return scenes


def audio_name(locale, fmt, variant=None):
    return f"audio/{locale}-{fmt}" + (f"-{variant}" if variant else "") + ".json"


def use_proxies(config, props):
    """Previews and stills read the 540 px proxies of the recordings (process_clips.py), much
    faster to decode; the final render reads the full recordings."""
    for s in props["scenes"]:
        clip = s.get("clip")
        if clip and clip.endswith(".mp4") and not clip.endswith(".proxy.mp4"):
            proxy = clip[:-4] + ".proxy.mp4"
            if resolve(config, proxy).exists():
                s["clip"] = proxy
    return props


def build_props(config, locale, fmt, manifest=None, variant=None):
    script = {"scenes": script_scenes(config, locale, fmt, variant)}
    if manifest is None:
        path = resolve(config, audio_name(locale, fmt, variant))
        manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    voices = manifest.get("voice") or []
    width, height = FORMATS[fmt]
    transition = config.get("transition_frames", 12)
    rec = f"recordings/{locale}"
    scenes = []
    for i, s in enumerate(script["scenes"]):
        voice = voices[i] if i < len(voices) else None
        need = (VOICE_OFFSET + math.ceil(voice["seconds"] * FPS) + VOICE_TAIL + transition) if voice else 0
        if s["type"] == "feature":
            rate = s.get("rate", 1.0)
            span = s["out"] - s["in"]
            frames = max(round(span / rate * FPS), need)
            rate = span / (frames / FPS)  # slower when the voice needs more time
            scenes.append({"type": "feature", "frames": frames, "text": s["text"], "keyword": s.get("keyword"),
                           "clip": f"{rec}/{s['clip']}.mp4", "clipFrom": s["in"], "clipTo": s["out"], "rate": rate})
        elif s["type"] == "hook":
            hook = {"type": "hook", "frames": max(round(s["seconds"] * FPS), need), "text": s["text"], "keyword": s.get("keyword")}
            if s.get("clip"):
                hook.update({"clip": f"{rec}/{s['clip']}.mp4", "clipFrom": s["in"], "clipTo": s["out"]})
            if s.get("broll"):
                hook["broll"], hook["brollStage"] = s["broll"], s.get("brollStage", "final")
            scenes.append(hook)
        elif s["type"] == "outro":
            # The green fish swims in when the voice has said the call to action (as when the app opens).
            fish_from = (VOICE_OFFSET + math.ceil(voice["seconds"] * FPS) + 4) if voice else 45
            frames = max(round(s["seconds"] * FPS), need - transition, fish_from + FISH_FRAMES + FISH_HOLD)
            scenes.append({"type": "outro", "frames": frames, "text": s["text"], "tagline": s.get("tagline"),
                           "fishFrom": fish_from})
        else:
            fail(f"Unknown scene type {s['type']}")
    for s in scenes:
        if "clip" in s and not resolve(config, s["clip"]).exists():
            fail(f"Missing recording {s['clip']}: run capture.py and process_clips.py")

    # Absolute timing: the transitions overlap the scenes.
    starts, t = [], 0
    for i, s in enumerate(scenes):
        starts.append(t)
        t += s["frames"] - transition
    voice_tracks, captions = [], []
    for i, voice in enumerate(voices[:len(scenes)]):
        if not voice:
            continue
        begin = starts[i] + VOICE_OFFSET
        voice_tracks.append({"src": voice["file"], "from": begin, "frames": math.ceil(voice["seconds"] * FPS) + 2})
        # The hook and the outro already show what the voice says in big letters (and the
        # outro's button sits where the captions go): captions only where they add something.
        source = script["scenes"][i]
        if source.get("captions", source["type"] == "feature"):
            captions += captions_for(voice["words"], begin)
    sfx = []
    if manifest.get("sfx", {}).get("transition"):
        sfx = [{"src": manifest["sfx"]["transition"], "from": max(0, starts[i] - 3), "volume": 0.35}
               for i in range(1, len(scenes))]
        sfx += [{"src": manifest["sfx"]["transition"], "from": starts[i] + s["fishFrom"], "volume": 0.22}
                for i, s in enumerate(scenes) if s.get("fishFrom") is not None]
    music = None
    if manifest.get("music"):
        m = config.get("music", {})
        music = {"src": manifest["music"]["file"], "volume": m.get("volume", 0.85), "ducked": m.get("ducked", 0.38)}
    return {
        "width": width, "height": height, "fps": FPS,
        "appName": config["app_name"], "logo": config.get("logo", "assets/logo.png"),
        "logoIncludesName": bool(config.get("logo_includes_name", False)),
        "logoParts": config.get("logo_parts"),
        "theme": theme_from(config), "transitionFrames": transition,
        "scenes": scenes, "voice": voice_tracks, "captions": captions, "sfx": sfx, "music": music,
    }


def promo_frames(props):
    return sum(s["frames"] for s in props["scenes"]) - max(0, len(props["scenes"]) - 1) * props["transitionFrames"]


def promo_seconds(props):
    return promo_frames(props) / props["fps"]


def stage_public(config, props, name):
    """A public dir with only the files the props use (hard links, so no copy): Remotion copies
    the whole public dir on every render, and the promo folder has every raw recording."""
    import os
    stage = resolve(config, ".render") / name
    if stage.exists():
        shutil.rmtree(stage)
    used = {props["logo"]} | {s["clip"] for s in props["scenes"] if s.get("clip")}
    used |= {s["broll"] for s in props["scenes"] if s.get("broll")}
    if props.get("logoParts"):
        used |= set(props["logoParts"].values())
    used |= {v["src"] for v in props["voice"]} | {x["src"] for x in props["sfx"]}
    if props.get("music"):
        used.add(props["music"]["src"])
    for rel in used:
        src, dst = resolve(config, rel), stage / rel
        if not src.exists():
            fail(f"Missing {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
    return stage


def normalize_loudness(source, target):
    """Two-pass EBU R128 loudnorm of the audio, the video stream copied as it is."""
    ffmpeg, _ = ffmpeg_paths()
    spec = f"I={LOUDNESS['I']}:TP={LOUDNESS['TP']}:LRA={LOUDNESS['LRA']}"
    log = run([ffmpeg, "-hide_banner", "-i", str(source), "-af", f"loudnorm={spec}:print_format=json",
               "-vn", "-f", "null", "-"], check=False).stderr
    m = json.loads(log[log.rindex("{"):log.rindex("}") + 1])
    second = (f"loudnorm={spec}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    run([ffmpeg, "-v", "error", "-y", "-i", str(source), "-c:v", "copy", "-af", second,
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(target)])
    return float(m["input_i"])


def remotion(config, props, name, out_dir, still=None, final=False):
    props_path = out_dir / f"{name}.props.json"
    write_json(props_path, props)
    if not (REMOTION_DIR / "node_modules").exists():
        run(["npm", "install", "--no-audit", "--no-fund"], cwd=REMOTION_DIR, shell=True)
    npx = shutil.which("npx") or fail("npx not found (Node.js)")
    common = ["--props", str(props_path), "--public-dir", str(stage_public(config, props, name))]
    if still is not None:
        out = out_dir / f"{name}-{still:g}s.png"
        command = [npx, "remotion", "still", "src/index.ts", "Promo", str(out), "--frame", str(round(still * FPS))] + common
    else:
        out = out_dir / f"{name}.raw.mp4"
        # Preview: half size (540p; Remotion needs whole dimensions, 2/3 gives 720.036) and a fast x264
        # preset; final: full size and quality.
        quality = (["--crf", "16"] if final else ["--scale", "0.5", "--crf", "23", "--x264-preset", "veryfast"])
        command = [npx, "remotion", "render", "src/index.ts", "Promo", str(out), "--codec", "h264", *quality,
                   "--pixel-format", "yuv420p", "--audio-codec", "aac", "--audio-bitrate", "320k", "--concurrency", "50%"] + common
    if run(command, check=False, capture=False, cwd=REMOTION_DIR).returncode != 0:
        fail("Remotion render failed (see the output above).")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_json")
    parser.add_argument("--locale", default=None)
    parser.add_argument("--format", default="vertical", choices=list(FORMATS))
    parser.add_argument("--final", action="store_true",
                        help="The approved video: also the voice-only version; the AI scenes must be final")
    parser.add_argument("--variant", default=None, help="Hook variant (locales.<locale>.hook_variants)")
    parser.add_argument("--still", type=float, default=None)
    args = parser.parse_args()

    config = load_video_json(args.video_json)
    locale = args.locale or next(iter(config["locales"]))
    props = build_props(config, locale, args.format, variant=args.variant)
    if not args.final:
        use_proxies(config, props)
    out_dir = resolve(config, "output")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"promo-{locale}-{args.format}" + (f"-{args.variant}" if args.variant else "")

    if args.still is not None:
        print(f"OK {remotion(config, props, base, out_dir, args.still)}")
        return
    if args.final:
        unfinished = [s.get("brollStage") for s in props["scenes"] if s.get("brollStage") not in (None, "final")]
        if unfinished:
            fail(f"The hook's AI scene is still a {unfinished[0]}: generate it with broll.py --stage final first.")
    # A preview never takes the final's name: it would overwrite the approved 1080p video.
    variants = [(base if args.final else base + "-preview", props)]
    if args.final and props.get("voice"):
        variants.append((base + "-voz", {**props, "music": None}))
    for name, p in variants:
        raw = remotion(config, p, name, out_dir, final=args.final)
        final = out_dir / f"{name}.mp4"
        if p.get("voice") or p.get("music"):
            measured = normalize_loudness(raw, final)
            raw.unlink()
            print(f"OK {final} ({promo_seconds(p):.1f} s, {'1080p final' if args.final else '540p preview'}, "
                  f"loudness {measured:.1f} -> {LOUDNESS['I']} LUFS)")
        else:
            raw.replace(final)
            print(f"OK {final} ({promo_seconds(p):.1f} s, no audio)")


if __name__ == "__main__":
    main()
