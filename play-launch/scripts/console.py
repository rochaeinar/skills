"""Play Console screens that have no API, driven in the user's own browser session (stage 3 only).

    python console.py open     --profile erasoft            start the dedicated browser; the user signs in by hand
    python console.py whoami   --profile erasoft            signed in? which developer account? (must match the bound one)
    python console.py bind     --profile erasoft            record the developer account id of this profile (once)
    python console.py bind-app --app <folder>               record the Play Console id of the app open in the browser
    python console.py snapshot --profile erasoft [--out dir] [--name x]   screenshot + accessibility tree of the page
    python console.py run <screen> --app <folder> [--dry-run]   run screens/<screen>.json with the approved expediente

Rules (never change them): a visible browser started by `open` (never headless, never Playwright-launched), the
sign-in is always by hand, one tab and one app at a time, human pauses, same PC and network. The scripts attach
over CDP to that browser. A step that does not find its field stops the run with a screenshot and the page's
accessibility tree: Claude repairs the screen file, runs it with --dry-run, and only then for real.
"""
import argparse
import datetime as dt
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import launch  # noqa: E402

SKILL = launch.SKILL
ACCOUNTS = SKILL / "accounts.json"          # per PC: profile -> developer id, port, browser
SCREENS = SKILL / "screens"
CONSOLE = "https://play.google.com/console"
BROWSERS = {
    "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
    "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
               os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")],
}
BASE_PORT = 9333


def fail(msg):
    launch.fail(msg)


def accounts():
    return launch.read_json(ACCOUNTS, {})


def profile_cfg(profile):
    acc = accounts()
    cfg = acc.get(profile) or {}
    cfg.setdefault("port", BASE_PORT + sorted(set(acc) | {profile}).index(profile))
    cfg.setdefault("browser", "edge")
    return cfg


def save_profile(profile, cfg):
    acc = accounts()
    acc[profile] = cfg
    launch.write_json(ACCOUNTS, acc)


def user_data_dir(profile):
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "play-launch" / f"browser-{profile}"


# --- the dedicated browser ---------------------------------------------------------------------------

