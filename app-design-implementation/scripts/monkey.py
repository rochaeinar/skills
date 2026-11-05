#!/usr/bin/env python3
"""Monkey testing: miles de eventos al azar en la app, en paralelo en cada dispositivo conectado.

Encuentra crashes y ANR que ningún flujo automatiza. Correrlo con la app en un escenario de
dobles reales (abrir antes el enlace de prueba), así el mono ejercita la app completa sin hardware.

  python monkey.py com.example.app
  python monkey.py com.example.app --events 20000 --seed 42 --throttle 50
  python monkey.py com.example.app --scenario "myapp-test://scenario?name=connected"

Guarda la salida de monkey y el logcat de cada dispositivo en impl/monkey/<fecha>/, y un
resumen con los crashes (FATAL EXCEPTION / ANR) encontrados. Mismo --seed = misma secuencia,
para reproducir un crash después de corregirlo.
"""
import argparse
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from devices import ADB  # noqa: E402

CRASH_RE = re.compile(r"FATAL EXCEPTION|ANR in |// CRASH: |// NOT RESPONDING: ")


def connected():
    out = subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout
    return [l.split()[0] for l in out.splitlines()[1:] if l.split()[-1:] == ["device"]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package")
    ap.add_argument("--devices", help="seriales separados por coma (por defecto: todos los conectados)")
    ap.add_argument("--events", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=int(datetime.now().strftime("%H%M%S")))
    ap.add_argument("--throttle", type=int, default=30, help="ms entre eventos")
    ap.add_argument("--scenario", help="enlace de prueba que se abre antes (escenario de dobles reales)")
    ap.add_argument("--out", default="impl/monkey")
    a = ap.parse_args()

    devs = a.devices.split(",") if a.devices else connected()
    if not devs:
        print("Sin dispositivos: usar devices.py --wait --interval 600 y seguir programando", file=sys.stderr)
        return 3
    run_dir = Path(a.out) / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    def worker(serial):
        adb = [ADB, "-s", serial]
        safe = serial.replace(":", "_").replace(".", "_")
        subprocess.run(adb + ["logcat", "-c"])
        if a.scenario:
            subprocess.run(adb + ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", a.scenario])
        # Sin barra de notificaciones ni cambio de app: el mono se queda dentro del paquete
        cmd = adb + ["shell", "monkey", "-p", a.package, "-s", str(a.seed), "--throttle", str(a.throttle),
                     "--pct-syskeys", "0", "--pct-appswitch", "5", "--ignore-security-exceptions",
                     "--monitor-native-crashes", "-v", "-v", str(a.events)]
        out = subprocess.run(cmd, capture_output=True, text=True, errors="replace").stdout
        (run_dir / f"monkey-{safe}.txt").write_text(out, encoding="utf-8")
        log = subprocess.run(adb + ["logcat", "-d", "-v", "threadtime"], capture_output=True, text=True,
                             errors="replace").stdout
        (run_dir / f"logcat-{safe}.txt").write_text(log, encoding="utf-8")
        hits = [l.strip() for l in (out + "\n" + log).splitlines() if CRASH_RE.search(l)]
        results[serial] = ("Monkey finished" in out, hits)

    threads = [threading.Thread(target=worker, args=(d,)) for d in devs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = [f"# Monkey {run_dir.name} · paquete {a.package} · seed {a.seed} · {a.events} eventos", "",
             "| Dispositivo | Terminó | Crashes/ANR | Primero |", "|---|---|---|---|"]
    bad = False
    for d in devs:
        finished, hits = results.get(d, (False, ["sin resultado"]))
        bad |= bool(hits) or not finished
        lines.append(f"| {d} | {'sí' if finished else 'no'} | {len(hits)} | {hits[0][:120] if hits else '—'} |")
    summary = "\n".join(lines) + "\n"
    (run_dir / "resumen.md").write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Salidas en {run_dir}. Reproducir con --seed {a.seed}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
