import tempfile
import unittest
from pathlib import Path

from mindcrafted.generator.course_assembler import assemble_course_platform


class CourseAssemblerTests(unittest.TestCase):
    def test_course_page_uses_real_player_route_and_escapes_content(self):
        manifest = {
            "course": {
                "title": "Curso </script><script>alert(1)</script>",
                "subtitle": "Aprender <seguro>",
                "description": "Descripción & práctica",
                "learning_objectives": ["Comparar <conceptos>"],
            },
            "games": [{
                "chunk_id": "chunk-1",
                "title": "Lección <uno>",
                "subtitle": "Fundamentos & ejemplos",
                "theme": "ocean-dream",
                "learning_objectives": ["Aplicar <ideas>"],
                "status": "success",
            }],
        }
        with tempfile.TemporaryDirectory(prefix="mindcrafted-course-test-") as tmp:
            output = Path(tmp) / "course-safe"
            output.mkdir()
            page = Path(assemble_course_platform(manifest, str(output))).read_text(encoding="utf-8")

        self.assertIn('/play?course=course-safe&amp;game=chunk-1', page)
        self.assertIn("Lección &lt;uno&gt;", page)
        self.assertIn("escapeCourseHtml(o)", page)
        self.assertNotIn("</script><script>alert(1)</script>", page)
        self.assertIn("<\\/script><script>alert(1)<\\/script>", page)


if __name__ == "__main__":
    unittest.main()
