"""reapply.py <lang> <bible>: after changing typography/editor_notes, recompute the fixes of one Bible.

The override/typo/split_words decisions store the whole verse in criteria_overrides, so a new cleaning rule would
not reach those verses. This drops that Bible's criteria_overrides and puts its resolved text decisions (typo,
split_words, dedupe, use_source, override, ligature) back among the issues. Then: pack.py import, validate, apply."""
import json, os, sys
from pathlib import Path

lang, bid = sys.argv[1:3]
cfg = Path(os.environ.get("BIBLE_PACK_CONFIG") or Path(__file__).with_name("config.json"))
P = Path(json.load(open(cfg, encoding="utf-8"))["packs_dir"]) / lang
p = json.load(open(P / "pack.json", encoding="utf-8"))
for b in p["bibles"]:
    if b["id"] == bid:
        b.pop("criteria_overrides", None)
json.dump(p, open(P / "pack.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
c = json.load(open(P / "criteria.json", encoding="utf-8"))
keep, back = [], 0
for e in c["resolved"]:
    a = (e.get("decision") or {}).get("action")
    if e["bible"] == bid and a in ("typo", "split_words", "dedupe", "use_source", "override", "ligature"):
        e.pop("status", None)
        c["issues"].append(e)
        back += 1
    else:
        keep.append(e)
c["resolved"] = keep
json.dump(c, open(P / "criteria.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{back} decisions back to issues. Next: pack.py import {lang}, validate, apply")
