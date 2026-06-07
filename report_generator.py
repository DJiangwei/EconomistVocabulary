#!/usr/bin/env python3
"""
Generate static reports from the vocabulary database.

Usage:
    python report_generator.py              # Generate all reports
    python report_generator.py --reports difficulty,economist-core  # Specific only
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path("/Users/jiangwei/Claude/English_Vocabulary")
DB_PATH = PROJECT / "vocab.db"
REPORTS_DIR = PROJECT / "reports"

TIERS = [
    ("B1", "cefr = 'B1' AND is_common = 0"),
    ("B2", "cefr = 'B2' AND is_common = 0"),
    ("C1", "cefr = 'C1' AND is_common = 0"),
    ("C2", "cefr = 'C2' AND is_common = 0"),
    ("SAT", "sat = 1 AND is_common = 0"),
    ("GRE", "gre = 1 AND is_common = 0"),
    ("Economist Core", "sat=0 AND gre=0 AND cefr IS NULL AND is_common=0 AND issue_count>=3"),
]

TIER_COLORS = {
    "B1": "#4caf50", "B2": "#ff9800", "C1": "#f44336",
    "C2": "#9c27b0", "SAT": "#2196f3", "GRE": "#00bcd4",
    "Economist Core": "#ff6f00",
}


def connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ── HTML helpers ────────────────────────────────────────────────

def html_header(title: str, extra_css: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Economist Vocabulary</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; line-height: 1.5; }}
  .container {{ max-width: 1000px; margin: 0 auto; }}
  h1, h2, h3 {{ color: #58a6ff; }}
  a {{ color: #58a6ff; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #21262d; }}
  th {{ background: #161b22; cursor: pointer; user-select: none; position: sticky; top: 0; z-index: 1; }}
  th:hover {{ background: #1f2937; }}
  tr:hover {{ background: #161b22; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px;
            font-weight: 600; margin: 0 2px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 20px 0; }}
  .stat-card {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; text-align: center; }}
  .stat-value {{ font-size: 28px; font-weight: 700; color: #58a6ff; }}
  .stat-label {{ font-size: 12px; color: #8b949e; margin-top: 4px; }}
  .tabs {{ display: flex; gap: 4px; margin: 16px 0; flex-wrap: wrap; }}
  .tab {{ padding: 8px 16px; background: #161b22; border: 1px solid #21262d; border-radius: 6px 6px 0 0;
          cursor: pointer; font-size: 13px; color: #8b949e; }}
  .tab.active {{ background: #1f2937; color: #58a6ff; border-bottom-color: #1f2937; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .nav {{ margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #21262d; }}
  .nav a {{ margin-right: 16px; }}
  .search-box {{ margin: 16px 0; }}
  .search-box input {{ width: 100%; padding: 10px 16px; background: #161b22; border: 1px solid #30363d;
                      border-radius: 6px; color: #c9d1d9; font-size: 14px; }}
  .comment {{ color: #8b949e; font-size: 12px; }}
  footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #21262d;
            font-size: 12px; color: #8b949e; }}
  {extra_css}
</style>
</head>
<body><div class="container">
"""


html_footer = """
<footer>Generated {timestamp} — English Vocabulary Project</footer>
</div>
<script>
// Table sorting
document.querySelectorAll('th').forEach(th => {{
  th.addEventListener('click', () => {{
    const table = th.closest('table');
    const tbody = table.querySelector('tbody');
    const col = Array.from(th.parentNode.children).indexOf(th);
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const asc = th.classList.contains('asc');
    rows.sort((a, b) => {{
      let va = a.children[col].textContent.trim();
      let vb = b.children[col].textContent.trim();
      let na = parseFloat(va.replace(/,/g, ''));
      let nb = parseFloat(vb.replace(/,/g, ''));
      if (!isNaN(na) && !isNaN(nb)) return asc ? nb - na : na - nb;
      return asc ? vb.localeCompare(va) : va.localeCompare(vb);
    }});
    table.querySelectorAll('th').forEach(h => h.classList.remove('asc', 'desc'));
    th.classList.add(asc ? 'desc' : 'asc');
    rows.forEach(r => tbody.appendChild(r));
  }});
}});
// Tab switching
document.querySelectorAll('.tab').forEach(tab => {{
  tab.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.target).classList.add('active');
  }});
}});
// Search filtering
document.querySelectorAll('.search-box input').forEach(input => {{
  input.addEventListener('input', () => {{
    const term = input.value.toLowerCase();
    const table = input.closest('.search-box').nextElementSibling;
    table.querySelectorAll('tbody tr').forEach(tr => {{
      tr.style.display = tr.textContent.toLowerCase().includes(term) ? '' : 'none';
    }});
  }});
}});
</script>
</body></html>""".replace("{timestamp}", datetime.now().strftime("%Y-%m-%d %H:%M"))


