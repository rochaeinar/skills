"""Generates the AI scenes of the hooks (the first seconds of the video) with fal.ai.

Usage:
    python broll.py <video.json> --stage placeholder|draft|final [--format vertical] [--variant A,B] [--over-budget]

video.json:
    "broll": {
      "draft_model": "fal-ai/veo3.1/lite",  "draft_resolution": "720p",
      "final_model": "fal-ai/veo3.1",       "final_resolution": "1080p",
      "seconds": 4, "negative_prompt": "..."
    }
    "hooks": { "A": {"prompt": "..."}, ... }      the scene of each hook variant (no text in it,
                                                 so every language reuses it)

Three stages, each one only after the previous is approved:
  placeholder  a still image (fal-ai/flux/dev, ~$0.02) of the scene, shown for the whole scene
               with a slow zoom: voice, timing and texts are tuned with the idea of the end result
  draft        the video, cheap (Veo 3.1 Lite 720p), to choose
  final        the video in full quality (Veo 3.1 1080p), the expensive part
render.py uses the best one there is: final, then draft, then placeholder. Before each call the live price (fal pricing API) gives the cost; the run
stops if the spent total plus it would pass video.json "budget_usd" (unless --over-budget).
Everything is cached by model and input in broll-library/video/, listed in library.json, and
the result of each variant is written to broll/<format>.json for render.py.
The key is read from the credential PromoVideo-Fal (or FAL_KEY) and only sent to fal.ai.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import credential, fail, ffmpeg_paths, load_video_json, log_cost, resolve, run, sha, write_json  # noqa: E402

ASPECT = {"vertical": "9:16", "horizontal": "16:9"}
IMAGE_SIZE = {"vertical": "portrait_16_9", "horizontal": "landscape_16_9"}  # flux: 576x1024 / 1024x576
# What fal really bills, from its billing detail (2026-10-19): a video without audio is billed on
# fewer "seconds" than it lasts (Veo 3.1: 4 s -> 2; Veo 3.1 Lite: 12 s -> 7.2), and every image
# counts as at least 1 megapixel. The pricing API only gives the price with audio, so without a
# factor here the full price is used (an upper bound).
SILENT_FACTOR = {"fal-ai/veo3.1": 0.5, "fal-ai/veo3.1/fast": 0.5, "fal-ai/veo3.1/lite": 0.6}
IMAGE_MEGAPIXELS = 1.0
DEFAULT_NEGATIVE = ("text, letters, subtitles, captions, watermark, logo, brand names, readable screen, "
                    "distorted hands, extra fingers, deformed face, face of Jesus, religious caricature")


def http(method, url, key, body=None, timeout=120):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Authorization": f"Key {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        fail(f"fal {method} {url}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:600]}")


def live_price(key, endpoint, unit="seconds"):
    r = http("GET", "https://api.fal.ai/v1/models/pricing?endpoint_id=" + urllib.parse.quote(endpoint, safe=""), key)
    prices = r.get("prices") or fail(f"No price for {endpoint}: the model may be retired. Pick another in video.json broll.")
    p = prices[0]
    if p.get("unit") != unit:
        fail(f"{endpoint} is priced per {p.get('unit')}, not per {unit}: check it before using it.")
    return float(p["unit_price"])


def download(url, target):
    """With curl: it uses the system's certificates (Python's own store may not know fal's CDN)."""
    import shutil
    curl = shutil.which("curl") or fail("curl not found")
    target.parent.mkdir(parents=True, exist_ok=True)
    run([curl, "-sSfL", "--retry", "3", "-o", str(target), url])
    if not target.exists() or target.stat().st_size == 0:
        fail(f"Empty download: {url}")


def spent(config):
    path = resolve(config, "costs.json")
    return json.loads(path.read_text(encoding="utf-8")).get("total_usd", 0.0) if path.exists() else 0.0


def library_add(config, file, info):
    path = resolve(config, "broll-library/library.json")
    lib = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"items": []}
    if not any(i["file"] == file for i in lib["items"]):
        import datetime
        lib["items"].append({"kind": "image" if file.endswith(".jpg") else "video", "file": file, "created": datetime.date.today().isoformat(), **info})
        write_json(path, lib)


