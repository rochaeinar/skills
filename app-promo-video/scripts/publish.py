"""Publishing a promo video on YouTube: everything for the upload, and the upload itself.

    python publish.py prepare <video.json> --locale en-US --format horizontal [--variant A]
    python publish.py auth    <client_secret.json> [--no-browser] [--profile name]   once per account
    python publish.py upload  <video.json> --locale en-US --format horizontal [--variant A] [--privacy unlisted] [--profile name]

prepare writes upload/<name>/ next to video.json, enough to upload by hand in YouTube Studio:
    video.mp4 (hard link to the final render), thumbnail.jpg (1280x720, the hook with its question),
    captions-<lang>.srt (from the voice's word times), title.txt, description.txt, tags.txt,
    metadata.json (all of it) and CHECKLIST.md (the steps and settings, in Spanish).
The texts come from video.json "publish": {"<locale>": {"title", "description", "tags", "playstore_url"}}.

upload sends the same through the YouTube Data API v3 (videos.insert, thumbnails.set,
captions.insert) with: the privacy asked for, embeddable, not made for kids and
containsSyntheticMedia = true (the AI hook). Projects without the API compliance audit get their
uploads locked as private: the script reads back the real privacy and says so. The video id and
link are saved in video.json "publish.<locale>.uploaded.<name>", so a video is never uploaded twice.

Credentials (Windows Credential Manager, never in files or the chat). Several Google accounts: one
Google Cloud project per account and a profile name for each, whose credentials end in "@<profile>"
(PromoVideo-YouTube@otherdev). An app picks its channel with video.json "youtube_profile" or
--profile; without a profile, the plain names below:
    PromoVideo-YouTube-Client   user = OAuth client id, secret = client secret (Desktop app client)
    PromoVideo-YouTube          user = channel, secret = refresh token (written by "auth")
"""
import argparse
import base64
import hashlib
import http.server
import json
import math
import os
import secrets
import shutil
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (credential, credential_user, profiled, fail, ffmpeg_paths, load_video_json, resolve, run,  # noqa: E402
                    save_credential, write_json)

SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl"
CLIENT = "PromoVideo-YouTube-Client"
TOKEN = "PromoVideo-YouTube"
CATEGORY = "22"  # People & Blogs; "28" is Science & Technology


# --- prepare --------------------------------------------------------------------------------------

