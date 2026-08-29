
"""Course generation pipeline — generates multiple games from a structured JSON content file."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .pipeline import generate_game
from .fast_template import FAST_THEME


async def generate_course(
    content_path: str,
    output_dir: str,
    audio_base: str | None = None,
    locale: str = "es",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    personal_profile: dict | None = None,
    after_each_chunk: Callable[..., Any] | None = None,
    fast_mode: bool = True,
) -> dict:
    """Generate a complete course with multiple game lessons from structured JSON.

    Args:
        content_path: Path to the structured JSON file with course metadata and chunks.
        output_dir: Base output directory for the course.
        audio_base: Optional audio base path for games.
        after_each_chunk: Optional async callback (course_id, out_dir, chunk_id, game_result, game_results_so_far, course_meta)
                         called after each chunk is generated so R2 can be updated for incremental preview.

    Returns:
        Dict with course metadata and paths to generated game files.
    """
    t_total = time.monotonic()

    content = json.loads(Path(content_path).read_text(encoding="utf-8"))
    course_meta = content["course"]
    chunks = content["chunks"]

    output = Path(output_dir)
    games_dir = output / "games"
    games_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  MindCrafted Course Generator", file=sys.stderr)
    print(f"  Course: {course_meta['title']}", file=sys.stderr)
    print(f"  Chunks: {len(chunks)}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    game_results: list[dict] = []
    used_mechanics: set[str] = set()

    for i, chunk in enumerate(chunks):
        chunk_id = chunk["id"]
        chunk_title = chunk["title"]
        theme = FAST_THEME if fast_mode else chunk.get("theme", "pink-cute")
        game_dir = str(games_dir / chunk_id)
        topic = _build_topic_from_chunk(chunk)

        print(f"\n[Game {i+1}/{len(chunks)}] Generating: {chunk_title} (theme: {theme})", file=sys.stderr)
        t0 = time.monotonic()

        try:
            html_path = await generate_game(
                topic, game_dir, theme=theme, chunk_id=chunk_id,
                exclude_mechanics=sorted(used_mechanics) if used_mechanics else None,
                game_index=i, total_games=len(chunks),
                locale=locale,
                forced_title=chunk_title,
                api_key=api_key, base_url=base_url, model=model,
                personal_profile=personal_profile,
                fast_mode=fast_mode,
            )

            next_chunk_id = chunks[i + 1]["id"] if i + 1 < len(chunks) else None
            next_game_url = f"../{next_chunk_id}/" if next_chunk_id else None
            course_id_for_patch = output.name
            _patch_game_html(html_path, game_dir, output_dir=str(output), audio_base=audio_base, next_game_url=next_game_url, course_id=course_id_for_patch)

            elapsed = time.monotonic() - t0
            print(f"  Game {i+1} done in {elapsed:.1f}s", file=sys.stderr)

            new_mechanics = _extract_mechanics_from_html(html_path)
            assessment_mechanics = {m for m in new_mechanics if not m.startswith("sim_")}
            used_mechanics.update(assessment_mechanics)

            cover_js_abs = Path(game_dir) / "cover.js"
            cover_js_src = (
                os.path.relpath(str(cover_js_abs), output_dir)
                if cover_js_abs.exists()
                else None
            )

            game_result = {
                "chunk_id": chunk_id,
                "title": chunk_title,
                "subtitle": chunk.get("subtitle", ""),
                "theme": theme,
                "html_path": html_path,
                "cover_js_src": cover_js_src,
                "learning_objectives": chunk.get("learning_objectives", []),
                "mechanics": sorted(new_mechanics),
                "status": "success",
            }
            game_results.append(game_result)
            if after_each_chunk:
                course_id_for_cb = output.name
                try:
                    if asyncio.iscoroutinefunction(after_each_chunk):
                        await after_each_chunk(course_id_for_cb, str(output), chunk_id, game_result, list(game_results), course_meta)
                    else:
                        after_each_chunk(course_id_for_cb, str(output), chunk_id, game_result, list(game_results), course_meta)
                except Exception as cb_err:
                    print(f"  [WARN] after_each_chunk failed: {cb_err}", file=sys.stderr)
        except Exception as e:
            elapsed = time.monotonic() - t0
            print(f"  [ERROR] Game {i+1} failed after {elapsed:.1f}s: {e}", file=sys.stderr)
            game_results.append({
                "chunk_id": chunk_id,
                "title": chunk_title,
                "subtitle": chunk.get("subtitle", ""),
                "theme": theme,
                "html_path": None,
                "learning_objectives": chunk.get("learning_objectives", []),
                "status": "failed",
                "error": str(e),
            })


    course_manifest = {
        "course": course_meta,
        "games": game_results,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    manifest_path = output / "course-manifest.json"
    manifest_path.write_text(
        json.dumps(course_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    elapsed_total = time.monotonic() - t_total
    success_count = sum(1 for g in game_results if g["status"] == "success")
    print(
        f"\n{'='*60}\n"
        f"  Course generation complete in {elapsed_total:.1f}s\n"
        f"  Games: {success_count}/{len(chunks)} successful\n"
        f"  Manifest: {manifest_path}\n"
        f"{'='*60}\n",
        file=sys.stderr,
    )

    return course_manifest


def _extract_mechanics_from_html(html_path: str) -> set[str]:
    """Extract minigame mechanic types from a generated game HTML."""
    import re
    html = Path(html_path).read_text(encoding="utf-8")
    mechanics = set()
    for match in re.finditer(r'"type"\s*:\s*"minigame"\s*,\s*"game"\s*:\s*"([^"]+)"', html):
        mechanics.add(match.group(1))
    if not mechanics:
        for match in re.finditer(r'registerMinigame\(["\'](\w+)["\']', html):
            mechanics.add(match.group(1))
    return mechanics


def _build_topic_from_chunk(chunk: dict) -> str:
    """Build a topic string from a chunk for the game generator."""
    parts = [chunk["title"]]
    if chunk.get("subtitle"):
        parts.append(chunk["subtitle"])
    if chunk.get("learning_objectives"):
        parts.append("Objetivos de aprendizaje: " + "; ".join(chunk["learning_objectives"]))
    if chunk.get("content"):
        parts.append(chunk["content"])
    return "\n\n".join(parts)


_SCROLLBAR_CSS = """::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.12);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,0.25)}
*{scrollbar-width:thin;scrollbar-color:rgba(255,255,255,0.12) transparent}"""


def _patch_game_html(html_path: str, game_dir: str, output_dir: str, audio_base: str | None = None, next_game_url: str | None = None, course_id: str | None = None):
    """Patch the generated game HTML for correct font, audio, asset paths, and layout."""
    html = Path(html_path).read_text(encoding="utf-8")

    font_filename = "ZhengQingKeNanBeiCiGongPuSongTi-2.ttf"
    html = html.replace(
        f"url('{font_filename}')",
        f"url('/assets/{font_filename}')",
    )

    extra_fields = '"audioBase": "/assets/audio/"'
    if course_id:
        extra_fields += f',\n  "courseId": "{course_id}"'
    if next_game_url:
        extra_fields += f',\n  "nextGameUrl": "{next_game_url}"'
    html = html.replace(
        "const GAME = {",
        f'const GAME = {{\n  {extra_fields},',
        1,
    )

    # Inject custom scrollbar CSS
    css_marker = "*{margin:0;padding:0;box-sizing:border-box}"
    if "::-webkit-scrollbar" not in html and css_marker in html:
        html = html.replace(css_marker, css_marker + "\n" + _SCROLLBAR_CSS)

    # Fix mini-game overlay padding
    old_overlay = "#mini-game-overlay{background:rgba(20,6,18,0.96);z-index:15;display:none;overflow-y:auto}"
    new_overlay = "#mini-game-overlay{background:rgba(20,6,18,0.96);z-index:15;display:none;overflow-y:auto;overflow-x:hidden;padding:16px 24px;justify-content:flex-start}"
    html = html.replace(old_overlay, new_overlay)

    # Fix mg-area responsive width
    html = html.replace(
        ".mg-area{position:relative;width:720px;min-height:280px}",
        ".mg-area{position:relative;width:100%;max-width:720px;min-height:200px;margin:0 auto}",
    )

    Path(html_path).write_text(html, encoding="utf-8")


async def _translate_manifest_to_locale(
    manifest: dict,
    locale: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    """Compatibilidad: el producto es monolingue y no realiza traducciones."""
    return manifest


async def generate_course_with_platform(
    content_path: str,
    output_dir: str,
    audio_base: str | None = None,
    locale: str = "es",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    personal_profile: dict | None = None,
    after_each_chunk: Callable[..., Any] | None = None,
    fast_mode: bool = True,
) -> str:
    """Generate course games and the course platform homepage.

    Returns path to the generated course index.html.
    """
    manifest = await generate_course(
        content_path, output_dir, audio_base, locale=locale,
        api_key=api_key, base_url=base_url, model=model,
        personal_profile=personal_profile,
        after_each_chunk=after_each_chunk,
        fast_mode=fast_mode,
    )

    from .course_assembler import assemble_course_platform
    platform_path = assemble_course_platform(manifest, output_dir, locale="es")

    return platform_path


if __name__ == "__main__":
    content_path = sys.argv[1] if len(sys.argv) > 1 else "./json/content.json"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./output/course"
    audio_base = sys.argv[3] if len(sys.argv) > 3 else None

    result = asyncio.run(generate_course_with_platform(content_path, output_dir, audio_base))
    print(result)
