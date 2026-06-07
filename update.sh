#!/bin/bash
# update.sh — Download new Economist issues + extract text
# Run manually or via cron: cd English_Vocabulary && ./update.sh

set -e
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

echo "============================================"
echo "Economist Update — $(date '+%Y-%m-%d %H:%M')"
echo "============================================"

# Step 1: Discover new issues from GitHub
echo ""
echo "[1/3] Checking for new issues on GitHub..."

REPO_URL="https://github.com/hehonghui/awesome-english-ebooks/tree/master/01_economist"
NEW_PDFS=0

# Fetch directory listing, extract folder names matching te_2026.*
ISSUES=$(curl -sL "$REPO_URL" 2>/dev/null | \
    grep -oE 'te_2026\.[0-9]{2}\.[0-9]{2}' | \
    sort -u)

for folder in $ISSUES; do
    # Extract date from folder name
    date_str=$(echo "$folder" | sed 's/te_//')
    outfile="$PROJECT_DIR/2026/TheEconomist.${date_str}.pdf"

    if [ -f "$outfile" ] && [ -s "$outfile" ]; then
        continue  # Already have it
    fi

    # Also check if it already exists in 2025 folder
    alt_outfile="$PROJECT_DIR/2025/TheEconomist.${date_str}.pdf"
    if [ -f "$alt_outfile" ] && [ -s "$alt_outfile" ]; then
        continue
    fi

    echo "  New issue: $date_str — downloading..."
    url="https://raw.githubusercontent.com/hehonghui/awesome-english-ebooks/master/01_economist/${folder}/TheEconomist.${date_str}.pdf"
    curl -sL --connect-timeout 10 --max-time 120 -o "$outfile" "$url"

    if [ -f "$outfile" ] && [ -s "$outfile" ]; then
        size=$(du -h "$outfile" | cut -f1)
        echo "    Downloaded: $size"
        NEW_PDFS=$((NEW_PDFS + 1))
    else
        echo "    Failed to download (may not exist yet)"
        rm -f "$outfile"
    fi
done

echo "  New PDFs downloaded: $NEW_PDFS"

# Step 2: Extract text
echo ""
echo "[2/5] Extracting text..."
python3 "$PROJECT_DIR/extract_text.py"

# Step 3: Rebuild vocabulary database
echo ""
echo "[3/5] Rebuilding vocabulary database..."
python3 "$PROJECT_DIR/build_corpus.py"

# Step 4: Regenerate reports
echo ""
echo "[4/5] Regenerating reports..."
python3 "$PROJECT_DIR/report_generator.py"

# Step 5: Regenerate Anki decks
echo ""
echo "[5/5] Regenerating Anki decks..."
python3 "$PROJECT_DIR/anki_exporter.py"

# Step 6: Show stats
echo ""
echo "Library stats:"
echo "  PDFs: $(find "$PROJECT_DIR"/2025 "$PROJECT_DIR"/2026 -name '*.pdf' 2>/dev/null | wc -l | tr -d ' ')"
echo "  TXTs: $(find "$PROJECT_DIR"/txt -name '*.txt' 2>/dev/null | wc -l | tr -d ' ')"

total_size=$(du -sh "$PROJECT_DIR" 2>/dev/null | cut -f1)
echo "  Total: $total_size"

echo ""
echo "Done."
