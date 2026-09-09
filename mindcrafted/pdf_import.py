"""Conversión segura de documentos PDF con texto a Markdown educativo.

El conversor no usa IA: extrae el texto localmente, elimina encabezados y pies
repetidos y crea secciones ``##`` que el parser de MindCrafted transforma en
lecciones/juegos. Los PDF compuestos únicamente por imágenes requieren OCR y se
rechazan con un mensaje accionable en vez de generar contenido vacío.
"""

from __future__ import annotations

import io
import math
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 150
MAX_MARKDOWN_CHARS = 300_000
MAX_GAME_SECTIONS = 12


class PDFImportError(ValueError):
    """Error de PDF que puede mostrarse directamente al usuario."""


@dataclass(frozen=True)
class PDFImportResult:
    markdown: str
    filename: str
    pages: int
    characters: int
    sections: int
    truncated: bool = False

    def as_dict(self) -> dict:
        return {
            "markdown": self.markdown,
            "filename": self.filename,
            "pages": self.pages,
            "characters": self.characters,
            "sections": self.sections,
            "truncated": self.truncated,
        }


def _safe_title(value: str) -> str:
    value = re.sub(r"[\x00-\x1f]+", " ", value or "")
    value = re.sub(r"\s+", " ", value).strip(" ._-\t")
    return value[:160]


def _fallback_title(filename: str) -> str:
    stem = Path(filename or "documento.pdf").stem
    return _safe_title(re.sub(r"[_-]+", " ", stem)) or "Documento importado"


def _safe_filename(filename: str) -> str:
    basename = Path((filename or "documento.pdf").replace("\\", "/")).name
    basename = re.sub(r"[\x00-\x1f]+", " ", basename).strip()
    return basename[:220] or "documento.pdf"


def validate_pdf(data: bytes, filename: str) -> None:
    if not filename.lower().endswith(".pdf"):
        raise PDFImportError("El archivo debe tener extensión .pdf")
    if not data:
        raise PDFImportError("El archivo PDF está vacío")
    if len(data) > MAX_PDF_BYTES:
        limit = MAX_PDF_BYTES // (1024 * 1024)
        raise PDFImportError(f"El PDF supera el límite de {limit} MB")
    if not data.lstrip()[:5] == b"%PDF-":
        raise PDFImportError("El archivo no tiene una firma PDF válida")


def _extract_with_pypdf(data: bytes) -> tuple[list[str], str]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ModuleNotFoundError from exc

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:
                raise PDFImportError("El PDF está protegido con contraseña") from exc
            if not unlocked:
                raise PDFImportError("El PDF está protegido con contraseña")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise PDFImportError(f"El PDF supera el límite de {MAX_PDF_PAGES} páginas")
        pages = [(page.extract_text() or "") for page in reader.pages]
        metadata = reader.metadata or {}
        title = _safe_title(str(getattr(metadata, "title", "") or ""))
        return pages, title
    except PDFImportError:
        raise
    except (PdfReadError, EOFError, OSError, ValueError) as exc:
        raise PDFImportError("No se pudo leer el PDF; puede estar dañado") from exc


