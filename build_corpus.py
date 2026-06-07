#!/usr/bin/env python3
"""
Build vocabulary database from extracted Economist text files.

Reads all .txt files, counts words, classifies by difficulty (SAT/GRE/CEFR),
looks up Chinese definitions (ECDICT), and populates vocab.db.

Usage:
    python build_corpus.py              # Full rebuild
    python build_corpus.py --incremental  # Only process new files (TODO)
"""

import csv
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path("/Users/jiangwei/Claude/English_Vocabulary")
TXT_DIR = PROJECT / "txt"
WL_DIR = PROJECT / "word_lists"
DB_PATH = PROJECT / "vocab.db"

# ── SQLite Schema ──────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    word_lower TEXT NOT NULL UNIQUE,
    total_count INTEGER DEFAULT 0,
    issue_count INTEGER DEFAULT 0,
    cefr TEXT,
    sat INTEGER DEFAULT 0,
    gre INTEGER DEFAULT 0,
    is_common INTEGER DEFAULT 0,
    chinese TEXT,
    english_def TEXT,
    phonetic TEXT,
    pos TEXT
);

CREATE TABLE IF NOT EXISTS occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL REFERENCES words(id),
    issue_date TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    sample_sentence TEXT
);

CREATE TABLE IF NOT EXISTS learning (
    word_id INTEGER PRIMARY KEY REFERENCES words(id),
    status TEXT DEFAULT 'new',
    review_count INTEGER DEFAULT 0,
    last_reviewed TEXT
);

CREATE INDEX IF NOT EXISTS idx_words_lower ON words(word_lower);
CREATE INDEX IF NOT EXISTS idx_words_sat ON words(sat);
CREATE INDEX IF NOT EXISTS idx_words_gre ON words(gre);
CREATE INDEX IF NOT EXISTS idx_words_cefr ON words(cefr);
CREATE INDEX IF NOT EXISTS idx_words_common ON words(is_common);
CREATE INDEX IF NOT EXISTS idx_words_issue_count ON words(issue_count);
CREATE INDEX IF NOT EXISTS idx_occ_word ON occurrences(word_id);
CREATE INDEX IF NOT EXISTS idx_occ_date ON occurrences(issue_date);
"""


# ── Word List Loaders ──────────────────────────────────────────

def load_ngsl(path: Path) -> set[str]:
    """Load NGSL — first column is lemma, rest are inflected forms."""
    common = set()
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            if row:
                for cell in row:
                    word = cell.strip().lower()
                    if word and word.isalpha():
                        common.add(word)
    print(f"  NGSL: {len(common):,} lemmas+forms loaded")
    return common


def load_nawl(path: Path) -> set[str]:
    """Load NAWL — first column is word, rest are inflected forms."""
    common = set()
    with open(path, encoding="latin-1") as f:
        for line in f:
            parts = line.strip().split(",")
            for p in parts:
                word = p.strip().lower()
                if word and word.isalpha():
                    common.add(word)
    print(f"  NAWL: {len(common):,} lemmas+forms loaded")
    return common


def load_sat(path: Path) -> tuple[dict[str, str], set[str]]:
    """Load SAT word list from JSON. Returns (word→def dict, word set)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    sat_words = {}
    for entry in data:
        w = entry.get("word", "").strip().lower()
        if w and w.isalpha():
            sat_words[w] = entry.get("def", "")
    print(f"  SAT: {len(sat_words):,} words loaded")
    return sat_words, set(sat_words.keys())


def load_gre(path: Path) -> set[str]:
    """Load GRE word list — one word per line."""
    gre_words = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if w and w.isalpha():
                gre_words.add(w)
    print(f"  GRE: {len(gre_words):,} words loaded")
    return gre_words


def load_cefr(path: Path) -> dict[str, str]:
    """Load CEFR dataset. Returns word→level dict (highest level wins)."""
    level_rank = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    cefr = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            w = row.get("Word", "").strip().lower()
            level = row.get("CEFR", "").strip().upper()
            if w and w.isalpha() and level in level_rank:
                if w not in cefr or level_rank[level] > level_rank.get(cefr[w], 0):
                    cefr[w] = level
    print(f"  CEFR: {len(cefr):,} words with levels")
    return cefr


def load_ecdict(path: Path) -> dict[str, dict]:
    """Load ECDICT — word→{chinese, english_def, phonetic, pos}."""
    ecdict = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 5:
                continue
            w = row[0].strip().lower()
            if not w or not w.isalpha():
                continue
            ecdict[w] = {
                "phonetic": row[1].strip() if len(row) > 1 else "",
                "english_def": row[2].strip() if len(row) > 2 else "",
                "chinese": row[3].strip() if len(row) > 3 else "",
                "pos": row[4].strip() if len(row) > 4 else "",
            }
    print(f"  ECDICT: {len(ecdict):,} entries loaded")
    return ecdict


# ── Text Processing ────────────────────────────────────────────

