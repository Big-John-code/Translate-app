# PDF Book Translator — EN → UA

Локальний перекладач технічної PDF-літератури з англійської на українську.
**Безкоштовно. Без інтернету. Повністю на вашому Mac.**

Використовує **MLX** (Apple Silicon native) або **Ollama** як LLM-бекенд.
Модель: `aya-expanse:8b` — навчена на 23 мовах, найкраща якість для української.

---

## Як це працює

```
PDF файл
   ↓
extractor.py    — витягує текст (H1/H2/paragraph/code) + PNG зображення (PyMuPDF)
   ↓
translator.py   — перекладає чанками через MLX або Ollama
                  • зберігає code-блоки незмінними (placeholder round-trip)
                  • checkpoint після кожного чанку → безпечний resume
                  • 40+ технічних термінів залишаються англійськими
   ↓
postprocess.py  — перший вжиток терміна: "зв'язаність (coupling)"
   ↓
books/{id}/output/book_ua.md  +  images/
   ↓
API (port 8000) + Docker Nginx (port 3000) — веб-бібліотека
```

**Все локально.** Жодного API-ключа, жодного інтернету під час перекладу.

---

## Вимоги

- macOS з Apple Silicon (M1/M2/M3/M4) — для MLX бекенду
- Python 3.11+
- Docker Desktop — для веб-інтерфейсу
- `pandoc` + WeasyPrint — для експорту в EPUB/PDF

---

## Перший запуск після клонування

```bash
# registry.json не в репо — стартуємо з порожнього
cp registry.example.json registry.json
```

> `registry.json` ігнорується `.gitignore` — він зберігає ваш особистий список книг
> і не повинен потрапляти до репозиторію.

---

## Встановлення

```bash
# 1. Клонуємо та встановлюємо залежності Python
git clone <repo>
cd LibreTranslate
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Встановити системні залежності
brew install pandoc
brew install pango          # для WeasyPrint (PDF export)

# 3. (Опціонально) Ollama-бекенд замість MLX
brew install ollama
brew services start ollama
ollama pull aya-expanse:8b
```

---

## Запуск

### Веб-інтерфейс (рекомендовано)

```bash
# Термінал 1 — FastAPI бекенд
.venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000

# Термінал 2 — Docker nginx (веб-переглядач)
docker compose up -d

# Відкрити: http://localhost:3000
```

У веб-інтерфейсі можна:
- Завантажити PDF (drag & drop), вказати назву і скільки сторінок пропустити
- Спостерігати прогрес у реальному часі (оновлюється кожні 15 секунд)
- Читати переклад прямо у браузері (з відображенням зображень)
- Завантажити готову книгу у форматі **EPUB** або **PDF**
- Переглядати лог перекладу
- Зупинити переклад (прогрес збережено, можна продовжити або почати знову)
- Видалити книгу (зупиняє процес і очищує файли)

### CLI (без Docker)

```bash
# Перекласти книгу
nohup .venv/bin/python main.py translate \
  --input /path/to/book.pdf \
  --output output/book_ua.md \
  --from-page 21 \
  --chunk-words 400 \
  --backend mlx \
  --title "Назва книги" \
  > output/translation.log 2>&1 &

# Слідкувати за прогресом
tail -f output/translation.log

# Продовжити після перерви (checkpoint зберігається автоматично)
.venv/bin/python main.py translate \
  --input /path/to/book.pdf \
  --output output/book_ua.md \
  --from-page 21 --resume

# Перевірити PDF перед перекладом
.venv/bin/python main.py info --input /path/to/book.pdf

# Переглянути глосарій
.venv/bin/python main.py glossary

# Експортувати в EPUB або PDF
.venv/bin/python main.py export --input output/book_ua.md --format epub
.venv/bin/python main.py export --input output/book_ua.md --format pdf
```

---

## Параметри `translate`