def cmd_open(args):
    cfg = profile_cfg(args.profile)
    if args.browser:
        cfg["browser"] = args.browser
    exe = next((p for p in BROWSERS[cfg["browser"]] if Path(p).exists()), None) or fail(f"{cfg['browser']} not installed")
    save_profile(args.profile, cfg)
    data = user_data_dir(args.profile)
    data.mkdir(parents=True, exist_ok=True)
    # Remote debugging only works outside the default profile (Chrome/Edge 136+): this is a profile of its own.
    subprocess.Popen([exe, f"--user-data-dir={data}", f"--remote-debugging-port={cfg['port']}",
                      "--remote-debugging-address=127.0.0.1", "--lang=en-US", "--no-first-run",
                      "--no-default-browser-check", CONSOLE], close_fds=True,
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    print(f"Opened {cfg['browser']} (profile '{args.profile}', {data}). Sign in BY HAND with the developer "
          f"account's Google user, open Play Console, and set its language to English (Settings > Preferences).")


class Session:
    def __init__(self, profile):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            fail("Missing Playwright: python -m pip install --user playwright (no browser download needed)")
        self.cfg = profile_cfg(profile)
        self.profile = profile
        self._pw = sync_playwright().start()
        try:
            self.browser = self._pw.chromium.connect_over_cdp(f"http://127.0.0.1:{self.cfg['port']}")
        except Exception:
            self._pw.stop()
            fail(f"The dedicated browser is not running: python console.py open --profile {profile}")
        ctx = self.browser.contexts[0]
        # The Play Console tab if there is one; else a web tab (never the browser's own edge:// or chrome:// pages).
        console = [p for p in ctx.pages if "play.google.com/console" in p.url]
        web = [p for p in ctx.pages if p.url.startswith("http")]
        self.page = (console or web or [ctx.new_page()])[0]

    def close(self):
        # Detach only: the user's browser stays open.
        self._pw.stop()

    def developer_id(self):
        if "accounts.google.com" in self.page.url or "/signin" in self.page.url:
            return None
        if "play.google.com/console" not in self.page.url:
            self.page.goto(CONSOLE, wait_until="domcontentloaded")
            self.page.wait_for_load_state("networkidle", timeout=60000)
        m = re.search(r"/developers/(\d+)", self.page.url)
        return m.group(1) if m else None

    def pause(self, lo=0.7, hi=2.0):
        time.sleep(random.uniform(lo, hi))


def cmd_whoami(args, quiet=False):
    s = Session(args.profile)
    try:
        dev = s.developer_id()
        bound = s.cfg.get("developer_id")
        if not dev:
            fail("Not signed in to Play Console in the dedicated browser: sign in by hand")
        if bound and dev != bound:
            fail(f"WRONG ACCOUNT: the browser shows developer {dev}, profile '{args.profile}' is {bound}. Nothing done.")
        if not quiet:
            print(f"OK: signed in, developer {dev}" + ("" if bound else " (not bound yet: console.py bind)"))
        return dev
    finally:
        s.close()


def cmd_bind(args):
    dev = cmd_whoami(args, quiet=True)
    cfg = profile_cfg(args.profile)
    cfg["developer_id"] = dev
    save_profile(args.profile, cfg)
    print(f"OK: profile '{args.profile}' = developer account {dev}")


def cmd_bind_app(args):
    app = launch.App(args.app)
    profile = app.meta["profiles"]["play"]
    s = Session(profile)
    try:
        m = re.search(r"/developers/(\d+)/app/(\d+)", s.page.url) or fail("Open the app in Play Console first")
        if m.group(1) != profile_cfg(profile).get("developer_id"):
            fail("The open app belongs to another developer account")
        st = app.state()
        st["console_app_id"] = m.group(2)
        launch.write_json(app.state_path, st)
        print(f"OK: {app.slug} = Play Console app {m.group(2)}")
    finally:
        s.close()


def evidence_dir(app=None, out=None):
    d = Path(out) if out else ((app.launch if app else SKILL) / "evidence" / dt.date.today().isoformat())
    d.mkdir(parents=True, exist_ok=True)
    return d


def snapshot(page, folder, name):
    stamp = dt.datetime.now().strftime("%H%M%S")
    png = folder / f"{stamp}-{name}.png"
    page.screenshot(path=str(png), full_page=True)
    tree = folder / f"{stamp}-{name}.aria.yaml"
    try:
        tree.write_text(page.locator("body").aria_snapshot(), encoding="utf-8")
    except Exception as e:
        tree.write_text(f"(no accessibility snapshot: {e})", encoding="utf-8")
    return png, tree


def cmd_snapshot(args):
    s = Session(args.profile)
    try:
        png, tree = snapshot(s.page, evidence_dir(out=args.out), args.name or "page")
        print(f"{s.page.url}\n  {png}\n  {tree}")
    finally:
        s.close()


# --- screens: declarative steps over the approved expediente --------------------------------------------

def resolve(value, ctx):
    """'${a.b.c}' -> the value in ctx (the expediente + ids). A missing value stops the run (fail-closed)."""
    if not isinstance(value, str):
        return value
    full = re.fullmatch(r"\$\{([^}]+)\}", value)

    def lookup(path):
        cur = ctx
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                fail(f"The screen needs '{path}', which is not in the approved expediente")
        if cur is None:
            fail(f"'{path}' has no value in the approved expediente")
        return cur

    if full:
        return lookup(full.group(1))
    return re.sub(r"\$\{([^}]+)\}", lambda m: str(lookup(m.group(1))), value)


def locator(page, step, ctx):
    if "role" in step:
        return page.get_by_role(step["role"], name=resolve(step["name"], ctx), exact=step.get("exact", True))
    if "label" in step:
        return page.get_by_label(resolve(step["label"], ctx), exact=step.get("exact", True))
    if "text" in step:
        return page.get_by_text(resolve(step["text"], ctx), exact=step.get("exact", False))
    fail(f"Step without role/label/text: {step}")


def run_steps(s, steps, ctx, dry, log):
    page = s.page
    for step in steps:
        kind = step["do"]
        if kind == "when":
            if resolve(step["value"], ctx) == step["equals"]:
                run_steps(s, step["steps"], ctx, dry, log)
            continue
        if kind == "each":
            for item in resolve(step["in"], ctx):
                run_steps(s, step["steps"], {**ctx, "item": item}, dry, log)
            continue
        s.pause()
        if kind == "goto":
            page.goto(CONSOLE + resolve(step["path"], ctx), wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=60000)
        elif kind == "expect":
            locator(page, step, ctx).first.wait_for(state="visible", timeout=step.get("timeout", 20000))
        elif kind == "click":
            if dry and step.get("commits"):
                log.append(f"DRY: would click {step.get('name')}")
                continue
            locator(page, step, ctx).first.click(timeout=20000)
        elif kind == "check":
            locator(page, step, ctx).first.check(timeout=20000)
        elif kind == "fill":
            target = locator(page, step, ctx).first
            target.click(timeout=20000)
            target.fill("")
            target.press_sequentially(str(resolve(step["value"], ctx)), delay=random.randint(35, 90))
        elif kind == "select":
            locator(page, step, ctx).first.select_option(label=resolve(step["option"], ctx))
        elif kind == "upload":
            path = Path(resolve(step["file"], ctx))
            path.exists() or fail(f"Upload file not found: {path}")
            with page.expect_file_chooser(timeout=20000) as fc:
                locator(page, step, ctx).first.click()
            fc.value.set_files(str(path))
            if step.get("wait_text"):
                page.get_by_text(step["wait_text"]).first.wait_for(timeout=step.get("timeout", 600000))
        elif kind == "save":
            if dry:
                log.append(f"DRY: would save ({step.get('name')})")
                continue
            locator(page, step, ctx).first.click(timeout=20000)
            if step.get("saved_text"):
                page.get_by_text(step["saved_text"]).first.wait_for(timeout=30000)
        elif kind == "readback":
            # Verification: what the page shows after saving must equal what was approved.
            loc = locator(page, step, ctx).first
            if "checked" in step and loc.is_checked() != bool(resolve(step["checked"], ctx)):
                fail(f"Readback: '{step.get('name')}' checked={loc.is_checked()}, approved {step['checked']}")
            if "value" in step and loc.input_value().strip() != str(resolve(step["value"], ctx)).strip():
                fail(f"Readback: '{step.get('label') or step.get('name')}' differs from the approved text")
            log.append(f"readback OK: {step.get('name') or step.get('label')}")
        else:
            fail(f"Unknown step '{kind}'")


def cmd_run(args):
    app = launch.App(args.app)
    screen_file = SCREENS / f"{args.screen}.json"
    screen = launch.read_json(screen_file) or fail(f"No screen {screen_file} (see screens/README.md)")
    if screen.get("status") != "verified" and not args.dry_run:
        fail(f"Screen '{args.screen}' is {screen.get('status', 'draft')}: run it with --dry-run until it is verified")
    if not args.dry_run:
        ok, why = launch.approval_valid(app)
        ok or fail(f"{app.slug}: approval {why}. Nothing is sent without a valid approval.")
    profile = app.meta["profiles"]["play"]
    bound = profile_cfg(profile).get("developer_id") or fail(f"Bind the profile first: console.py bind --profile {profile}")
    ctx = {**app.expediente(), "developer": bound, "app_id": app.state().get("console_app_id"),
           "facts": launch.read_json(app.launch / "facts.json", {})}
    s = Session(profile)
    log, folder = [], evidence_dir(app)
    try:
        dev = s.developer_id()
        if dev != bound:
            fail(f"WRONG ACCOUNT or signed out: browser shows {dev}, expected {bound}. Nothing done.")
        run_steps(s, screen["steps"], ctx, args.dry_run, log)
        png, _ = snapshot(s.page, folder, f"{args.screen}{'-dry' if args.dry_run else ''}")
        log.append(f"evidence: {png}")
        print(f"OK: {args.screen} {'(dry run, nothing saved)' if args.dry_run else 'saved and read back'}")
    except SystemExit:
        png, tree = snapshot(s.page, folder, f"{args.screen}-FAILED")
        print(f"STOPPED on {args.screen}. Evidence: {png} and {tree}", file=sys.stderr)
        raise
    except Exception as e:
        png, tree = snapshot(s.page, folder, f"{args.screen}-FAILED")
        fail(f"{args.screen}: {type(e).__name__}: {str(e)[:400]}\nEvidence: {png} and {tree}\n"
             f"Claude: read both, fix screens/{args.screen}.json, run with --dry-run.")
    finally:
        for line in log:
            print(f"  {line}")
        with open(app.launch / "console-log.txt", "a", encoding="utf-8") as f:
            f.write(f"{launch.now()} {args.screen} dry={args.dry_run}\n" + "".join(f"  {l}\n" for l in log))
        s.close()


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open"); o.add_argument("--profile", required=True); o.add_argument("--browser", choices=list(BROWSERS))
    for name in ("whoami", "bind"):
        w = sub.add_parser(name); w.add_argument("--profile", required=True)
    b = sub.add_parser("bind-app"); b.add_argument("--app", required=True)
    sn = sub.add_parser("snapshot"); sn.add_argument("--profile", required=True); sn.add_argument("--out"); sn.add_argument("--name")
    r = sub.add_parser("run"); r.add_argument("screen"); r.add_argument("--app", required=True)
    r.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    {"open": cmd_open, "whoami": cmd_whoami, "bind": cmd_bind, "bind-app": cmd_bind_app, "snapshot": cmd_snapshot,
     "run": cmd_run}[args.cmd](args)


if __name__ == "__main__":
    main()
