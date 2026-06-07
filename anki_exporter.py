#!/usr/bin/env python3
"""
Generate Anki-compatible CSV flashcard decks from the vocabulary database.

Usage:
    python anki_exporter.py                  # Generate all decks
    python anki_exporter.py --deck SAT       # Specific deck only

Output: anki_decks/*.csv — ready to import into Anki (File → Import).
"""

import csv
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path("/Users/jiangwei/Claude/English_Vocabulary")
DB_PATH = PROJECT / "vocab.db"
ANKI_DIR = PROJECT / "anki_decks"

DECKS = {
    "SAT_priority": {
        "description": "SAT words appearing in 3+ issues",
        "query": """
            SELECT w.word, w.phonetic, w.chinese, w.english_def, w.pos,
                   w.cefr, w.total_count, w.issue_count,
                   GROUP_CONCAT(DISTINCT SUBSTR(o.issue_date, 1, 7)) as months,
                   MAX(o.sample_sentence) as sentence
            FROM words w
            LEFT JOIN occurrences o ON o.word_id = w.id
            WHERE w.sat = 1 AND w.is_common = 0 AND w.issue_count >= 3
            GROUP BY w.id
            ORDER BY w.total_count DESC
            LIMIT 500
        """,
    },
    "GRE_frontier": {
        "description": "GRE words appearing in 1-2 issues (your growth edge)",
        "query": """
            SELECT w.word, w.phonetic, w.chinese, w.english_def, w.pos,
                   w.cefr, w.total_count, w.issue_count,
                   GROUP_CONCAT(DISTINCT SUBSTR(o.issue_date, 1, 7)) as months,
                   MAX(o.sample_sentence) as sentence
            FROM words w
            LEFT JOIN occurrences o ON o.word_id = w.id
            WHERE w.gre = 1 AND w.is_common = 0 AND w.issue_count BETWEEN 1 AND 2
            GROUP BY w.id
            ORDER BY w.total_count DESC
            LIMIT 500
        """,
    },
    "Economist_Core": {
        "description": "Words unique to The Economist (not on any standard list)",
        "query": """
            SELECT w.word, w.phonetic, w.chinese, w.english_def, w.pos,
                   w.cefr, w.total_count, w.issue_count,
                   GROUP_CONCAT(DISTINCT SUBSTR(o.issue_date, 1, 7)) as months,
                   MAX(o.sample_sentence) as sentence
            FROM words w
            LEFT JOIN occurrences o ON o.word_id = w.id
            WHERE w.sat = 0 AND w.gre = 0 AND w.cefr IS NULL
              AND w.is_common = 0 AND w.issue_count >= 3
            GROUP BY w.id
            ORDER BY w.total_count DESC
            LIMIT 500
        """,
    },
    "This_Week": {
        "description": "New vocabulary from the latest issue",
        "query": """
            SELECT w.word, w.phonetic, w.chinese, w.english_def, w.pos,
                   w.cefr, w.total_count, w.issue_count,
                   GROUP_CONCAT(DISTINCT SUBSTR(o.issue_date, 1, 7)) as months,
                   o2.sample_sentence as sentence
            FROM words w
            JOIN occurrences o ON o.word_id = w.id
            LEFT JOIN occurrences o2 ON o2.word_id = w.id
                AND o2.issue_date = (SELECT MAX(issue_date) FROM occurrences)
            WHERE o.issue_date = (SELECT MAX(issue_date) FROM occurrences)
              AND w.is_common = 0
            GROUP BY w.id
            ORDER BY w.total_count DESC
            LIMIT 100
        """,
    },
}


def build_tags(row):
    """Build Anki tags string from word metadata."""
    tags = []

    # Difficulty tier
    cefr = row["cefr"]
    if cefr:
        tags.append(f"CEFR::{cefr}")

    # Test-prep
    # We check the DECKS context — but since we don't have sat/gre in the query,
    # we infer from the deck name. Actually, let's add them.
    # For now, just use CEFR.

    # Source section — we don't have section data easily, skip for now

    # Quarter from months
    months = row["months"] or ""
    if months:
        # e.g., "2025-01, 2025-03" → tag "2025-Q1"
        years_qs = set()
        for m in months.split(","):
            m = m.strip()
            if "-" in m:
                y, mo = m.split("-")
                q = f"{y}-Q{(int(mo)-1)//3 + 1}"
                years_qs.add(q)
        for q in sorted(years_qs):
            tags.append(q)

    return " ".join(tags)


def build_front(row):
    """Build Anki card front: word, phonetic, example sentence."""
    word = row["word"]
    phonetic = row["phonetic"] or ""
    sentence = row["sentence"] or ""

    parts = [word]
    if phonetic:
        parts.append(f"/{phonetic}/")
    parts.append("")
    if sentence:
        parts.append(f"_{sentence}_")
    else:
        parts.append(f"_[The Economist — {row['months'] or 'multiple issues'}]_")

    return "\n".join(parts)


def build_back(row):
    """Build Anki card back: Chinese, English definition, POS, metadata."""
    word = row["word"]
    chinese = row["chinese"] or ""
    english_def = row["english_def"] or ""
    pos = row["pos"] or ""
    cefr = row["cefr"] or ""
    count = row["total_count"]
    issues = row["issue_count"]

    lines = []
    lines.append(f"## {word}")
    lines.append("")

    if chinese:
        lines.append(f"**Chinese:** {chinese}")
    if english_def:
        lines.append(f"**English:** {english_def}")
    if pos:
        lines.append(f"**POS:** {pos}")
    if cefr:
        lines.append(f"**CEFR:** {cefr}")

    lines.append("")
    lines.append(f"📊 Appears in {issues} issue(s) · {count} occurrences")

    return "\n".join(lines)


def export_deck(name, config):
    """Export one deck to CSV."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    rows = db.execute(config["query"]).fetchall()
    db.close()

    if not rows:
        print(f"  {name}: ❌ No matching words found")
        return

    outpath = ANKI_DIR / f"{name}.csv"
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Front", "Back", "Tags"])
        for r in rows:
            writer.writerow([
                build_front(r),
                build_back(r),
                build_tags(r),
            ])

    print(f"  {name}: ✅ {len(rows)} cards → {outpath}")


def main():
    ANKI_DIR.mkdir(parents=True, exist_ok=True)

    requested = None
    if len(sys.argv) > 2 and sys.argv[1] == "--deck":
        requested = sys.argv[2]

    print(f"Generating Anki decks ({datetime.now().strftime('%Y-%m-%d')})...")

    for name, config in DECKS.items():
        if requested and name != requested:
            continue
        print(f"  {name} — {config['description']}")
        export_deck(name, config)

    print(f"\nDecks saved to {ANKI_DIR}/")
    print("Import into Anki: File → Import → select .csv file")


if __name__ == "__main__":
    main()
