#!/usr/bin/env python3
"""
Download historical Economist PDFs from multiple GitHub forks.

Sources:
  1. luqiyuezhihua/2024-awesome-english-ebooks → 2024 (52 issues)
  2. Passw/hehonghui-awesome-english-ebooks → 2023 Q1 (13 issues)
  3. hnguoxia/english-ebooks-20230824 → 2023 Q2-Q3 (24 issues)
  4. will-ln/the-economist-ebooks → 2020 (partial, ~39 issues)
"""

import urllib.request
import os
from datetime import date, timedelta

OUTPUT = "/Users/jiangwei/Claude/English_Vocabulary"

SOURCES = [
    {
        "name": "2024 (luqiyuezhihua)",
        "base": "https://raw.githubusercontent.com/luqiyuezhihua/2024-awesome-english-ebooks/master/01_economist",
        "start": date(2024, 1, 6),
        "end": date(2024, 12, 28),
        "folder_fmt": "te_{dt:%Y.%m.%d}",
        "file_fmt": "TheEconomist.{dt:%Y.%m.%d}.pdf",
    },
    {
        "name": "2023 Q1 (Passw)",
        "base": "https://raw.githubusercontent.com/Passw/hehonghui-awesome-english-ebooks/master/01_economist",
        "start": date(2023, 1, 7),
        "end": date(2023, 3, 25),
        "folder_fmt": "te_{dt:%Y.%m.%d}",
        "file_fmt": "TheEconomist.{dt:%Y.%m.%d}.pdf",
    },
    {
        "name": "2023 Q2-Q3 (hnguoxia)",
        "base": "https://raw.githubusercontent.com/hnguoxia/english-ebooks-20230824/master/01_economist",
        "start": date(2023, 3, 4),
        "end": date(2023, 8, 19),
        "folder_fmt": "te_{dt:%Y.%m.%d}",
        "file_fmt": "TheEconomist.{dt:%Y.%m.%d}.pdf",
    },
    {
        "name": "2020 (will-ln)",
        "base": "https://raw.githubusercontent.com/will-ln/the-economist-ebooks/master/01_economist",
        "start": date(2020, 1, 4),
        "end": date(2020, 10, 8),
        "folder_fmt": None,  # Try multiple patterns per date
        "file_fmt": None,
    },
    {
        "name": "2018 (will-ln)",
        "base": "https://raw.githubusercontent.com/will-ln/the-economist-ebooks/master/01_economist/2018",
        "start": date(2018, 12, 29),
        "end": date(2018, 12, 29),
        "folder_fmt": "te_{dt:%Y-%m-%d}",
        "file_fmt": "TheEconomist.{dt:%Y-%m-%d}.pdf",
    },
]


def download(url, outfile):
    """Download a file. Returns True on success."""
    if os.path.exists(outfile) and os.path.getsize(outfile) > 1000:
        return "skip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(outfile, "wb") as f:
            f.write(data)
        return "ok"
    except Exception as e:
        return f"fail: {e}"


def saturdays(start, end):
    """Generate all Saturdays in a date range."""
    d = start
    while d <= end:
        if d.weekday() == 5:
            yield d
        d += timedelta(days=1)


def main():
    total_ok = 0
    total_skip = 0
    total_fail = 0

    for src in SOURCES:
        print(f"\n{'='*60}")
        print(f"📥 {src['name']}")
        print(f"   {src['start']} → {src['end']}")
        print(f"{'='*60}")

        # Confirm repo is accessible
        test_url = src["base"] + "/README.md"
        try:
            urllib.request.urlopen(urllib.request.Request(test_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15)
        except Exception as e:
            print(f"   ⚠️  Repo not accessible: {e}")
            print(f"   Repo may be deleted or renamed — skipping")
            continue

        ok = skip = fail = 0

        for d in saturdays(src["start"], src["end"]):
            year = str(d.year)
            os.makedirs(os.path.join(OUTPUT, year), exist_ok=True)

            if src["folder_fmt"]:
                # Fixed pattern
                folder = src["folder_fmt"].format(dt=d)
                filename = src["file_fmt"].format(dt=d)
                url = f"{src['base']}/{folder}/{filename}"
                out = os.path.join(OUTPUT, year, filename)
                result = download(url, out)
            else:
                # Try multiple patterns (for will-ln 2020)
                patterns = [
                    (f"te_{d:%Y.%m.%d}", f"TheEconomist.{d:%Y.%m.%d}.pdf"),
                    (f"te_{d:%Y-%m-%d}", f"TheEconomist.{d:%Y-%m-%d}.pdf"),
                    (f"te_{d:%Y.%m.%d}", f"TheEconomist.{d:%Y-%m-%d}.pdf"),
                    (f"te_{d:%Y-%m-%d}", f"TheEconomist.{d:%Y.%m.%d}.pdf"),
                ]
                result = "fail: all patterns"
                for folder, filename in patterns:
                    url = f"{src['base']}/{folder}/{filename}"
                    out = os.path.join(OUTPUT, year, filename)
                    result = download(url, out)
                    if result in ("ok", "skip"):
                        break

            if result == "ok":
                size = os.path.getsize(out) / (1024*1024)
                print(f"   ✅ {d:%Y.%m.%d} ({size:.1f}MB)")
                ok += 1
            elif result == "skip":
                skip += 1
            else:
                print(f"   ❌ {d:%Y.%m.%d} — {result}")
                fail += 1

        print(f"   📊 {ok} new, {skip} skipped, {fail} failed")
        total_ok += ok
        total_skip += skip
        total_fail += fail

    print(f"\n{'='*60}")
    print(f"🏁 Total: {total_ok} downloaded, {total_skip} skipped, {total_fail} failed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
