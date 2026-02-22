# Running LibreTranslate with NLLB-200 Neural Network

This guide explains how to run the LibreTranslate server with the integrated
[NLLB-200](https://huggingface.co/facebook/nllb-200-3.3B) neural translation model
as a post-processing refiner.

---

## How It Works

LibreTranslate first translates text using **Argos Translate** (fast, offline).
Then **NLLB-200** (Meta's 200-language model) independently re-translates the
original source text and returns the higher-quality result.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- ~20 GB free disk space for the NLLB-200 model cache
- External drive recommended (model is 17.6 GB in safetensors format)

---

## Quick Start (Docker)

### 1. Clone and enter the project

```bash
git clone https://github.com/your-fork/LibreTranslate
cd LibreTranslate
```

### 2. Configure the model cache location

By default the model downloads to `/Volumes/Neyo/libretranslate_hf_cache`.
To change this, edit `docker-compose.yml`:

```yaml
volumes:
  - /your/drive/libretranslate_hf_cache:/hf_cache:rw
```

Create the directory first:

```bash
mkdir -p /Volumes/Neyo/libretranslate_hf_cache
```

### 3. Build and start

```bash
docker compose up --build
```

The first startup downloads the NLLB-200 model (**~17.6 GB**).
Subsequent starts load from cache (no re-download).

The API is available at **http://localhost:5001**

---

## Configuration

All options are set via environment variables in `docker-compose.yml`:

| Variable | Default | Description |
|---|---|---|
| `LT_NLLB_REFINER` | `false` | Set to `true` to enable NLLB-200 |
| `LT_NLLB_MODEL` | `facebook/nllb-200-distilled-600M` | Model to use |
| `LT_LOAD_ONLY` | `en,uk` | Language models to load (saves RAM) |
| `HF_HOME` | `/hf_cache` | HuggingFace model cache path (inside container) |

### Available NLLB models

| Model | Size | Quality | RAM needed |
|---|---|---|---|
| `facebook/nllb-200-distilled-600M` | ~2.5 GB | Good | ~4 GB |
| `facebook/nllb-200-distilled-1.3B` | ~5 GB | Better | ~8 GB |
| `facebook/nllb-200-3.3B` | ~17.6 GB | Best | ~16 GB |

The project is currently configured to use **3.3B** (highest quality).

---

## Testing Translation

```bash
# Simple test
curl -s http://localhost:5001/translate \
  -H "Content-Type: application/json" \
  -d '{"q":"The neural network processes the input tensor.","source":"en","target":"uk","format":"text"}'

# With Python
python3 -c "
import urllib.request, json
data = json.dumps({'q': 'Hello world', 'source': 'en', 'target': 'uk', 'format': 'text'}).encode()
req = urllib.request.Request('http://localhost:5001/translate', data=data,
                             headers={'Content-Type': 'application/json'})
print(json.loads(urllib.request.urlopen(req).read()))
"
```

---

## Translating a Book (PDF or TXT)

```bash
# Basic usage
python3 scripts/translate_book.py book.pdf --target uk

# With technical term preservation (recommended for programming books)
python3 scripts/translate_book.py book.pdf --target uk --preserve-terms

# Resume after interruption
python3 scripts/translate_book.py book.pdf --target uk --preserve-terms --resume

# Custom API URL or chunk size
python3 scripts/translate_book.py book.pdf --target uk \
  --api-url http://localhost:5001 \
  --chunk-size 3000
```

**Requirements for the script:**

```bash
pip install pymupdf requests
```

### PDF handling notes

- Table of Contents pages are **automatically detected and skipped**
- Dot-leader lines (`Title . . . . . . 42`) are removed
- Technical identifiers (`useState`, `os.path.join`, etc.) are preserved when `--preserve-terms` is used
- Progress is saved after each chunk — safe to interrupt with Ctrl+C and resume

---

## Running Without Docker

```bash
pip install -e ".[nllb]"
LT_NLLB_REFINER=true \
LT_NLLB_MODEL=facebook/nllb-200-3.3B \
LT_LOAD_ONLY=en,uk \
libretranslate --port 5001
```

The model will download to `~/.cache/huggingface/` on first run.

---

## Stopping the Server

```bash
docker compose down
```

Models remain cached on disk and will not be re-downloaded on next start.

---

## Troubleshooting

**Docker socket not found:**
Open Docker Desktop and wait for the whale icon to stop animating.

**Out of disk space during model download:**
Set `HF_HOME` to point to a drive with 20+ GB free and mount it in `docker-compose.yml`.

**Translation quality is low:**
Upgrade to a larger model (`facebook/nllb-200-3.3B`). The 600M model is faster
but less accurate.

**NLLB not responding / slow first request:**
The model loads lazily on the first translation request. The first request may
take 30–120 seconds while the model loads into RAM.
