#!/usr/bin/env python3
"""
Interactive CLI for querying the vocabulary database.

Usage:
    python query_tool.py top --tier sat --min-issues 3
    python query_tool.py frontier
    python query_tool.py economist-core
    python query_tool.py issue 2026.06.06
    python query_tool.py search inflation
    python query_tool.py word abate
    python query_tool.py stats
    python query_tool.py sql "SELECT ..."
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("/Users/jiangwei/Claude/English_Vocabulary/vocab.db")

TIER_LEVELS = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6}
TIER_RANK = {**TIER_LEVELS, "sat": 7, "gre": 8}


def connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ── Shared query builder ────────────────────────────────────────

def build_tier_filter(tier: str) -> str:
    """Convert tier name to SQL WHERE clause."""
    t = tier.lower()
    if t in TIER_LEVELS:
        return f"cefr = '{t.upper()}'"
    elif t == "sat":
        return "sat = 1"
    elif t == "gre":
        return "gre = 1"
    elif t == "all":
        return "is_common = 0"
    elif t == "core":
        return "sat = 0 AND gre = 0 AND cefr IS NULL AND is_common = 0"
    else:
        print(f"Unknown tier: {tier}. Use: a1,a2,b1,b2,c1,c2,sat,gre,all,core")
        sys.exit(1)


def format_output(rows, json_output=False):
    """Print rows as table or JSON."""
    if json_output:
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
        return
    if not rows:
        print("No results.")
        return
    try:
        from tabulate import tabulate
        headers = rows[0].keys()
        table = [[r[h] for h in headers] for r in rows]
        print(tabulate(table, headers=headers, tablefmt="simple", maxcolwidths=60))
    except ImportError:
        for r in rows:
            print(dict(r))


# ── Subcommands ─────────────────────────────────────────────────

def cmd_top(args):
    """Show top vocabulary words by tier."""
    tier_filter = build_tier_filter(args.tier)
    min_issues = args.min_issues or 2

    query = f"""
        SELECT word, total_count, issue_count,
               COALESCE(cefr, '') as cefr,
               CASE WHEN sat THEN 'SAT' ELSE '' END as sat_label,
               CASE WHEN gre THEN 'GRE' ELSE '' END as gre_label,
               chinese, pos
        FROM words
        WHERE {tier_filter} AND issue_count >= ? AND is_common = 0
        ORDER BY total_count DESC
        LIMIT ?
    """
    db = connect()
    rows = db.execute(query, (min_issues, args.limit)).fetchall()
    db.close()
    format_output(rows, args.json)


def cmd_frontier(args):
    """Show words at the frontier: seen 1-2 times, not common."""
    query = """
        SELECT word, total_count, issue_count, chinese,
               COALESCE(cefr, '') as cefr,
               CASE WHEN sat THEN 'SAT' ELSE '' END as sat,
               CASE WHEN gre THEN 'GRE' ELSE '' END as gre
        FROM words
        WHERE issue_count BETWEEN 1 AND ? AND is_common = 0
        ORDER BY total_count DESC
        LIMIT ?
    """
    db = connect()
    rows = db.execute(query, (args.max_issues, args.limit)).fetchall()
    db.close()
    format_output(rows, args.json)


def cmd_economist_core(args):
    """Show frequent words NOT on standard lists — Economist house vocab."""
    query = """
        SELECT word, total_count, issue_count, chinese, pos
        FROM words
        WHERE sat = 0 AND gre = 0 AND cefr IS NULL AND is_common = 0
          AND issue_count >= ?
        ORDER BY total_count DESC
        LIMIT ?
    """
    db = connect()
    rows = db.execute(query, (args.min_issues, args.limit)).fetchall()
    db.close()
    format_output(rows, args.json)


def cmd_issue(args):
    """Show vocabulary for a specific issue."""
    issue = args.issue
    if issue == "latest":
        db = connect()
        r = db.execute("SELECT MAX(issue_date) FROM occurrences").fetchone()
        issue = r[0] if r else None
        db.close()
        if not issue:
            print("No issues found in database.")
            return

    tier_filter = build_tier_filter(args.tier) if args.tier else "1=1"

    query = f"""
        SELECT w.word, w.total_count, w.issue_count, w.chinese,
               COALESCE(w.cefr, '') as cefr,
               CASE WHEN w.sat THEN 'SAT' ELSE '' END as sat,
               CASE WHEN w.gre THEN 'GRE' ELSE '' END as gre,
               o.sample_sentence
        FROM words w
        JOIN occurrences o ON o.word_id = w.id
        WHERE o.issue_date = ? AND w.is_common = 0 AND ({tier_filter})
        ORDER BY w.total_count DESC
        LIMIT ?
    """
    db = connect()
    rows = db.execute(query, (issue, args.limit)).fetchall()
    db.close()
    print(f"Issue: {issue} — {len(rows)} words")
    format_output(rows, args.json)


def cmd_search(args):
    """Search for words matching a pattern."""
    query = """
        SELECT word, total_count, issue_count, chinese, pos,
               COALESCE(cefr, '') as cefr
        FROM words
        WHERE word LIKE ? AND is_common = 0
        ORDER BY total_count DESC
        LIMIT ?
    """
    db = connect()
    rows = db.execute(query, (f"%{args.query}%", args.limit)).fetchall()
    db.close()
    format_output(rows, args.json)


def cmd_word(args):
    """Show full details for a specific word."""
    query = """
        SELECT w.*, GROUP_CONCAT(o.issue_date, ', ') as issues,
               MAX(o.sample_sentence) as best_sample
        FROM words w
        LEFT JOIN occurrences o ON o.word_id = w.id
        WHERE w.word_lower = ?
        GROUP BY w.id
    """
    db = connect()
    row = db.execute(query, (args.word.lower(),)).fetchone()
    db.close()

    if not row:
        print(f"Word '{args.word}' not found in corpus.")
        return

    d = dict(row)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(f"Word:       {d['word']}")
        print(f"Phonetic:   {d['phonetic']}")
        print(f"POS:        {d['pos']}")
        print(f"Chinese:    {d['chinese']}")
        print(f"English:    {d['english_def']}")
        print(f"Count:      {d['total_count']} occurrences in {d['issue_count']} issues")
        print(f"CEFR:       {d['cefr'] or '—'}")
        print(f"SAT:        {'✓' if d['sat'] else '—'}")
        print(f"GRE:        {'✓' if d['gre'] else '—'}")
        print(f"Common:     {'✓' if d['is_common'] else '—'}")
        print(f"Issues:     {d['issues'] or '—'}")
        if d['best_sample']:
            print(f"Sentence:   {d['best_sample']}")


def cmd_stats(args):
    """Show corpus statistics."""
    db = connect()

    total = db.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    learning = db.execute("SELECT COUNT(*) FROM words WHERE is_common = 0").fetchone()[0]
    issues = db.execute("SELECT COUNT(DISTINCT issue_date) FROM occurrences").fetchone()[0]
    total_words = db.execute("SELECT SUM(total_count) FROM words").fetchone()[0] or 0

    print(f"Corpus:  {issues} issues, {total_words:,} total words")
    print(f"Words:   {total:,} unique ({learning:,} learning targets)")
    print(f"DB:      {DB_PATH.stat().st_size / (1024*1024):.1f} MB")

    if args.by_tier:
        print()
        tiers = [
            ("A1", "cefr = 'A1'"),
            ("A2", "cefr = 'A2'"),
            ("B1", "cefr = 'B1'"),
            ("B2", "cefr = 'B2'"),
            ("C1", "cefr = 'C1'"),
            ("C2", "cefr = 'C2'"),
            ("SAT", "sat = 1"),
            ("GRE", "gre = 1"),
            ("Economist Core", "sat=0 AND gre=0 AND cefr IS NULL AND is_common=0 AND issue_count>=3"),
            ("Common (filtered)", "is_common = 1"),
        ]
        for label, where in tiers:
            count = db.execute(f"SELECT COUNT(*) FROM words WHERE {where}").fetchone()[0]
            print(f"  {label:20s}: {count:,}")

    db.close()


def cmd_sql(args):
    """Run raw SQL query (read-only)."""
    db = connect()
    try:
        rows = db.execute(args.query).fetchall()
        format_output(rows, args.json)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


# ── CLI ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Query the Economist Vocabulary Database",
        epilog="Examples: python query_tool.py top --sat --min-issues 3\n"
               "          python query_tool.py word abate\n"
               "          python query_tool.py issue latest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Commands")

    # top
    p = sub.add_parser("top", help="Top words by tier")
    p.add_argument("--tier", default="all", help="Tier: a1,a2,b1,b2,c1,c2,sat,gre,all,core")
    p.add_argument("--min-issues", type=int, default=2, help="Min issues word appears in")
    p.add_argument("--limit", type=int, default=30, help="Max results")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.set_defaults(func=cmd_top)

    # frontier
    p = sub.add_parser("frontier", help="Words seen only 1-2 times")
    p.add_argument("--max-issues", type=int, default=2, help="Max issue count for frontier")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_frontier)

    # economist-core
    p = sub.add_parser("economist-core", help="Frequent non-list words")
    p.add_argument("--min-issues", type=int, default=3)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_economist_core)

    # issue
    p = sub.add_parser("issue", help="Words from a specific issue")
    p.add_argument("issue", help="Issue date (YYYY.MM.DD) or 'latest'")
    p.add_argument("--tier", help="Filter by tier")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_issue)

    # search
    p = sub.add_parser("search", help="Search for words")
    p.add_argument("query", help="Search term")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    # word
    p = sub.add_parser("word", help="Full details for one word")
    p.add_argument("word", help="Word to look up")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_word)

    # stats
    p = sub.add_parser("stats", help="Corpus statistics")
    p.add_argument("--by-tier", action="store_true", help="Breakdown by tier")
    p.set_defaults(func=cmd_stats)

    # sql
    p = sub.add_parser("sql", help="Run raw SQL query")
    p.add_argument("query", help="SQL query (read-only)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_sql)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
