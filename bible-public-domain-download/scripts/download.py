"""Downloads public domain Bibles that only exist on Bible.com, for the language packs of Bible Versions.

Only the versions in PUBLIC_DOMAIN can be downloaded: each one with the reason it is in the public domain
(the age of the text and of its translator). Licensed texts are never downloaded from Bible.com: those are
asked from their Bible Society (bible-language-pack).

  download.py list                      the versions, why they are public domain, and how far each download is
  download.py get <vid|all> [--max N]   downloads chapter by chapter (one request every 4 s, cached: it resumes
                                        where it stopped), then builds the Bible and registers it
  download.py build <vid>               builds the Bible again from the cache and registers it (no requests)

The result is a getBible v2 JSON (`biblecom_<vid>.json` in the language's folder of BibleVersionsSelected), which
`pack.py import` reads like any other getBible file. It is added to bibles-manifest.json and, if the language
already has a pack.json, to it with include=false (as `pack.py fetch` does).

Paths come from bible-language-pack's scripts/config.json (or --config).
"""
import argparse
import datetime
import hashlib
import html.parser
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE.parent.parent / "bible-language-pack" / "scripts" / "config.json"

CHAPTER_URL = "https://nodejs.bible.com/api/bible/chapter/3.1?id={vid}&reference={ref}"
VERSION_URL = "https://nodejs.bible.com/api/bible/version/3.1?id={vid}"
PAGE_URL = "https://www.bible.com/bible/{vid}/{ref}"
MIN_INTERVAL_S = 4.0
USER_AGENT = "Mozilla/5.0 (bible-versions; public domain text, low volume)"

BOOKS = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZK DAN HOS "
         "JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM "
         "HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
BOOKNUM = {b: i for i, b in enumerate(BOOKS, 1)}

# The only versions this script downloads. Checked on 2026-10-23 against the Bible.com version metadata.
PUBLIC_DOMAIN = {
    3526: {
        "lang": "xh", "language": "Xhosa", "language_code": "xh", "folder": "XH-Xhosa/bibles",
        "abbreviation": "XHO1902", "title": "Incwadi Yezibalo Ezingcwele (Appleyard, 1864/1902)",
        "year": "1902", "books": 66,
        "translator": "John Whittle Appleyard (1814-1874), Wesleyan Methodist missionary",
        "publisher": "British and Foreign Bible Society, 1902",
        "reason": "Text first published in 1864 and in this edition in 1902; the translator died in 1874. "
                  "Public domain everywhere (more than 120 years, author dead for more than 150).",
        "notes": "Old Xhosa spelling (before the 1950s orthography). Complete Bible, 66 books.",
    },
    805: {
        "lang": "gn", "language": "Guarani (Paraguayan)", "language_code": "gn", "folder": "GN-Guarani/bibles",
        "abbreviation": "GRN1913", "title": "Tûpâ Ñandeyára 1913 (Paraguayan Guarani New Testament)",
        "year": "1913", "books": 27,
        "translator": "Dr. John William Lindsay (1875-1946), Scottish medical missionary in Belén, Paraguay",
        "publisher": "British and Foreign Bible Society, 1913; digitized by the Paraguayan Bible Society, 2013",
        "reason": "Text printed in 1913; the translator died in 1946, so it is in the public domain in Paraguay "
                  "(life + 70 years, since 2017) and in the United States (published before 1929). The 2013 "
                  "digitization only transcribes that text.",
        "notes": "New Testament only (27 books), translated from the Greek. Paraguayan Guarani, not Mbyá.",
    },
}

TODAY = datetime.date.today().isoformat()


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def cfg(path):
    p = Path(path)
    if not p.exists():
        fail(f"No config at {p} (bible-language-pack's scripts/config.json, or pass --config)")
    c = json.loads(p.read_text(encoding="utf-8"))
    return {k: Path(v) if k.endswith("_dir") else v for k, v in c.items()}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class Fetcher:
    """One request every MIN_INTERVAL_S; a 403 or 429 stops the run (the cache keeps what was downloaded)."""

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
            return urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                fail(f"HTTP {e.code} from Bible.com: stopped. Run it again later; it resumes from the cache.")
            raise


