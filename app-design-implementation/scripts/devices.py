#!/usr/bin/env python3
"""Dispositivos Android disponibles para probar, y espera con reintento.

  python devices.py                         lista dispositivos conectados y emuladores (AVD) ya creados
  python devices.py --json                  lo mismo en JSON
  python devices.py --wait --interval 600   espera hasta que haya al menos un dispositivo, revisando
                                            cada 600 s (10 min); termina con código 0 cuando aparece
  python devices.py --wait --min 2          espera hasta tener 2 dispositivos

Nunca crea emuladores ni cambia la configuración de los dispositivos.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime


def sdk_tool(name):
    """Busca una herramienta del SDK de Android en el PATH o en ANDROID_HOME / ANDROID_SDK_ROOT / la ruta por defecto."""
    import os
    found = shutil.which(name)
    if found:
        return found
    sub = {"adb": "platform-tools", "emulator": "emulator"}[name]
    exe = name + (".exe" if os.name == "nt" else "")
    roots = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"),
             os.path.expanduser("~/Library/Android/sdk"), os.path.expanduser("~/Android/Sdk")]
    for r in roots:
        if r and os.path.isfile(os.path.join(r, sub, exe)):
            return os.path.join(r, sub, exe)
    return None


ADB = sdk_tool("adb") or "adb"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def prop(serial, name):
    return run([ADB, "-s", serial, "shell", "getprop", name])


def devices():
    if not sdk_tool("adb"):
        return None
    out = run([ADB, "devices"])
    result = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        d = {"serial": serial, "state": state}
        if state == "device":
            size = run([ADB, "-s", serial, "shell", "wm", "size"]).split(":")[-1].strip()
            density = run([ADB, "-s", serial, "shell", "wm", "density"]).split(":")[-1].strip()
            d.update({
                "model": prop(serial, "ro.product.model"),
                "android": prop(serial, "ro.build.version.release"),
                "sdk": prop(serial, "ro.build.version.sdk"),
                "size": size, "density": density,
                "emulator": serial.startswith("emulator-") or prop(serial, "ro.kernel.qemu") == "1",
            })
            try:
                w, h = (int(x) for x in size.split("x"))
                dpi = int(density) if density.isdigit() else 160
                d["smallest_dp"] = round(min(w, h) * 160 / dpi)
                d["tablet"] = d["smallest_dp"] >= 600
            except ValueError:
                pass
        result.append(d)
    return result


def avds():
    exe = sdk_tool("emulator")
    if not exe:
        return []
    return [l for l in run([exe, "-list-avds"]).splitlines() if l and not l.startswith("INFO")]


def ready(devs):
    return [d for d in (devs or []) if d["state"] == "device"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--interval", type=int, default=600, help="segundos entre intentos (por defecto 600 = 10 min)")
    ap.add_argument("--min", type=int, default=1, help="dispositivos necesarios para dejar de esperar")
    ap.add_argument("--max-hours", type=float, default=24.0, help="tiempo máximo de espera")
    a = ap.parse_args()

    if a.wait:
        deadline = time.time() + a.max_hours * 3600
        while True:
            devs = devices()
            ok = ready(devs)
            stamp = datetime.now().strftime("%H:%M")
            if devs is None:
                print(f"[{stamp}] adb no encontrado", flush=True)
            elif len(ok) >= a.min:
                print(f"[{stamp}] listo: " + ", ".join(f"{d['serial']} ({d.get('model', '')})" for d in ok), flush=True)
                return 0
            else:
                other = [f"{d['serial']}={d['state']}" for d in devs if d["state"] != "device"]
                print(f"[{stamp}] {len(ok)}/{a.min} dispositivos" + (f" ({', '.join(other)})" if other else "")
                      + f"; nuevo intento en {a.interval // 60} min", flush=True)
            if time.time() + a.interval > deadline:
                print("Tiempo máximo de espera alcanzado", flush=True)
                return 2
            time.sleep(a.interval)

    devs = devices()
    data = {"adb": devs is not None, "devices": devs or [], "avds": avds()}
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if devs is None:
        print("adb no encontrado (PATH, ANDROID_HOME o Android/Sdk/platform-tools)")
    elif not devs:
        print("Sin dispositivos conectados")
    for d in data["devices"]:
        if d["state"] != "device":
            print(f"- {d['serial']}: {d['state']} (autorizar en el teléfono / reconectar)")
            continue
        kind = "emulador" if d.get("emulator") else "físico"
        form = "tablet" if d.get("tablet") else "teléfono"
        print(f"- {d['serial']}: {d['model']} · Android {d['android']} (API {d['sdk']}) · {kind} · {form} "
              f"· {d['size']} @ {d['density']} dpi · sw{d.get('smallest_dp', '?')}dp")
    print("Emuladores ya creados (no se crean nuevos): " + (", ".join(data["avds"]) if data["avds"] else "ninguno"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
