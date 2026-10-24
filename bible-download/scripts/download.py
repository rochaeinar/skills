#!/usr/bin/env python3
"""Step 1 of 5 of Modules/README.md: download Bibles into Modules/languages/<lang>/sources and register them
(languages/manifest.json and, if the language has one, its pack.json with include=false).
Next: bible-language-pack (pack.py init <lang>, or choose the Bible in pack.json).

  python download.py list                                   caches and how many chapters they have
  python download.py get 3526                               a Bible.com version, chapter by chapter (resumes from the cache)
  python download.py get all --max 200                      every cached version, at most 200 requests
  python download.py build 2998 --lang ti --language-code ti   rebuild from the cache, no requests
  python download.py get-book 805 GEN                       one book only (a test file)
  python download.py getbible synodal --lang ru             a whole getBible translation in ONE request
  python download.py --output-dir D:\\bible-test get 805     isolated test: nothing in Modules is touched

Paths: Modules/config.json (BIBLE_VERSIONS_CONFIG for another one); everything lives next to it.
"""
import argparse
import datetime
import hashlib
import html.parser
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent

CHAPTER_URL = "https://nodejs.bible.com/api/bible/chapter/3.1?id={vid}&reference={ref}"
VERSION_URL = "https://nodejs.bible.com/api/bible/version/3.1?id={vid}"
PAGE_URL = "https://www.bible.com/bible/{vid}/{ref}"
MIN_INTERVAL_S = 0.2
USER_AGENT = "Mozilla/5.0 (bible-versions; public domain text, low volume)"

BOOKS = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZK DAN HOS "
         "JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM "
         "HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
BOOKNUM = {b: i for i, b in enumerate(BOOKS, 1)}
TODAY = datetime.date.today().isoformat()


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_version_id(value):
    """Accept numeric Bible.com version IDs only; prevent malformed URL/path input."""
    value = str(value).strip()
    if not re.fullmatch(r"\d+", value):
        fail(f"Invalid Bible.com version ID {value!r}; expected a numeric ID.")
    return int(value)


class Fetcher:
    """Throttle requests; stop on HTTP 403/429 and preserve the cache."""

    def __init__(self):
        self.last = 0.0
        self.requests = 0

    def get(self, url):
        wait = MIN_INTERVAL_S - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        self.requests += 1
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                fail(f"HTTP {e.code} from Bible.com: stopped. Run it again later; it resumes from the cache.")
            raise