| Параметр | За замовч. | Опис |
|---|---|---|
| `--input` | — | Шлях до PDF (обов'язково) |
| `--output` | `output/book_ua.md` | Вихідний Markdown файл |
| `--from-page` | 1 | Пропустити N сторінок (обкладинка, зміст) |
| `--to-page` | остання | Зупинитись на сторінці N |
| `--chunk-words` | 600 | Розмір чанку в словах |
| `--backend` | `mlx` | `mlx` (Apple Silicon) або `ollama` |
| `--title` | ім'я файлу | Назва книги для заголовку |
| `--checkpoint` | `<output>/.checkpoint.json` | Файл чекпоінту |
| `--resume` | false | Продовжити з чекпоінту |
| `--neural-fix` | false | Другий LLM-прохід для термінів (~2x повільніше) |
| `--glossary` | false | Зберегти окремий файл глосарію |

---

## Структура проекту

```
LibreTranslate/
├── api.py              ← FastAPI бекенд (port 8000)
│                          GET/POST/DELETE /api/books
│                          POST /api/books/{id}/stop
│                          POST /api/books/{id}/restart
│                          GET  /api/books/{id}/export?format=epub|pdf
│                          GET  /api/books/{id}/log
├── main.py             ← CLI: translate / info / glossary / export
├── extractor.py        ← PyMuPDF: блоки тексту + PNG зображень
├── translator.py       ← MLX/Ollama, checkpoint, code preservation, terms
├── glossary.py         ← 77 EN→UA термінів + список KEEP_AS_IS
├── postprocess.py      ← Анотація першого вжитку термінів
├── requirements.txt
├── registry.json       ← Реєстр книг для веб-інтерфейсу
├── docker-compose.yml
├── docker/
│   ├── Dockerfile
│   ├── nginx.conf      ← /api/ → host:8000, /data/ → файли книг
│   └── index.html      ← SPA: бібліотека + рідер
└── books/              ← Книги завантажені через веб-інтерфейс
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

## Як влаштований переклад

### Code-блоки
Перед відправкою чанку до моделі всі ` ``` ``` ` блоки замінюються на плейсхолдери `«CODE_BLOCK_N»` і відновлюються після перекладу — код ніколи не йде до LLM.

### Зображення
Витягуються через PyMuPDF при DPI=150 і зберігаються в `images/`.
Позиція кожного зображення (відносна в межах чанку) фіксується і при записі Markdown вони вставляються між абзацами пропорційно їх позиції в PDF.

### Checkpoint / Resume
Після кожного чанку: `{"chunks": {"0": "...", "1": "..."}, "last_chunk": 5}`.
`progress.json` — легкий файл `{"done": 5, "total": 321}` тільки для UI.
`--resume` пропускає вже перекладені чанки.

### Технічні терміни
40+ патернів в `_FORCE_ENGLISH`: `API`, `Docker`, `CI/CD`, `microservices`, `REST`, `GraphQL`, `DevOps` та ін. — ніколи не перекладаються.
`_fix_english_terms()` — regex post-process після кожного чанку.
`--neural-fix` — другий LLM-виклик для автоматичного пошуку термінів що "протекли" у переклад.

---

## Модель

**aya-expanse:8b** (Cohere) — найкраща безкоштовна модель для перекладу на українську:
- Навчена рівномірно на 23 мовах, включно з українською
- Не "витікає" в інші мови (на відміну від qwen та інших китайських моделей)
- MLX (4-bit quant): `mlx-community/aya-expanse-8b-4bit` — ~6 GB, нативно на Apple Silicon
- Ollama: `aya-expanse:8b` — ~6 GB

---

## Експорт

Підтримується через `pandoc` + WeasyPrint:

```bash
# Через CLI
.venv/bin/python main.py export --input output/book_ua.md --format epub
.venv/bin/python main.py export --input output/book_ua.md --format pdf

# Або через кнопки ⬇ EPUB / ⬇ PDF у веб-інтерфейсі
```

EPUB — рекомендований формат: зберігає структуру глав, зображення, невеликий розмір (~1–15 MB).
PDF — генерується через WeasyPrint (потребує `brew install pango`).

---

## Важливо для Docker / macOS VirtioFS

Docker Desktop на macOS кешує inode bind-mount.
- **Ніколи не видаляти** файли що монтуються в Docker — тільки перезаписувати
- `_write_output()` використовує `os.fsync()` щоб VirtioFS бачило зміни одразу
- Якщо Docker не бачить оновлень: `docker compose restart viewer`
