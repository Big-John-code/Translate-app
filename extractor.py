"""
PDF text + image extractor using PyMuPDF.
Extracts text blocks (headings, paragraphs, code) AND images.
Images are rendered from the page region and saved to output/images/.
"""

import re
import fitz  # PyMuPDF
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class Block:
    page_num: int
    kind: str   # "heading1", "heading2", "paragraph", "code", "caption", "image"
    text: str   # for images: markdown image tag  ![](images/...)
    bbox: tuple = None  # (x0, y0, x1, y1) — position on page, used for ordering


def _is_noise(text: str, page_num: int) -> bool:
    t = text.strip()
    if not t or len(t) < 3:
        return True
    if re.fullmatch(r'\d+', t):
        return True
    if re.fullmatch(r'[\d\s]{10,}', t):
        return True
    if re.search(r'ISBN|US \$|CAN \$', t) and len(t) < 80:
        return True
    if re.search(r'Twitter:|linkedin\.com|youtube\.com', t):
        return True
    if re.match(r'^\d+\s*\|\s*', t) or re.match(r'.+\|\s*\d+$', t):
        return True
    if page_num > 5 and len(t) < 40 and not re.search(r'[.,:;]', t):
        if t.isupper() or re.fullmatch(r'[A-Z][a-z ]+', t):
            return True
    return False


def _classify_block(spans_info: list[dict]) -> tuple[str, str]:
    all_text_parts = []
    max_font_size = 0.0
    has_bold = False
    has_mono = False
    all_italic = True

    for span in spans_info:
        text = span["text"]
        size = span["size"]
        font = span["font"].lower()
        flags = span.get("flags", 0)

        all_text_parts.append(text)

        if size > max_font_size:
            max_font_size = size
        if flags & 2**4 or "bold" in font:
            has_bold = True
        if not (flags & 2**1 or "italic" in font or "oblique" in font):
            all_italic = False
        if any(m in font for m in ["mono", "courier", "consola", "inconsolata", "sourcecodepro", "code"]):
            has_mono = True

    text = " ".join(all_text_parts).strip()
    text = re.sub(r'\s+', ' ', text)

    if has_mono:
        kind = "code"
    elif max_font_size >= 18:
        kind = "heading1"
    elif max_font_size >= 14 or (has_bold and max_font_size >= 12):
        kind = "heading2"
    elif all_italic and len(text) < 200:
        kind = "caption"
    else:
        kind = "paragraph"

    return kind, text


def _is_tiny(bbox: tuple) -> bool:
    """Skip images smaller than 60×40 px (icons, decorations, bullets)."""
    x0, y0, x1, y1 = bbox
    return (x1 - x0) < 60 or (y1 - y0) < 40


def extract_blocks(
    pdf_path: str,
    start_page: int = 1,
    end_page: int | None = None,
    images_dir: str | None = None,
    dpi: int = 150,
) -> Iterator[Block]:
    """
    Yield Block objects from the PDF (text + images) in reading order.

    Args:
        pdf_path:   Path to the PDF file.
        start_page: 1-based start page.
        end_page:   1-based end page (inclusive). None = last page.
        images_dir: Directory to save extracted images. None = skip images.
        dpi:        Resolution for rendering image regions (150 is good quality, small size).
    """
    doc = fitz.open(pdf_path)
    total = len(doc)
    end = min(end_page, total) if end_page else total
    start = max(1, start_page)

    images_path = Path(images_dir).resolve() if images_dir else None
    if images_path:
        images_path.mkdir(parents=True, exist_ok=True)

    img_counter: dict[int, int] = {}  # page_num → image count on that page

    for page_idx in range(start - 1, end):
        page = doc[page_idx]
        page_num = page_idx + 1
        raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_IMAGES)

        all_blocks: list[Block] = []

        # ── Text blocks ──
        for block in raw["blocks"]:
            bbox = tuple(block.get("bbox", (0, 0, 0, 0)))

            if block.get("type") == 0:  # text
                spans_info = []
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span["text"].strip():
                            spans_info.append(span)

                if not spans_info:
                    continue

                kind, text = _classify_block(spans_info)
                if _is_noise(text, page_num):
                    continue

                all_blocks.append(Block(page_num=page_num, kind=kind, text=text, bbox=bbox))

            elif block.get("type") == 1 and images_path:  # image
                if _is_tiny(bbox):
                    continue

                img_counter[page_num] = img_counter.get(page_num, 0) + 1
                idx = img_counter[page_num]
                filename = f"p{page_num:04d}_img{idx:02d}.png"
                img_path = images_path / filename

                # Render the image region from the page at given DPI
                zoom = dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)
                clip = fitz.Rect(bbox)
                pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
                pix.save(str(img_path))

                md_tag = f"\n![Рисунок {page_num}-{idx}](images/{filename})\n"
                all_blocks.append(
                    Block(page_num=page_num, kind="image", text=md_tag, bbox=bbox)
                )

        # Sort all blocks by vertical position (top→bottom), then horizontal
        all_blocks.sort(key=lambda b: (b.bbox[1], b.bbox[0]) if b.bbox else (0, 0))

        yield from all_blocks

    doc.close()


def blocks_to_chunks(blocks: Iterator[Block], max_words: int = 600) -> Iterator[list[Block]]:
    """
    Group blocks into translation chunks.
    Images are attached to the chunk they appear in — NOT sent to the translator
    (image blocks are filtered in chunk_to_text and re-inserted after translation).
    """
    chunk: list[Block] = []
    word_count = 0

    for block in blocks:
        block_words = len(block.text.split()) if block.kind != "image" else 0

        if block.kind == "heading1" and chunk:
            yield chunk
            chunk = []
            word_count = 0

        chunk.append(block)
        word_count += block_words

        if word_count >= max_words and block.kind not in ("heading1", "heading2", "image"):
            yield chunk
            chunk = []
            word_count = 0

    if chunk:
        yield chunk


def chunk_to_text(chunk: list[Block]) -> str:
    """Convert chunk to plain text for the translation prompt (images excluded)."""
    parts = []
    for block in chunk:
        if block.kind == "image":
            continue  # images not sent to translator
        elif block.kind == "code":
            parts.append(f"```\n{block.text}\n```")
        elif block.kind == "heading1":
            parts.append(f"# {block.text}")
        elif block.kind == "heading2":
            parts.append(f"## {block.text}")
        elif block.kind == "caption":
            parts.append(f"*{block.text}*")
        else:
            parts.append(block.text)
    return "\n\n".join(parts)


def chunk_images(chunk: list[Block]) -> list[str]:
    """Return markdown image tags from a chunk (to re-insert after translation)."""
    return [b.text for b in chunk if b.kind == "image"]


def chunk_image_positions(chunk: list[Block]) -> list[tuple[float, str]]:
    """
    Return list of (position_fraction, image_md) for each image in the chunk.
    position_fraction is 0.0–1.0: where in the text-block sequence this image appears.
    Used to interleave images at the correct position inside the translated text.
    """
    text_blocks = [b for b in chunk if b.kind != "image"]
    total_text = len(text_blocks)
    if total_text == 0:
        return [(1.0, b.text) for b in chunk if b.kind == "image"]

    text_idx = 0
    result: list[tuple[float, str]] = []
    for block in chunk:
        if block.kind == "image":
            result.append((text_idx / total_text, block.text))
        else:
            text_idx += 1
    return result


def get_total_pages(pdf_path: str) -> int:
    doc = fitz.open(pdf_path)
    n = len(doc)
    doc.close()
    return n
