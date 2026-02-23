# CLAUDE.md — контекст проекту для Claude Code

## Що це за проект

Локальний перекладач PDF-книг EN→UA на базі Ollama (aya-expanse:8b).
Перекладає "Fundamentals of Software Architecture" безкоштовно, без інтернету.

## Ключові файли

| Файл | Роль |
|------|------|
| `main.py` | CLI точка входу. Команди: `translate`, `info`, `glossary` |
| `extractor.py` | PDF→блоки тексту + PNG зображень. Використовує PyMuPDF (fitz) |
| `translator.py` | Ollama HTTP API, checkpoint, `_strip_noise`, `_fix_english_terms`, `_neural_fix_terms` |
| `glossary.py` | `KEEP_AS_IS` (терміни що не перекладаються) + `TECH_GLOSSARY` (77 термінів EN→UA) |
| `postprocess.py` | Post-processing: перший вжиток терміна → `"термін (term)"` |
| `docker-compose.yml` | Nginx на порту 3000, сервить `output/book_ua.md` + `progress.json` + `images/` |

## Архітектура перекладу

```
PDF → extract_blocks() → blocks_to_chunks() → translate_chunk() → _write_output()
                                                      ↓
                                           [optional] _neural_fix_terms()
                                                      ↓
                                            _save_checkpoint()  →  progress.json
```

Після кожного чанку: зберігається checkpoint + пишеться в `output/book_ua.md` через `os.fsync()`.

## Важливі технічні деталі

### Docker / macOS VirtioFS
- **Ніколи не видаляти** `output/book_ua.md` і `progress.json` — Docker Desktop на macOS кешує inode bind-mount
- Щоб скинути: `echo "" > output/book_ua.md` (перезаписати, не видаляти)
- `_write_output()` використовує `os.fsync()` щоб VirtioFS одразу бачило зміни
- Якщо Docker не бачить зміни: `docker compose restart viewer`

### Checkpoint
- `.checkpoint.json` — повний стан: `{"chunks": {"0": "...", "1": "..."}, "last_chunk": 2}`
- `progress.json` — легкий файл для UI: `{"done": 3, "total": 321}`
- `--resume` читає checkpoint і продовжує з `last_chunk + 1`

### Моделі
- **aya-expanse:8b** — поточна модель, найкраща для украïнської, ~40с/чанк
- **qwen2.5:14b** — якість вища але "витікає" китайськими символами (проблема тренування)
- `_strip_noise()` — видаляє CJK блоки регексом якщо модель їх генерує

### Терміни що залишаються англійськими
- system prompt явно перераховує: `software architect`, `API`, `Docker`...
- `_fix_english_terms()` — regex post-process для відомих патернів (напр. `архітектор програмного забезпечення` → `software architect`)
- `--neural-fix` — другий Ollama виклик порівнює оригінал і переклад, виправляє будь-які технічні терміни автоматично (~2x повільніше)

### Зображення
- Extracted через `page.get_pixmap(clip=fitz.Rect(bbox))` при DPI=150
- Зберігаються в `output/images/p{page:04d}_img{n:02d}.png`
- В Markdown вставляються як `![...](images/filename.png)` після відповідного чанку

## Типові команди

```bash
# Запуск перекладу в фоні
nohup .venv/bin/python main.py translate \
  --input ../fundamentalsofsoftwarearchitecture.pdf \
  --output output/book_ua.md \
  --from-page 21 --chunk-words 400 --glossary --neural-fix \
  > output/translation.log 2>&1 &

# Стежити за прогресом
tail -f output/translation.log
cat progress.json

# Зупинити
pkill -f "main.py translate"

# Скинути і почати заново
echo '{"chunks":{},"last_chunk":-1}' > .checkpoint.json
echo "" > output/book_ua.md
echo '{"done":0,"total":321}' > progress.json

# Docker
docker compose up -d        # запустити переглядач
docker compose restart viewer  # якщо не бачить оновлень
```

## Що не чіпати

- `output/book_ua.md` і `progress.json` — не видаляти, тільки перезаписувати
- `.venv/` — virtualenv з усіма залежностями
- `output/images/` — PNG з PDF, заново генерується тільки при повному рестарті
