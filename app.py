#!/usr/bin/env python3
"""
Flask web app for interactive vocabulary learning.
Run: python app.py → http://localhost:5000
"""

import csv
import io
import re
import sqlite3
from datetime import date
from pathlib import Path

from flask import Flask, Response, g, jsonify, redirect, render_template, request, url_for

PROJECT = Path("/Users/jiangwei/Claude/English_Vocabulary")
DB_PATH = PROJECT / "vocab.db"

app = Flask(__name__)

TIER_LEVELS = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6}

# ── Database ────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(str(DB_PATH))
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    g.pop("db", None).close() if "db" in g else None


def init_db():
    """Create view if not exists."""
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""
        CREATE VIEW IF NOT EXISTS word_learning AS
        SELECT w.*,
               COALESCE(l.status, 'new') as learn_status,
               COALESCE(l.review_count, 0) as review_count,
               l.last_reviewed
        FROM words w
        LEFT JOIN learning l ON l.word_id = w.id
    """)
    db.commit()
    db.close()


# ── Query helpers ───────────────────────────────────────────────

def tier_to_sql(tier: str) -> str:
    """Convert tier name to SQL WHERE clause."""
    t = tier.lower()
    if t in TIER_LEVELS:
        return f"wl.cefr = '{t.upper()}'"
    mapping = {"sat": "wl.sat = 1", "gre": "wl.gre = 1",
               "all": "wl.is_common = 0",
               "core": "wl.sat = 0 AND wl.gre = 0 AND wl.cefr IS NULL AND wl.is_common = 0"}
    return mapping.get(t, "wl.is_common = 0")


def query_words(where="wl.is_common = 0", order="wl.total_count DESC", limit=25, offset=0, status=None):
    """Flexible word query. Always uses word_learning view."""
    clauses = [where]
    params = []
    if status:
        clauses.append("wl.learn_status = ?")
        params.append(status)
    sql = f"""
        SELECT wl.*, (SELECT GROUP_CONCAT(o2.issue_date, ', ')
                      FROM occurrences o2 WHERE o2.word_id = wl.id) as issue_list
        FROM word_learning wl
        WHERE {' AND '.join(clauses)}
        ORDER BY {order}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    return get_db().execute(sql, params).fetchall()


def count_words(where="wl.is_common = 0", status=None):
    clauses = [where]
    params = []
    if status:
        clauses.append("wl.learn_status = ?")
        params.append(status)
    sql = f"SELECT COUNT(*) FROM word_learning wl WHERE {' AND '.join(clauses)}"
    return get_db().execute(sql, params).fetchone()[0]


def word_detail(word_id):
    row = get_db().execute("""
        SELECT wl.*, GROUP_CONCAT(o.issue_date, ', ') as issue_list,
               GROUP_CONCAT(o.sample_sentence, '|||') as all_samples
        FROM word_learning wl
        LEFT JOIN occurrences o ON o.word_id = wl.id
        WHERE wl.id = ?
        GROUP BY wl.id
    """, (word_id,)).fetchone()
    return row


