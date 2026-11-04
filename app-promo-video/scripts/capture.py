"""Records the app scenes on a connected Android phone: Maestro drives the app while
adb screenrecord records the screen.

Usage:
    python capture.py <video.json> [--locale es-419] [--scene home,parallel] [--device SERIAL] [--prep] [--app-locale]

--app-locale: the app was put in the recording's language from inside the app (its Languages
screen or a debug link), not with the phone's language; skips the phone language check.

video.json ("capture" section):
    "capture": {
      "app_id": "com.example.app",
      "flows_dir": "<repo>/.maestro/promo",        Maestro flows, one per scene
      "prep": ["parallel_prep.yaml"],              run once per device (not recorded), or with --prep
      "env": { "es-419": {"BIBLE": "RV 60"}, "en-US": {"BIBLE": "KJV"} },   Maestro -e values per language
      "scenes": { "home": "home.yaml",
                  "audio": { "flow": "audio.yaml", "freeze_noise": 0.0003 } }
    }
    A scene is a flow file, or an object with "flow" and options for process_clips.py; with
    "gesture" (a JSON in flows_dir, see gesture.py) a continuous touch gesture plays after the flow,
    still recording: for joystick-like controls a straight Maestro swipe cannot show. Its positions
    are in px of one phone: "gesture_by_model": {"SM-A217M": "quick_search_a21s.json"} picks
    another file by ro.product.model. Tap positions in flows go in the locale's env the same way.

Writes recordings/<locale>/<scene>.raw.mp4 and recordings/<locale>/capture.json (device, system bar
sizes, result of each scene). The phone's app data is never backed up or restored: the flows only
look, or change settings that may stay (see SKILL.md). The only system setting it changes, "stay
awake while charging", is put back at the end.
"""
import argparse
import datetime
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import adb_path, fail, load_video_json, maestro_env, resolve, run, write_json  # noqa: E402

DEVICE_FILE = "/sdcard/promo-rec.mp4"
BIT_RATE = "24000000"
MAX_SECONDS = 170  # screenrecord stops by itself at 180 s


class Phone:
    def __init__(self, adb, serial):
        self.adb, self.serial = adb, serial

    def sh(self, *args, check=False):
        return run([self.adb, "-s", self.serial, "shell", *args], check=check).stdout.strip()

    def adb_cmd(self, *args, check=True):
        return run([self.adb, "-s", self.serial, *args], check=check)


def scene_flow(entry):
    return entry if isinstance(entry, str) else entry["flow"]


def pick_device(adb, wanted):
    lines = run([adb, "devices"]).stdout.splitlines()[1:]
    devices = [l.split("\t")[0] for l in lines if l.endswith("\tdevice")]
    if wanted:
        if wanted not in devices:
            fail(f"Device {wanted} is not connected.")
        return wanted
    if len(devices) != 1:
        fail(f"Expected one connected phone, found {len(devices)}. Connect it by USB, unlock it, or use --device.")
    return devices[0]


def system_bars(phone):
    """Heights in px of the status bar (top) and navigation bar (bottom), from dumpsys window."""
    import re
    dump = phone.sh("dumpsys", "window")
    top = bottom = 0
    # Android 13+: "statusBars ... frame=", Android 12: "type=ITYPE_STATUS_BAR frame="
    for kind, y1, y2 in re.findall(r"(statusBars|navigationBars|ITYPE_STATUS_BAR|ITYPE_NAVIGATION_BAR)\S* "
                                   r"frame=\[-?\d+,(-?\d+)\]\[-?\d+,(-?\d+)\]", dump):
        if kind in ("statusBars", "ITYPE_STATUS_BAR"):
            top = max(top, int(y2) - int(y1))
        else:
            bottom = max(bottom, int(y2) - int(y1))
    return top, bottom


def flow_vars(values):
    """Maestro -e arguments for the values of the recording's language."""
    args = []
    for k, v in (values or {}).items():
        args += ["-e", f"{k}={v}"]
    return args


def unicode_wrapper(flow, values):
    """On Windows, maestro.bat hands its arguments to Java in the ANSI code page: a -e value in
    another script (Hindi) arrives as "???". Those values go in the env block of a small UTF-8
    wrapper flow next to the scene's flow instead. Returns (flow to run, ASCII values, wrapper)."""
    values = dict(values or {})
    other = {k: v for k, v in values.items() if not str(v).isascii()}
    if not other:
        return flow, values, None
    import json
    wrapper = Path(flow).parent / f"_utf8_{Path(flow).stem}.yaml"
    lines = ["appId: any", "---", "- runFlow:", f"    file: {Path(flow).name}", "    env:"]
    lines += [f"      {k}: {json.dumps(str(v), ensure_ascii=False)}" for k, v in values.items()]
    app_id = next((l.split(":", 1)[1].strip() for l in Path(flow).read_text(encoding="utf-8").splitlines()
                   if l.startswith("appId:")), "any")
    lines[0] = f"appId: {app_id}"
    wrapper.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    return wrapper, {}, wrapper


