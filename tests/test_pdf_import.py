import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mindcrafted.pdf_import import (
    MAX_PDF_BYTES,
    PDFImportError,
    pages_to_markdown,
    validate_pdf,
)
from mindcrafted.server import (
    MAX_MARKDOWN_CHARS,
    _safe_job_id,
    _validate_ai_base_url,
    _validate_generation_content,
    parse_markdown,
    report_minigame_error,
)


class PDFImportTests(unittest.TestCase):
    def test_converts_pages_to_game_ready_markdown(self):
        pages = [
            "Manual de Biología\nCAPÍTULO 1 - LA CÉLULA\nLa célula es la unidad básica de la vida.\n- Membrana celular\nPágina 1",
            "Manual de Biología\nCAPÍTULO 2 - EL ADN\nEl ADN almacena la informa-\nción genética de los seres vivos.\nPágina 2",
            "Manual de Biología\nCAPÍTULO 3 - HERENCIA\nLos genes transmiten características.\nPágina 3",
        ]

        markdown = pages_to_markdown(pages, "biologia.pdf")
        parsed = parse_markdown(markdown)

        self.assertTrue(markdown.startswith("# Manual de Biología"))
        self.assertNotIn("Página 1", markdown)
        self.assertIn("información genética", markdown)
        self.assertGreaterEqual(markdown.count("\n## "), 3)
        self.assertGreaterEqual(len(parsed["chunks"]), 3)
        self.assertIn("ADN", " ".join(chunk["content"] for chunk in parsed["chunks"]))

    def test_document_without_headings_is_split_into_manageable_parts(self):
        pages = [f"Texto educativo de la página {i}. Incluye conceptos y ejemplos suficientes." for i in range(1, 8)]

        markdown = pages_to_markdown(pages, "apuntes-de-clase.pdf")

        self.assertIn("# Texto educativo de la página 1", markdown)
        self.assertGreater(markdown.count("\n## Parte"), 1)

    def test_rejects_invalid_signature_and_oversized_file(self):
        with self.assertRaisesRegex(PDFImportError, "firma PDF"):
            validate_pdf(b"not a pdf", "archivo.pdf")
        with self.assertRaisesRegex(PDFImportError, "límite"):
            validate_pdf(b"%PDF-" + b"0" * MAX_PDF_BYTES, "archivo.pdf")

    def test_filename_cannot_inject_markdown_structure(self):
        markdown = pages_to_markdown(
            ["Material educativo suficientemente extenso para poder crear una lección útil, con conceptos, explicaciones y varios ejemplos claros para estudiantes."],
            "curso.pdf\n## Lección inyectada",
        )
        self.assertNotIn("\n## Lección inyectada", markdown)

    def test_rejects_scanned_or_empty_text(self):
        with self.assertRaisesRegex(PDFImportError, "OCR"):
            pages_to_markdown(["1", "2", "3"], "escaneado.pdf")


class ServerValidationTests(unittest.TestCase):
    def test_generation_content_limits_are_enforced(self):
        valid = {
            "course": {"title": "Curso"},
            "chunks": [{"id": "chunk-1", "title": "Tema", "content": "Contenido"}],
        }
        self.assertIs(_validate_generation_content(valid), valid)

        too_large = {
            "course": {"title": "Curso"},
            "chunks": [{"id": "chunk-1", "title": "Tema", "content": "x" * (MAX_MARKDOWN_CHARS + 1)}],
        }
        with self.assertRaises(Exception):
            _validate_generation_content(too_large)

        traversal = {
            "course": {"title": "Curso"},
            "chunks": [{"id": "../../escape", "title": "Tema", "content": "Contenido"}],
        }
        with self.assertRaises(Exception):
            _validate_generation_content(traversal)

    def test_url_and_job_id_validation(self):
        self.assertEqual(_validate_ai_base_url("https://example.com/v1/"), "https://example.com/v1")
        self.assertEqual(_safe_job_id("abcdef1234"), "abcdef1234")
        for invalid_url in ("file:///etc/passwd", "javascript:alert(1)", "https://user:pass@example.com"):
            with self.assertRaises(Exception):
                _validate_ai_base_url(invalid_url)
        for invalid_id in ("../../secret", "abc", "ABCDEF1234"):
            with self.assertRaises(Exception):
                _safe_job_id(invalid_id)


class ReportEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_minigame_report_is_persisted_without_unbounded_fields(self):
        with tempfile.TemporaryDirectory(prefix="mindcrafted-report-test-") as tmp:
            root = Path(tmp)
            courses = root / "courses"
            reports = root / "reports"
            (courses / "course-1" / "games" / "chunk-1").mkdir(parents=True)
            body = {
                "course_id": "course-1",
                "chunk_id": "chunk-1",
                "minigame_type": "quiz",
                "message": "La pregunta no aparece",
            }
            with patch("mindcrafted.server.COURSES_DIR", courses), patch("mindcrafted.server.REPORTS_DIR", reports):
                response = await report_minigame_error(body)

            saved = json.loads(next(reports.glob("*.json")).read_text(encoding="utf-8"))
            self.assertTrue(response["ok"])
            self.assertEqual(saved["course_id"], "course-1")
            self.assertEqual(saved["message"], body["message"])


if __name__ == "__main__":
    unittest.main()