class ChapterParser(html.parser.HTMLParser):
    """The verses of one chapter of Bible.com's HTML.

    Text is taken only from <span class="content"> inside a verse (<span class="verse" data-usfm="PSA.3.1">);
    a verse split across paragraphs is joined. Headings, notes, cross references and labels are left out. A Psalm
    title (<div class="d">) becomes verse 0, which pack.py joins to verse 1. A combined verse
    (data-usfm="GEN.1.1+GEN.1.2") keeps its text in the first one.
    """

    SKIP = {"heading", "note", "label", "x", "f", "fr", "ft", "xo", "xt"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # (tag, classes, verse or None, title)
        self.verses = {}

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


def parse_chapter(content_html):
    p = ChapterParser()
    p.feed(content_html)
    p.close()
    out = {}
    for v, text in p.verses.items():
        text = " ".join(text.split())
        if text:
            out[v] = text
    return out


def cache_dir(c, vid):
    return c["packs_dir"] / "_cache" / "biblecom_pd" / str(vid)


def version_meta(c, vid, fetcher):
    path = cache_dir(c, vid) / "_version.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fetcher.get(VERSION_URL.format(vid=vid)), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def chapter_refs(meta):
    """Canonical chapters of the 66 books, in the app's order."""
    refs = []
    for book in meta.get("books") or []:
        code = book.get("usfm")
        if code not in BOOKNUM:
            continue
        for ch in book.get("chapters") or []:
            if ch.get("canonical", True) and ch.get("usfm", "").split(".")[-1].isdigit():
                refs.append(ch["usfm"])
    return sorted(refs, key=lambda r: (BOOKNUM[r.split(".")[0]], int(r.split(".")[1])))


def check_vid(vid):
    if vid not in PUBLIC_DOMAIN:
        known = ", ".join(str(v) for v in PUBLIC_DOMAIN)
        fail(f"{vid} is not in PUBLIC_DOMAIN ({known}). Licensed Bibles are never downloaded from Bible.com: "
             "ask their Bible Society for the text (see bible-language-pack).")


def cmd_list(c, _a):
    for vid, pd in PUBLIC_DOMAIN.items():
        cache = cache_dir(c, vid)
        done = len(list(cache.glob("*.*.json"))) if cache.exists() else 0
        meta_path = cache / "_version.json"
        total = len(chapter_refs(json.loads(meta_path.read_text(encoding="utf-8")))) if meta_path.exists() else None
        out = c["bibles_dir"] / pd["folder"] / f"biblecom_{vid}.json"
        print(f"{vid}  {pd['lang']}  {pd['abbreviation']}  {pd['title']}")
        print(f"     {pd['translator']}; {pd['publisher']}")
        print(f"     Public domain: {pd['reason']}")
        print(f"     Chapters in cache: {done}/{total if total is not None else '?'}"
              f"{'  ->  ' + str(out) if out.exists() else ''}")


def cmd_get(c, a):
    vids = list(PUBLIC_DOMAIN) if a.vid == "all" else [int(a.vid)]
    for vid in vids:
        check_vid(vid)
    fetcher = Fetcher()
    budget = a.max
    for vid in vids:
        meta = version_meta(c, vid, fetcher)
        refs = chapter_refs(meta)
        cache = cache_dir(c, vid)
        missing = [r for r in refs if not (cache / f"{r}.json").exists()]
        print(f"{vid} {PUBLIC_DOMAIN[vid]['abbreviation']}: {len(refs) - len(missing)}/{len(refs)} chapters in cache, "
              f"{len(missing)} to download (~{len(missing) * MIN_INTERVAL_S / 60:.0f} min)")
        for i, ref in enumerate(missing, 1):
            if budget is not None and budget <= 0:
                print(f"Stopped at --max; run it again to continue.")
                return
            raw = fetcher.get(CHAPTER_URL.format(vid=vid, ref=ref))
            content = json.loads(raw).get("content", "")
            if not content:
                fail(f"{ref}: empty chapter from Bible.com (nothing saved for it)")
            (cache / f"{ref}.json").write_text(json.dumps({"content": content}, ensure_ascii=False), encoding="utf-8")
            if budget is not None:
                budget -= 1
            if i % 25 == 0 or i == len(missing):
                print(f"  {ref} ({i}/{len(missing)})", flush=True)
        build(c, vid)


def cmd_build(c, a):
    vid = int(a.vid)
    check_vid(vid)
    build(c, vid)


def build(c, vid):
    pd = PUBLIC_DOMAIN[vid]
    cache = cache_dir(c, vid)
    meta_path = cache / "_version.json"
    if not meta_path.exists():
        fail(f"No cache for {vid}: run `download.py get {vid}` first")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    refs = chapter_refs(meta)
    missing = [r for r in refs if not (cache / f"{r}.json").exists()]
    if missing:
        fail(f"{len(missing)} chapters still missing ({', '.join(missing[:5])}...): run `download.py get {vid}`")

    books, verses_total, empty_chapters = {}, 0, []
    for ref in refs:
        code, ch = ref.split(".")[0], int(ref.split(".")[1])
        content = json.loads((cache / f"{ref}.json").read_text(encoding="utf-8"))["content"]
        verses = parse_chapter(content)
        if not any(v > 0 for v in verses):
            empty_chapters.append(ref)
        book = books.setdefault(code, {"nr": BOOKNUM[code], "name": code, "chapters": []})
        book["chapters"].append({"chapter": ch, "verses": [
            {"chapter": ch, "verse": v, "text": t} for v, t in sorted(verses.items())]})
        verses_total += sum(1 for v in verses if v > 0)
    if empty_chapters:
        fail(f"Chapters without verses (the HTML changed?): {', '.join(empty_chapters[:10])}")

    licence = f"Public domain. {pd['reason']}"
    about = f"{pd['title']}. {pd['translator']}. {pd['publisher']}. {pd['notes']}"
    out = {
        "translation": pd["title"], "abbreviation": pd["abbreviation"], "description": pd["title"],
        "lang": pd["language_code"], "language": pd["language"],
        "distribution_license": licence, "distribution_about": about,
        "distribution_source": PAGE_URL.format(vid=vid, ref="GEN.1" if "GEN" in books else "MAT.1"),
        "distribution_version_date": TODAY,
        "books": [books[b] for b in BOOKS if b in books],
    }
    dest = c["bibles_dir"] / pd["folder"] / f"biblecom_{vid}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    register(c, vid, dest, len(books), verses_total)
    print(f"OK: {dest} ({dest.stat().st_size / 1e6:.1f} MB, {len(books)} books, {verses_total} verses)")


def register(c, vid, dest, books, verses):
    """bibles-manifest.json and, if the language already has one, pack.json (include=false, like pack.py fetch)."""
    pd = PUBLIC_DOMAIN[vid]
    sid = f"biblecom_{vid}"
    mpath = c["bibles_dir"] / "bibles-manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    entry = {"tracker_code": pd["lang"], "language": pd["language"], "language_code": pd["language_code"],
             "folder": pd["folder"], "file": dest.name, "source": "Bible.com (public domain text)", "id": sid,
             "title": pd["title"], "short_title": pd["abbreviation"], "year": pd["year"], "books": books,
             "verses": verses, "copyright": f"{pd['translator']}; {pd['publisher']}",
             "licence": f"Public domain. {pd['reason']}", "licence_url": PAGE_URL.format(vid=vid, ref="JHN.1"),
             "download_url": CHAPTER_URL.format(vid=vid, ref="<BOOK.CH>"),
             "format": "getBible v2 JSON: books[nr, chapters[verses[chapter, verse, text]]]",
             "bytes": dest.stat().st_size, "sha256": sha256_file(dest), "downloaded": TODAY, "notes": pd["notes"]}
    manifest["bibles"] = [b for b in manifest["bibles"] if b["id"] != sid] + [entry]
    manifest["count"] = len(manifest["bibles"])
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    ppath = c["packs_dir"] / pd["lang"] / "pack.json"
    if not ppath.exists():
        print(f"  {pd['lang']} has no pack.json yet: `pack.py init {pd['lang']}` will offer {sid}")
        return
    pack = json.loads(ppath.read_text(encoding="utf-8"))
    if any(b["id"] == sid for b in pack["bibles"]):
        return
    pack["bibles"].append({"id": sid, "file": f"{pd['folder']}/{dest.name}", "source": entry["source"],
                           "title": pd["title"], "books": books, "licence": entry["licence"], "non_commercial": False,
                           "include": False, "abbreviation": pd["abbreviation"], "description": pd["title"],
                           "attribution": entry["copyright"], "rejected": False, "notes": pd["notes"]})
    ppath.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Added to {ppath} as {sid} (include=false: choose it there)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    g = sub.add_parser("get")
    g.add_argument("vid", help="a Bible.com version id from PUBLIC_DOMAIN, or all")
    g.add_argument("--max", type=int, default=None, help="at most this many chapter requests in this run")
    b = sub.add_parser("build")
    b.add_argument("vid")
    a = ap.parse_args()
    c = cfg(a.config)
    {"list": cmd_list, "get": cmd_get, "build": cmd_build}[a.cmd](c, a)


if __name__ == "__main__":
    main()
