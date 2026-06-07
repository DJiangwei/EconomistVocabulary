#!/usr/bin/env python3
"""
Extract text from Economist PDFs into clean .txt files.

Usage:
    python3 extract_text.py                          # Process all PDFs
    python3 extract_text.py path/to/file.pdf         # Process single file
    python3 extract_text.py --year 2026              # Process all in a year folder
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import fitz  # PyMuPDF

PROJECT = Path("/Users/jiangwei/Claude/English_Vocabulary")
TXT_DIR = PROJECT / "txt"

# --- Layout constants (612x792 page at 72dpi) ---
HEADER_Y_MAX = 85      # Blocks above this are headers (issue title, date)
FOOTER_Y_MIN = 710      # Blocks below this are footers (page numbers)
MIN_BLOCK_WIDTH = 60    # Skip very narrow blocks (side labels)
WATERMARK_PATTERNS = [
    "This article was downloaded",
    "zlibrary",
    "Downloaded from",
]


def is_junk(text: str) -> bool:
    """Check if a text block is a header, footer, or watermark."""
    t = text.strip()
    if not t:
        return True
    for pat in WATERMARK_PATTERNS:
        if pat in t:
            return True
    # Skip page-number-only lines
    if t.isdigit() and len(t) <= 3:
        return True
    return False


def extract_page_text(page) -> str:
    """Extract clean, reading-order text from one PDF page."""
    blocks = page.get_text("blocks")  # list of (x0,y0,x1,y1,text,type,block_no)

    content_blocks = []
    for b in blocks:
        x0, y0, x1, y1, text, btype, _ = b

        # Skip image blocks
        if btype != 0 and btype != "text":
            continue

        # Skip header/footer zones
        if y1 < HEADER_Y_MAX:
            continue
        if y0 > FOOTER_Y_MIN:
            continue

        # Skip narrow side labels
        if (x1 - x0) < MIN_BLOCK_WIDTH:
            continue

        if is_junk(text):
            continue

        content_blocks.append((y0, x0, text.strip()))

    # Sort by vertical position, then left-to-right (for multi-column)
    content_blocks.sort(key=lambda b: (b[0] // 10, b[1]))

    return "\n".join(b[2] for b in content_blocks)


def extract_pdf(pdf_path: Path) -> Path:
    """Extract text from one PDF, write .txt alongside it."""
    txt_path = TXT_DIR / pdf_path.parent.name / (pdf_path.stem + ".txt")
    txt_path.parent.mkdir(parents=True, exist_ok=True)

    if txt_path.exists() and txt_path.stat().st_size > 100:
        return txt_path  # Already extracted

    doc = fitz.open(str(pdf_path))
    pages_text = []

    for i in range(doc.page_count):
        page = doc[i]
        text = extract_page_text(page)
        if text.strip():
            pages_text.append(text)

    doc.close()

    full_text = "\n\n".join(pages_text)

    # Remove excessive blank lines
    while "\n\n\n\n" in full_text:
        full_text = full_text.replace("\n\n\n\n", "\n\n")

    txt_path.write_text(full_text, encoding="utf-8")
    return txt_path


def find_pdfs(year: str = None) -> list[Path]:
    """Find all PDFs, optionally filtered by year folder."""
    pdfs = []
    if year:
        years = [year]
    else:
        # Auto-discover all year folders (20xx)
        years = sorted(d.name for d in PROJECT.iterdir() if d.is_dir() and d.name.startswith("20"))
    for y in years:
        folder = PROJECT / y
        if folder.is_dir():
            pdfs.extend(sorted(folder.glob("*.pdf")))
    return pdfs


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith("--year") and len(sys.argv) > 2:
            pdfs = find_pdfs(sys.argv[2])
        elif arg.endswith(".pdf"):
            pdfs = [Path(arg)]
        elif os.path.isdir(arg):
            pdfs = sorted(Path(arg).glob("*.pdf"))
        else:
            print(f"Usage: {sys.argv[0]} [file.pdf|directory|--year YYYY]")
            sys.exit(1)
    else:
        pdfs = find_pdfs()

    if not pdfs:
        print("No PDFs found.")
        return

    total = len(pdfs)
    start = datetime.now()
    extracted = 0

    for i, pdf in enumerate(pdfs):
        print(f"[{i+1:3d}/{total}] {pdf.stem}...", end=" ", flush=True)
        try:
            txt = extract_pdf(pdf)
            size_kb = txt.stat().st_size // 1024
            print(f"{size_kb}KB")
            extracted += 1
        except Exception as e:
            print(f"ERROR: {e}")

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\nDone: {extracted}/{total} extracted in {elapsed:.1f}s")
    print(f"Output: {TXT_DIR}/")


if __name__ == "__main__":
    main()
