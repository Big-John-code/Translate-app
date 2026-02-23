"""
Translation engine with two backends:
  - MLX  (default): mlx-lm + aya-expanse-8b-4bit — native Apple Silicon, fastest
  - Ollama         : HTTP API fallback, model must be running locally
"""

import json
import time
import os
import urllib.request
import urllib.error
from pathlib import Path

from glossary import TECH_GLOSSARY

# ── Config ──────────────────────────────────────────────────────────────────

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "aya-expanse:8b"
MLX_MODEL    = "mlx-community/aya-expanse-8b-4bit"

SYSTEM_PROMPT = """Ти — професійний перекладач технічної літератури з англійської на українську.
Перекладаєш книгу "Fundamentals of Software Architecture" Марка Річардса та Ніла Форда.

Правила:
1. Відповідай ТІЛЬКИ перекладом — без коментарів, без вступних слів
2. Зберігай Markdown: # ## ### — * ** * `код`
3. Блоки коду ``` не перекладай — залишай як є
4. ЗАВЖДИ англійською (не перекладати): API, REST, GraphQL, gRPC, Docker, Kubernetes, CI/CD, DevOps, SOLID, DDD, TDD, ADR, SLA, SQL, NoSQL, AWS, GCP, Azure, software architect, software architecture, software engineering
5. Не перекладай: власні назви, назви компаній, назви інструментів, акроніми
6. Перший вжиток архітектурного терміну: українська (english). Приклад: зв'язаність (coupling)
7. Стиль: академічна українська, чітка і зрозуміла
8. Зберігай структуру абзаців оригіналу
9. Числа, URL, email — без змін"""


# ── Noise filter ─────────────────────────────────────────────────────────────

def _strip_noise(text: str) -> str:
    """Remove CJK characters and lines that are clearly not Ukrainian/English."""
    import re
    text = re.sub(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+[^\n]*', '', text)
    lines = text.splitlines()
    clean = [l for l in lines if l.strip() == '' or re.search(r'[а-яіїєґА-ЯІЇЄҐA-Za-z0-9\s\-#*`_.,!?:()\[\]"]', l)]
    return '\n'.join(clean).strip()


# ── Force English terms ───────────────────────────────────────────────────────

_FORCE_ENGLISH: list[tuple[str, str]] = [
    (r'архітектор[аиуові]?\s+програмного\s+забезпечення', 'software architect'),
    (r'архітектор[аиуові]?\s+програмне\s+забезпечення',  'software architect'),
    (r'архітектур[аиуові]+\s+програмного\s+забезпечення', 'software architecture'),
    (r'програмн[аиоу]+\s+архітектур[аиуові]*',           'software architecture'),
    (r'програмн[аиоу]+\s+архітектор[аиуові]*',           'software architect'),
    (r'інженерія\s+програмного\s+забезпечення',           'software engineering'),
    (r'розробк[аи]\s+програмного\s+забезпечення',         'software development'),
]


def _fix_english_terms(text: str) -> str:
    import re
    for pattern, replacement in _FORCE_ENGLISH:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(text: str, prev_context: str = "") -> str:
    context_part = ""
    if prev_context.strip():
        context_part = f"[Попередній контекст для узгодженості термінології]:\n{prev_context[-400:]}\n\n"

    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"{context_part}"
        f"[Текст для перекладу]:\n{text}\n\n"
        f"[Переклад українською]:"
    )


# ── MLX backend ───────────────────────────────────────────────────────────────

_mlx_model = None
_mlx_tokenizer = None


def _load_mlx_model(model_id: str) -> None:
    global _mlx_model, _mlx_tokenizer
    if _mlx_model is None:
        print(f"  Завантаження MLX моделі {model_id} ...")
        from mlx_lm import load
        _mlx_model, _mlx_tokenizer = load(model_id)
        print("  Модель завантажена в пам'ять (Neural Engine / GPU)")


def _mlx_generate(prompt: str, model_id: str, max_tokens: int = 4096) -> str:
    _load_mlx_model(model_id)
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler
    sampler = make_sampler(temp=0.2, top_p=0.9)
    result = generate(
        _mlx_model,
        _mlx_tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        sampler=sampler,
        verbose=False,
    )
    return _strip_noise(result)


# ── Ollama backend ────────────────────────────────────────────────────────────

def _is_ollama_running() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=3)
        return True
    except Exception:
        return False


def _is_model_available(model: str) -> bool:
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            return any(model in m for m in models)
    except Exception:
        return False


def _ollama_generate(prompt: str, model: str, retries: int = 3) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 4096, "top_p": 0.9},
    }).encode("utf-8")

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                OLLAMA_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read())
                return _strip_noise(result.get("response", ""))
        except urllib.error.URLError as e:
            if attempt == retries - 1:
                raise RuntimeError(f"Ollama недоступний: {e}")
            time.sleep(3)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(3)

    return ""


# ── Neural fix (second pass) ──────────────────────────────────────────────────

