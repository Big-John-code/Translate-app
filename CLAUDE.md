# CLAUDE.md — LibreTranslate Project Guide

## Project Overview

LibreTranslate is a self-hosted, free and open-source Machine Translation API powered by Argos Translate. This fork adds technical term preservation and book translation utilities on top of the upstream project.

**License:** AGPL v3
**Python:** 3.8–3.13
**Primary port:** 5001 (mapped to internal 5000)

---

## Architecture

```
libretranslate/
├── app.py              # Flask app factory — all API routes (1413 lines)
├── main.py             # CLI entry point — 40+ argparse options
├── init.py             # Model initialization and boot logic
├── term_protector.py   # Custom: technical term preservation (460 lines)
├── language.py         # Language code conversion and detection
├── api_keys.py         # SQLite-backed API key management
├── cache.py            # Translation result caching
├── flood.py            # DDoS/flood protection
├── storage.py          # Shared storage abstraction (memory/Redis)
├── default_values.py   # Env-var defaults (LT_* prefix, 41 options)
├── templates/
│   ├── index.html          # Vue.js 2 SPA (modified)
│   └── app.js.template     # Frontend JS (modified)
└── tests/              # pytest suite

scripts/
├── translate_book.py   # Custom: PDF/TXT book translation utility (348 lines)
├── healthcheck.py
└── gunicorn_conf.py

docker/
├── Dockerfile          # Multi-stage production image (Python 3.11 slim)
├── cuda.Dockerfile     # GPU variant
└── arm.Dockerfile      # ARM variant
```

---

## Custom Modifications (Our Changes)

### 1. `libretranslate/term_protector.py` (NEW)
Protects technical terms from being mistranslated. Handles:
- Fenced/inline code blocks
- URLs, emails, file paths
- Dot notation (`os.path.join`), function calls, camelCase/snake_case
- CLI flags (`--verbose`), version numbers (`v1.2.3`), hex values
- Generic types (`List<String>`), operators (`=>`, `->`, `::`)
- Acronyms, `@decorators`, `$vars`

Key classes: `TechTermProtector`, `TermProtectingTranslator`

### 2. `scripts/translate_book.py` (NEW)
Standalone CLI utility to translate PDF/TXT books via the local API.
- PDF extraction via PyMuPDF
- Intelligent chunking (paragraph/sentence boundaries)
- Progress saving and resumption
- Retry logic with exponential backoff
- Usage: `python scripts/translate_book.py book.pdf --target uk`

### 3. `libretranslate/nllb_refiner.py` (NEW)
NLLB-200 post-processing refiner. Після Argos Translate перекладає оригінальний текст незалежно за допомогою NLLB-200 і повертає якісніший результат. Lazy-load моделі при першому запиті. Graceful fallback на Argos якщо мова не підтримується або помилка.

Key: `NLLBRefiner`, `get_refiner(model_name)` — singleton.

Активація: `LT_NLLB_REFINER=true`, `LT_NLLB_MODEL=facebook/nllb-200-3.3B`

NLLB lang codes: `eng_Latn`, `ukr_Cyrl` (повний список у `NLLB_LANG_MAP`).

### 4. `docker-compose.yml` (MODIFIED)
- Port mapping: `5001:5000`
- `LT_LOAD_ONLY=en,uk` — only English and Ukrainian models loaded
- Named volume `libretranslate_models` for model persistence

### 4. `libretranslate/templates/` (MODIFIED)
- `index.html` — Vue.js frontend
- `app.js.template` — frontend application logic

---

## API Endpoints

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/` | GET | No | Web UI |
| `/translate` | POST | Optional | Core translation |
| `/translate_file` | POST | Optional | File translation |
| `/detect` | POST | Optional | Language detection |
| `/languages` | GET | No | List supported languages |
| `/health` | GET | No | Health check |
| `/suggest` | POST | No | Submit suggestion |
| `/frontend/settings` | GET | No | Frontend config |
| `/metrics` | GET | Optional | Prometheus metrics |
| `/docs` | GET | No | Swagger UI |

**Translate request body:**
```json
{
  "q": "text or array",
  "source": "en",
  "target": "uk",
  "format": "text",
  "api_key": "optional",
  "preserve_terms": true,
  "alternatives": 0
}
```

---

## Configuration

All config via environment variables with `LT_` prefix or CLI args.

Key variables (set in `default_values.py`):
```bash
LT_HOST=127.0.0.1
LT_PORT=5000
LT_LOAD_ONLY=en,uk                              # Our setting — only load these models
LT_CHAR_LIMIT=-1                                # -1 = unlimited
LT_REQ_LIMIT=-1                                 # -1 = unlimited
LT_API_KEYS=false
LT_REQUIRE_API_KEY_ORIGIN=
LT_METRICS=false
LT_TRANSLATION_CACHE=0                          # 0 = disabled
LT_NLLB_REFINER=false                           # Enable NLLB-200 post-processing
LT_NLLB_MODEL=facebook/nllb-200-distilled-600M # NLLB model to use
```

---

## Development Commands

### Run locally (without Docker)
```bash
pip install -e .
libretranslate --load-only en,uk --port 5000
```

### Run with Docker
```bash
docker compose up --build
# API available at http://localhost:5001
```

### Run tests
```bash
pytest
# or
hatch test
```

### Generate coverage report
```bash
hatch cov
```

### Compile locales (after editing translations)
```bash
python scripts/compile_locales.py
```

### Translate a book
```bash
python scripts/translate_book.py book.pdf --target uk --source en
python scripts/translate_book.py book.txt --target uk
```

---

## Testing

Framework: pytest + pytest-cov
Location: `libretranslate/tests/`

```
tests/
├── test_init.py
└── test_api/
    ├── conftest.py                    # Flask test client fixture
    ├── test_api_translate.py          # POST /translate
    ├── test_api_health.py             # GET /health
    ├── test_api_get_languages.py      # GET /languages
    ├── test_api_detect_language.py    # POST /detect
    ├── test_api_spec.py               # GET /spec
    └── test_api_frontend_settings.py  # GET /frontend/settings
```

---

## Dependencies

Core: `argostranslate==1.11.0`, `Flask==2.2.5`, `Flask-Limiter==2.6.3`,
`Flask-Babel==3.1.0`, `waitress==2.1.2`, `APScheduler==3.9.1.post1`,
`translatehtml==1.5.2`, `argos-translate-files==1.4.0`, `torch==2.4.0`

Optional: `redis==4.4.4` (caching), `prometheus-client==0.15.0` (metrics)

---

## Key Patterns

- **App factory:** `create_app(args)` in `app.py` — always use this, never instantiate Flask directly
- **Config:** Read from `default_values.py` env vars, overridden by CLI args passed to `create_app`
- **Rate limiting:** Flask-Limiter with per-endpoint decorators
- **Models:** Downloaded to `~/.local/share/argos-translate/` (persisted in Docker volume)
- **API keys:** SQLite database at path set by `--api-keys-db-path`
- **Term protection:** Pass `preserve_terms=true` in translate request or use `TermProtectingTranslator` directly

---

## Upstream Repository

https://github.com/LibreTranslate/LibreTranslate

When merging upstream changes, watch for conflicts in:
- `libretranslate/app.py` (our term_protector integration)
- `libretranslate/templates/` (our UI modifications)
- `docker-compose.yml` (our port/env config)
