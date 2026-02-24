#!/usr/bin/env python3
"""
Book Translation Manager API
Run: .venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

app = FastAPI(title="Book Translator API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PROJECT = Path(__file__).parent
BOOKS_DIR = PROJECT / "books"
REGISTRY = PROJECT / "registry.json"
VENV_PY = PROJECT / ".venv" / "bin" / "python"


# ── Registry helpers ──────────────────────────────────────────────────────────

def load_reg() -> dict:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {}


def save_reg(data: dict) -> None:
    REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_progress(output_dir: Path) -> dict:
    p = output_dir / "progress.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"done": 0, "total": 0}


def pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def kill_process(pid) -> None:
    """SIGTERM → wait 3s → SIGKILL якщо ще живий."""
    if not pid_alive(pid):
        return
    try:
        os.kill(int(pid), 15)
        for _ in range(30):
            time.sleep(0.1)
            if not pid_alive(pid):
                return
        if pid_alive(pid):
            os.kill(int(pid), 9)
    except Exception:
        pass


def _launch_translation(pdf_path: Path, out_dir: Path, title: str, from_page: int) -> subprocess.Popen:
    log = open(out_dir / "translation.log", "w")
    return subprocess.Popen(
        [
            str(VENV_PY), "main.py", "translate",
            "--input", str(pdf_path),
            "--output", str(out_dir / "book_ua.md"),
            "--from-page", str(from_page),
            "--chunk-words", "400",
            "--backend", "mlx",
            "--checkpoint", str(out_dir / ".checkpoint.json"),
            "--title", title,
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
        cwd=str(PROJECT),
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/books")
def list_books():
    reg = load_reg()
    result = {}
    for book_id, book in reg.items():
        out = PROJECT / book["output_dir"]
        prog = read_progress(out)
        done, total = prog.get("done", 0), prog.get("total", 0)
        pid = book.get("pid")
        if pid_alive(pid):
            status = "running"
        elif total > 0 and done >= total:
            status = "done"
        else:
            status = "idle"
        result[book_id] = {**book, "done": done, "total": total, "status": status}
    return result


@app.post("/api/books")
async def create_book(
    file: UploadFile,
    title: str = Form(...),
    from_page: int = Form(1),
):
    book_id = uuid.uuid4().hex[:10]
    book_dir = BOOKS_DIR / book_id
    out_dir = book_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "images").mkdir(exist_ok=True)

    # Save PDF
    pdf_path = book_dir / "book.pdf"
    pdf_path.write_bytes(await file.read())

    # Init empty output files (nginx can serve them right away)
    (out_dir / "book_ua.md").write_text("", encoding="utf-8")
    (out_dir / "progress.json").write_text('{"done":0,"total":0}', encoding="utf-8")
    checkpoint = out_dir / ".checkpoint.json"
    checkpoint.write_text('{"chunks":{},"last_chunk":-1}', encoding="utf-8")

    # Launch translation subprocess
    proc = _launch_translation(pdf_path, out_dir, title, from_page)

    reg = load_reg()
    reg[book_id] = {
        "title": title,
        "from_page": from_page,
        "output_dir": str(out_dir.relative_to(PROJECT)),
        "url_prefix": f"/data/books/{book_id}/output",
        "pdf_path": str(pdf_path),
        "created_at": datetime.now().isoformat(),
        "pid": proc.pid,
    }
    save_reg(reg)
    return {"id": book_id, "status": "started"}


@app.delete("/api/books/{book_id}")
def delete_book(book_id: str):
    reg = load_reg()
    if book_id not in reg:
        raise HTTPException(status_code=404, detail="Not found")

    kill_process(reg[book_id].get("pid"))

    # Remove files: new books live in books/{id}/, legacy books in output/ etc.
    out_dir_rel = Path(reg[book_id]["output_dir"])
    if str(out_dir_rel).startswith("books/"):
        shutil.rmtree(PROJECT / out_dir_rel.parent, ignore_errors=True)
    else:
        shutil.rmtree(PROJECT / out_dir_rel, ignore_errors=True)

    del reg[book_id]
    save_reg(reg)
    return {"status": "deleted"}


@app.post("/api/books/{book_id}/stop")
def stop_book(book_id: str):
    reg = load_reg()
    if book_id not in reg:
        raise HTTPException(status_code=404, detail="Not found")
    kill_process(reg[book_id].get("pid"))
    reg[book_id]["pid"] = None
    save_reg(reg)
    return {"status": "stopped"}


@app.post("/api/books/{book_id}/restart")
def restart_book(book_id: str):
    reg = load_reg()
    if book_id not in reg:
        raise HTTPException(status_code=404, detail="Not found")

    book = reg[book_id]
    pdf_path_str = book.get("pdf_path")
    if not pdf_path_str:
        raise HTTPException(status_code=400, detail="PDF не знайдено — ця книга не підтримує перезапуск")
    pdf_path = Path(pdf_path_str)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF файл не знайдено на диску")

    kill_process(book.get("pid"))

    out_dir = PROJECT / book["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "book_ua.md").write_text("", encoding="utf-8")
    (out_dir / "progress.json").write_text('{"done":0,"total":0}', encoding="utf-8")
    (out_dir / ".checkpoint.json").write_text('{"chunks":{},"last_chunk":-1}', encoding="utf-8")
    images_dir = out_dir / "images"
    if images_dir.exists():
        shutil.rmtree(images_dir)
    images_dir.mkdir(exist_ok=True)

    proc = _launch_translation(pdf_path, out_dir, book["title"], book.get("from_page", 1))
    reg[book_id]["pid"] = proc.pid
    save_reg(reg)
    return {"status": "restarted", "pid": proc.pid}


@app.get("/api/books/{book_id}/log")
def get_log(book_id: str):
    reg = load_reg()
    if book_id not in reg:
        raise HTTPException(status_code=404, detail="Not found")
    log = PROJECT / reg[book_id]["output_dir"] / "translation.log"
    if log.exists():
        return {"log": log.read_text(encoding="utf-8", errors="replace")[-4000:]}
    return {"log": ""}


@app.get("/api/books/{book_id}/export")
def export_book(book_id: str, format: str = "epub"):
    """Generate and stream EPUB or PDF via pandoc."""
    reg = load_reg()
    if book_id not in reg:
        raise HTTPException(status_code=404, detail="Not found")

    fmt = format.lower()
    if fmt not in ("epub", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be epub or pdf")

    if not shutil.which("pandoc"):
        raise HTTPException(status_code=503, detail="pandoc не встановлено на сервері")

    out_dir = PROJECT / reg[book_id]["output_dir"]
    md_path = out_dir / "book_ua.md"
    if not md_path.exists() or md_path.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="Переклад ще не готовий")

    # Temp file so concurrent requests don't collide
    tmp = tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False)
    out_path = Path(tmp.name)
    tmp.close()

    cmd = ["pandoc", str(md_path), "-o", str(out_path), "--resource-path", str(out_dir)]
    if fmt == "epub":
        cmd += ["--epub-chapter-level=1", "-V", "lang=uk"]
    elif fmt == "pdf":
        weasyprint = str(PROJECT / ".venv" / "bin" / "weasyprint")
        cmd += [f"--pdf-engine={weasyprint}", "-V", "lang=uk"]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        out_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"pandoc: {result.stderr[:400]}")

    title_slug = reg[book_id]["title"][:40].replace(" ", "_")
    media = "application/epub+zip" if fmt == "epub" else "application/pdf"
    return FileResponse(
        path=str(out_path),
        media_type=media,
        filename=f"{title_slug}.{fmt}",
        background=BackgroundTask(lambda p=out_path: p.unlink(missing_ok=True)),
    )
