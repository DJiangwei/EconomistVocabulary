#!/bin/bash
# Download Economist PDFs for 2025 and 2026
BASE_URL="https://raw.githubusercontent.com/hehonghui/awesome-english-ebooks/master/01_economist"
OUTPUT_DIR="/Users/jiangwei/Claude/English_Vocabulary"

download_pdf() {
  local year=$1
  local date_str=$2
  local subpath=$3
  local url="${BASE_URL}/${subpath}/TheEconomist.${date_str}.pdf"
  local outfile="${OUTPUT_DIR}/${year}/TheEconomist.${date_str}.pdf"

  if [ -f "$outfile" ] && [ -s "$outfile" ]; then
    echo "  [SKIP] Already exists: ${date_str}"
    return 0
  fi

  echo "  [DOWNLOAD] ${date_str}..."
  curl -sL --connect-timeout 10 --max-time 120 -o "$outfile" "$url"

  if [ -f "$outfile" ] && [ -s "$outfile" ]; then
    local size=$(du -h "$outfile" | cut -f1)
    echo "  [OK] ${date_str} (${size})"
  else
    echo "  [FAIL] ${date_str}"
    rm -f "$outfile"
  fi
}

echo "============================================"
echo "Downloading Economist PDFs"
echo "============================================"

# --- 2025 ---
echo ""
echo "=== 2025 (52 issues) ==="
# Generate all Saturdays in 2025
year=2025
# Start from 2025-01-04 (first Saturday)
for week in $(seq 0 51); do
  d=$(date -j -v+${week}w -v-sat "2025-01-04" +%Y.%m.%d 2>/dev/null || date -d "2025-01-04 + ${week} weeks" +%Y.%m.%d 2>/dev/null)
  [ -z "$d" ] && continue
  download_pdf "$year" "$d" "2025/te_${d}"
done

# --- 2026 ---
echo ""
echo "=== 2026 (Jan 3 - Jun 7) ==="
# Generate Saturdays from Jan 3 to Jun 7, 2026
for week in $(seq 0 22); do
  d=$(date -j -v+${week}w -v-sat "2026-01-03" +%Y.%m.%d 2>/dev/null || date -d "2026-01-03 + ${week} weeks" +%Y.%m.%d 2>/dev/null)
  [ -z "$d" ] && continue
  download_pdf "$year" "$d" "te_${d}"
done

echo ""
echo "============================================"
echo "Download complete!"
echo "PDFs saved to: ${OUTPUT_DIR}/2025/ and ${OUTPUT_DIR}/2026/"
echo "============================================"
