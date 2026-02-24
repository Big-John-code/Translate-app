# PDF Book Translator — EN → UA

Local translator for technical PDF books from English to Ukrainian.
**Free. Offline. Runs entirely on your Mac.**

Uses **MLX** (Apple Silicon native) or **Ollama** as the LLM backend.
Model: `aya-expanse:8b` — trained on 23 languages, best quality for Ukrainian.

---

## How it works

```
PDF file
   ↓
extractor.py    — extracts text (H1/H2/paragraph/code) + PNG images (PyMuPDF)
   ↓
translator.py   — translates in chunks via MLX or Ollama
                  • preserves code blocks unchanged (placeholder round-trip)
                  • checkpoint after each chunk → safe resume
                  • 40+ technical terms stay in English
   ↓
postprocess.py  — first occurrence annotation: "зв'язаність (coupling)"
   ↓
books/{id}/output/book_ua.md  +  images/
   ↓
API (port 8000) + Docker Nginx (port 3000) — web library UI
```

**Everything runs locally.** No API keys, no internet required during translation.

---

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4) — for MLX backend
- Python 3.11+
- Docker Desktop — for the web UI
- `pandoc` + WeasyPrint — for EPUB/PDF export

---

## First run after cloning

```bash
# registry.json is not in the repo — start from the empty template
cp registry.example.json registry.json
```

> `registry.json` is in `.gitignore` — it stores your personal book list
> and should never be committed to the repository.

---

## Installation

```bash
# 1. Clone and install Python dependencies
git clone <repo>
cd LibreTranslate
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Install system dependencies
brew install pandoc
brew install pango          # for WeasyPrint (PDF export)

# 3. (Optional) Ollama backend instead of MLX
brew install ollama
brew services start ollama
ollama pull aya-expanse:8b
```

---

## Running

### Web UI (recommended)

```bash
# Terminal 1 — FastAPI backend
.venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000

# Terminal 2 — Docker nginx (web viewer)
docker compose up -d

# Open: http://localhost:3000
```

The web UI lets you:
- Upload a PDF (drag & drop), set a title and how many pages to skip
- Monitor translation progress in real time (auto-refreshes every 15 seconds)
- Read the translation directly in the browser (with images)
- Download the finished book as **EPUB** or **PDF**
- View the translation log
- Stop a running translation (progress is saved — you can resume or restart)
- Delete a book (kills the process and cleans up all files)

### CLI (without Docker)

```bash
# Translate a book
nohup .venv/bin/python main.py translate \
  --input /path/to/book.pdf \
  --output output/book_ua.md \
  --from-page 21 \
  --chunk-words 400 \
  --backend mlx \
  --title "Book Title" \
  > output/translation.log 2>&1 &

# Follow progress
tail -f output/translation.log

# Resume after interruption (checkpoint is saved automatically)
.venv/bin/python main.py translate \
  --input /path/to/book.pdf \
  --output output/book_ua.md \
  --from-page 21 --resume

# Inspect a PDF before translating
.venv/bin/python main.py info --input /path/to/book.pdf

# Show the glossary
.venv/bin/python main.py glossary

# Export to EPUB or PDF
.venv/bin/python main.py export --input output/book_ua.md --format epub
.venv/bin/python main.py export --input output/book_ua.md --format pdf
```

---

## `translate` options

| Option | Default | Description |
|---|---|---|
| `--input` | — | Path to PDF (required) |
| `--output` | `output/book_ua.md` | Output Markdown file |
| `--from-page` | 1 | Skip N pages (cover, TOC, preface) |
| `--to-page` | last | Stop at page N |
| `--chunk-words` | 600 | Chunk size in words |
| `--backend` | `mlx` | `mlx` (Apple Silicon) or `ollama` |
| `--title` | filename | Book title for the header |
| `--checkpoint` | `<output>/.checkpoint.json` | Checkpoint file path |
| `--resume` | false | Resume from checkpoint |
| `--neural-fix` | false | Second LLM pass for term correction (~2x slower) |
| `--glossary` | false | Save a separate glossary file |

---