_TERM_FIX_PROMPT = """Ти — редактор технічного перекладу. Тобі дано оригінальний англійський текст і його переклад на українську.

Твоє завдання: знайди технічні терміни в оригіналі, які **потрібно залишати англійською** (CamelCase назви, абревіатури, назви фреймворків/бібліотек/інструментів, власні назви продуктів), але які були неправильно перекладені.

Поверни ТІЛЬКИ виправлений Ukrainian текст. Без пояснень, без коментарів.
Якщо виправлень немає — поверни текст без змін."""


def _neural_fix_terms(source: str, translated: str, backend: str, model: str) -> str:
    if not translated.strip() or not source.strip():
        return translated

    prompt = (
        f"{_TERM_FIX_PROMPT}\n\n"
        f"[Оригінал (англійська)]:\n{source[:1200]}\n\n"
        f"[Переклад (до виправлення)]:\n{translated}\n\n"
        f"[Виправлений переклад]:"
    )

    try:
        if backend == "mlx":
            fixed = _mlx_generate(prompt, model, max_tokens=2048)
        else:
            payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 2048, "top_p": 0.9},
            }).encode("utf-8")
            req = urllib.request.Request(
                OLLAMA_URL, data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                fixed = _strip_noise(json.loads(resp.read()).get("response", "")).strip()

        if len(fixed) < len(translated) * 0.5:
            return translated
        return fixed
    except Exception:
        return translated


# ── Checkpoint helpers ────────────────────────────────────────────────────────

def _load_checkpoint(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"chunks": {}, "last_chunk": -1}


def _save_checkpoint(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    progress_path = path.parent / "progress.json"
    progress = {"done": state["last_chunk"] + 1, "total": 321}
    progress_path.write_text(json.dumps(progress), encoding="utf-8")


def _write_output(path: Path, results: list[str], up_to: int) -> None:
    text = "\n\n---\n\n".join(r for r in results[:up_to + 1] if r)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


# ── Main translator class ─────────────────────────────────────────────────────

class Translator:
    def __init__(
        self,
        checkpoint_path: str = ".checkpoint.json",
        model: str | None = None,
        backend: str = "mlx",
    ):
        self.checkpoint_path = Path(checkpoint_path)
        self.backend = backend

        if backend == "mlx":
            self.model = model or MLX_MODEL
            # Trigger model load early so we fail fast if mlx-lm is missing
            _load_mlx_model(self.model)
        else:
            self.model = model or OLLAMA_MODEL
            if not _is_ollama_running():
                raise RuntimeError("Ollama не запущено.\nВиконай: brew services start ollama")
            if not _is_model_available(self.model):
                raise RuntimeError(
                    f"Модель '{self.model}' не завантажена.\n"
                    f"Виконай: ollama pull {self.model}"
                )

    def clear_checkpoint(self) -> None:
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()

    def translate_chunk(self, text: str, prev_context: str = "", neural_fix: bool = False) -> str:
        if not text.strip():
            return text
        prompt = _build_prompt(text, prev_context)

        if self.backend == "mlx":
            result = _mlx_generate(prompt, self.model)
        else:
            result = _ollama_generate(prompt, self.model)

        result = _fix_english_terms(result)

        if neural_fix:
            result = _neural_fix_terms(text, result, self.backend, self.model)

        return result

    def translate_chunks(
        self,
        chunks_text: list[str],
        output_path: str,
        resume: bool = True,
        chunks_imgs: list[list[str]] | None = None,
        neural_fix: bool = False,
    ) -> str:
        state = _load_checkpoint(self.checkpoint_path) if resume else {"chunks": {}, "last_chunk": -1}
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        results: list[str] = [""] * len(chunks_text)
        prev_context = ""

        for idx_str, translated in state["chunks"].items():
            idx = int(idx_str)
            if idx < len(results):
                results[idx] = translated

        start_from = state["last_chunk"] + 1
        total = len(chunks_text)

        from tqdm import tqdm

        print(f"  Бекенд: {self.backend.upper()}")
        print(f"  Модель: {self.model}")
        print(f"  Чанків: {total} (залишилось: {total - start_from})")
        print()

        with tqdm(total=total, initial=start_from, unit="chunk", desc="Переклад") as pbar:
            for i in range(start_from, total):
                t0 = time.time()
                translated = self.translate_chunk(chunks_text[i], prev_context, neural_fix=neural_fix)
                elapsed = time.time() - t0

                if chunks_imgs and i < len(chunks_imgs) and chunks_imgs[i]:
                    imgs_md = "\n\n".join(chunks_imgs[i])
                    translated = translated + "\n\n" + imgs_md

                results[i] = translated
                prev_context = translated

                state["chunks"][str(i)] = translated
                state["last_chunk"] = i
                _save_checkpoint(self.checkpoint_path, state)
                _write_output(out, results, i)

                remaining = total - i - 1
                eta_min = int(remaining * elapsed / 60)
                pbar.update(1)
                pbar.set_postfix({"швидкість": f"{elapsed:.0f}с/чанк", "ETA": f"~{eta_min}хв"})

        full_text = "\n\n---\n\n".join(r for r in results if r)
        out.write_text(full_text, encoding="utf-8")
        return full_text