def _extract_with_pdftotext(data: bytes) -> tuple[list[str], str]:
    """Respaldo local para desarrollo si todavía no se instaló pypdf."""
    executable = shutil.which("pdftotext")
    if not executable:
        raise PDFImportError(
            "Falta el lector de PDF. Instala las dependencias con: pip install -r requirements.txt"
        )
    with tempfile.TemporaryDirectory(prefix="mindcrafted-pdf-") as tmp:
        source = Path(tmp) / "source.pdf"
        target = Path(tmp) / "document.txt"
        source.write_bytes(data)
        try:
            proc = subprocess.run(
                [executable, "-layout", str(source), str(target)],
                capture_output=True,
                timeout=45,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PDFImportError("La lectura del PDF agotó el tiempo de espera") from exc
        if proc.returncode != 0 or not target.exists():
            raise PDFImportError("No se pudo leer el PDF; puede estar dañado o protegido")
        # pdftotext separa las páginas con form feed.
        pages = target.read_text(encoding="utf-8", errors="replace").split("\f")
        pages = [page for page in pages if page.strip()]
        if len(pages) > MAX_PDF_PAGES:
            raise PDFImportError(f"El PDF supera el límite de {MAX_PDF_PAGES} páginas")
        return pages, ""


def extract_pdf_pages(data: bytes) -> tuple[list[str], str]:
    try:
        return _extract_with_pypdf(data)
    except ModuleNotFoundError:
        return _extract_with_pdftotext(data)


def _normalized_lines(page: str) -> list[str]:
    page = page.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines: list[str] = []
    for raw in page.splitlines():
        clean = re.sub(r"[ \t]+", " ", raw).strip()
        if clean:
            lines.append(clean)
    return lines


def _line_fingerprint(line: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", line.casefold())).strip()


def _remove_repeated_margins(pages: list[list[str]]) -> list[list[str]]:
    if len(pages) < 3:
        return pages
    candidates: Counter[str] = Counter()
    for lines in pages:
        if len(lines) < 3:
            continue
        for line in list(dict.fromkeys(lines[:2] + lines[-2:])):
            if len(line) <= 180:
                candidates[_line_fingerprint(line)] += 1
    threshold = max(3, math.ceil(len(pages) * 0.55))
    repeated = {line for line, count in candidates.items() if count >= threshold}
    result: list[list[str]] = []
    for lines in pages:
        if len(lines) < 3:
            result.append(lines)
            continue
        last_margin = len(lines) - 2
        result.append([
            line for index, line in enumerate(lines)
            if not ((index < 2 or index >= last_margin) and _line_fingerprint(line) in repeated)
        ])
    return result


_HEADING_RE = re.compile(
    r"^(?:cap[ií]tulo|unidad|tema|lecci[oó]n|m[oó]dulo|parte|secci[oó]n|"
    r"chapter|unit|lesson|module|section)\s+(?:[\divxlcdm]+)(?:\s*[:.\-–—]\s*|\s+).+",
    re.IGNORECASE,
)
_NUMBERED_HEADING_RE = re.compile(r"^\d{1,2}(?:\.\d{1,2}){0,2}[.)]?\s+[A-ZÁÉÍÓÚÑ¿¡].{2,100}$")
_BULLET_RE = re.compile(r"^(?:[•●▪◦‣*-]|\d+[.)])\s+")


def _looks_like_heading(line: str) -> bool:
    if len(line) < 4 or len(line) > 120 or line.endswith((".", ",", ";", ":")):
        return False
    if _HEADING_RE.match(line) or _NUMBERED_HEADING_RE.match(line):
        return True
    letters = [char for char in line if char.isalpha()]
    return len(letters) >= 4 and line.upper() == line and len(line.split()) <= 14


def _as_paragraphs(lines: list[str]) -> list[str]:
    blocks: list[str] = []
    paragraph = ""

    def flush() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(paragraph.strip())
            paragraph = ""

    for line in lines:
        if _BULLET_RE.match(line):
            flush()
            item = _BULLET_RE.sub("", line, count=1).strip()
            blocks.append(f"- {item}")
            continue
        if _looks_like_heading(line):
            flush()
            blocks.append(f"### {line.title() if line.upper() == line else line}")
            continue
        if paragraph.endswith("-") and line[:1].islower():
            paragraph = paragraph[:-1] + line
        else:
            paragraph = f"{paragraph} {line}".strip()
        if line.endswith((".", "?", "!", ":")) or len(paragraph) > 650:
            flush()
    flush()
    return blocks


def pages_to_markdown(pages: list[str], filename: str, metadata_title: str = "") -> str:
    filename = _safe_filename(filename)
    normalized = [_normalized_lines(page) for page in pages]
    cover_lines = [line for page in normalized[:2] for line in page[:4]]
    cleaned = _remove_repeated_margins(normalized)
    if not cleaned:
        raise PDFImportError("El PDF no contiene páginas legibles")
    total_text = " ".join(line for page in cleaned for line in page)
    alphanumeric = sum(char.isalnum() for char in total_text)
    if alphanumeric < max(80, len(cleaned) * 20):
        raise PDFImportError(
            "No se encontró texto suficiente. Si el PDF está escaneado como imagen, aplícale OCR antes de subirlo."
        )

    title = _safe_title(metadata_title) or _fallback_title(filename)
    # Si la primera línea parece una portada, es mejor título que el nombre del archivo.
    first_title = next(
        (
            line for line in cover_lines
            if 4 <= len(line) <= 140 and not _BULLET_RE.match(line) and not _looks_like_heading(line)
        ),
        "",
    )
    if not metadata_title and first_title:
        title = _safe_title(first_title)
        for page in cleaned[:1]:
            if first_title in page:
                page.remove(first_title)
                break

    sections: list[tuple[str, list[str]]] = []
    current_title = "Introducción"
    current_lines: list[str] = []
    for page in cleaned:
        for line in page:
            if _looks_like_heading(line) and len(sections) < MAX_GAME_SECTIONS - 1:
                if current_lines:
                    sections.append((current_title, current_lines))
                current_title = line.title() if line.upper() == line else line
                current_lines = []
            else:
                current_lines.append(line)
    if current_lines:
        sections.append((current_title, current_lines))

    # Los documentos sin títulos se dividen en hasta 8 partes equilibradas.
    if len(sections) == 1 and len(cleaned) > 2:
        sections = []
        group_size = max(1, math.ceil(len(cleaned) / min(8, len(cleaned))))
        for index in range(0, len(cleaned), group_size):
            group = [line for page in cleaned[index:index + group_size] for line in page]
            sections.append((f"Parte {len(sections) + 1}", group))

    rendered = [f"# {title}", "", f"Contenido importado de `{Path(filename).name}`."]
    for section_title, lines in sections:
        blocks = _as_paragraphs(lines)
        if not blocks:
            continue
        # Evita repetir el título como subtítulo interno.
        if blocks and blocks[0].casefold().removeprefix("### ") == section_title.casefold():
            blocks.pop(0)
        if blocks:
            rendered.extend(["", f"## {section_title}", "", "\n\n".join(blocks)])
    return "\n".join(rendered).strip() + "\n"


def import_pdf(data: bytes, filename: str) -> PDFImportResult:
    filename = _safe_filename(filename)
    validate_pdf(data, filename)
    pages, metadata_title = extract_pdf_pages(data)
    markdown = pages_to_markdown(pages, filename, metadata_title)
    truncated = len(markdown) > MAX_MARKDOWN_CHARS
    if truncated:
        markdown = markdown[:MAX_MARKDOWN_CHARS].rsplit("\n", 1)[0]
        markdown += "\n\n> Contenido truncado por el límite de importación.\n"
    return PDFImportResult(
        markdown=markdown,
        filename=Path(filename).name,
        pages=len(pages),
        characters=len(markdown),
        sections=len(re.findall(r"^## ", markdown, re.MULTILINE)),
        truncated=truncated,
    )