def get_review_words(tier="all", status=None, limit=50, offset=0):
    """Get words for card-by-card review."""
    where = tier_to_sql(tier)
    clauses = [where]
    params = []
    if status:
        # status can be comma-separated: "new,unsure"
        statuses = status.split(",")
        clauses.append(f"wl.learn_status IN ({','.join('?' * len(statuses))})")
        params.extend(statuses)
    else:
        clauses.append("wl.learn_status != 'known'")
    sql = f"""
        SELECT wl.*, (SELECT o.sample_sentence FROM occurrences o
                      WHERE o.word_id = wl.id ORDER BY o.issue_date DESC LIMIT 1) as best_sample
        FROM word_learning wl
        WHERE {' AND '.join(clauses)}
        ORDER BY wl.learn_status = 'new' DESC, wl.total_count DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    return get_db().execute(sql, params).fetchall()


def get_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM word_learning WHERE is_common = 0").fetchone()[0]
    known = db.execute("SELECT COUNT(*) FROM word_learning WHERE is_common = 0 AND learn_status = 'known'").fetchone()[0]
    unknown = db.execute("SELECT COUNT(*) FROM word_learning WHERE is_common = 0 AND learn_status = 'unknown'").fetchone()[0]
    unsure = db.execute("SELECT COUNT(*) FROM word_learning WHERE is_common = 0 AND learn_status = 'unsure'").fetchone()[0]
    new = db.execute("SELECT COUNT(*) FROM word_learning WHERE is_common = 0 AND learn_status = 'new'").fetchone()[0]
    today = db.execute("SELECT COUNT(*) FROM learning WHERE last_reviewed = ?", (str(date.today()),)).fetchone()[0]
    return {"total": total, "known": known, "unknown": unknown, "unsure": unsure, "new": new, "today": today}


# ── Routes ──────────────────────────────────────────────────────

@app.route("/")
def index():
    stats = get_stats()
    return render_template("index.html", stats=stats)


@app.route("/browse")
def browse():
    tier = request.args.get("tier", "all")
    status = request.args.get("status", "")
    search = request.args.get("search", "")
    sort = request.args.get("sort", "count")
    page = int(request.args.get("page", 1))

    where = tier_to_sql(tier)
    if search:
        where += f" AND (wl.word LIKE '%{search}%' OR wl.chinese LIKE '%{search}%')"

    order_map = {"count": "wl.total_count DESC", "issues": "wl.issue_count DESC",
                 "word": "wl.word ASC", "recent": "wl.last_reviewed DESC NULLS LAST"}
    order = order_map.get(sort, "wl.total_count DESC")

    limit = 25
    offset = (page - 1) * limit
    total = count_words(where, status if status else None)
    words = query_words(where, order, limit, offset, status if status else None)
    pages = (total + limit - 1) // limit

    return render_template("browse.html", words=words, tier=tier, status=status,
                           search=search, sort=sort, page=page, pages=pages, total=total)


@app.route("/review")
def review():
    tier = request.args.get("tier", "all")
    status = request.args.get("status", "new,unsure")
    idx = int(request.args.get("idx", 0))

    row = get_review_words(tier, status, limit=1, offset=idx)
    if not row:
        return render_template("review.html", word=None, tier=tier, status=status, idx=0, total=0)

    word = row[0]
    # Count total available
    total = count_words(tier_to_sql(tier), status)
    stats = get_stats()

    return render_template("review.html", word=word, tier=tier, status=status,
                           idx=idx, total=total, stats=stats)


@app.route("/word/<path:word_str>")
def word_page(word_str):
    # Accept word string or numeric ID
    if word_str.isdigit():
        w = word_detail(int(word_str))
    else:
        w = get_db().execute("SELECT wl.* FROM word_learning wl WHERE wl.word_lower = ?",
                             (word_str.lower(),)).fetchone()
        if w:
            w = word_detail(w["id"])
    if not w:
        return render_template("404.html"), 404

    # Parse sample sentences
    samples = w["all_samples"].split("|||") if w["all_samples"] else []

    return render_template("word.html", word=w, samples=samples)


@app.route("/api/word/<int:word_id>/status", methods=["POST"])
def api_set_status(word_id):
    data = request.get_json(force=True)
    new_status = data.get("status")
    if new_status not in ("known", "unknown", "unsure", "new"):
        return jsonify({"ok": False, "error": "invalid status"}), 400

    db = get_db()
    db.execute("""
        INSERT INTO learning (word_id, status, review_count, last_reviewed)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(word_id) DO UPDATE SET
            status = excluded.status,
            review_count = learning.review_count + 1,
            last_reviewed = excluded.last_reviewed
    """, (word_id, new_status, str(date.today())))
    db.commit()

    return jsonify({"ok": True, "status": new_status})


@app.route("/export")
def export_csv():
    tier = request.args.get("tier", "all")
    status = request.args.get("status", "unknown")
    where = tier_to_sql(tier)
    if status:
        where += f" AND wl.learn_status = '{status}'"

    rows = get_db().execute(f"""
        SELECT wl.word, wl.phonetic, wl.chinese, wl.english_def, wl.pos,
               wl.cefr, wl.total_count, wl.issue_count,
               (SELECT o.sample_sentence FROM occurrences o
                WHERE o.word_id = wl.id ORDER BY o.issue_date DESC LIMIT 1) as sentence,
               (SELECT GROUP_CONCAT(DISTINCT SUBSTR(o2.issue_date, 1, 7))
                FROM occurrences o2 WHERE o2.word_id = wl.id) as months
        FROM word_learning wl
        WHERE {where}
        ORDER BY wl.total_count DESC
        LIMIT 500
    """).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Front", "Back", "Tags"])
    for r in rows:
        # Build front card
        front = r["word"]
        if r["phonetic"]:
            front += f"\n/{r['phonetic']}/"
        front += "\n"
        if r["sentence"]:
            front += f"\n_{r['sentence']}_"

        # Build back card
        back = f"## {r['word']}\n\n"
        if r["chinese"]:
            back += f"**Chinese:** {r['chinese']}\n"
        if r["english_def"]:
            back += f"**English:** {r['english_def']}\n"
        if r["pos"]:
            back += f"**POS:** {r['pos']}\n"
        if r["cefr"]:
            back += f"**CEFR:** {r['cefr']}\n"
        back += f"\n📊 Appears in {r['issue_count']} issue(s) · {r['total_count']} occurrences"

        # Tags
        tags = []
        if r["cefr"]:
            tags.append(f"CEFR::{r['cefr']}")
        if r["months"]:
            for m in set(s.strip() for s in r["months"].split(",")):
                m = m.strip()
                if "-" in m:
                    y, mo = m.split("-")
                    tags.append(f"{y}-Q{(int(mo)-1)//3 + 1}")
        writer.writerow([front, back, " ".join(tags)])

    resp = Response(output.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f"attachment; filename=economist_vocab_{status or 'all'}.csv"
    return resp


# ── Error handling ──────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


# ── Main ────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print(f"\n  📖 Economist Vocabulary — http://localhost:8080\n")
    app.run(debug=True, host="0.0.0.0", port=8080)
