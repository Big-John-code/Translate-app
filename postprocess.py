"""
Post-processor for translated markdown.
Finds the FIRST occurrence of each Ukrainian technical term and appends
the English original in parentheses: зв'язаність (coupling)

Run after translation is complete (or anytime — safe to run multiple times).
Usage:
    python postprocess.py output/book_ua.md
    python postprocess.py output/book_ua.md --preview   # show changes without saving
"""

import re
import sys
import argparse
from pathlib import Path

# ── Glossary: Ukrainian → English ──────────────────────────────────────────
# Only terms that are meaningful to show with English original.
# Format: "ukrainian_term": "English Term"
TERMS: dict[str, str] = {
    # Core concepts
    "зв'язаність":              "coupling",
    "зчепленість":              "cohesion",
    "модульність":              "modularity",
    "абстракція":               "abstraction",
    "абстрактність":            "abstractness",
    "нестабільність":           "instability",
    "конасценція":              "connascence",
    "доцентрова зв'язаність":   "afferent coupling",
    "відцентрова зв'язаність":  "efferent coupling",

    # Architecture characteristics
    "архітектурні характеристики": "architecture characteristics",
    "архітектурна характеристика": "architecture characteristic",
    "архітектурний квант":      "architecture quantum",
    "фітнес-функція":           "fitness function",
    "обмежений контекст":       "bounded context",

    # Quality attributes
    "масштабованість":          "scalability",
    "доступність":              "availability",
    "надійність":               "reliability",
    "зручність супроводу":      "maintainability",
    "тестованість":             "testability",
    "придатність до розгортання": "deployability",
    "еластичність":             "elasticity",
    "продуктивність":           "performance",
    "спостережуваність":        "observability",
    "відмовостійкість":         "fault tolerance",
    "відновлюваність":          "recoverability",

    # Architecture styles
    "шарувата архітектура":     "layered architecture",
    "мікроядерна архітектура":  "microkernel architecture",
    "конвеєрна архітектура":    "pipeline architecture",
    "мікросервісна архітектура": "microservices architecture",
    "мікросервіси":             "microservices",
    "великий клубок бруду":     "big ball of mud",

    # Patterns & decisions
    "антипатерн":               "anti-pattern",
    "антипатерни":              "anti-patterns",
    "запис архітектурного рішення": "ADR",
    "штурм ризиків":            "risk storming",
    "матриця ризиків":          "risk matrix",

    # Engineering
    "безперервне постачання":   "continuous delivery",
    "безперервна інтеграція":   "continuous integration",
    "безперервне розгортання":  "continuous deployment",
    "технічний борг":           "technical debt",
    "рефакторинг":              "refactoring",
    "оркестрація":              "orchestration",
    "хореографія":              "choreography",
    "сага":                     "saga",
    "компроміс":                "trade-off",
}

# Regex flags
_FLAGS = re.IGNORECASE


def _make_pattern(term: str) -> re.Pattern:
    """Build a word-boundary-aware pattern for a Ukrainian term."""
    escaped = re.escape(term)
    # Ukrainian word boundary: look for term NOT already followed by (...)
    return re.compile(
        r'(?<!\w)(' + escaped + r')(?!\w)(?!\s*\([^)]*\))',
        _FLAGS
    )


def process(text: str, preview: bool = False) -> tuple[str, list[str]]:
    """
    Add English originals to first occurrence of each Ukrainian term.

    Returns:
        (processed_text, list_of_changes)
    """
    changes: list[str] = []
    seen: set[str] = set()

    # Skip code blocks — don't modify content inside ``` ... ```
    code_blocks: list[tuple[int, int]] = []
    for m in re.finditer(r'```.*?```', text, re.DOTALL):
        code_blocks.append((m.start(), m.end()))

    def in_code_block(pos: int) -> bool:
        return any(s <= pos < e for s, e in code_blocks)

    # Process each term
    for ua_term, en_term in sorted(TERMS.items(), key=lambda x: -len(x[0])):
        key = ua_term.lower()
        if key in seen:
            continue

        pattern = _make_pattern(ua_term)
        match = pattern.search(text)

        if not match:
            continue

        # Skip if inside a code block
        if in_code_block(match.start()):
            # Try to find the next occurrence outside code blocks
            for m in pattern.finditer(text):
                if not in_code_block(m.start()):
                    match = m
                    break
            else:
                continue

        seen.add(key)
        original = match.group(1)
        replacement = f"{original} ({en_term})"
        changes.append(f"  «{original}» → «{replacement}»")

        # Replace only this specific occurrence
        start, end = match.span(1)
        text = text[:start] + replacement + text[end:]

        # Rebuild code_blocks offsets after replacement (offset shift)
        delta = len(replacement) - len(original)
        code_blocks = [
            (s + delta if s > start else s, e + delta if e > start else e)
            for s, e in code_blocks
        ]

    return text, changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-process translated markdown")
    parser.add_argument("file", help="Path to translated .md file")
    parser.add_argument("--preview", action="store_true", help="Show changes without saving")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"[помилка] Файл не знайдено: {path}")
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    processed, changes = process(text)

    if not changes:
        print("Змін немає — всі терміни вже мають англійські оригінали.")
        return

    print(f"Знайдено {len(changes)} термінів для оновлення:\n")
    for c in changes:
        print(c)

    if args.preview:
        print("\n[preview] Файл не змінено.")
        return

    # Backup original
    backup = path.with_suffix(".md.bak")
    backup.write_text(text, encoding="utf-8")

    path.write_text(processed, encoding="utf-8")
    print(f"\nГотово! Файл оновлено: {path}")
    print(f"Резервна копія: {backup}")


if __name__ == "__main__":
    main()