def col_or(row, key, default=""):
    """Get column value from sqlite3.Row or dict, with fallback."""
    try:
        v = row[key]
        return v if v is not None else default
    except (KeyError, IndexError):
        return default


def word_row(w, show_sample=False):
    """Render HTML table row for a single word."""
    badges = []
    cefr = col_or(w, "cefr")
    sat = col_or(w, "sat", 0)
    gre = col_or(w, "gre", 0)
    if cefr:
        badges.append(f'<span class="badge" style="background:{TIER_COLORS.get(cefr, "#555")}">{cefr}</span>')
    if sat:
        badges.append('<span class="badge" style="background:#2196f3">SAT</span>')
    if gre:
        badges.append('<span class="badge" style="background:#00bcd4">GRE</span>')
    badges_html = " ".join(badges)

    sample = ""
    sample_text = col_or(w, "sample_sentence")
    if show_sample and sample_text:
        sample = f'<br><span class="comment">{sample_text}</span>'

    eng = col_or(w, "english_def")

    return f"""<tr>
      <td><strong>{w['word']}</strong></td>
      <td>{badges_html}</td>
      <td>{col_or(w, 'chinese')}</td>
      <td class="comment">{eng[:120]}</td>
      <td class="comment">{col_or(w, 'pos')}</td>
      <td style="text-align:right">{w['total_count']:,}</td>
      <td style="text-align:right">{col_or(w, 'issue_count')}</td>
    </tr>"""


def render_tier_section(title: str, where: str, db, limit=200):
    """Generate HTML for one tier tab."""
    rows = db.execute(f"""
        SELECT word, total_count, issue_count, cefr, sat, gre, chinese, english_def, pos
        FROM words
        WHERE {where}
        ORDER BY total_count DESC
        LIMIT ?
    """, (limit,)).fetchall()

    rows_html = "\n".join(word_row(r) for r in rows)

    return f"""
    <div class="tab-content" id="tier-{title.lower().replace(' ','-')}">
      <div class="search-box"><input type="text" placeholder="Filter {len(rows)} words..." /></div>
      <table>
        <thead><tr>
          <th>Word</th><th>Level</th><th>Chinese</th><th>English</th><th>POS</th><th>Count</th><th>Issues</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>"""


# ── Reports ─────────────────────────────────────────────────────

def build_difficulty_report(db):
    """Build reports/difficulty.html with tabbed tiers."""
    print("  Building difficulty.html...")

    tabs_html = ""
    tab_labels = ""
    for label, where in TIERS:
        safe_id = label.lower().replace(" ", "-")
        active = " active" if label == "SAT" else ""
        tab_labels += f'<span class="tab{active}" data-target="tier-{safe_id}">{label}</span>\n'
        tabs_html += render_tier_section(label, where, db)

    html = html_header("Difficulty-Tiered Vocabulary") + f"""
    <div class="nav"><a href="index.html">← Back to Index</a></div>
    <h1>📚 Vocabulary by Difficulty</h1>
    <p>Words sorted by CEFR level and test-prep category. Click column headers to sort.</p>
    <div class="tabs">{tab_labels}</div>
    {tabs_html}
    {html_footer}"""

    (REPORTS_DIR / "difficulty.html").write_text(html, encoding="utf-8")