## Project structure

```
LibreTranslate/
├── api.py              ← FastAPI backend (port 8000)
│                          GET/POST/DELETE /api/books
│                          POST /api/books/{id}/stop
│                          POST /api/books/{id}/restart
│                          GET  /api/books/{id}/export?format=epub|pdf
│                          GET  /api/books/{id}/log
├── main.py             ← CLI: translate / info / glossary / export
├── extractor.py        ← PyMuPDF: text blocks + PNG images
├── translator.py       ← MLX/Ollama, checkpoint, code preservation, terms
├── glossary.py         ← 77 EN→UA terms + KEEP_AS_IS list
├── postprocess.py      ← First-occurrence term annotation
├── requirements.txt
├── registry.json       ← Book registry for the web UI
├── docker-compose.yml
├── docker/
│   ├── Dockerfile
│   ├── nginx.conf      ← /api/ → host:8000, /data/ → book files
│   └── index.html      ← SPA: library + reader
└── books/              ← Books uploaded via the web UI
    └── {book_id}/
        ├── book.pdf
        └── output/
            ├── book_ua.md
            ├── progress.json
            ├── .checkpoint.json
            ├── translation.log
            └── images/
```

---

## How translation works

### Code blocks
Before sending a chunk to the model, all ` ``` ``` ` blocks are replaced with `«CODE_BLOCK_N»` placeholders and restored after translation — code never reaches the LLM.

### Images
Extracted via PyMuPDF at DPI=150, saved as PNG in `images/`.
Each image's relative position within the chunk is tracked, and images are inserted between paragraphs proportionally when writing Markdown.

### Checkpoint / Resume
After each chunk: `{"chunks": {"0": "...", "1": "..."}, "last_chunk": 5}`.
`progress.json` — lightweight `{"done": 5, "total": 321}` for the UI only.
`--resume` skips already-translated chunks.

### Technical terms
40+ patterns in `_FORCE_ENGLISH`: `API`, `Docker`, `CI/CD`, `microservices`, `REST`, `GraphQL`, `DevOps`, etc. — never translated.
`_fix_english_terms()` — regex post-process after each chunk.
`--neural-fix` — a second LLM call to automatically find and restore any terms that "leaked" into the translation.

---

## Model

**aya-expanse:8b** (Cohere) — best free model for Ukrainian translation:
- Trained evenly on 23 languages including Ukrainian
- Does not "leak" into other languages (unlike qwen and other Chinese models)
- MLX (4-bit quant): `mlx-community/aya-expanse-8b-4bit` — ~6 GB, native on Apple Silicon
- Ollama: `aya-expanse:8b` — ~6 GB

---

## Export

Supported via `pandoc` + WeasyPrint:

```bash
# Via CLI
.venv/bin/python main.py export --input output/book_ua.md --format epub
.venv/bin/python main.py export --input output/book_ua.md --format pdf

# Or use the ⬇ EPUB / ⬇ PDF buttons in the web UI
```

EPUB — recommended format: preserves chapter structure, images, small file size (~1–15 MB).
PDF — generated via WeasyPrint (requires `brew install pango`).

---

## Web API endpoints

The FastAPI backend runs on `http://localhost:8000` and exposes:

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/books` | List all books with status and progress |
| `POST` | `/api/books` | Upload PDF and start translation |
| `DELETE` | `/api/books/{id}` | Stop translation, delete all files |
| `POST` | `/api/books/{id}/stop` | Stop translation, keep files and progress |
| `POST` | `/api/books/{id}/restart` | Reset progress and retranslate from scratch |
| `GET` | `/api/books/{id}/log` | Last 4000 chars of translation log |
| `GET` | `/api/books/{id}/export` | Generate and stream EPUB or PDF (`?format=epub\|pdf`) |

---

## Docker / macOS VirtioFS note

Docker Desktop on macOS caches inode bind-mounts.
- **Never delete** files mounted into Docker — overwrite them instead
- `_write_output()` uses `os.fsync()` so VirtioFS sees changes immediately
- If Docker doesn't pick up updates: `docker compose restart viewer`