class ChapterParser(html.parser.HTMLParser):
    """Extract verse text from Bible.com's chapter HTML."""

    SKIP = {"heading", "note", "label", "x", "f", "fr", "ft", "xo", "xt"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.verses = {}
        self.last = None

    def _state(self):
        verse, title, skip, content = None, False, False, False
        for _, classes, v, t in self.stack:
            if v is not None:
                verse = v
            title = title or t
            skip = skip or bool(classes & self.SKIP)
            content = content or "content" in classes
        return verse, title, skip, content

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div" and self.last is not None:
            # A new paragraph or poetry line: the HTML has no space between lines.
            self.verses[self.last] += " "
        classes = set((a.get("class") or "").split())
        verse = None
        if "verse" in classes and a.get("data-usfm"):
            first = a["data-usfm"].split("+")[0]
            try:
                verse = int(first.split(".")[2])
            except (IndexError, ValueError):
                verse = None
        self.stack.append((tag, classes, verse, tag == "div" and "d" in classes))

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        verse, title, skip, content = self._state()
        if skip or not content:
            return
        if verse is None and title:
            verse = 0
        if verse is None:
            return
        self.verses[verse] = self.verses.get(verse, "") + data
        self.last = verse


def parse_chapter(content_html):
    parser = ChapterParser()
    parser.feed(content_html)
    parser.close()
    out = {}
    for verse, text in parser.verses.items():
        text = " ".join(text.split())
        if text:
            out[verse] = text
    return out


DEFAULT_CONFIG = "D:/Documents/BibleVersions/Modules/config.json"


def load_config(output_dir):
    """Paths: --output-dir keeps everything in one folder (tests); otherwise Modules/config.json and its folder."""
    if output_dir:
        out = Path(output_dir).expanduser().resolve()
        return {"cache_root": out / "_cache" / "biblecom_pd", "bibles_dir": out / "bibles",
                "manifest": out / "bibles-manifest.json", "packs_dir": None}
    path = Path(os.environ.get("BIBLE_VERSIONS_CONFIG") or DEFAULT_CONFIG)
    if not path.exists():
        fail(f"Missing {path}: see Modules/README.md, or pass --output-dir.")
    root = path.parent
    return {"cache_root": root / "_cache" / "biblecom_pd", "bibles_dir": root / "languages",
            "manifest": root / "languages" / "manifest.json", "packs_dir": root / "languages"}


def lang_dir(lang):
    return lang.replace(" / ", "-").replace("/", "-")


def resolve_folder(c, pd, overrides):
    """With config.json, <lang>/sources under Modules/languages (--folder sets another one, relative to it)."""
    if overrides.get("folder") or not c["packs_dir"]:
        return pd["folder"]
    return f"{lang_dir(pd['lang'])}/sources"


def cache_dir(c, vid):
    return c["cache_root"] / str(vid)


def version_meta(c, vid, fetcher, refresh=False):
    path = cache_dir(c, vid) / "_version.json"
    if refresh or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = fetcher.get(VERSION_URL.format(vid=vid))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            fail(f"Bible.com returned invalid version metadata for {vid}: {e}")
        # Some API responses wrap the version object.
        if isinstance(data, dict) and isinstance(data.get("version"), dict):
            data = data["version"]
        if not isinstance(data, dict):
            fail(f"Unexpected metadata response for Bible.com version {vid}.")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def _first(meta, *keys, default=None):
    for key in keys:
        value = meta.get(key)
        if value not in (None, ""):
            return value
    return default


def normalize_metadata(meta, vid, overrides=None):
    """Map Bible.com metadata into this project's manifest fields.

    API schemas vary; optional CLI overrides make the output deterministic when a
    field is absent. We do not infer copyright status from API metadata.
    """
    overrides = overrides or {}
    language = _first(meta, "language", "language_name", default=None)
    language_code = _first(meta, "language_code", "languageCode", "iso", "iso_code", default=None)
    abbreviation = _first(meta, "abbreviation", "short_title", "shortTitle", default=f"BIBLECOM-{vid}")
    title = _first(meta, "title", "name", "full_name", "fullName", default=f"Bible.com version {vid}")
    publisher = _first(meta, "publisher", "publisher_name", "publisherName", default="Unknown publisher")
    if isinstance(publisher, dict):  # Bible.com: {"id": 2, "name": "Bible Society of South Africa", ...}
        publisher = publisher.get("name") or publisher.get("local_name") or "Unknown publisher"
    translator = _first(meta, "translator", "translation_by", "translationBy", default="Unknown translator")
    year = _first(meta, "year", "publication_year", "publicationYear", default=0)
    notes = _first(meta, "notes", "description", default="Metadata retrieved from Bible.com.")
    folder = _first(meta, "folder", default=None)

    # Accept common nested language metadata forms.
    lang_obj = meta.get("language")
    if isinstance(lang_obj, dict):
        language = _first(lang_obj, "name", "title", default=language)
        language_code = _first(lang_obj, "iso_639_1", "code", "iso", "iso_639_3", default=language_code)

    normalized = {
        "vid": int(vid),
        "title": str(overrides.get("title") or title),
        "abbreviation": str(overrides.get("abbreviation") or abbreviation),
        "language": str(overrides.get("language") or (language if isinstance(language, str) else "Unknown language")),
        "language_code": str(overrides.get("language_code") or language_code or "und"),
        "lang": str(overrides.get("lang") or language_code or "und").lower(),
        "folder": str(overrides.get("folder") or folder or (language_code or "und").lower()),
        "translator": str(overrides.get("translator") or translator),
        "publisher": str(overrides.get("publisher") or publisher),
        "year": int(overrides.get("year") or year or 0),
        "notes": str(overrides.get("notes") or notes),
    }
    return normalized


def chapter_refs(meta):
    """Canonical chapters of the 66 books, in the app's order."""
    refs = []
    for book in meta.get("books") or []:
        code = book.get("usfm")
        if code not in BOOKNUM:
            continue
        for chapter in book.get("chapters") or []:
            usfm = chapter.get("usfm", "")
            if chapter.get("canonical", True) and usfm.split(".")[-1].isdigit():
                refs.append(usfm)
    return sorted(set(refs), key=lambda r: (BOOKNUM[r.split(".")[0]], int(r.split(".")[1])))


def cache_status(c, vid):
    cache = cache_dir(c, vid)
    done = len(list(cache.glob("*.*.json"))) if cache.exists() else 0
    meta_path = cache / "_version.json"
    total = None
    if meta_path.exists():
        try:
            total = len(chapter_refs(json.loads(meta_path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, KeyError, TypeError):
            total = None
    return done, total


def cmd_list(c, _a):
    root = c["cache_root"]
    if not root.exists():
        print("No Bible.com version caches found.")
        return
    found = False
    for path in sorted(root.iterdir(), key=lambda p: p.name):
        if not path.is_dir() or not path.name.isdigit():
            continue
        found = True
        vid = int(path.name)
        meta_path = path / "_version.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        pd = normalize_metadata(meta, vid)
        done, total = cache_status(c, vid)
        print(f"{vid}  {pd['language']}  {pd['abbreviation']}  {pd['title']}")
        print(f"     Chapters in cache: {done}/{total if total is not None else '?'}")
    if not found:
        print("No Bible.com version caches found.")


def get_overrides(args):
    return {key: getattr(args, key, None) for key in
            ("title", "abbreviation", "language", "language_code", "lang", "folder",
             "translator", "publisher", "year", "notes") if getattr(args, key, None) is not None}


def cmd_get(c, a):
    vids = discover_cached_ids(c) if a.vid == "all" else [safe_version_id(a.vid)]
    if not vids:
        fail("No cached Bible.com version IDs found; specify a numeric version ID.")
    fetcher = Fetcher()
    budget = a.max
    for vid in vids:
        meta = version_meta(c, vid, fetcher)
        refs = chapter_refs(meta)
        if not refs:
            fail(f"No chapter references found in Bible.com metadata for version {vid}.")
        cache = cache_dir(c, vid)
        missing = [ref for ref in refs if not (cache / f"{ref}.json").exists()]
        print(f"{vid}: {len(refs) - len(missing)}/{len(refs)} chapters in cache, "
              f"{len(missing)} to download (~{len(missing) * MIN_INTERVAL_S / 60:.0f} min)")
        for i, ref in enumerate(missing, 1):
            if budget is not None and budget <= 0:
                print("Stopped at --max; run it again to continue.")
                return
            raw = fetcher.get(CHAPTER_URL.format(vid=vid, ref=ref))
            try:
                content = json.loads(raw).get("content", "")
            except json.JSONDecodeError:
                fail(f"{ref}: invalid chapter response from Bible.com (nothing saved for it).")
            if not content:
                fail(f"{ref}: empty chapter from Bible.com (nothing saved for it).")
            (cache / f"{ref}.json").write_text(
                json.dumps({"content": content}, ensure_ascii=False), encoding="utf-8")
            if budget is not None:
                budget -= 1
            if i % 25 == 0 or i == len(missing):
                print(f"  {ref} ({i}/{len(missing)})", flush=True)
        # A --max-limited run is intentionally allowed to leave a partial cache.
        remaining = [ref for ref in refs if not (cache / f"{ref}.json").exists()]
        if not remaining:
            build(c, vid, get_overrides(a))
        elif budget is not None and budget <= 0:
            print(f"Partial cache saved for {vid}; {len(remaining)} chapters remain. "
                  "Run the command again without --max to continue.")



def cmd_get_book(c, a):
    """Download one canonical book and write it as its own structured JSON file."""
    vid = safe_version_id(a.vid)
    book_code = a.book.upper()
    if book_code not in BOOKNUM:
        fail(f"Unknown book code {a.book!r}. Use a USFM code such as GEN, EXO, PSA, MAT, or JHN.")
        
    fetcher = Fetcher()
    meta = version_meta(c, vid, fetcher)
    refs = [ref for ref in chapter_refs(meta) if ref.split(".")[0] == book_code]
    if not refs:
        fail(f"No chapter references found for {book_code} in version {vid}.")
    cache = cache_dir(c, vid)
    missing = [ref for ref in refs if not (cache / f"{ref}.json").exists()]
    print(f"{vid} {book_code}: {len(refs) - len(missing)}/{len(refs)} chapters in cache, "
          f"{len(missing)} to download (~{len(missing) * MIN_INTERVAL_S / 60:.0f} min)")
    budget = a.max
    for i, ref in enumerate(missing, 1):
        if budget is not None and budget <= 0:
            print("Stopped at --max; run the same command again to continue.")
            return
        raw = fetcher.get(CHAPTER_URL.format(vid=vid, ref=ref))
        try:
            content = json.loads(raw).get("content", "")
        except json.JSONDecodeError:
            fail(f"{ref}: invalid chapter response from Bible.com (nothing saved for it).")
        if not content:
            fail(f"{ref}: empty chapter from Bible.com (nothing saved for it).")
        (cache / f"{ref}.json").write_text(
            json.dumps({"content": content}, ensure_ascii=False), encoding="utf-8")
        if budget is not None:
            budget -= 1
        print(f"  {ref} ({i}/{len(missing)})", flush=True)

    remaining = [ref for ref in refs if not (cache / f"{ref}.json").exists()]
    if remaining:
        print(f"Partial book cache saved; {len(remaining)} chapters remain. Run the command again to continue.")
        return

    pd = normalize_metadata(meta, vid, get_overrides(a))
    chapters, verses_total, empty = [], 0, []
    for ref in refs:
        chapter_num = int(ref.split(".")[1])
        content = json.loads((cache / f"{ref}.json").read_text(encoding="utf-8"))["content"]
        verses = parse_chapter(content)
        if not any(v > 0 for v in verses):
            empty.append(ref)
        chapters.append({"chapter": chapter_num, "verses": [
            {"chapter": chapter_num, "verse": verse, "text": text}
            for verse, text in sorted(verses.items())]})
        verses_total += sum(1 for verse in verses if verse > 0)
    if empty:
        fail(f"Chapters without verses (the HTML changed?): {', '.join(empty)}")

    
    out = {
        "translation": pd["title"], "abbreviation": pd["abbreviation"],
        "description": f"{pd['title']} — {book_code}",
        "lang": pd["language_code"], "language": pd["language"],
        "distribution_about": f"{pd['title']}. {pd['translator']}. {pd['publisher']}. {pd['notes']}",
        "distribution_source": PAGE_URL.format(vid=vid, ref=refs[0]),
        "distribution_version_date": TODAY,
        "books": [{"nr": BOOKNUM[book_code], "name": book_code, "chapters": chapters}],
    }
    dest_dir = c["bibles_dir"] / resolve_folder(c, pd, get_overrides(a))
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"biblecom_{vid}_{book_code}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {dest} ({dest.stat().st_size / 1e6:.2f} MB, {len(chapters)} chapters, {verses_total} verses)")

def discover_cached_ids(c):
    root = c["cache_root"]
    if not root.exists():
        return []
    return sorted(int(p.name) for p in root.iterdir() if p.is_dir() and p.name.isdigit())


def cmd_build(c, a):
    vid = safe_version_id(a.vid)
    build(c, vid, get_overrides(a))


def build(c, vid, overrides=None):
    cache = cache_dir(c, vid)
    meta_path = cache / "_version.json"
    if not meta_path.exists():
        fail(f"No version metadata cached for {vid}: run `download.py get {vid} ...` first.")
    raw_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    pd = normalize_metadata(raw_meta, vid, overrides)
    refs = chapter_refs(raw_meta)
    if not refs:
        fail(f"No canonical chapters found in cached metadata for version {vid}.")
    missing = [ref for ref in refs if not (cache / f"{ref}.json").exists()]
    if missing:
        fail(f"{len(missing)} chapters still missing ({', '.join(missing[:5])}...): run `download.py get {vid} ...`.")

    books, verses_total, empty_chapters = {}, 0, []
    for ref in refs:
        code, ch = ref.split(".")[0], int(ref.split(".")[1])
        content = json.loads((cache / f"{ref}.json").read_text(encoding="utf-8"))["content"]
        verses = parse_chapter(content)
        if not any(v > 0 for v in verses):
            empty_chapters.append(ref)
        book = books.setdefault(code, {"nr": BOOKNUM[code], "name": code, "chapters": []})
        book["chapters"].append({"chapter": ch, "verses": [
            {"chapter": ch, "verse": verse, "text": text}
            for verse, text in sorted(verses.items())]})
        verses_total += sum(1 for verse in verses if verse > 0)
    if empty_chapters:
        fail(f"Chapters without verses (the HTML changed?): {', '.join(empty_chapters[:10])}")

    about = f"{pd['title']}. {pd['translator']}. {pd['publisher']}. {pd['notes']}"
    out = {
        "translation": pd["title"], "abbreviation": pd["abbreviation"], "description": pd["title"],
        "lang": pd["language_code"], "language": pd["language"],
        "distribution_about": about,
        "distribution_source": PAGE_URL.format(vid=vid, ref="GEN.1" if "GEN" in books else "MAT.1"),
        "distribution_version_date": TODAY,
        "books": [books[book] for book in BOOKS if book in books],
    }
    pd["folder"] = resolve_folder(c, pd, overrides or {})
    dest = c["bibles_dir"] / pd["folder"] / f"biblecom_{vid}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    register(c, vid, dest, pd, len(books), verses_total)
    print(f"OK: {dest} ({dest.stat().st_size / 1e6:.1f} MB, {len(books)} books, {verses_total} verses)")


def register(c, vid, dest, pd, books, verses):
    """Update languages/manifest.json and, if present, pack.json."""
    sid = f"biblecom_{vid}"
    entry = {
        "tracker_code": pd["lang"], "language": pd["language"], "language_code": pd["language_code"],
        "folder": pd["folder"], "file": dest.name, "source": "Bible.com (public domain/authorized text)",
        "id": sid, "title": pd["title"], "short_title": pd["abbreviation"], "year": pd["year"],
        "books": books, "verses": verses, "copyright": f"{pd['translator']}; {pd['publisher']}",
        "licence_url": PAGE_URL.format(vid=vid, ref="JHN.1"),
        "download_url": CHAPTER_URL.format(vid=vid, ref="<BOOK.CH>"),
        "format": "getBible v2 JSON: books[nr, chapters[verses[chapter, verse, text]]]",
        "bytes": dest.stat().st_size, "sha256": sha256_file(dest), "downloaded": TODAY,
        "notes": pd["notes"],
    }
    save_entry(c, entry)

    offer_in_pack(c, pd["lang"], entry)


def offer_in_pack(c, lang, entry):
    """If the language already has a pack.json, the Bible is offered there with include=false (step 2 decides)."""
    ppath = c["packs_dir"] / lang_dir(lang) / "pack.json" if c["packs_dir"] else None
    if not ppath or not ppath.exists():
        print(f"Next (step 2, bible-language-pack): pack.py init {lang}")
        return
    pack = json.loads(ppath.read_text(encoding="utf-8"))
    if not any(b.get("id") == entry["id"] for b in pack.get("bibles", [])):
        pack.setdefault("bibles", []).append({
            "id": entry["id"], "file": f"{entry['folder']}/{entry['file']}", "source": entry["source"], "title": entry["title"],
            "books": entry["books"], "licence": entry.get("licence", ""), "non_commercial": False, "include": False,
            "abbreviation": "", "description": entry["title"], "attribution": entry["copyright"],
            "rejected": False, "notes": entry["notes"]})
        ppath.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Added to {ppath} as {entry['id']} (include=false: choose it there)")
    print(f"Next (step 2, bible-language-pack): choose it in pack.json and run  pack.py import {lang}")


def save_entry(c, entry):
    """Adds or replaces the entry of languages/manifest.json."""
    mpath = c["manifest"]
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {"bibles": [], "count": 0}
    manifest["bibles"] = [b for b in manifest.get("bibles", []) if b.get("id") != entry["id"]] + [entry]
    manifest["count"] = len(manifest["bibles"])
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_getbible(c, a):
    """A whole getBible translation (api.getbible.net/v2/<abbr>.json) in ONE request, never chapter by chapter."""
    if not c["packs_dir"]:
        fail("getbible needs Modules/config.json (no --output-dir)")
    folder = f"{lang_dir(a.lang)}/sources"
    dest = c["bibles_dir"] / folder / f"getbible_{a.abbr}.json"
    url = f"https://api.getbible.net/v2/{a.abbr}.json"
    if dest.exists():
        print(f"Already downloaded: {dest} (no request)")
    else:
        print(f"Downloading {url} (one request)...")
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bible-versions; one download)"})
        dest.write_bytes(urllib.request.urlopen(req, timeout=300).read())
    d = json.loads(dest.read_text(encoding="utf-8"))
    canon = [b for b in d["books"] if 1 <= int(b["nr"]) <= 66]
    entry = {"tracker_code": a.lang, "language": d.get("language", ""), "language_code": d.get("lang", ""), "folder": folder,
             "file": dest.name, "source": "getBible.net (CrossWire SWORD)", "id": f"getbible_{a.abbr}",
             "title": d.get("description") or d.get("translation", ""), "short_title": d.get("translation", ""),
             "books": len(canon), "copyright": (d.get("distribution_about") or "")[:400],
             "licence": d.get("distribution_license", ""), "licence_url": f"https://getbible.net/{a.abbr}", "download_url": url,
             "format": "getBible v2 JSON: books[nr, chapters[verses[chapter, verse, text]]]", "bytes": dest.stat().st_size,
             "sha256": sha256_file(dest), "downloaded": TODAY,
             "notes": f"Source: {d.get('distribution_source', '')}; SWORD {d.get('distribution_abbreviation', '')} "
                      f"{d.get('distribution_version', '')} ({d.get('distribution_version_date', '')}); "
                      f"versification {d.get('distribution_versification', '')}"}
    save_entry(c, entry)
    print(f"OK: {dest} ({entry['bytes'] / 1e6:.1f} MB, {len(canon)} books of the 66, licence {entry['licence']})")
    offer_in_pack(c, a.lang, entry)


def add_metadata_arguments(parser):
    parser.add_argument("--title")
    parser.add_argument("--abbreviation")
    parser.add_argument("--language")
    parser.add_argument("--language-code")
    parser.add_argument("--lang", help="Project tracker language code (overrides API-derived value).")
    parser.add_argument("--folder", help="Output subfolder under the selected output directory.")
    parser.add_argument("--translator")
    parser.add_argument("--publisher")
    parser.add_argument("--year", type=int)
    parser.add_argument("--notes")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output-dir", default=None,
                    help="Isolated test folder for cache, Bible JSON files and manifest "
                         "(default: Modules/config.json and its folder).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List versions already present in the cache.")

    get_parser = sub.add_parser("get", help="Download a Bible.com version by numeric ID.")
    get_parser.add_argument("vid", help="Numeric Bible.com version ID, or 'all' cached IDs.")
    get_parser.add_argument("--max", type=int, default=None,
                            help="At most this many chapter requests in this run.")
    add_metadata_arguments(get_parser)

    book_parser = sub.add_parser("get-book", help="Download one book and save it as an individual JSON file.")
    book_parser.add_argument("vid", help="Numeric Bible.com version ID.")
    book_parser.add_argument("book", help="USFM book code, e.g. GEN, EXO, PSA, MAT, JHN.")
    book_parser.add_argument("--max", type=int, default=None,
                             help="At most this many chapter requests in this run.")

    add_metadata_arguments(book_parser)

    gb_parser = sub.add_parser("getbible", help="Download a whole getBible translation in one request.")
    gb_parser.add_argument("abbr", help="Abbreviation of api.getbible.net/v2/translations.json, e.g. synodal.")
    gb_parser.add_argument("--lang", required=True, help="Tracker code of the language, e.g. ru.")

    build_parser = sub.add_parser("build", help="Build output JSON from a completed cache.")
    build_parser.add_argument("vid", help="Numeric Bible.com version ID.")
    add_metadata_arguments(build_parser)

    args = ap.parse_args()
    config = load_config(args.output_dir)
    {"list": cmd_list, "get": cmd_get, "get-book": cmd_get_book, "build": cmd_build, "getbible": cmd_getbible}[args.cmd](config, args)


if __name__ == "__main__":
    main()
