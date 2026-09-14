"""V1 contracts retained during migration, without restoring deleted test files.

The small algebra fixture ports still-relevant coverage from the former fast
pipeline suite. All model responses are controlled and output stays in tmp_path.
"""
import asyncio
import json
import re
import subprocess
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path

import httpx
import pytest

from mindcrafted.generator import course_pipeline, package_builder, pipeline
from mindcrafted.generator.course_assembler import assemble_course_platform
from mindcrafted.pdf_import import pages_to_markdown


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    "Una ecuación conserva la igualdad al aplicar la misma operación en ambos miembros. "
    "Para resolver 2x + 4 = 14, resta cuatro a ambos lados y divide entre dos. "
    "Una fracción representa partes iguales de un todo: el numerador cuenta las partes "
    "elegidas y el denominador indica el total de partes iguales. "
    "Tres cuartos significa elegir tres de cuatro partes iguales."
)


def legacy_plan():
    examples = [
        ("balance_equation", "Despeja la incógnita", {"a": 2, "b": 4, "c": 14, "solution": 99},
         "Una ecuación conserva la igualdad al aplicar la misma operación en ambos miembros."),
        ("fraction_fill", "Representa tres cuartos", {"numerator": 3, "denominator": 4},
         "Tres cuartos significa elegir tres de cuatro partes iguales."),
        ("evidence_choice", "Miembros de la igualdad", {
            "options": ["Restar cuatro en ambos miembros", "Restar cuatro solo a la izquierda", "Sumar cuatro solo a la derecha"],
            "answer": 0,
        }, "Para resolver 2x + 4 = 14, resta cuatro a ambos lados y divide entre dos."),
    ]
    return {
        "subject": "Matemáticas", "world": "mathematics",
        "introduction": "Resuelve los retos aplicando las reglas y los ejemplos de los apuntes.",
        "puzzles": [dict(kind=kind, title=title, concept=title, data=data, evidence=evidence,
                         explanation=evidence, instruction="Aplica la regla del material para completar este reto.",
                         hint="Consulta la regla descrita en los apuntes.")
                    for kind, title, data, evidence in examples],
    }


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_legacy_bkt_survives_reload_and_isolates_courses():
    result = subprocess.run(["node", str(ROOT / "tests/check_legacy_compatibility.cjs")],
                            cwd=ROOT, capture_output=True, text=True, timeout=10, check=True)
    assert "legacy BKT" in result.stdout


def test_course_assembler_escapes_content_and_locks_failed_lessons(tmp_path):
    manifest = {
        "course": {"title": "Curso </script><script>alert(1)</script>", "subtitle": "Aprender <seguro>",
                   "description": "Descripción & práctica", "learning_objectives": ["Comparar <conceptos>"]},
        "games": [dict(chunk_id="chunk-2", title="Lección <uno>", subtitle="Fundamentos & ejemplos",
                       learning_objectives=["Aplicar <ideas>"], status="success"),
                  dict(chunk_id="fallo", title="Fallida", status="failed")],
    }
    original = deepcopy(manifest)
    page = Path(assemble_course_platform(manifest, str(tmp_path))).read_text(encoding="utf-8")
    buttons = [attrs for tag, attrs in Tags(page).elements if tag == "button" and attrs.get("class") == "play-btn"]
    assert buttons[0]["data-href"] == f"/play?course={tmp_path.name}&game=chunk-2"
    assert "disabled" not in buttons[0]
    assert buttons[1]["data-href"] == ""
    assert "disabled" in buttons[1]
    assert "Lección &lt;uno&gt;" in page
    assert "Aplicar &lt;ideas&gt;" in page
    assert "</script><script>alert(1)</script>" not in page
    assert "<\\/script><script>alert(1)<\\/script>" in page
    assert "escapeCourseHtml(o)" in page
    assert manifest == original