def build_economist_core_report(db):
    """Build reports/economist_core.html — words unique to The Economist."""
    print("  Building economist_core.html...")

    rows = db.execute("""
        SELECT w.word, w.total_count, w.issue_count, w.cefr, w.sat, w.gre, w.chinese, w.english_def, w.pos,
               o.sample_sentence
        FROM words w
        LEFT JOIN (SELECT word_id, MAX(sample_sentence) as sample_sentence FROM occurrences GROUP BY word_id) o
          ON o.word_id = w.id
        WHERE sat=0 AND gre=0 AND cefr IS NULL AND is_common=0 AND issue_count >= 3
        ORDER BY total_count DESC
        LIMIT 500
    """).fetchall()

    rows_html = "\n".join(word_row(r, show_sample=True) for r in rows)

    html = html_header("Economist Core Vocabulary") + f"""
    <div class="nav"><a href="index.html">← Back to Index</a></div>
    <h1>🔑 Economist Core Vocabulary</h1>
    <p>Words appearing in 3+ issues that are NOT on NGSL, NAWL, SAT, GRE, or CEFR lists.
       These are The Economist's "house vocabulary" — your highest-value learning targets.</p>
    <p class="comment">{len(rows)} words found</p>
    <div class="search-box"><input type="text" placeholder="Search {len(rows)} words..." /></div>
    <table>
      <thead><tr>
        <th>Word</th><th>Level</th><th>Chinese</th><th>English</th><th>POS</th><th>Count</th><th>Issues</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    {html_footer}"""

    (REPORTS_DIR / "economist_core.html").write_text(html, encoding="utf-8")


def build_index_report(db):
    """Build reports/index.html and reports/index.md — master index."""
    print("  Building index.html + index.md...")

    # Stats
    total = db.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    learning = db.execute("SELECT COUNT(*) FROM words WHERE is_common=0").fetchone()[0]
    issues = db.execute("SELECT COUNT(DISTINCT issue_date) FROM occurrences").fetchone()[0]
    words_total = db.execute("SELECT SUM(total_count) FROM words").fetchone()[0] or 0
    sat_n = db.execute("SELECT COUNT(*) FROM words WHERE sat=1 AND is_common=0").fetchone()[0]
    gre_n = db.execute("SELECT COUNT(*) FROM words WHERE gre=1 AND is_common=0").fetchone()[0]
    core_n = db.execute("SELECT COUNT(*) FROM words WHERE sat=0 AND gre=0 AND cefr IS NULL AND is_common=0 AND issue_count>=3").fetchone()[0]
    c1plus = db.execute("SELECT COUNT(*) FROM words WHERE cefr IN ('C1','C2') AND is_common=0").fetchone()[0]

    # Top 50 words across tiers for index page
    top_rows = db.execute("""
        SELECT word, total_count, issue_count, cefr, sat, gre, chinese, english_def, pos
        FROM words
        WHERE is_common = 0
        ORDER BY total_count DESC
        LIMIT 50
    """).fetchall()
    rows_html = "\n".join(word_row(r) for r in top_rows)

    # ── HTML ──
    html = html_header("Vocabulary Index") + f"""
    <h1>📖 Economist Vocabulary</h1>
    <p class="comment">Corpus: {issues} issues · {words_total:,} words · {learning:,} learning targets</p>

    <div class="stats">
      <div class="stat-card"><div class="stat-value">{learning:,}</div><div class="stat-label">Learning Targets</div></div>
      <div class="stat-card"><div class="stat-value">{sat_n:,}</div><div class="stat-label">SAT Words</div></div>
      <div class="stat-card"><div class="stat-value">{gre_n:,}</div><div class="stat-label">GRE Words</div></div>
      <div class="stat-card"><div class="stat-value">{c1plus:,}</div><div class="stat-label">C1-C2 Words</div></div>
      <div class="stat-card"><div class="stat-value">{core_n:,}</div><div class="stat-label">Economist Core</div></div>
      <div class="stat-card"><div class="stat-value">{issues}</div><div class="stat-label">Issues</div></div>
    </div>

    <h2>📊 Reports</h2>
    <ul>
      <li><a href="difficulty.html">Vocabulary by Difficulty</a> — Tabbed view: B1, B2, C1, C2, SAT, GRE, Economist Core</li>
      <li><a href="economist_core.html">Economist Core</a> — Words unique to The Economist (not on any standard list)</li>
    </ul>

    <h2>Top 50 Words (by total frequency)</h2>
    <div class="search-box"><input type="text" placeholder="Filter words..." /></div>
    <table>
      <thead><tr>
        <th>Word</th><th>Level</th><th>Chinese</th><th>English</th><th>POS</th><th>Count</th><th>Issues</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    {html_footer}"""

    (REPORTS_DIR / "index.html").write_text(html, encoding="utf-8")

    # ── Markdown ──
    md = f"""# Economist Vocabulary Index

**Corpus:** {issues} issues · {words_total:,} words · {learning:,} learning targets

## Stats

| Category | Count |
|----------|-------|
| Learning Targets | {learning:,} |
| SAT Words | {sat_n:,} |
| GRE Words | {gre_n:,} |
| C1-C2 Words | {c1plus:,} |
| Economist Core | {core_n:,} |

## Reports

- [Vocabulary by Difficulty](difficulty.html)
- [Economist Core](economist_core.html)
- [Per-Issue Reports](by_issue/)

## Top 50 Words

| # | Word | Level | Chinese | Count | Issues |
|---|------|-------|---------|-------|--------|
"""
    for i, r in enumerate(top_rows[:30], 1):
        level = r["cefr"] or ""
        if r["sat"]: level += " SAT" if not level else ", SAT"
        if r["gre"]: level += " GRE" if not level else ", GRE"
        md += f"| {i} | **{r['word']}** | {level} | {r['chinese'] or ''} | {r['total_count']:,} | {r['issue_count']} |\n"

    (REPORTS_DIR / "index.md").write_text(md, encoding="utf-8")


