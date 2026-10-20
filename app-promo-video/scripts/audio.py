"""Generates the audio of a promo video with ElevenLabs: the voice of each scene (with the time of
each word, for the captions), the music and the transition sound. Everything is cached by what
it depends on, so changing one sentence only pays for that sentence.

Usage:
    python audio.py <video.json> [--locale es-419] [--format vertical] [--variant A] [--only voice,music,sfx] [--force]

video.json:
    locales.<locale>.voice           {"voice_id", "model_id", "language_code", "settings"?}
    locales.<locale>.<format>.scenes[i].voice   the sentence Nico says in that scene (optional)
    music   {"prompt", "model_id"?}   instrumental, composed as long as the video (rounded up to the
            second, so the variants of a format share it) and asked to END with a resolved final
            chord on the logo: it finishes like a real piece instead of being cut (Soundtrack only
            adds a soft 1.5 s fade as a safety net)
    sfx     {"transition": "soft whoosh..."}   optional

Writes:
    cache/voice/<hash>.mp3 + .json        one sentence and its words with start/end seconds
    broll-library/music/<hash>.mp3, broll-library/sfx/<hash>.mp3, broll-library/library.json
                                          reusable in other videos and languages (no text inside)
    audio/<locale>-<format>[-<variant>].json   what render.py uses: voice of each scene, music, sfx
The key is never sent anywhere but api.elevenlabs.io.
"""
import argparse
import base64
import json
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import credential, fail, load_video_json, log_cost, resolve, sha, write_json  # noqa: E402

API = "https://api.elevenlabs.io"
CREDENTIAL = "PromoVideo-ElevenLabs"


