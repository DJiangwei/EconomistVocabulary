# Economist Vocabulary

Corpus-based vocabulary mining from The Economist magazine (2020-2026).

## Quick Start

```bash
# Explore vocabulary
python query_tool.py stats
python query_tool.py top --tier c2 --min-issues 10
python query_tool.py economist-core
python query_tool.py word hegemony

# Generate reports
python report_generator.py

# Generate Anki flashcards
python anki_exporter.py
```

## Setup (from scratch)

```bash
# 1. Download PDFs (see download scripts)
python download_historical.py

# 2. Extract text
python extract_text.py

# 3. Build vocabulary database
python build_corpus.py

# 4. Generate outputs
python report_generator.py
python anki_exporter.py
```

## Corpus

| Year | Issues |
|------|--------|
| 2026 | 18 (updating weekly) |
| 2025 | 51 |
| 2024 | 49 |
| 2023 | 33 |
| 2022 | 26 |
| 2021 | 25 |
| 2020 | 5 |
| **Total** | **207** |

## Components

| File | Purpose |
|------|---------|
| `build_corpus.py` | Build SQLite database from extracted text |
| `query_tool.py` | CLI for querying vocabulary by tier, frequency, issue |
| `report_generator.py` | Generate HTML + Markdown reports |
| `anki_exporter.py` | Generate Anki-compatible CSV flashcard decks |
| `extract_text.py` | Extract text from PDF files |
| `download_pdfs.sh` | Download recent issues (2025-2026) |
| `download_historical.py` | Download historical issues from forks |
| `update.sh` | Weekly auto-update (download → extract → build → reports → Anki) |

## Word Lists

This project uses the following free word lists:
- **NGSL 1.2** — 2,809 common English words (filtered out)
- **NAWL 1.2** — 960 academic words (filtered out)
- **SAT** — 6,000 SAT vocabulary words (classification)
- **GRE** — 9,566 GRE vocabulary words (classification)
- **CEFR** — 152,377 words with CEFR levels (A1-C2)
- **ECDICT** — 770K English-Chinese dictionary entries

## License

This project is for personal educational use. The Economist is a registered trademark of The Economist Newspaper Limited.