def record_scene(phone, maestro, env, flow, out, gesture=None, values=None):
    """Starts screenrecord, runs the flow (and the gesture), stops screenrecord, pulls the file."""
    phone.sh("rm", "-f", DEVICE_FILE)
    rec = subprocess.Popen([phone.adb, "-s", phone.serial, "shell", "screenrecord", "--bit-rate", BIT_RATE,
                            "--time-limit", str(MAX_SECONDS), DEVICE_FILE],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    started = time.time()
    flow, values, wrapper = unicode_wrapper(flow, values)
    try:
        result = run([maestro, "--device", phone.serial, "test", *flow_vars(values), str(flow)], check=False, env=env)
    finally:
        if wrapper:
            wrapper.unlink(missing_ok=True)
    if result.returncode == 0 and gesture:
        import gesture as gesture_player
        gesture_player.play(phone.adb, phone.serial, gesture)
    seconds = time.time() - started
    time.sleep(1.0)  # the last frame of the flow stays a moment
    phone.sh("pkill", "-INT", "-x", "screenrecord")
    try:
        rec.wait(timeout=10)
    except subprocess.TimeoutExpired:
        rec.kill()
    time.sleep(1.0)  # screenrecord writes the end of the file after the signal
    phone.adb_cmd("pull", DEVICE_FILE, str(out))
    phone.sh("rm", "-f", DEVICE_FILE)
    ok = result.returncode == 0
    if not ok:
        print(result.stdout[-1500:])
    return ok, seconds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_json")
    parser.add_argument("--locale", default=None, help="Defaults to the first locale of video.json")
    parser.add_argument("--scene", default="", help="Comma separated; defaults to all")
    parser.add_argument("--device", default="")
    parser.add_argument("--prep", action="store_true", help="Run the prep flows again")
    parser.add_argument("--app-locale", action="store_true",
                        help="The app's own language was switched inside the app (e.g. Android 12, no per-app "
                             "locale): skip the check that the phone is in the recording's language")
    args = parser.parse_args()

    config = load_video_json(args.video_json)
    cap = config["capture"]
    locale = args.locale or next(iter(config["locales"]))
    flows_dir = resolve(config, cap["flows_dir"])
    scenes = cap["scenes"]
    wanted = [s.strip() for s in args.scene.split(",") if s.strip()] or list(scenes)
    for s in wanted:
        if s not in scenes:
            fail(f"Unknown scene {s}. Scenes: {', '.join(scenes)}")

    adb = adb_path()
    maestro, env = maestro_env()
    phone = Phone(adb, pick_device(adb, args.device))

    # --- Preflight ---------------------------------------------------------------------------
    if "isKeyguardShowing=true" in phone.sh("dumpsys", "window"):
        fail("The phone is locked. Unlock it and run again.")
    if f"package:{cap['app_id']}" not in phone.sh("pm", "list", "packages", cap["app_id"]):
        fail(f"{cap['app_id']} is not installed on the phone.")
    device_locale = phone.sh("getprop", "persist.sys.locale") or phone.sh("getprop", "ro.product.locale")
    if not args.app_locale and device_locale.split("-")[0] != locale.split("-")[0]:
        fail(f"The phone is in {device_locale} and the recording is for {locale}: change the phone's "
             f"language (the app follows it) and run again.")
    top, bottom = system_bars(phone)
    size = phone.sh("wm", "size").split(":")[-1].strip()

    model = phone.sh("getprop", "ro.product.model")
    out_dir = resolve(config, "recordings") / locale
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "capture.json"
    print(f"Phone {phone.serial} ({phone.sh('getprop', 'ro.product.model')}), {size}, "
          f"bars {top}/{bottom} px, {device_locale}")

    stay_on = phone.sh("settings", "get", "global", "stay_on_while_plugged_in")
    phone.sh("svc", "power", "stayon", "usb")
    results = {}
    try:
        # --- Prep flows: once per device ------------------------------------------------------
        marker = out_dir / f"prep-done-{phone.serial}.txt"
        if cap.get("prep") and (args.prep or not marker.exists()):
            for flow in cap["prep"]:
                print(f"Prep: {flow}")
                result = run([maestro, "--device", phone.serial, "test", *flow_vars(cap.get("env", {}).get(locale)),
                              str(flows_dir / flow)], check=False, env=env)
                if result.returncode != 0:
                    print(result.stdout[-1500:])
                    fail(f"Prep flow {flow} failed.")
            marker.write_text(datetime.datetime.now().isoformat(timespec="seconds"), encoding="utf-8")

        # --- Scenes ----------------------------------------------------------------------------
        for scene in wanted:
            out = out_dir / f"{scene}.raw.mp4"
            for attempt in (1, 2):
                print(f"Recording {scene} (attempt {attempt})...")
                entry = scenes[scene]
                gesture = None
                if isinstance(entry, dict) and entry.get("gesture"):
                    # "gesture_by_model": {"SM-A217M": "x_a21s.json"}: positions measured on another phone
                    gesture = flows_dir / entry.get("gesture_by_model", {}).get(model, entry["gesture"])
                ok, seconds = record_scene(phone, maestro, env, flows_dir / scene_flow(entry), out, gesture,
                                           cap.get("env", {}).get(locale))
                if ok:
                    break
            results[scene] = {"ok": ok, "flow": scene_flow(scenes[scene]), "seconds": round(seconds, 1),
                              "file": out.name, "recorded": datetime.datetime.now().isoformat(timespec="seconds")}
            print(f"  {'OK' if ok else 'FAILED'} {scene}: {out}")
    finally:
        phone.sh("settings", "put", "global", "stay_on_while_plugged_in", stay_on or "0")

    previous = {}
    if meta_path.exists():
        import json
        previous = json.loads(meta_path.read_text(encoding="utf-8")).get("scenes", {})
    write_json(meta_path, {
        "device": {"serial": phone.serial, "model": phone.sh("getprop", "ro.product.model"),
                   "size": size, "locale": device_locale, "status_bar": top, "navigation_bar": bottom},
        "scenes": {**previous, **results},
    })
    failed = [s for s, r in results.items() if not r["ok"]]
    if failed:
        fail(f"Scenes that failed twice: {', '.join(failed)}. See the Maestro output above.")


if __name__ == "__main__":
    main()
