# CLAUDE.md — контекст проекту для Claude Code

## Що це за проект

Локальний перекладач PDF-книг EN→UA на базі MLX (Apple Silicon) або Ollama.
Два режими: **CLI** (`main.py`) і **Веб-інтерфейс** (FastAPI + Docker nginx).

## Ключові файли

| Файл | Роль |
|------|------|
| `api.py` | FastAPI бекенд (port 8000). CRUD книг, stop/restart, export EPUB/PDF, log |
| `main.py` | CLI: команди `translate`, `info`, `glossary`, `export` |
| `extractor.py` | PDF→блоки тексту + PNG зображень. PyMuPDF (fitz) |
| `translator.py` | MLX/Ollama, checkpoint, code-block preservation, `_fix_english_terms` |
| `glossary.py` | `KEEP_AS_IS` + `TECH_GLOSSARY` (77 термінів EN→UA) |
| `postprocess.py` | Перший вжиток терміна → `"термін (term)"` |
| `registry.json` | Реєстр книг для веб-UI: title, output_dir, url_prefix, pid, pdf_path |
| `docker-compose.yml` | Nginx port 3000; монтує `output/`, `output_react/`, `books/` |
| `docker/nginx.conf` | `/api/` → host:8000, `/data/` → alias /data/ |
| `docker/index.html` | SPA: бібліотека + рідер + upload/stop/restart/delete/export |

## Архітектура

```
Web UI upload → POST /api/books → subprocess(main.py translate) → progress.json
                                                                  ↓
                                              GET /api/books — читає progress.json + pid_alive()

CLI: PDF → extract_blocks() → blocks_to_chunks() → translate_chunk() → _write_output()
                                    ↓ code блоки витягуються до LLM, відновлюються після
                                    ↓ _save_checkpoint() → progress.json
```

## Важливі технічні деталі

### Бекенди
- **mlx** (за замовч.) — `mlx-community/aya-expanse-8b-4bit`, Apple Silicon native, ~5–10 с/чанк
- **ollama** — `aya-expanse:8b`, потребує `brew install ollama && ollama pull aya-expanse:8b`

### Code-block preservation
`_extract_code_blocks()` / `_restore_code_blocks()` — плейсхолдер `«CODE_BLOCK_N»`
перед відправкою до LLM і відновлення після. Chunks що містять тільки код — пропускаються.

### Docker / macOS VirtioFS
- **Ніколи не видаляти** файли що монтуються в Docker — тільки перезаписувати
- `_write_output()` використовує `os.fsync()` щоб VirtioFS одразу бачило зміни
- Якщо Docker не бачить зміни: `docker compose restart viewer`

### Checkpoint
- `.checkpoint.json` — `{"chunks": {"0": "...", "1": "..."}, "last_chunk": 2}`
- `progress.json` — `{"done": 3, "total": 321}` тільки для UI
- `--resume` продовжує з `last_chunk + 1`

### Структура книг
- **Нові книги** (завантажені через UI): `books/{id}/book.pdf` + `books/{id}/output/`
- **Легасі** (arch, react): `output/` і `output_react/` — без `pdf_path`, restart недоступний

### API — ключові ендпоінти
- `GET /api/books` — список + статус (running/done/idle)
- `POST /api/books` — upload PDF, запуск перекладу
- `DELETE /api/books/{id}` — SIGTERM→SIGKILL + видалення файлів
- `POST /api/books/{id}/stop` — SIGTERM→SIGKILL, зберігає файли
- `POST /api/books/{id}/restart` — скидає checkpoint/output, перезапускає
- `GET /api/books/{id}/export?format=epub|pdf` — pandoc + WeasyPrint

## Типові команди

```bash
# Запустити API сервер
.venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000

# Запустити Docker (веб-переглядач)
docker compose up -d
docker compose restart viewer  # якщо не бачить оновлень

# CLI переклад
nohup .venv/bin/python main.py translate \
  --input book.pdf --output output/book_ua.md \
  --from-page 21 --chunk-words 400 --backend mlx --title "Назва" \
  > output/translation.log 2>&1 &

# Зупинити переклад
pkill -f "main.py translate"

# Перевірити прогрес
tail -f output/translation.log
cat output/progress.json
```

## Що не чіпати

- `.venv/` — virtualenv з усіма залежностями
- `registry.json` — реєстр книг (редагувати тільки через API)
- Файли в `output/` і `output_react/` — не видаляти (Docker кешує inode)