def sheet(path, out):
    """Three frames of a clip side by side, to look at it with Read."""
    ffmpeg, _ = ffmpeg_paths()
    run([ffmpeg, "-v", "error", "-y", "-i", str(path), "-vf", "fps=0.9,scale=360:-2,tile=4x1", "-frames:v", "1", str(out)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_json")
    parser.add_argument("--stage", required=True, choices=["placeholder", "draft", "final"])
    parser.add_argument("--format", default="vertical", choices=list(ASPECT))
    parser.add_argument("--variant", default="", help="Comma separated; defaults to all hooks")
    parser.add_argument("--over-budget", action="store_true")
    args = parser.parse_args()

    config = load_video_json(args.video_json)
    hooks = config.get("hooks") or fail("No hooks in video.json")
    wanted = [v.strip() for v in args.variant.split(",") if v.strip()] or list(hooks)
    cfg = config.get("broll", {})
    default_model = {"placeholder": "fal-ai/flux/dev", "draft": "fal-ai/veo3.1/lite", "final": "fal-ai/veo3.1"}
    model = cfg.get(f"{args.stage}_model", default_model[args.stage])
    resolution = cfg.get(f"{args.stage}_resolution", "720p" if args.stage == "draft" else "1080p")
    still = args.stage == "placeholder"
    seconds = int(cfg.get("seconds", 4))
    key = credential("PromoVideo-Fal", "FAL_KEY")

    manifest_path = resolve(config, f"broll/{args.format}.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    jobs = []
    for variant in wanted:
        hook = hooks.get(variant) or fail(f"No hook {variant}")
        if still:
            body = {"prompt": hook["prompt"] + " A single still frame of this scene, photorealistic, no text.",
                    "image_size": IMAGE_SIZE[args.format], "num_images": 1, "enable_safety_checker": True}
        else:
            body = {"prompt": hook["prompt"], "aspect_ratio": ASPECT[args.format], "duration": f"{seconds}s",
                    "resolution": resolution, "generate_audio": False,
                    "negative_prompt": hook.get("negative_prompt", cfg.get("negative_prompt", DEFAULT_NEGATIVE))}
        if hook.get("seed") is not None:
            body["seed"] = hook["seed"]
        h = sha("broll", model, body)
        rel = f"broll-library/image/{h}.jpg" if still else f"broll-library/video/{h}.mp4"
        jobs.append({"variant": variant, "body": body, "rel": rel, "cached": resolve(config, rel).exists()})

    todo = [j for j in jobs if not j["cached"]]
    # Requests submitted (and paid) by a run that did not finish: wait for them instead of paying again.
    pending_path = resolve(config, f"broll/pending-{args.stage}-{args.format}.json")
    pending_saved = json.loads(pending_path.read_text(encoding="utf-8")) if pending_path.exists() else {}
    if todo:
        price = live_price(key, model, "megapixels" if still else "seconds")
        units = IMAGE_MEGAPIXELS if still else seconds * cfg.get("silent_factor", SILENT_FACTOR).get(model, 1.0)
        new = [j for j in todo if j["rel"] not in pending_saved]
        estimate = price * units * len(new)
        budget = float(config.get("budget_usd", 20))
        already = spent(config)
        print(f"{model}: ${price:.3f} per {'megapixel' if still else 's'} (live) x {units:g} x {len(new)} new = ${estimate:.2f}; "
              f"spent so far ${already:.2f} of ${budget:.2f}")
        if already + estimate > budget and not args.over_budget:
            fail(f"This would pass the budget (${already + estimate:.2f} > ${budget:.2f}). Ask the user, then use --over-budget.")
        # Submit every request first (saved before waiting), then wait for all of them.
        for j in todo:
            if j["rel"] in pending_saved:
                j.update(pending_saved[j["rel"]])
                print(f"  {j['variant']}: resuming {j['status_url'].rsplit('/', 2)[-2]}")
                continue
            r = http("POST", f"https://queue.fal.run/{model}", key, j["body"])
            j["status_url"], j["response_url"] = r["status_url"], r["response_url"]
            pending_saved[j["rel"]] = {"status_url": r["status_url"], "response_url": r["response_url"], "logged": False}
            write_json(pending_path, pending_saved)
            print(f"  {j['variant']}: queued {r['request_id']}")
        deadline = time.time() + 900
        pending = list(todo)
        while pending:
            if time.time() > deadline:
                fail("fal took more than 15 minutes; the requests may still finish: run again later (they are not cached yet).")
            time.sleep(8)
            for j in list(pending):
                status = http("GET", j["status_url"], key).get("status")
                if status == "COMPLETED":
                    # Paid once it is done, so the cost is logged before the download.
                    if not pending_saved[j["rel"]].get("logged"):
                        log_cost(config, "fal.ai", f"{model} hook {j['variant']} {args.format} {args.stage}", units,
                                 "megapixels" if still else "seconds", price * units)
                        pending_saved[j["rel"]]["logged"] = True
                        write_json(pending_path, pending_saved)
                    result = http("GET", j["response_url"], key)
                    media = (result.get("images") or [{}])[0] if still else (result.get("video") or {})
                    url = media.get("url") or fail(f"{j['variant']}: no {'image' if still else 'video'} in {result}")
                    download(url, resolve(config, j["rel"]))
                    library_add(config, j["rel"], {"model": model, "stage": args.stage, "format": args.format,
                                                   "prompt": j["body"]["prompt"], "seconds": 0 if still else seconds,
                                                   "usd_max": round(price * units, 3)})
                    del pending_saved[j["rel"]]
                    write_json(pending_path, pending_saved)
                    pending.remove(j)
                    print(f"  {j['variant']}: done")
                elif status not in ("IN_QUEUE", "IN_PROGRESS"):
                    fail(f"{j['variant']}: fal status {status}")

    review = resolve(config, "review/hooks")
    review.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        manifest.setdefault(j["variant"], {})[args.stage] = j["rel"]
        if not still:
            sheet(resolve(config, j["rel"]), review / f"{args.format}-{j['variant']}-{args.stage}.jpg")
    write_json(manifest_path, manifest)
    print(f"OK {manifest_path}; frames to review in {review} (total spent ${spent(config):.2f})")


if __name__ == "__main__":
    main()
