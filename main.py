#!/usr/bin/env python3
"""
PDF Technical Book Translator
Translates "Fundamentals of Software Architecture" EN → UK using Ollama (aya-expanse:8b).

Usage:
    python main.py translate --input book.pdf --output output/book_ua.md
    python main.py translate --input book.pdf --output output/book_ua.md --from-page 50 --to-page 100
    python main.py translate --input book.pdf --output output/book_ua.md --resume
    python main.py info --input book.pdf
    python main.py glossary
"""

import argparse
import sys
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


def cmd_translate(args: argparse.Namespace) -> None:
    from extractor import extract_blocks, blocks_to_chunks, chunk_to_text, chunk_images, get_total_pages
    from translator import Translator
    from glossary import build_glossary_note

    pdf_path = args.input
    if not Path(pdf_path).exists():
        print(f"[помилка] Файл не знайдено: {pdf_path}")
        sys.exit(1)

    total_pages = get_total_pages(pdf_path)
    start_page = args.from_page or 1
    end_page = args.to_page or total_pages

    output_path = Path(args.output)
    images_dir = str(output_path.parent / "images")

    print(f"PDF:           {pdf_path}")
    print(f"Сторінки:      {start_page}–{end_page} (з {total_pages})")
    print(f"Вихідний файл: {output_path}")
    print(f"Зображення:    {images_dir}")
    print(f"Розмір чанку:  {args.chunk_words} слів")
    print(f"Відновлення:   {'так' if args.resume else 'ні'}")
    print()

    # Step 1: Extract blocks + images
    print("Крок 1/2 — Витягуємо текст і зображення з PDF...")
    blocks = list(extract_blocks(
        pdf_path,
        start_page=start_page,
        end_page=end_page,
        images_dir=images_dir,
        dpi=150,
    ))
    text_blocks = [b for b in blocks if b.kind != "image"]
    image_blocks = [b for b in blocks if b.kind == "image"]
    print(f"  Текстових блоків: {len(text_blocks)}")
    print(f"  Зображень:        {len(image_blocks)}")

    # Step 2: Group into chunks
    chunks = list(blocks_to_chunks(iter(blocks), max_words=args.chunk_words))
    chunks_text = [chunk_to_text(c) for c in chunks]
    chunks_imgs = [chunk_images(c) for c in chunks]
    print(f"  Чанків для перекладу: {len(chunks)}")
    print()

    # Step 3: Translate
    print("Крок 2/2 — Перекладаємо...")
    translator = Translator(checkpoint_path=".checkpoint.json", backend=args.backend)

    if not args.resume:
        translator.clear_checkpoint()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    glossary_header = (
        f"# Основи архітектури програмного забезпечення\n"
        f"*Марк Річардс та Ніл Форд — Fundamentals of Software Architecture (O'Reilly, 2020)*\n\n"
        f"> Переклад: сторінки {start_page}–{end_page} з {total_pages}\n\n"
        f"---\n\n"
    )

    translated = translator.translate_chunks(
        chunks_text=chunks_text,
        chunks_imgs=chunks_imgs,
        output_path=str(output_path),
        resume=args.resume,
        neural_fix=args.neural_fix,
    )

    final = glossary_header + translated
    output_path.write_text(final, encoding="utf-8")

    # Post-process: add English originals to first occurrence of each term
    print("Крок 3/3 — Post-processing термінів...")
    from postprocess import process as postprocess_text
    current = output_path.read_text(encoding="utf-8")
    processed, changes = postprocess_text(current)
    output_path.write_text(processed, encoding="utf-8")
    print(f"  Термінів оновлено: {len(changes)}")
    for c in changes:
        print(f"  {c}")

    print()
    print(f"Готово! Файл збережено: {output_path}")
    print(f"Зображень збережено:    {len(list(Path(images_dir).glob('*.png')))} шт.")
    print(f"Розмір файлу:           {output_path.stat().st_size / 1024:.1f} KB")

    if args.glossary:
        glossary_path = output_path.with_stem(output_path.stem + "_glossary")
        glossary_path.write_text(build_glossary_note(), encoding="utf-8")
        print(f"Глосарій: {glossary_path}")