def srt_time(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def captions_srt(props):
    """Every sentence of the voice, in caption chunks, with the times of the final video."""
    import render
    fps = props["fps"]
    lines, n = [], 0
    for c in props.get("all_captions") or props["captions"]:
        n += 1
        text = " ".join(w["text"] for w in c["words"])
        lines.append(f"{n}\n{srt_time(c['from'] / fps)} --> {srt_time(c['to'] / fps)}\n{text}\n")
    return "\n".join(lines)


def all_captions(config, locale, fmt, variant):
    """Captions of every voiced scene (the video only shows them on the feature scenes)."""
    import render
    script = {"scenes": render.script_scenes(config, locale, fmt, variant)}
    props = render.build_props(config, locale, fmt, variant=variant)
    manifest = json.loads(resolve(config, render.audio_name(locale, fmt, variant)).read_text(encoding="utf-8"))
    out = []
    for track, voice in zip(props["voice"], [v for v in manifest.get("voice", []) if v]):
        out += render.captions_for(voice["words"], track["from"])
    return out, props


def thumbnail(config, locale, fmt, variant, target):
    """The hook at 1.8 s (AI scene and question), 1280x720 JPEG under 2 MB (YouTube's limit)."""
    import render
    name = f"promo-{locale}-{fmt}" + (f"-{variant}" if variant else "")
    run([sys.executable, "-I", str(Path(render.__file__)), str(config["_dir"] / "video.json"), "--locale", locale,
         "--format", fmt] + (["--variant", variant] if variant else []) + ["--still", "1.8"], capture=False)
    still = resolve(config, "output") / f"{name}-1.8s.png"
    from PIL import Image
    im = Image.open(still).convert("RGB")
    if fmt == "horizontal":
        im = im.resize((1280, 720), Image.LANCZOS)
    im.save(target, quality=90, optimize=True)
    still.unlink()


def prepare(config, locale, fmt, variant):
    pub = (config.get("publish") or {}).get(locale) or fail(f"No publish.{locale} in video.json (title, description, tags)")
    name = f"promo-{locale}-{fmt}" + (f"-{variant}" if variant else "")
    video = resolve(config, "output") / f"{name}.mp4"
    if not video.exists():
        fail(f"Missing {video}: render it with render.py --final first.")
    out = resolve(config, "upload") / name
    out.mkdir(parents=True, exist_ok=True)
    target = out / "video.mp4"
    if target.exists():
        target.unlink()
    try:
        os.link(video, target)
    except OSError:
        shutil.copy2(video, target)

    lang = locale.split("-")[0]
    caps, props = all_captions(config, locale, fmt, variant)
    (out / f"captions-{lang}.srt").write_text(captions_srt({"fps": props["fps"], "all_captions": caps}), encoding="utf-8")
    thumbnail(config, locale, fmt, variant, out / "thumbnail.jpg")

    title = pub["title"][:100].replace("<", "").replace(">", "")
    description = pub["description"].replace("<", "").replace(">", "")
    if pub.get("playstore_url") and pub["playstore_url"] not in description:
        description += f"\n\n{pub['playstore_url']}"
    if len(description.encode("utf-8")) > 5000:
        fail("The description is longer than YouTube's 5000 bytes.")
    tags = pub.get("tags", [])
    if len(",".join(f'"{t}"' if " " in t else t for t in tags)) > 500:
        fail("The tags are longer than YouTube's 500 characters.")
    (out / "title.txt").write_text(title, encoding="utf-8")
    (out / "description.txt").write_text(description, encoding="utf-8")
    (out / "tags.txt").write_text(", ".join(tags), encoding="utf-8")
    metadata = {"title": title, "description": description, "tags": tags, "categoryId": CATEGORY,
                "defaultLanguage": lang, "defaultAudioLanguage": lang, "embeddable": True,
                "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True,
                "captions": f"captions-{lang}.srt", "thumbnail": "thumbnail.jpg", "video": "video.mp4",
                "seconds": round(__import__("render").promo_seconds(props), 1)}
    write_json(out / "metadata.json", metadata)
    (out / "CHECKLIST.md").write_text(f"""# Subir a YouTube: {title}

1. YouTube Studio → **Crear → Subir videos** → `video.mp4`.
2. **Título:** copiar `title.txt`. **Descripción:** copiar `description.txt`.
3. **Miniatura:** subir `thumbnail.jpg` (requiere el canal verificado por teléfono).
4. **Público:** "No, no es contenido para niños".
5. **Mostrar más:**
   - **Contenido alterado o sintético: Sí** (la escena del inicio está hecha con IA).
   - **Etiquetas:** copiar `tags.txt`.
   - **Idioma del video:** {lang}. **Categoría:** Personas y blogs.
   - **Licencia y distribución:** marcar **Permitir inserción**.
6. **Elementos del video → Subtítulos:** subir `captions-{lang}.srt` (con tiempos), idioma {lang}.
7. **Visibilidad:** **Oculto** (solo para la ficha de Play) o **Público**. Nunca privado: Play no lo muestra.
8. Monetización: **desactivada** (Play no acepta videos con anuncios).
9. Copiar el enlace (`https://youtu.be/...`), **sin** `&list=`, `&t=` ni otros parámetros, y pegarlo en
   Play Console → Presencia en Play Store → Ficha principal → **{locale}** → Video de YouTube.
""", encoding="utf-8")
    print(f"OK {out}")
    return out


# --- auth -----------------------------------------------------------------------------------------

def http_json(method, url, data=None, headers=None, raw=None):
    body = raw if raw is not None else (urllib.parse.urlencode(data).encode() if data is not None else None)
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            text = r.read().decode("utf-8")
            return json.loads(text) if text else {}, r.headers
    except urllib.error.HTTPError as e:
        fail(f"{method} {url.split('?')[0]}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:800]}")


def auth(client_file, open_browser=True, profile=None):
    """Installed-app OAuth with PKCE on a loopback port; stores the client and the refresh token."""
    data = json.loads(Path(client_file).read_text(encoding="utf-8"))
    c = data.get("installed") or fail("The JSON must be an OAuth client of type 'Desktop app'.")
    save_credential(profiled(CLIENT, profile), c["client_id"], c["client_secret"])

    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("Listo, puedes cerrar esta pestaña.".encode("utf-8"))

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{server.server_port}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256"})
    # The link always printed: it can be opened in any browser of this PC (a Firefox container,
    # another profile), the answer comes back to 127.0.0.1.
    print("Open this link in the browser where the channel's Google account is signed in:\n\n" + url + "\n", flush=True)
    if open_browser:
        webbrowser.open(url)
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    thread.join(timeout=900)
    server.server_close()
    if result.get("state") != state or "code" not in result:
        fail(f"Authorization not completed: {result.get('error', 'no answer in 15 minutes')}")
    token, _ = http_json("POST", "https://oauth2.googleapis.com/token", {
        "code": result["code"], "client_id": c["client_id"], "client_secret": c["client_secret"],
        "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier})
    if "refresh_token" not in token:
        fail("Google did not return a refresh token; revoke the app's access in your account and try again.")
    me, _ = http_json("GET", "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                      headers={"Authorization": f"Bearer {token['access_token']}"})
    channel = (me.get("items") or [{}])[0].get("snippet", {}).get("title", "channel")
    save_credential(profiled(TOKEN, profile), channel, token["refresh_token"])
    print(f"OK: authorized for the channel '{channel}'" + (f" (profile '{profile}')" if profile else ""))


def access_token(profile=None):
    client, tok = profiled(CLIENT, profile), profiled(TOKEN, profile)
    hint = f" --profile {profile}" if profile else ""
    client_id = credential_user(client) or fail(
        f"No YouTube credentials for this profile: run 'publish.py auth <client_secret.json>{hint}' first.")
    refresh = credential(tok)
    token, _ = http_json("POST", "https://oauth2.googleapis.com/token", {
        "client_id": client_id, "client_secret": credential(client), "refresh_token": refresh,
        "grant_type": "refresh_token"})
    return token["access_token"]


# --- upload ---------------------------------------------------------------------------------------

def upload(config, locale, fmt, variant, privacy, profile=None):
    name = f"promo-{locale}-{fmt}" + (f"-{variant}" if variant else "")
    pub = config["publish"][locale]
    done = pub.get("uploaded", {}).get(name)
    if done:
        print(f"Already uploaded: {done['url']} (privacy {done['privacy']}). Delete it from video.json to upload again.")
        return
    folder = prepare(config, locale, fmt, variant)
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    profile = profile or config.get("youtube_profile")
    channel = credential_user(profiled(TOKEN, profile))
    print(f"YouTube profile: {profile or '(default)'}, channel: {channel}")
    token = access_token(profile)
    auth_header = {"Authorization": f"Bearer {token}"}

    body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"],
                        "categoryId": meta["categoryId"], "defaultLanguage": meta["defaultLanguage"],
                        "defaultAudioLanguage": meta["defaultAudioLanguage"]},
            "status": {"privacyStatus": privacy, "embeddable": True, "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": True}}
    video = folder / "video.mp4"
    size = video.stat().st_size
    # Resumable upload: a session, then the file in one PUT.
    _, headers = http_json("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                           raw=json.dumps(body).encode("utf-8"),
                           headers={**auth_header, "Content-Type": "application/json; charset=UTF-8",
                                    "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    session = headers["Location"]
    print(f"Uploading {size // 1048576} MB...")
    result, _ = http_json("PUT", session, raw=video.read_bytes(),
                          headers={**auth_header, "Content-Type": "video/mp4", "Content-Length": str(size)})
    video_id = result["id"]
    real_privacy = result.get("status", {}).get("privacyStatus", "?")
    url = f"https://youtu.be/{video_id}"
    print(f"Uploaded: {url} (privacy requested {privacy}, YouTube set {real_privacy})")

    try:
        http_json("POST", f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}&uploadType=media",
                  raw=(folder / "thumbnail.jpg").read_bytes(), headers={**auth_header, "Content-Type": "image/jpeg"})
        print("  thumbnail OK")
    except SystemExit:
        print("  thumbnail failed (custom thumbnails need a phone-verified channel): upload thumbnail.jpg by hand")

    boundary = "promo" + secrets.token_hex(8)
    srt = (folder / meta["captions"]).read_text(encoding="utf-8")
    multipart = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                 + json.dumps({"snippet": {"videoId": video_id, "language": meta["defaultLanguage"], "name": ""}})
                 + f"\r\n--{boundary}\r\nContent-Type: application/x-subrip\r\n\r\n{srt}\r\n--{boundary}--\r\n").encode("utf-8")
    try:
        http_json("POST", "https://www.googleapis.com/upload/youtube/v3/captions?uploadType=multipart&part=snippet",
                  raw=multipart, headers={**auth_header, "Content-Type": f"multipart/related; boundary={boundary}"})
        print("  captions OK")
    except SystemExit:
        print(f"  captions failed: upload {meta['captions']} by hand")

    pub.setdefault("uploaded", {})[name] = {"id": video_id, "url": url, "privacy": real_privacy,
                                            "channel": channel, "profile": profile or ""}
    path = config["_dir"] / "video.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["publish"][locale] = pub
    write_json(path, data)
    if real_privacy != privacy:
        print(f"\nYouTube left the video {real_privacy}: the API project has no compliance audit yet. In YouTube"
              f" Studio try to change it to {privacy}; if it is locked, upload by hand with {folder / 'CHECKLIST.md'}.")
    print(f"Play Console: {url}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("prepare", "upload"):
        p = sub.add_parser(cmd)
        p.add_argument("video_json")
        p.add_argument("--locale", required=True)
        p.add_argument("--format", default="horizontal")
        p.add_argument("--variant", default=None)
        p.add_argument("--profile", default=None, help="YouTube account profile (default: video.json youtube_profile)")
        if cmd == "upload":
            p.add_argument("--privacy", default="unlisted", choices=["private", "unlisted", "public"])
    a = sub.add_parser("auth")
    a.add_argument("client_secret")
    a.add_argument("--no-browser", action="store_true", help="Only print the link (to open it in a chosen browser)")
    a.add_argument("--profile", default=None, help="Account profile these credentials belong to")
    args = parser.parse_args()
    if args.command == "auth":
        auth(args.client_secret, not args.no_browser, args.profile)
        return
    config = load_video_json(args.video_json)
    if args.command == "prepare":
        prepare(config, args.locale, args.format, args.variant)
    else:
        upload(config, args.locale, args.format, args.variant, args.privacy, args.profile)


if __name__ == "__main__":
    main()