@pytest.mark.parametrize("adventure,mode,version,data_id", [
    (False, "practica", 2, "practice-data"), (True, "aventura", 3, "adventure-data"),
])
def test_explicit_v1_generation_exports_grounded_self_contained_package(
        monkeypatch, tmp_path, adventure, mode, version, data_id):
    calls = []

    async def generate(prompt, system, **kwargs):
        calls.append((prompt, kwargs))
        return json.dumps(legacy_plan())

    monkeypatch.setattr(pipeline, "_bind_api_config", lambda *args: generate)
    title = "Álgebra </script><script>alert(1)</script>"
    path = asyncio.run(pipeline.generate_game("Título orientativo", str(tmp_path), world_native=False,
                                             adventure=adventure, source_text=SOURCE, forced_title=title,
                                             subject="Álgebra escolar", chunk_id="chunk-2"))
    package = json.loads((tmp_path / "game.pkg.json").read_text())
    html = Path(path).read_text()
    assert len(calls) == 1
    assert SOURCE in calls[0][0] and "Álgebra escolar" in calls[0][0]
    assert package["v"] == version
    assert package["config"]["generationMode"] == mode
    assert package["config"]["chunkId"] == "chunk-2"
    assert package["config"]["practice"]["title"] == title
    assert package["config"]["practice"]["puzzles"][0]["data"]["solution"] == 5
    assert package["config"]["pixelWorld"]["assets"]["explorer"]["image"].startswith("data:image/png;base64,")
    embedded = re.search(rf'<script id="{data_id}" type="application/json">(.*?)</script>', html, re.S)
    assert embedded and json.loads(embedded[1]) == package
    assert "</script><script>alert(1)</script>" not in html
    assert not any(tag == "script" and attrs.get("src", "").startswith("/engine/")
                   for tag, attrs in Tags(html).elements)
    assert (tmp_path / "practice-plan.json").exists()
    assert (tmp_path / "cover.js").exists()
    if adventure:
        assert len(package["config"]["adventure"]["layout"]["stations"]) == 3
        assert len(package["config"]["boss"]["phases"]) == 3


@pytest.mark.parametrize("repair", [True, False])
def test_legacy_generation_limits_repairs_without_unrelated_fallback(monkeypatch, tmp_path, repair):
    calls = []

    async def generate(prompt, system, **kwargs):
        calls.append(prompt)
        return json.dumps(legacy_plan()) if repair and len(calls) == 2 else "{}"

    monkeypatch.setattr(pipeline, "_bind_api_config", lambda *args: generate)
    call = pipeline.generate_game(SOURCE, str(tmp_path), world_native=False)
    if repair:
        assert Path(asyncio.run(call)).exists()
    else:
        with pytest.raises(ValueError, match="fieles"):
            asyncio.run(call)
        assert not (tmp_path / "game.pkg.json").exists()
    assert len(calls) == 2
    assert "no pasó la validación" in calls[1]


def test_partial_legacy_course_preserves_order_navigation_and_final_boss(monkeypatch, tmp_path):
    calls = []

    async def generate(prompt, system, **kwargs):
        calls.append(prompt)
        return "{}" if "material insuficiente" in prompt else json.dumps(legacy_plan())

    # Keep the actual course and V1 pipeline, selecting the supported explicit opt-out.
    async def legacy_game(*args, **kwargs):
        return await pipeline.generate_game(*args, **kwargs, world_native=False)

    monkeypatch.setattr(pipeline, "_bind_api_config", lambda *args: generate)
    monkeypatch.setattr(course_pipeline, "generate_game", legacy_game)
    output = tmp_path / "curso-legacy"
    content = tmp_path / "input.json"
    content.write_text(json.dumps({"course": {"title": "Álgebra", "subject": "Álgebra escolar"}, "chunks": [
        dict(id=id, title=id, content=source) for id, source in
        [("chunk-2", SOURCE), ("fallo", "material insuficiente " * 5), ("chunk-10", SOURCE)]
    ]}))
    index = asyncio.run(course_pipeline.generate_course_with_platform(str(content), str(output)))
    manifest = json.loads((output / "course-manifest.json").read_text())
    assert [g["chunk_id"] for g in manifest["games"]] == ["chunk-2", "fallo", "chunk-10"]
    assert [g["status"] for g in manifest["games"]] == ["success", "failed", "success"]
    assert "fieles" in manifest["games"][1]["error"]
    assert manifest["games"][0]["puzzle_count"] == 3
    first, last = [json.loads((output / f"games/{id}/game.pkg.json").read_text())
                   for id in ("chunk-2", "chunk-10")]
    assert first["config"]["courseId"] == "curso-legacy"
    assert first["config"]["nextGameUrl"] == "/play?course=curso-legacy&game=chunk-10"
    assert "nextGameUrl" not in last["config"]
    assert first["config"]["boss"] is None
    assert last["config"]["boss"]["partial"] is True
    assert [entry["chunkId"] for entry in last["config"]["courseRoute"]] == ["chunk-2", "chunk-10"]
    assert len(calls) == 4 and "Álgebra escolar" in calls[0]
    assert "balance_equation" in calls[-1]
    assert Path(index).exists()


