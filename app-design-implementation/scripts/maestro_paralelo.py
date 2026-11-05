#!/usr/bin/env python3
"""Corre flujos Maestro en paralelo en todos los dispositivos conectados.

Reparte los flujos (archivos .yaml fuera de las carpetas de subflujos) entre los dispositivos
y lanza un proceso `maestro --device <serial> test ...` por dispositivo. Cada flujo debe ser
independiente (limpia y prepara su estado). Junta reportes JUnit y salidas en una carpeta.

  python maestro_paralelo.py .maestro
  python maestro_paralelo.py .maestro --include-tags smoke,core --exclude-tags real
  python maestro_paralelo.py .maestro --all-on-each        # todo en cada dispositivo (p. ej. teléfono + tablet)
  python maestro_paralelo.py .maestro --devices SERIAL1,SERIAL2 --out impl/maestro

Las etiquetas se pasan a Maestro (--include-tags/--exclude-tags), que las lee de cada flujo.
"""
import argparse
import shutil
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from devices import ADB  # noqa: E402  (misma búsqueda de adb y salida UTF-8)

SUBFLOW_DIRS = {"common", "subflows", "shared", "helpers"}


def connected():
    out = subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout
    return [l.split()[0] for l in out.splitlines()[1:] if l.split()[-1:] == ["device"]]


def find_maestro():
    """Maestro en el PATH o en ~/.maestro/bin (la ruta del instalador oficial)."""
    found = shutil.which("maestro")
    if found:
        return found
    for name in ("maestro.bat", "maestro"):
        p = Path.home() / ".maestro" / "bin" / name
        if p.exists():
            return str(p)
    return "maestro"


def flows(root: Path):
    found = []
    for p in sorted(root.rglob("*.yaml")):
        rel = p.relative_to(root)
        if p.name == "config.yaml" or any(part in SUBFLOW_DIRS for part in rel.parts[:-1]):
            continue
        found.append(p)
    return found


def junit_counts(path: Path):
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return None
    cases = tree.getroot().iter("testcase")
    total = failed = 0
    names = []
    for c in cases:
        total += 1
        if c.find("failure") is not None or c.find("error") is not None:
            failed += 1
            names.append(c.get("name", "?"))
    return total, failed, names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("flows_dir")
    ap.add_argument("--devices", help="seriales separados por coma (por defecto: todos los conectados)")
    ap.add_argument("--include-tags")
    ap.add_argument("--exclude-tags")
    ap.add_argument("--all-on-each", action="store_true", help="correr todos los flujos en cada dispositivo")
    ap.add_argument("--out", default="impl/maestro")
    ap.add_argument("--maestro", default=find_maestro())
    a = ap.parse_args()

    devs = a.devices.split(",") if a.devices else connected()
    if not devs:
        print("Sin dispositivos: usar devices.py --wait --interval 600 y seguir programando", file=sys.stderr)
        return 3
    all_flows = flows(Path(a.flows_dir))
    if not all_flows:
        print(f"No hay flujos en {a.flows_dir}", file=sys.stderr)
        return 1

    if a.all_on_each:
        plan = {d: all_flows for d in devs}
    else:
        plan = {d: all_flows[i::len(devs)] for i, d in enumerate(devs)}

    run_dir = Path(a.out) / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    def worker(serial, items):
        if not items:
            results[serial] = (0, None)
            return
        safe = serial.replace(":", "_").replace(".", "_")
        report = run_dir / f"junit-{safe}.xml"
        out_dir = run_dir / safe
        out_dir.mkdir(exist_ok=True)
        cmd = [a.maestro, "--device", serial, "test", *map(str, items), "--format", "junit", "--output", str(report),
               "--test-output-dir", str(out_dir)]
        if a.include_tags:
            cmd += ["--include-tags", a.include_tags]
        if a.exclude_tags:
            cmd += ["--exclude-tags", a.exclude_tags]
        with open(run_dir / f"log-{safe}.txt", "w", encoding="utf-8") as log:
            code = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
        if code != 0 and not report.exists():
            # Versiones viejas de Maestro sin --test-output-dir: reintentar sin esa opción
            cmd = [c for c in cmd if c not in ("--test-output-dir", str(out_dir))]
            with open(run_dir / f"log-{safe}.txt", "a", encoding="utf-8") as log:
                code = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
        results[serial] = (code, report)

    threads = [threading.Thread(target=worker, args=(d, plan[d])) for d in devs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = [f"# Maestro {run_dir.name}", "", "| Dispositivo | Flujos | Pasados | Fallidos | Fallos |", "|---|---|---|---|---|"]
    any_fail = False
    for d in devs:
        code, report = results.get(d, (1, None))
        counts = junit_counts(report) if report else None
        if counts:
            total, failed, names = counts
        else:
            total, failed, names = len(plan[d]), (len(plan[d]) if code else 0), ([] if not code else ["ver log"])
        any_fail |= bool(failed) or code != 0
        lines.append(f"| {d} | {total} | {total - failed} | {failed} | {', '.join(names) or '—'} |")
    summary = "\n".join(lines) + "\n"
    (run_dir / "resumen.md").write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Reportes, logs y capturas en {run_dir}")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