def process_text_file(txt_path: Path) -> tuple[str, dict[str, tuple[int, str]]]:
    """
    Process one text file.
    Returns (issue_date, {word: (count, sample_sentence)})

    Optimized: one pass through sentences builds both word counts and
    sample sentences, instead of O(words × sentences).
    """
    from collections import Counter

    # Extract date from filename: TheEconomist.YYYY.MM.DD.txt
    match = re.search(r"(\d{4}\.\d{2}\.\d{2})", txt_path.stem)
    issue_date = match.group(1) if match else txt_path.stem

    text = txt_path.read_text(encoding="utf-8")

    # Extract all alphabetic words (lowercased, min length 2)
    all_words = [w.lower() for w in re.findall(r"[a-zA-Z]{2,}", text)]
    word_counts = Counter(all_words)

    # One pass: split sentences, build word→first_sentence index
    sentences = re.split(r"(?<=[.!?])\s+", text)

    # For each sentence, record which words appear (first occurrence wins)
    word_sample: dict[str, str] = {}
    seen_in_this_file: set[str] = set()

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        # Extract unique words in this sentence
        sent_words = set(w.lower() for w in re.findall(r"[a-zA-Z]{2,}", sent))
        for w in sent_words:
            if w not in seen_in_this_file:
                seen_in_this_file.add(w)
                # Bold the word in the sentence (first occurrence only)
                window = 160
                marked = re.sub(
                    rf"\b({re.escape(w)})\b",
                    r"**\1**",
                    sent,
                    count=1,
                    flags=re.IGNORECASE,
                )
                # Truncate long sentences
                if len(marked) > window:
                    pos = marked.lower().find(f"**{w}**")
                    if pos < 0:
                        pos = len(marked) // 2
                    start = max(0, pos - window // 2)
                    end = min(len(marked), pos + window // 2)
                    marked = ("…" if start > 0 else "") + marked[start:end].strip() + ("…" if end < len(marked) else "")
                word_sample[w] = marked

    # Build result
    result = {}
    for word, count in word_counts.items():
        result[word] = (count, word_sample.get(word, ""))

    return issue_date, result


# ── Database Builder ───────────────────────────────────────────

def build_database(incremental: bool = False):
    """Main: load lists, process texts, populate database."""

    # 1. Load all reference lists
    print("Loading word lists...")
    common_words = load_ngsl(WL_DIR / "NGSL_raw.csv")
    common_words |= load_nawl(WL_DIR / "NAWL_raw.csv")
    print(f"  Total common words: {len(common_words):,}")

    sat_defs, sat_words = load_sat(WL_DIR / "SAT_raw.json")
    gre_words = load_gre(WL_DIR / "GRE_raw.csv")
    cefr = load_cefr(WL_DIR / "CEFR_raw.csv")
    ecdict = load_ecdict(WL_DIR / "ECDICT_raw.csv")

    # 2. Initialize database
    print("\nInitializing database...")
    db = sqlite3.connect(str(DB_PATH))
    db.executescript(SCHEMA)

    if not incremental:
        db.execute("DELETE FROM occurrences")
        db.execute("DELETE FROM words")
    db.commit()

    # 3. Process all text files
    txt_files = sorted(TXT_DIR.rglob("*.txt"))
    print(f"\nProcessing {len(txt_files)} text files...")

    # In-memory accumulator: word → {total_count, issue_set, first_sample}
    corpus: dict[str, dict] = {}

    start = datetime.now()
    for i, txt_path in enumerate(txt_files):
        issue_date, word_data = process_text_file(txt_path)
        print(f"  [{i+1:3d}/{len(txt_files)}] {issue_date} — {len(word_data)} unique words")

        for word, (count, sentence) in word_data.items():
            if word not in corpus:
                corpus[word] = {
                    "total_count": 0,
                    "issues": set(),
                    "sample": sentence,
                }
            entry = corpus[word]
            entry["total_count"] += count
            entry["issues"].add(issue_date)
            # Keep first sample sentence found
            if not entry["sample"] and sentence:
                entry["sample"] = sentence

    elapsed = (datetime.now() - start).total_seconds()
    print(f"  Processed in {elapsed:.1f}s — {len(corpus):,} unique words in corpus")

    # 4. Write to database
    print("\nWriting to database...")
    db.execute("BEGIN TRANSACTION")

    insert_word_sql = """
        INSERT OR REPLACE INTO words
            (word, word_lower, total_count, issue_count, cefr, sat, gre, is_common, chinese, english_def, phonetic, pos)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    insert_occ_sql = """
        INSERT INTO occurrences (word_id, issue_date, count, sample_sentence)
        VALUES (?, ?, ?, ?)
    """

    written = 0
    for word_lower, data in corpus.items():
        # Classification
        is_common = 1 if word_lower in common_words else 0
        sat_flag = 1 if word_lower in sat_words else 0
        gre_flag = 1 if word_lower in gre_words else 0
        cefr_level = cefr.get(word_lower, None)

        # Dictionary lookup
        entry = ecdict.get(word_lower, {})
        chinese = entry.get("chinese", "")
        english_def = entry.get("english_def", "")
        phonetic = entry.get("phonetic", "")
        pos = entry.get("pos", "")

        db.execute(insert_word_sql, (
            word_lower,  # word (display form = lowercase for simplicity)
            word_lower,
            data["total_count"],
            len(data["issues"]),
            cefr_level,
            sat_flag,
            gre_flag,
            is_common,
            chinese,
            english_def,
            phonetic,
            pos,
        ))
        word_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Write occurrences (one row per issue)
        for issue in data["issues"]:
            # We don't have per-issue count in the compact accumulator,
            # but we store the first-encountered sample sentence
            db.execute(insert_occ_sql, (word_id, issue, 0, data["sample"]))

        written += 1

    db.commit()
    db.close()

    # 5. Stats
    db_size = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"\n{'='*50}")
    print(f"Database built: {DB_PATH}")
    print(f"  Unique words: {len(corpus):,}")
    print(f"  Non-common (learning targets): {sum(1 for w,d in corpus.items() if w not in common_words):,}")
    print(f"  DB size: {db_size:.1f} MB")
    print(f"  Total time: {(datetime.now() - start).total_seconds():.1f}s")


if __name__ == "__main__":
    incremental = "--incremental" in sys.argv
    build_database(incremental=incremental)