@pytest.mark.parametrize("encrypted", [False, True])
def test_classic_v1_package_roundtrips_config_and_executable_fields(monkeypatch, tmp_path, encrypted):
    monkeypatch.delenv("OBFS_JS", raising=False)
    monkeypatch.setenv("GAME_PACKAGE_SECRET", "test-only-package-secret-123456789")
    # Avoid invoking npx/the network; cipher and package generation remain real.
    monkeypatch.setattr(package_builder, "_obfuscate_js", lambda code: code)
    content = {"config": {"title": "Fracciones", "subtitle": "Partes iguales", "totalChapters": 1,
                           "chunkId": "fraction-1", "ui": {}},
               "script": [{"type": "chapter", "chapter": 0}, {"type": "end"}],
               "pixel_art_js": "function drawFraction() {}", "minigames_js": "function playFraction() {}",
               "cover_js": "function drawCover() {}", "theme": "ocean-dream"}
    json_path, encrypted_path = package_builder.write_package(content, str(ROOT / "mindcrafted/engine"),
                                                              str(tmp_path), write_encrypted=encrypted)
    package = json.loads(Path(json_path).read_text())
    assert package["v"] == 1
    for field in ("config", "script", "pixel_art_js", "minigames_js", "cover_js"):
        assert package[field] == content[field]
    assert package["title"] == "Fracciones" and package["total_chapters"] == 1
    assert package["init_js"] and package["styleBlock"].startswith("<style>")
    if encrypted:
        assert package_builder.decrypt_package(encrypted_path) == package
    else:
        assert encrypted_path is None


@pytest.mark.parametrize("mode,player", [(None, "player.html"), ("practica", "practice/player.html"),
                                         ("aventura", "adventure/player.html")])
def test_server_serves_existing_legacy_packages_and_skips_failed_lessons(monkeypatch, tmp_path, mode, player):
    from mindcrafted import server
    monkeypatch.setattr(server, "COURSES_DIR", tmp_path)
    monkeypatch.setattr(server, "REGISTRY", tmp_path / "courses.json")
    directory = tmp_path / "legacy/games/chunk-2"
    directory.mkdir(parents=True)
    package = {"v": 1, "config": {"nextGameUrl": "stale"}, "script": [{"type": "end"}]}
    if mode:
        package["config"]["generationMode"] = mode
    raw = json.dumps(package)
    (directory / "game.pkg.json").write_text(raw)
    manifest = {"games": [dict(chunk_id=id, status=status) for id, status in
                          [("chunk-2", "success"), ("fallo", "failed"), ("chunk-10", "success")]]}
    (tmp_path / "legacy/course-manifest.json").write_text(json.dumps(manifest))

    async def verify():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as client:
            page = await client.get("/play?course=legacy&game=chunk-2")
            assert page.status_code == 200
            assert page.text == (server.ENGINE_DIR / player).read_text()
            response = await client.get("/api/play/legacy/chunk-2/package")
            assert response.status_code == 200
            served = response.json()
            assert served["config"]["courseId"] == "legacy"
            assert served["config"]["chunkId"] == "chunk-2"
            assert served["config"]["nextGameUrl"] == "/play?course=legacy&game=chunk-10"
            assert served["script"] == package["script"]

    asyncio.run(verify())
    assert (directory / "game.pkg.json").read_text() == raw


def test_two_page_pdf_removes_margins_but_preserves_repeated_source_and_lesson_headings():
    fact = "Cada router tiene una capacidad limitada y distribuye paquetes hacia otros dispositivos."
    markdown = pages_to_markdown([
        f"Manual de Redes\nCAPÍTULO 1 - ROUTING\n{fact}\nPágina 1",
        f"Manual de Redes\nCAPÍTULO 2 - CONGESTIÓN\n{fact}\nPágina 2",
    ], "redes.pdf")
    assert "Página 1" not in markdown and "Página 2" not in markdown
    assert markdown.count("Manual de Redes") == 1
    assert "## Capítulo 1 - Routing" in markdown
    assert "## Capítulo 2 - Congestión" in markdown
    assert markdown.count(fact) == 2