def call(key, method, path, body=None, raw=False, timeout=300):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(API + path, data=data, method=method,
                                     headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as e:
        fail(f"ElevenLabs {method} {path}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:500]}")
    return payload if raw else json.loads(payload.decode("utf-8"))


def credits(key):
    s = call(key, "GET", "/v1/user/subscription")
    return s["character_count"], s["character_limit"], s.get("tier")


def words_from_alignment(alignment):
    """Groups the characters of the alignment into words with their start and end seconds."""
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    words, current, w_start, w_end = [], "", None, None
    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            if current:
                words.append({"text": current, "start": round(w_start, 3), "end": round(w_end, 3)})
            current, w_start = "", None
            continue
        if w_start is None:
            w_start = s
        current += c
        w_end = e
    if current:
        words.append({"text": current, "start": round(w_start, 3), "end": round(w_end, 3)})
    return words


MUSIC_ATTEMPTS = 3


def loudness_profile(path, seconds):
    """Mean volume (dB) of each of the last `seconds` seconds."""
    from common import ffmpeg_paths, run
    ffmpeg, _ = ffmpeg_paths()
    total = mp3_seconds(path)
    out = []
    for i in range(seconds, 0, -1):
        log = run([ffmpeg, "-hide_banner", "-ss", f"{max(0.0, total - i):.3f}", "-t", "1", "-i", str(path),
                   "-af", "volumedetect", "-f", "null", "-"], check=False).stderr
        import re
        m = re.search(r"mean_volume: (-?[\d.]+)", log)
        out.append(float(m.group(1)) if m else -91.0)
    return out


def ending_ok(path):
    """The music keeps its level until ~3 s before the end and then dies away: the ending is on the
    logo, not during the last scenes. Compares the seconds before the ending with the body."""
    p = loudness_profile(path, 12)            # p[-1] is the last second
    body = sorted(p[:6])[3]                   # typical level 12..6 s before the end
    before_ending = max(p[-5], p[-4])         # 5..3 s before the end
    ok = before_ending >= body - 6 and p[-1] <= body - 10
    return ok, " ".join(f"{v:.0f}" for v in p)


def mp3_seconds(path):
    from common import ffmpeg_paths, run
    _, ffprobe = ffmpeg_paths()
    out = run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout
    return float(out.strip())


def library_add(config, kind, file, info):
    path = resolve(config, "broll-library/library.json")
    lib = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"items": []}
    if not any(i["file"] == file for i in lib["items"]):
        import datetime
        lib["items"].append({"kind": kind, "file": file, "created": datetime.date.today().isoformat(), **info})
        write_json(path, lib)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_json")
    parser.add_argument("--locale", default=None)
    parser.add_argument("--format", default="vertical")
    parser.add_argument("--variant", default=None, help="Hook variant: its text replaces the hook's")
    parser.add_argument("--only", default="voice,music,sfx")
    parser.add_argument("--force", action="store_true", help="Regenerate even if cached")
    args = parser.parse_args()
    only = set(args.only.split(","))

    config = load_video_json(args.video_json)
    locale = args.locale or next(iter(config["locales"]))
    loc = config["locales"][locale]
    import render
    scenes = render.script_scenes(config, locale, args.format, args.variant)
    voice = loc.get("voice") or fail(f"No voice for {locale} in video.json")
    key = credential(CREDENTIAL, "ELEVENLABS_API_KEY")
    used_before, limit, tier = credits(key)
    if tier in (None, "free"):
        fail("ElevenLabs is on the free plan: its audio needs attribution and is not for commercial use.")
    print(f"ElevenLabs {tier}: {used_before}/{limit} credits used")

    manifest_path = resolve(config, render.audio_name(locale, args.format, args.variant))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.update({"locale": locale, "format": args.format})

    # --- Voice: one request per sentence, with the neighbours as context -----------------------
    if "voice" in only:
        texts = [s.get("voice") for s in scenes]
        planned = sum(len(t) for t in texts if t)
        if limit - used_before < planned * 2:
            fail(f"Not enough ElevenLabs credits: {limit - used_before} left, the voice needs ~{planned}.")
        voices = []
        for i, text in enumerate(texts):
            if not text:
                voices.append(None)
                continue
            previous = next((t for t in reversed(texts[:i]) if t), None)
            following = next((t for t in texts[i + 1:] if t), None)
            body = {"text": text, "model_id": voice.get("model_id", "eleven_v4"),
                    "language_code": voice.get("language_code"), "previous_text": previous, "next_text": following}
            if voice.get("settings"):
                body["voice_settings"] = voice["settings"]
            body = {k: v for k, v in body.items() if v is not None}
            h = sha("voice", voice["voice_id"], body)
            mp3 = resolve(config, f"cache/voice/{h}.mp3")
            meta = mp3.with_suffix(".json")
            if args.force or not (mp3.exists() and meta.exists()):
                print(f"  voice {i}: generating ({len(text)} chars) {text!r}")
                r = call(key, "POST", f"/v1/text-to-speech/{voice['voice_id']}/with-timestamps?output_format=mp3_44100_128", body)
                mp3.parent.mkdir(parents=True, exist_ok=True)
                mp3.write_bytes(base64.b64decode(r["audio_base64"]))
                words = words_from_alignment(r.get("alignment") or r["normalized_alignment"])
                write_json(meta, {"text": text, "voice_id": voice["voice_id"], "words": words})
                log_cost(config, "elevenlabs", f"voice {locale} scene {i}", len(text), "credits")
            else:
                print(f"  voice {i}: cached")
            info = json.loads(meta.read_text(encoding="utf-8"))
            voices.append({"file": f"cache/voice/{h}.mp3", "seconds": round(mp3_seconds(mp3), 3), "words": info["words"]})
        manifest["voice"] = voices
        write_json(manifest_path, manifest)

    # --- Music: composed for the length of the video, with a real ending -------------------------
    if "music" in only and config.get("music"):
        props = render.build_props(config, locale, args.format, manifest, args.variant)
        total = render.promo_seconds(props)
        music = config["music"]
        length_ms = int(math.ceil(total)) * 1000
        ending = (" Keep the full arrangement and energy until three seconds before the end; only the last three "
                  "seconds are the ending: a warm, fully resolved final chord that rings out softly to silence at the "
                  "very end. A natural ending, never cut off, and no early fade-out.")
        body = {"prompt": music["prompt"] + ending, "music_length_ms": length_ms,
                "model_id": music.get("model_id", "music_v1"), "force_instrumental": True}
        rel = mp3 = None
        for attempt in range(1, MUSIC_ATTEMPTS + 1):
            h = sha("music", body, attempt)
            rel = f"broll-library/music/{h}.mp3"
            mp3 = resolve(config, rel)
            if args.force or not mp3.exists():
                print(f"  music: generating {length_ms / 1000:.1f} s ({body['model_id']}), attempt {attempt}")
                data = call(key, "POST", "/v1/music?output_format=mp3_44100_128", body, raw=True, timeout=600)
                mp3.parent.mkdir(parents=True, exist_ok=True)
                mp3.write_bytes(data)
                log_cost(config, "elevenlabs", f"music {length_ms} ms", length_ms, "ms")
            else:
                print(f"  music: cached (attempt {attempt})")
            ok, profile = ending_ok(mp3)
            print(f"    ending {'OK' if ok else 'too early'}: {profile}")
            if ok:
                break
        else:
            print(f"  WARNING: none of {MUSIC_ATTEMPTS} attempts keeps the music up to the end; using the last one. "
                  "Listen to it, or change the prompt.")
        library_add(config, "music", rel, {"prompt": body["prompt"], "model_id": body["model_id"],
                                           "seconds": length_ms / 1000, "license": f"ElevenLabs {tier} (commercial, no attribution)"})
        manifest["music"] = {"file": rel, "seconds": round(mp3_seconds(mp3), 3)}
        write_json(manifest_path, manifest)

    # --- Transition sound -------------------------------------------------------------------------
    if "sfx" in only and config.get("sfx", {}).get("transition"):
        body = {"text": config["sfx"]["transition"], "duration_seconds": config["sfx"].get("seconds", 1.0),
                "prompt_influence": 0.6, "model_id": "eleven_text_to_sound_v2"}
        h = sha("sfx", body)
        rel = f"broll-library/sfx/{h}.mp3"
        mp3 = resolve(config, rel)
        if args.force or not mp3.exists():
            print("  sfx: generating transition")
            data = call(key, "POST", "/v1/sound-generation?output_format=mp3_44100_128", body, raw=True)
            mp3.parent.mkdir(parents=True, exist_ok=True)
            mp3.write_bytes(data)
            log_cost(config, "elevenlabs", "sfx transition", body["duration_seconds"], "seconds")
            library_add(config, "sfx", rel, {"prompt": body["text"], "license": f"ElevenLabs {tier}"})
        else:
            print("  sfx: cached")
        manifest["sfx"] = {"transition": rel}
        write_json(manifest_path, manifest)

    used_after, _, _ = credits(key)
    print(f"OK {manifest_path} (credits used now {used_after}/{limit}, +{used_after - used_before})")


if __name__ == "__main__":
    main()
