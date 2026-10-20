"""Release an Android app to Google Play: next version (name = today's date, code = one above
everything Play has seen), signed release bundle, then publish it with the play-console skill.

    python release.py plan                       local version, Play's versions, the proposed one, notes, git
    python release.py bump                       writes the proposed versionCode/versionName to build.gradle
    python release.py build [--skip-tests]       unit tests + bundleRelease, checks the bundle is signed
    python release.py publish [--track production] [--rollout 1] [--yes]

Run from the Android project's folder (or --project <folder>). The app's Play data folder is found
like play-console does (applicationId -> apps.json), or --app <folder>. Optional settings in that
folder's play.json, all with defaults:
    "release": {"module": "app",                       Gradle module of the app
                "version_name": "%y.%m.%d",             strftime format (default: guessed from the current name)
                "test_task": ":app:testDebugUnitTest"}  "" to never run tests
Nothing is published without --yes (the edit is validated by Google and discarded otherwise).
Run without -I: play-console signs its token with the "cryptography" package.
"""
import argparse
import datetime
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

PLAY = Path(__file__).resolve().parents[2] / "play-console" / "scripts"
sys.path.insert(0, str(PLAY))
try:
    import play  # the play-console skill: app lookup, Play API, release
except ImportError:
    sys.exit(f"ERROR: the play-console skill is missing (expected {PLAY / 'play.py'})")

fail = play.fail
CODE = re.compile(r"(\bversionCode\s*=?\s*)(\d+)")
NAME = re.compile(r"(\bversionName\s*=?\s*)([\"'])([^\"']*)\2")
FORMATS = [(r"\d{2}\.\d{2}\.\d{2}", "%y.%m.%d"), (r"\d{4}\.\d{2}\.\d{2}", "%Y.%m.%d"),
           (r"\d{4}\d{2}\d{2}", "%Y%m%d")]


# --- project ---------------------------------------------------------------------------------------------

class Project:
    def __init__(self, args):
        self.root = Path(args.project or Path.cwd()).resolve()
        if not (self.root / "settings.gradle").exists() and not (self.root / "settings.gradle.kts").exists():
            fail(f"{self.root} is not the root of an Android project (no settings.gradle): use --project")
        os.chdir(self.root)  # play.find_app reads the applicationId of the current folder
        self.cfg = play.find_app(args.app)
        self.opts = self.cfg.get("release", {})
        self.module = self.opts.get("module", "app")
        gradles = [self.root / self.module / n for n in ("build.gradle", "build.gradle.kts")]
        self.gradle = next((g for g in gradles if g.exists()), None) or fail(f"No build.gradle in {self.module}/")

    def text(self):
        with open(self.gradle, encoding="utf-8", newline="") as f:  # keeps CRLF/LF as they are
            return f.read()

    def version(self):
        t = self.text()
        codes, names = CODE.findall(t), NAME.findall(t)
        if len(codes) != 1 or len(names) != 1:
            fail(f"{self.gradle.name}: expected one literal versionCode and versionName in defaultConfig, "
                 f"found {len(codes)} and {len(names)} (flavors or variables are not supported)")
        return int(codes[0][1]), names[0][2]

    def write_version(self, code, name):
        t = CODE.sub(lambda m: f"{m.group(1)}{code}", self.text(), count=1)
        t = NAME.sub(lambda m: f"{m.group(1)}{m.group(2)}{name}{m.group(2)}", t, count=1)
        with open(self.gradle, "w", encoding="utf-8", newline="") as f:
            f.write(t)

    def name_format(self, current):
        if self.opts.get("version_name"):
            return self.opts["version_name"]
        for pattern, fmt in FORMATS:
            if re.fullmatch(pattern, current):
                return fmt
        fail(f"versionName '{current}' is not a date: set \"release\": {{\"version_name\": \"<strftime format>\"}} "
             f"in {self.cfg['_dir'] / 'play.json'}")

    def bundle(self):
        return self.root / self.module / "build" / "outputs" / "bundle" / "release" / f"{self.module}-release.aab"

    def git(self, *args):
        r = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        return r.stdout.strip() if r.returncode == 0 else ""


def proposal(p):
    """The next version: one above every code Play has seen (and the local one), named after today."""
    code, name = p.version()
    known = play.known_versions(p.cfg)
    new_code = max(code, known["maxVersionCode"]) + 1
    base = datetime.date.today().strftime(p.name_format(name))
    # Play names a release "16 (26.10.15)" or just "26.10.19"
    used = {name}
    for r in known["releases"]:
        m = re.search(r"\((.+)\)", r["name"])
        used.add(m.group(1) if m else r["name"])
    new_name, n = base, 2
    while new_name in used:  # a second release the same day
        new_name, n = f"{base}.{n}", n + 1
    return code, name, known, new_code, new_name


def missing_notes(p, code):
    folder = p.cfg["_dir"] / "changelogs"
    return [lang for lang in play.languages(p.cfg) if not (folder / lang / f"{code}.txt").exists()]


# --- commands --------------------------------------------------------------------------------------------