def build_per_issue_reports(db):
    """Build per-issue markdown files."""
    print("  Building per-issue reports...")

    issues = db.execute("SELECT DISTINCT issue_date FROM occurrences ORDER BY issue_date").fetchall()
    by_issue_dir = REPORTS_DIR / "by_issue"
    by_issue_dir.mkdir(parents=True, exist_ok=True)

    for (issue_date,) in issues:
        rows = db.execute("""
            SELECT w.word, w.total_count, w.cefr, w.sat, w.gre, w.chinese, w.english_def, w.pos,
                   o.sample_sentence
            FROM words w
            JOIN occurrences o ON o.word_id = w.id
            WHERE o.issue_date = ? AND w.is_common = 0
            ORDER BY
              CASE
                WHEN w.sat THEN 0 WHEN w.gre THEN 1
                WHEN w.cefr = 'C2' THEN 2 WHEN w.cefr = 'C1' THEN 3
                WHEN w.cefr = 'B2' THEN 4 ELSE 5
              END,
              w.total_count DESC
            LIMIT 80
        """, (issue_date,)).fetchall()

        if not rows:
            continue

        md = f"# The Economist — {issue_date}\n\n"
        md += f"**Pre-read vocabulary list** · {len(rows)} words\n\n"
        md += "---\n\n"

        for r in rows:
            level = r["cefr"] or ""
            tags = []
            if r["sat"]: tags.append("SAT")
            if r["gre"]: tags.append("GRE")
            tags_str = " · ".join([level] + tags) if level or tags else ""

            md += f"## {r['word']}\n\n"
            md += f"- **{r['chinese'] or '—'}**\n"
            if r["english_def"]:
                md += f"- {r['english_def'][:150]}\n"
            if tags_str:
                md += f"- {tags_str} | POS: {r['pos'] or '—'}\n"
            if r["sample_sentence"]:
                md += f"\n> {r['sample_sentence']}\n"
            md += "\n---\n\n"

        out = by_issue_dir / f"{issue_date}.md"
        out.write_text(md, encoding="utf-8")


# ── Main ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate vocabulary reports")
    parser.add_argument("--reports", help="Comma-separated: index,difficulty,economist-core,per-issue")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    requested = set(args.reports.split(",")) if args.reports else {"index", "difficulty", "economist-core", "per-issue"}

    db = connect()
    print("Generating reports...")

    if "index" in requested:
        build_index_report(db)
    if "difficulty" in requested:
        build_difficulty_report(db)
    if "economist-core" in requested:
        build_economist_core_report(db)
    if "per-issue" in requested:
        build_per_issue_reports(db)

    db.close()

    # Show what was created
    print(f"\nReports generated in {REPORTS_DIR}/")
    for f in sorted(REPORTS_DIR.rglob("*")):
        if f.is_file():
            size = f.stat().st_size / 1024
            print(f"  {f.relative_to(REPORTS_DIR)} ({size:.0f} KB)")


if __name__ == "__main__":
    main()
