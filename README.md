# PDF Book Translator — EN → UA

Перекладає технічну літературу з англійської на українську **локально і безкоштовно**.
Використовує Ollama (локальний LLM) замість платних API.

Оптимізовано для **"Fundamentals of Software Architecture"** (Mark Richards & Neal Ford, O'Reilly 2020).

---

## Як це працює

```
PDF файл
   ↓
extractor.py     — витягує текст + зображення (PyMuPDF)
   ↓
translator.py    — перекладає чанками через Ollama (aya-expanse:8b)
                   → після кожного чанку: checkpoint + запис у файл
   ↓
postprocess.py   — перший вжиток терміна: "зв'язаність (coupling)"
   ↓
output/book_ua.md  +  output/images/
   ↓
Docker (Nginx)   — веб-переглядач на localhost:3000
```

**Все локально.** Жодного API-ключа, жодного інтернету під час перекладу.

---

## Вимоги

- macOS (протестовано на M4)
- Python 3.11+
- [Ollama](https://ollama.com) — локальний LLM-сервер
- Docker Desktop — для веб-переглядача

---

## Встановлення

```bash
# 1. Встановити Ollama
brew install ollama
brew services start ollama

# 2. Завантажити модель (~5GB, один раз)
ollama pull aya-expanse:8b

# 3. Встановити залежності Python
cd /Users/ivantsymbrak/Code/LibreTranslate
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Запуск веб-переглядача

```bash
docker compose up -d
# Відкрити: http://localhost:3000
```

Сайт автоматично оновлюється кожні 15 секунд — видно прогрес перекладу в реальному часі.

---

## Використання

### Перевірити PDF

```bash
python main.py info --input ../fundamentalsofsoftwarearchitecture.pdf
```

### Перекласти всю книгу

```bash
nohup .venv/bin/python main.py translate \
  --input ../fundamentalsofsoftwarearchitecture.pdf \
  --output output/book_ua.md \
  --from-page 21 \
  --chunk-words 400 \
  --glossary \
  > output/translation.log 2>&1 &
```

> `--from-page 21` — пропускає обкладинку і зміст, починає з Розділу 1.

### З нейронним виправленням термінів (точніше, але ~2x повільніше)

```bash
nohup .venv/bin/python main.py translate \
  --input ../fundamentalsofsoftwarearchitecture.pdf \
  --output output/book_ua.md \
  --from-page 21 \
  --chunk-words 400 \
  --glossary \
  --neural-fix \
  > output/translation.log 2>&1 &
```

`--neural-fix` запускає другий LLM-прохід після кожного чанку: модель порівнює оригінал і переклад, знаходить технічні терміни (CamelCase, абревіатури, назви бібліотек), які були перекладені, і відновлює їх англійською — автоматично, без ручного списку.

### Продовжити після перерви

```bash
.venv/bin/python main.py translate \
  --input ../fundamentalsofsoftwarearchitecture.pdf \
  --output output/book_ua.md \
  --from-page 21 \
  --resume
```

### Стежити за прогресом

```bash
tail -f output/translation.log
cat progress.json   # {"done": 42, "total": 321}
```

### Переглянути глосарій

```bash
python main.py glossary
```

---

## Структура проекту

```
LibreTranslate/
├── main.py            ← CLI: команди translate / info / glossary
├── extractor.py       ← PyMuPDF: витягує текст + зображення з PDF
├── translator.py      ← Ollama API, checkpoint/resume, neural-fix
├── glossary.py        ← 77 архітектурних термінів EN→UA
├── postprocess.py     ← Анотує перший вжиток: "термін (term)"
├── requirements.txt
├── docker-compose.yml
├── docker/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── index.html     ← веб-переглядач (marked.js + auto-refresh)
├── .checkpoint.json   ← прогрес перекладу (автоматично)
├── progress.json      ← {"done": N, "total": 321} для UI
└── output/
    ├── book_ua.md     ← готовий переклад
    ├── images/        ← зображення з PDF (PNG)
    └── translation.log
```

---

## Компоненти

| Файл | Що робить |
|------|-----------|
| `extractor.py` | Читає PDF, класифікує блоки (H1/H2/paragraph/code/caption/image), рендерить зображення як PNG |
| `translator.py` | Надсилає чанки до Ollama, зберігає checkpoint після кожного, фільтрує CJK-символи, виправляє англійські терміни |
| `glossary.py` | `KEEP_AS_IS` — терміни що залишаються англійськими; `TECH_GLOSSARY` — словник EN→UA |
| `postprocess.py` | Пробігає готовий текст, при першому вживанні додає оригінал: `зв'язаність (coupling)` |
| `main.py` | Склеює все разом, CLI інтерфейс |

---

## Модель

**aya-expanse:8b** (Cohere) — найкраща безкоштовна модель для перекладу на українську:
- Навчена на 23 мовах з рівним балансом
- Не "витікає" в інші мови (на відміну від китайських моделей як qwen)
- Потребує ~6GB RAM, комфортно працює на M4 16GB

---

## Checkpoint / Resume

Після кожного перекладеного чанку стан зберігається в `.checkpoint.json`.
При перезапуску з `--resume` переклад продовжується з місця зупинки.

Щоб почати заново (скинути без видалення файлів — важливо для Docker):

```bash
echo '{"chunks":{},"last_chunk":-1}' > .checkpoint.json
echo "" > output/book_ua.md
echo '{"done":0,"total":321}' > progress.json
```

---

## Правила перекладу

Терміни, що **завжди залишаються англійською**: `software architect`, `software architecture`,
`software engineering`, `API`, `REST`, `GraphQL`, `Docker`, `Kubernetes`, `CI/CD`, `DevOps` та ін.

Перший вжиток архітектурного терміна: `зв'язаність (coupling)`, `зчепленість (cohesion)` тощо.
