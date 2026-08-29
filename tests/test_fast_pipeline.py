import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mindcrafted.generator import pipeline
from mindcrafted.generator.fast_template import FAST_THEME


class FastPipelineTests(unittest.IsolatedAsyncioTestCase):
    def test_normalization_limits_content_and_forces_known_speakers(self):
        data = {
            "title": "Titulo ignorado",
            "introduction": "Introduccion breve",
            "dialogue": [
                {"speaker": "guía", "text": "Primera linea"},
                {"speaker": "jugador", "text": "Segunda linea"},
                {"speaker": "desconocido", "text": "Tercera linea"},
            ],
        }

        result = pipeline._normalize_fast_content(data, "Tema", "Titulo fijo")

        self.assertEqual(result["title"], "Titulo fijo")
        self.assertEqual(len(result["dialogue"]), 4)
        self.assertEqual(result["dialogue"][0]["speaker"], "AURA")
        self.assertEqual(result["dialogue"][1]["speaker"], "{player}")
        self.assertEqual(result["dialogue"][2]["speaker"], "AURA")

    async def test_fast_generation_uses_one_ai_call_and_fixed_template(self):
        calls = []

        async def fake_generate(prompt, system_prompt, **kwargs):
            calls.append((prompt, system_prompt, kwargs))
            return json.dumps(
                {
                    "title": "Titulo devuelto",
                    "introduction": "La nave Horizonte estudia el oceano desde la orbita.",
                    "dialogue": [
                        {"speaker": "AURA", "text": "Observa el planeta."},
                        {"speaker": "{player}", "text": "Veo un mundo cubierto de agua."},
                        {"speaker": "Bit", "text": "Los sensores estan listos."},
                        {"speaker": "AURA", "text": "Relacionemos la vista con el tema."},
                    ],
                },
                ensure_ascii=False,
            )

        with tempfile.TemporaryDirectory(prefix="mindcrafted-test-") as tmp:
            with patch.object(pipeline, "_bind_api_config", return_value=fake_generate):
                html_path = await pipeline.generate_game(
                    "Contenido sobre el ciclo del agua",
                    tmp,
                    locale="en",
                    forced_title="Ciclo del agua",
                )

            output = Path(tmp)
            html = Path(html_path).read_text(encoding="utf-8")
            package = json.loads((output / "game.pkg.json").read_text(encoding="utf-8"))

            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][2]["max_tokens"], 900)
            self.assertIn("exclusivamente", calls[0][1].lower())
            self.assertIn("español", calls[0][1].lower())
            self.assertEqual(package["config"]["locale"], "es")
            self.assertEqual(package["config"]["generationMode"], "rapido")
            self.assertEqual(package["theme"]["bg"], pipeline.get_theme_css(FAST_THEME)["bg"])
            self.assertEqual(package["config"]["minigames"], {})
            self.assertFalse(any(command["type"] == "minigame" for command in package["script"]))
            self.assertIn("nave-planeta-agua-v1", html)
            self.assertIn("window.BACKGROUNDS", html)
            self.assertNotIn('data-lang="en"', html)
            self.assertTrue((output / "cover.js").exists())
            self.assertTrue((output / "locales" / "es.json").exists())
            self.assertFalse((output / "locales" / "en.json").exists())


if __name__ == "__main__":
    unittest.main()