def cmd_plan(args):
    p = Project(args)
    code, name, known, new_code, new_name = proposal(p)
    print(f"{p.cfg['package']}  (profile {p.cfg['profile']}, data {p.cfg['_dir']})")
    print(f"local      {p.gradle.relative_to(p.root)}: versionCode {code}, versionName {name}")
    for r in known["releases"]:
        frac = f" {r['userFraction'] * 100:g}%" if r.get("userFraction") else ""
        print(f"play       {r['track']:11} {r['status']}{frac}  {r['versionCodes']}  {r['name']}")
    print(f"play       highest versionCode ever uploaded: {known['maxVersionCode']}")
    if code > known["maxVersionCode"]:
        print(f"note       the local code {code} is above Play's: it was bumped and not published yet")
    print(f"proposed   versionCode {new_code}, versionName {new_name}")
    missing = missing_notes(p, new_code)
    notes_dir = p.cfg["_dir"] / "changelogs"
    print(f"notes      {notes_dir}\\<lang>\\{new_code}.txt (max {play.NOTES_MAX} characters): "
          + (f"MISSING {', '.join(missing)}" if missing else "all languages ready"))
    last = p.git("log", "-1", "--format=%h", "-G", r"versionCode", "--", str(p.gradle.relative_to(p.root)))
    if last:
        log = p.git("log", "--format=%h %s", f"{last}..HEAD").splitlines()
        print(f"commits    since the last version bump ({last}):")
        print("\n".join(f"  {l}" for l in log) or "  (none)")
    dirty = p.git("status", "--porcelain")
    print("git        " + ("UNCOMMITTED CHANGES (they would go into the build):\n" + dirty if dirty else "clean"))


def cmd_bump(args):
    p = Project(args)
    dirty = [l for l in p.git("status", "--porcelain").splitlines() if not l.endswith(p.gradle.name)]
    if dirty and not args.allow_dirty:
        fail("Uncommitted changes would go into the release build: commit them first (or --allow-dirty)\n"
             + "\n".join(dirty))
    code, name, _, new_code, new_name = proposal(p)
    p.write_version(new_code, new_name)
    print(f"OK: {p.gradle.relative_to(p.root)}  versionCode {code} -> {new_code}, versionName {name} -> {new_name}")


def gradle(p, *tasks):
    wrapper = p.root / ("gradlew.bat" if os.name == "nt" else "gradlew")
    env = dict(os.environ)
    studio_jbr = Path(r"C:\Program Files\Android\Android Studio\jbr")
    if not env.get("JAVA_HOME") and studio_jbr.exists():
        env["JAVA_HOME"] = str(studio_jbr)
    print(f"> gradlew {' '.join(tasks)}", flush=True)
    r = subprocess.run([str(wrapper), *tasks], cwd=p.root, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = r.stdout + r.stderr
    if r.returncode != 0:
        print(out[-6000:])
        fail(f"gradlew {' '.join(tasks)} failed")
    return out


def signed(aab):
    with zipfile.ZipFile(aab) as z:
        return any(re.fullmatch(r"META-INF/[^/]+\.(RSA|DSA|EC)", n) for n in z.namelist())


def cmd_build(args):
    p = Project(args)
    code, name = p.version()
    test_task = p.opts.get("test_task", f":{p.module}:testDebugUnitTest")
    if test_task and not args.skip_tests:
        out = gradle(p, test_task)
        print("  tests passed" + ("" if "BUILD SUCCESSFUL" in out else " (no BUILD SUCCESSFUL line?)"))
    started = datetime.datetime.now().timestamp()
    out = gradle(p, f":{p.module}:bundleRelease")
    aab = p.bundle()
    if not aab.exists() or aab.stat().st_mtime < started - 5:
        fail(f"No fresh bundle at {aab}")
    if "UNSIGNED" in out or not signed(aab):
        fail(f"{aab.name} is not signed: the upload key was not found (see the project's signing setup)")
    print(f"OK: {aab}  ({aab.stat().st_size / 1048576:.1f} MB, signed)  versionCode {code}, versionName {name}")


def cmd_publish(args):
    p = Project(args)
    code, name = p.version()
    known = play.known_versions(p.cfg)
    if code <= known["maxVersionCode"]:
        fail(f"versionCode {code} is not above Play's {known['maxVersionCode']}: run bump and build first")
    aab = p.bundle()
    if not aab.exists() or aab.stat().st_mtime < p.gradle.stat().st_mtime:
        fail(f"The bundle is missing or older than {p.gradle.name}: run build first")
    missing = missing_notes(p, code)
    if missing:
        fail(f"No release notes for {code} in {', '.join(missing)}: "
             f"{p.cfg['_dir'] / 'changelogs'}\\<lang>\\{code}.txt")
    play.cmd_release(argparse.Namespace(bundle=str(aab), app=str(p.cfg["_dir"]), track=args.track,
                                        rollout=args.rollout, name=None, yes=args.yes, version_code=code))


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("plan", "bump", "build", "publish"):
        s = sub.add_parser(n)
        s.add_argument("--project")
        s.add_argument("--app")
        if n == "bump":
            s.add_argument("--allow-dirty", action="store_true")
        if n == "build":
            s.add_argument("--skip-tests", action="store_true")
        if n == "publish":
            s.add_argument("--track", default="production")
            s.add_argument("--rollout", type=float, default=1.0, help="0.1 = 10%%; 1 = everyone")
            s.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    {"plan": cmd_plan, "bump": cmd_bump, "build": cmd_build, "publish": cmd_publish}[args.cmd](args)


if __name__ == "__main__":
    main()
