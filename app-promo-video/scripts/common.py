"""Shared helpers of the app-promo-video scripts: tool discovery, video.json, logging."""
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def profiled(target, profile):
    """The credential name of an account profile: "PromoVideo-YouTube" -> "PromoVideo-YouTube@<profile>".
    No profile: the plain name. Only YouTube uses profiles (one Google account and Cloud project
    each); ElevenLabs and fal.ai are shared by every app."""
    profile = (profile or "").strip()
    return f"{target}@{profile}" if profile else target


def load_video_json(path):
    """Reads video.json; relative paths inside it are relative to its folder."""
    path = Path(path).resolve()
    if not path.exists():
        fail(f"Not found: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    config["_dir"] = path.parent
    return config


def resolve(config, value):
    """Absolute path of a path from video.json."""
    p = Path(value)
    return p if p.is_absolute() else (config["_dir"] / p).resolve()


def find_tool(name, candidates):
    """First of: the PATH, then the candidate paths (globs allowed)."""
    found = shutil.which(name)
    if found:
        return found
    for pattern in candidates:
        for match in sorted(glob.glob(os.path.expandvars(os.path.expanduser(pattern)))):
            if Path(match).exists():
                return match
    return None


def adb_path():
    adb = find_tool("adb", [r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe",
                            "~/Library/Android/sdk/platform-tools/adb", "~/Android/Sdk/platform-tools/adb"])
    if not adb:
        fail("adb not found (Android SDK platform-tools).")
    return adb


def ffmpeg_paths():
    winget = r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin"
    ffmpeg = find_tool("ffmpeg", [winget + r"\ffmpeg.exe"])
    ffprobe = find_tool("ffprobe", [winget + r"\ffprobe.exe"])
    if not ffmpeg or not ffprobe:
        fail("ffmpeg/ffprobe not found. Windows: winget install Gyan.FFmpeg")
    return ffmpeg, ffprobe


def maestro_env():
    """Maestro CLI and the environment it needs (a JDK)."""
    maestro = find_tool("maestro", [r"%USERPROFILE%\.maestro\bin\maestro.bat", "~/.maestro/bin/maestro"])
    if not maestro:
        fail("Maestro CLI not found (~/.maestro/bin).")
    env = dict(os.environ)
    if not env.get("JAVA_HOME"):
        for jdk in [r"C:\Program Files\Android\Android Studio\jbr",
                    "/Applications/Android Studio.app/Contents/jbr/Contents/Home"]:
            if Path(jdk).exists():
                env["JAVA_HOME"] = jdk
                break
    env["MAESTRO_CLI_NO_ANALYTICS"] = "1"
    env["MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED"] = "true"
    return maestro, env


def run(command, check=True, capture=True, **kwargs):
    result = subprocess.run(command, capture_output=capture, text=True, encoding="utf-8",
                            errors="replace", **kwargs)
    if check and result.returncode != 0:
        fail(f"{' '.join(map(str, command))}\n{result.stdout}\n{result.stderr}")
    return result


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def credential(target, env=None):
    """API key: the password of a generic credential in the Windows Credential Manager (created
    with New-StoredCredential), or the environment variable `env` on other systems."""
    if env and os.environ.get(env):
        return os.environ[env]
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as w

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [("Flags", w.DWORD), ("Type", w.DWORD), ("TargetName", w.LPWSTR), ("Comment", w.LPWSTR),
                        ("LastWritten", w.FILETIME), ("CredentialBlobSize", w.DWORD),
                        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", w.DWORD),
                        ("AttributeCount", w.DWORD), ("Attributes", ctypes.c_void_p),
                        ("TargetAlias", w.LPWSTR), ("UserName", w.LPWSTR)]

        pointer = ctypes.POINTER(CREDENTIAL)()
        if ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(pointer)):  # 1 = CRED_TYPE_GENERIC
            try:
                c = pointer.contents
                return bytes(c.CredentialBlob[:c.CredentialBlobSize]).decode("utf-16-le")
            finally:
                ctypes.windll.advapi32.CredFree(pointer)
    fail(f"No API key: create the credential '{target}' (see SKILL.md)" + (f" or set {env}" if env else ""))


def save_credential(target, user, secret):
    """Stores a generic credential in the Windows Credential Manager (user + secret)."""
    if sys.platform != "win32":
        fail(f"Store {target} in an environment variable on this system.")
    import ctypes
    import ctypes.wintypes as w

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [("Flags", w.DWORD), ("Type", w.DWORD), ("TargetName", w.LPWSTR), ("Comment", w.LPWSTR),
                    ("LastWritten", w.FILETIME), ("CredentialBlobSize", w.DWORD),
                    ("CredentialBlob", ctypes.c_void_p), ("Persist", w.DWORD),
                    ("AttributeCount", w.DWORD), ("Attributes", ctypes.c_void_p),
                    ("TargetAlias", w.LPWSTR), ("UserName", w.LPWSTR)]

    blob = secret.encode("utf-16-le")
    buf = ctypes.create_string_buffer(blob, len(blob))
    cred = CREDENTIAL(Type=1, TargetName=target, CredentialBlobSize=len(blob),
                      CredentialBlob=ctypes.cast(buf, ctypes.c_void_p), Persist=2, UserName=user)  # 2 = LOCAL_MACHINE
    if not ctypes.windll.advapi32.CredWriteW(ctypes.byref(cred), 0):
        fail(f"Could not store the credential {target}")


def credential_user(target):
    """The user name of a stored generic credential, or None."""
    if sys.platform != "win32":
        return None
    import ctypes
    import ctypes.wintypes as w

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [("Flags", w.DWORD), ("Type", w.DWORD), ("TargetName", w.LPWSTR), ("Comment", w.LPWSTR),
                    ("LastWritten", w.FILETIME), ("CredentialBlobSize", w.DWORD),
                    ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", w.DWORD),
                    ("AttributeCount", w.DWORD), ("Attributes", ctypes.c_void_p),
                    ("TargetAlias", w.LPWSTR), ("UserName", w.LPWSTR)]

    pointer = ctypes.POINTER(CREDENTIAL)()
    if not ctypes.windll.advapi32.CredReadW(target, 1, 0, ctypes.byref(pointer)):
        return None
    try:
        return pointer.contents.UserName
    finally:
        ctypes.windll.advapi32.CredFree(pointer)


def log_cost(config, service, what, amount, unit, usd=0.0):
    """Appends a paid call to costs.json (credits or seconds, and USD when it is pay per use)."""
    import datetime
    path = resolve(config, "costs.json")
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"entries": []}
    data["entries"].append({"when": datetime.datetime.now().isoformat(timespec="seconds"), "service": service,
                            "what": what, "amount": amount, "unit": unit, "usd": round(usd, 4)})
    data["total_usd"] = round(sum(e.get("usd", 0) for e in data["entries"]), 4)
    write_json(path, data)


def sha(*parts):
    import hashlib
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