def cmd_info(args: argparse.Namespace) -> None:
    from extractor import extract_blocks, get_total_pages

    pdf_path = args.input
    if not Path(pdf_path).exists():
        print(f"[помилка] Файл не знайдено: {pdf_path}")
        sys.exit(1)

    total = get_total_pages(pdf_path)
    print(f"Файл:    {pdf_path}")
    print(f"Сторінок: {total}")
    print()
    print("Витягуємо перші 5 сторінок для перевірки...")
    blocks = list(extract_blocks(pdf_path, start_page=1, end_page=5, images_dir=None))
    imgs = [b for b in blocks if b.kind == "image"]
    text = [b for b in blocks if b.kind != "image"]
    print(f"Знайдено {len(text)} текстових блоків, {len(imgs)} зображень на перших 5 сторінках:\n")
    for b in blocks[:20]:
        kind_tag = {
            "heading1": "[H1]", "heading2": "[H2]",
            "paragraph": "[  ]", "code": "[CODE]",
            "caption": "[CAP]", "image": "[IMG]",
        }.get(b.kind, "[?]")
        preview = b.text[:80] + ("…" if len(b.text) > 80 else "")
        print(f"  p.{b.page_num:03d} {kind_tag} {preview}")

    all_blocks = list(extract_blocks(pdf_path, images_dir=None))
    total_words = sum(len(b.text.split()) for b in all_blocks if b.kind != "image")
    total_imgs = sum(1 for b in all_blocks if b.kind == "image")
    est_input_tokens = int(total_words * 1.5)
    est_output_tokens = int(total_words * 1.8)
    est_cost_usd = (est_input_tokens * 3 + est_output_tokens * 15) / 1_000_000
    print()
    print(f"Оцінка для повної книги ({total} стор.):")
    print(f"  Слів у тексті:    ~{total_words:,}")
    print(f"  Зображень у PDF:  ~{total_imgs}")
    print(f"  Вхідних токенів:  ~{est_input_tokens:,}")
    print(f"  Вихідних токенів: ~{est_output_tokens:,}")
    print(f"  Вартість API (якщо Claude): ~${est_cost_usd:.2f} USD")


def cmd_export(args: argparse.Namespace) -> None:
    import shutil
    import subprocess

    if not shutil.which("pandoc"):
        print("[помилка] pandoc не встановлено.")
        print("Встанови: brew install pandoc")
        sys.exit(1)

    src = Path(args.input)
    if not src.exists():
        print(f"[помилка] Файл не знайдено: {src}")
        sys.exit(1)

    fmt = args.format.lower()
    if fmt not in ("epub", "pdf"):
        print("[помилка] Формат має бути epub або pdf")
        sys.exit(1)

    out = Path(args.output) if args.output else src.with_suffix(f".{fmt}")
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["pandoc", str(src), "-o", str(out)]

    if fmt == "epub":
        cmd += [
            "--epub-chapter-level=1",
            "-V", "lang=uk",
        ]
        cover = Path("cover.png")
        if cover.exists():
            cmd += [f"--epub-cover-image={cover}"]

    elif fmt == "pdf":
        if not shutil.which("xelatex"):
            print("[увага] xelatex не знайдено, використовую wkhtmltopdf або pdflatex...")
        cmd += [
            "--pdf-engine=xelatex",
            "-V", "mainfont=Arial",
            "-V", "lang=uk",
            "-V", "geometry:margin=2cm",
        ]

    print(f"Конвертую {src} → {out} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[помилка] pandoc завершився з кодом {result.returncode}")
        print(result.stderr)
        sys.exit(1)

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"Готово! {out} ({size_mb:.1f} MB)")


def cmd_glossary(_args: argparse.Namespace) -> None:
    from glossary import build_glossary_note, TECH_GLOSSARY
    print(f"Глосарій: {len(TECH_GLOSSARY)} технічних термінів\n")
    for en, ua in sorted(TECH_GLOSSARY.items()):
        print(f"  {en:<45} → {ua}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Перекладач технічних PDF-книг EN → UA (Ollama / Claude API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    # --- translate ---
    p_tr = sub.add_parser("translate", help="Перекласти PDF")
    p_tr.add_argument("--input", "-i", required=True, help="Шлях до PDF файлу")
    p_tr.add_argument("--output", "-o", default="output/book_ua.md", help="Вихідний Markdown файл")
    p_tr.add_argument("--from-page", type=int, default=None, help="Початкова сторінка")
    p_tr.add_argument("--to-page", type=int, default=None, help="Кінцева сторінка")
    p_tr.add_argument("--chunk-words", type=int, default=600, help="Слів у чанку (за замовч.: 600)")
    p_tr.add_argument("--resume", action="store_true", help="Продовжити з checkpoint")
    p_tr.add_argument("--glossary", action="store_true", help="Зберегти окремий глосарій")
    p_tr.add_argument("--neural-fix", action="store_true", help="Нейронне виправлення термінів після перекладу (повільніше, але точніше)")
    p_tr.add_argument("--backend", default="mlx", choices=["mlx", "ollama"], help="Бекенд: mlx (швидше, Apple Silicon) або ollama (за замовч.: mlx)")

    # --- info ---
    p_info = sub.add_parser("info", help="Інформація про PDF")
    p_info.add_argument("--input", "-i", required=True, help="Шлях до PDF файлу")

    # --- glossary ---
    sub.add_parser("glossary", help="Показати глосарій")

    # --- export ---
    p_exp = sub.add_parser("export", help="Конвертувати переклад у EPUB або PDF")
    p_exp.add_argument("--input", "-i", default="output/book_ua.md", help="Markdown файл (за замовч.: output/book_ua.md)")
    p_exp.add_argument("--output", "-o", default=None, help="Вихідний файл (за замовч.: поряд з input)")
    p_exp.add_argument("--format", "-f", default="epub", choices=["epub", "pdf"], help="Формат: epub або pdf (за замовч.: epub)")

    args = parser.parse_args()

    if args.command == "translate":
        cmd_translate(args)
    elif args.command == "info":
        cmd_info(args)
    elif args.command == "glossary":
        cmd_glossary(args)
    elif args.command == "export":
        cmd_export(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
