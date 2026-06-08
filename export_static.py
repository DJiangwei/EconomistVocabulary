#!/usr/bin/env python3
"""
Export vocabulary data as gzipped JSON for the static web app.
Run: python export_static.py
Output: static/data/words.json.gz (~3-5 MB compressed)
"""

import gzip
import json
import sqlite3
from pathlib import Path

PROJECT = Path("/Users/jiangwei/Claude/English_Vocabulary")
DB_PATH = PROJECT / "vocab.db"
OUTPUT = PROJECT / "static" / "data" / "words.json.gz"

db = sqlite3.connect(str(DB_PATH))
db.row_factory = sqlite3.Row

# Export all learning targets with essential fields + one sample sentence each
rows = db.execute("""
    SELECT w.id, w.word, w.phonetic, w.chinese, w.english_def, w.pos,
           w.cefr, w.sat, w.gre, w.total_count, w.issue_count, w.is_common,
           (SELECT o.sample_sentence FROM occurrences o
            WHERE o.word_id = w.id ORDER BY o.issue_date DESC LIMIT 1) as sample
    FROM words w
    WHERE w.is_common = 0
    ORDER BY w.total_count DESC
""").fetchall()

words = []
for r in rows:
    words.append({
        "id": r["id"],
        "w": r["word"],
        "p": r["phonetic"] or "",
        "c": r["chinese"] or "",
        "e": (r["english_def"] or "")[:200],
        "pos": r["pos"] or "",
        "cefr": r["cefr"] or "",
        "sat": bool(r["sat"]),
        "gre": bool(r["gre"]),
        "count": r["total_count"],
        "issues": r["issue_count"],
        "sample": r["sample"] or "",
    })

# Write gzipped JSON
data = json.dumps(words, ensure_ascii=False, separators=(",", ":"))
with gzip.open(OUTPUT, "wt", encoding="utf-8", compresslevel=9) as f:
    f.write(data)

raw_size = len(data) / (1024*1024)
gz_size = OUTPUT.stat().st_size / (1024*1024)
print(f"Exported {len(words):,} words")
print(f"  Raw: {raw_size:.1f} MB")
print(f"  Gzip: {gz_size:.1f} MB")
print(f"  Output: {OUTPUT}")
db.close()
