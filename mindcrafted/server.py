# =============================================================================
# MindCrafted — AI Game-Based Learning Studio
# =============================================================================
"""MindCrafted — Self-hosted AI Game-Based Learning Studio

Convert any learning material into playable game-based micro-courses using AI.
No database, no login, no cloud infrastructure required.

Usage:
    # Crea un archivo .env con tu clave de API si quieres guardarla localmente.
    python -m uvicorn mindcrafted.server:app --reload --port 8000
    # OR: bash start.sh (sets PYTHONPATH for you)

Environment variables (set in .env):
    API_KEY         Your OpenAI-compatible API key (required unless you paste a key in the Studio)
                    Aliases also work: OPENROUTER_API_KEY, OPENROUTER_API_KEY_studio
    API_BASE_URL    API base URL (default: https://openrouter.ai/api/v1); alias STUDIO_AI_BASE_URL
    MODEL           Model name (default: google/gemini-3-flash-preview); alias STUDIO_MODEL
    PORT            Server port (default: 8000)
    BIND_HOST       Listen address (default: 127.0.0.1; use 0.0.0.0 for LAN)
    MINDCRAFTED_HOME Optional. Data directory for courses/, assets/, jobs/, courses.json
                    (default: repo root in dev; current working directory when installed)
"""

from pathlib import Path as _PathForEnv

_pkg = _PathForEnv(__file__).resolve().parent
_repo = _pkg.parent
for _env_candidate in (
    _PathForEnv.cwd() / ".env",
    _repo / ".env",
    _pkg / ".env",
):
    if _env_candidate.exists():
        from dotenv import load_dotenv

        load_dotenv(_env_candidate)
        break


def _unify_ai_env_aliases() -> None:
    """One key in .env is enough: sync API_KEY ↔ OPENROUTER_*, MODEL ↔ STUDIO_MODEL, URLs."""
    import os as _os

    k = (_os.environ.get("API_KEY") or "").strip()
    if not k:
        k = (
            (_os.environ.get("OPENROUTER_API_KEY_studio") or "").strip()
            or (_os.environ.get("OPENROUTER_API_KEY") or "").strip()
        )
        if k:
            _os.environ["API_KEY"] = k
    else:
        _os.environ.setdefault("OPENROUTER_API_KEY", k)

    b = (_os.environ.get("API_BASE_URL") or "").strip()
    if not b:
        b = (_os.environ.get("STUDIO_AI_BASE_URL") or "").strip()
        if b:
            _os.environ["API_BASE_URL"] = b
    else:
        _os.environ.setdefault("STUDIO_AI_BASE_URL", b)

    m = (_os.environ.get("MODEL") or "").strip()
    if not m:
        m = (_os.environ.get("STUDIO_MODEL") or "").strip()
        if m:
            _os.environ["MODEL"] = m
    else:
        _os.environ.setdefault("STUDIO_MODEL", m)


_unify_ai_env_aliases()

import asyncio
import contextvars
import io
import json
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Paths ──────────────────────────────────────────────────────────────────
PACKAGE_DIR = Path(__file__).resolve().parent


def _install_root() -> Path:
    env = (os.environ.get("MINDCRAFTED_HOME") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    # Código fuente del proyecto: el paquete vive dentro de la raíz del repositorio.
    if (_repo / ".git").exists() or (_repo / "start.sh").exists():
        return _repo.resolve()
    # Installed wheel: mutable data lives next to cwd unless MINDCRAFTED_HOME is set
    return Path.cwd().resolve()


INSTALL_ROOT = _install_root()
COURSES_DIR = INSTALL_ROOT / "courses"
ASSETS_DIR = INSTALL_ROOT / "assets"
AUDIO_DIR = ASSETS_DIR / "audio"
JOBS_DIR = INSTALL_ROOT / "jobs"
REPORTS_DIR = INSTALL_ROOT / "reports"
STATIC_DIR = PACKAGE_DIR / "static"
ENGINE_DIR = PACKAGE_DIR / "engine"
REGISTRY = INSTALL_ROOT / "courses.json"

COURSES_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# ── AI Config ───────────────────────────────────────────────────────────────
API_KEY      = (os.environ.get("API_KEY") or "").strip()
API_BASE_URL = os.environ.get("API_BASE_URL", "https://openrouter.ai/api/v1").strip()
MODEL        = os.environ.get("MODEL", "google/gemini-3-flash-preview").strip()

# ── Themes (must match generator/assembler.py) ──────────────────────────────
THEMES = [
    "pink-cute", "ocean-dream", "forest-sage", "sunset-warm", "galaxy-purple",
    "candy-pop", "retro-amber", "china-porcelain", "china-cinnabar", "china-ink",
    "dunhuang", "forbidden-red", "china-landscape", "china-rouge",
    "renaissance", "baroque", "nordic", "victorian", "mediterranean",
    "fairy-tale", "detective", "sci-fi", "academy", "myth",
]

ALLOWED_LOCALES = frozenset({"es"})
MAX_MARKDOWN_CHARS = 300_000
MAX_GAME_CHUNKS = 24
MAX_CHUNK_CHARS = 60_000

# ── Logging filter ───────────────────────────────────────────────────────────
import logging as _logging

class _PollFilter(_logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if "/api/jobs/" in msg and "GET" in msg:
            return False
        return True

_logging.getLogger("uvicorn.access").addFilter(_PollFilter())

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(title="MindCrafted")
_cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "MINDCRAFTED_CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response

@app.on_event("startup")
async def _startup():
    _prune_registry()
    if not API_KEY:
        print("[AVISO] API_KEY no está configurada. Agrégala a .env para habilitar la generación.", flush=True)
    print(f"[MindCrafted] Estudio listo en http://localhost:{os.environ.get('PORT', 8000)}/", flush=True)

@app.on_event("shutdown")
async def _shutdown():
    global _ai_client
    if _ai_client:
        try: await _ai_client.aclose()
        except Exception: pass
        _ai_client = None


# ── Job Manager ──────────────────────────────────────────────────────────────
_STEP_PATTERNS = [
    (re.compile(r'\[Game (\d+)/(\d+)\].*Generating:\s*(.+?)(?:\s*\(theme:.*\))?$'), 'game'),
    (re.compile(r'\[(\d+)/(\d+)\]\s*(.+?)(?:\s*\(theme:.*\))?\.\.\.'), 'substep'),
    (re.compile(r'Course generation complete in ([\d.]+)s'), 'course_complete'),
    (re.compile(r'Games:\s*(\d+)/(\d+)\s*successful'), 'games_summary'),
    (re.compile(r'✅'), 'done'),
    (re.compile(r'❌'), 'error'),
]

_PROGRESS_LABELS_ES = {
    "Analyzing topic and building knowledge structure": "Analizando el tema y creando la estructura de conocimiento",
    "Writing story dialog and character interactions": "Creando los diálogos y las interacciones de los personajes",
    "Story dialog complete": "Diálogos de la historia listos",
    "Game icons ready": "Iconos del juego listos",
    "Character sprites ready": "Personajes listos",
    "Scene backgrounds ready": "Escenarios listos",
    "Cover art ready": "Portada lista",
    "Polishing pixel art": "Mejorando el arte pixelado",
    "Assembling final game": "Armando el juego final",
}


def _progress_label_es(label: str) -> str:
    cached = " (cached)" in label
    clean = label.replace(" (cached)", "")
    translated = _PROGRESS_LABELS_ES.get(clean)
    if translated:
        return translated + (" (en caché)" if cached else "")
    match = re.match(r"Custom simulation (\d+)(?::\s*(.*)| ready| \(fallback\))?$", clean)
    if match:
        number, title = match.group(1), match.group(2)
        suffix = f": {title}" if title else " lista"
        if "fallback" in clean:
            suffix = " lista con versión alternativa"
        return f"Simulación personalizada {number}{suffix}" + (" (en caché)" if cached else "")
    return label

def _to_safe_log(line: str) -> str | None:
    for pat, kind in _STEP_PATTERNS:
        m = pat.search(line)
        if not m:
            continue
        if kind == 'game':
            return json.dumps({"type": "game", "current": int(m.group(1)), "total": int(m.group(2)), "title": m.group(3).strip()})
        if kind == 'substep':
            cur, tot = int(m.group(1)), int(m.group(2))
            pct = int((cur / tot) * 100) if tot > 0 else 0
            return json.dumps({"type": "substep", "current": cur, "total": tot, "label": _progress_label_es(m.group(3).strip()), "pct": pct})
        if kind == 'course_complete':
            return json.dumps({"type": "info", "label": "course_complete", "value": f"{m.group(1)}s"})
        if kind == 'games_summary':
            return json.dumps({"type": "info", "label": "games_summary", "value": f"{m.group(1)}/{m.group(2)} successful"})
        if kind == 'done':
            return json.dumps({"type": "done"})
        if kind == 'error':
            return json.dumps({"type": "error", "msg": line})
        return None
    if '[ERROR]' in line or '[SIM FALLBACK]' in line:
        return json.dumps({"type": "error", "msg": line.strip()})
    if 'Game ' in line and ' done in ' in line:
        m2 = re.search(r'Game (\d+) done in ([\d.]+)s', line)
        if m2:
            return json.dumps({"type": "game_done", "game": int(m2.group(1)), "time": float(m2.group(2))})
    return None


class JobManager:
    def __init__(self):
        self.jobs: dict[str, dict] = {}

    def _path(self, jid: str) -> Path:
        return JOBS_DIR / f"{jid}.json"

    def _save(self, jid: str) -> None:
        try:
            job = self.jobs[jid]
            snapshot = {k: v for k, v in job.items() if k != "logs"}
            self._path(jid).write_text(json.dumps(snapshot), encoding="utf-8")
        except Exception:
            pass

    def _load(self, jid: str) -> dict | None:
        try:
            p = self._path(jid)
            if not p.exists():
                return None
            data = json.loads(p.read_text(encoding="utf-8"))
            data.setdefault("logs", [])
            self.jobs[jid] = data
            return data
        except Exception:
            return None

    def create(self, course_id: str) -> str:
        jid = uuid.uuid4().hex[:10]
        self.jobs[jid] = {
            "id": jid, "course_id": course_id, "status": "running",
            "logs": [], "result": None, "error": None, "created_at": time.time(),
        }
        self._save(jid)
        return jid

    def log(self, jid: str, msg: str):
        if jid in self.jobs and msg.strip():
            self.jobs[jid]["logs"].append({"t": time.time(), "msg": msg.strip()})

    def done(self, jid: str, result=None, error=None):
        if jid in self.jobs:
            self.jobs[jid].update({
                "status": "failed" if error else "completed",
                "result": result, "error": str(error) if error else None,
            })
            self._save(jid)

    def get(self, jid: str) -> dict | None:
        if jid in self.jobs:
            return self.jobs[jid]
        return self._load(jid)


job_mgr = JobManager()
_current_job_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_job_id", default=None)
_REAL_STDERR = sys.__stderr__


class StderrDispatcher(io.TextIOBase):
    def __init__(self, mgr: JobManager, real_stderr):
        self._mgr = mgr
        self._real = real_stderr
        self._buffers: dict[str, str] = {}

    def write(self, s: str):
        jid = _current_job_id_ctx.get()
        if jid and jid in self._mgr.jobs:
            self._buffers.setdefault(jid, "")
            self._buffers[jid] += s
            while "\n" in self._buffers[jid]:
                line, self._buffers[jid] = self._buffers[jid].split("\n", 1)
                cleaned = line.strip()
                if not cleaned or cleaned.startswith('='):
                    continue
                safe = _to_safe_log(cleaned)
                if safe:
                    self._mgr.log(jid, safe)
        prefix = f"[{jid}] " if jid else ""
        lines = s.split("\n")
        for i, line in enumerate(lines):
            if i < len(lines) - 1:
                self._real.write(prefix + line + "\n")
            elif line:
                self._real.write(prefix + line)
        self._real.flush()
        return len(s)

    def flush(self):
        jid = _current_job_id_ctx.get()
        if jid and self._buffers.get(jid, "").strip():
            buf = self._buffers[jid].strip()
            self._buffers[jid] = ""
            safe = _to_safe_log(buf)
            if safe:
                self._mgr.log(jid, safe)
        self._real.flush()


sys.stderr = StderrDispatcher(job_mgr, _REAL_STDERR)


# ── Safety helpers ───────────────────────────────────────────────────────────
def _safe_course_id(s: str) -> str:
    if not isinstance(s, str) or not s or s == "." or len(s) > 128 or ".." in s or "/" in s or "\\" in s:
        raise HTTPException(400, "El identificador del curso no es válido")
    if not re.match(r"^[a-zA-Z0-9_.-]+$", s):
        raise HTTPException(400, "El identificador del curso no es válido")
    return s

def _safe_chunk_id(s: str) -> str:
    if not isinstance(s, str) or not s or s == "." or len(s) > 128 or ".." in s or "/" in s or "\\" in s:
        raise HTTPException(400, "El identificador de la lección no es válido")
    if not re.match(r"^[a-zA-Z0-9_.-]+$", s):
        raise HTTPException(400, "El identificador de la lección no es válido")
    return s


def _safe_job_id(s: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{10}", s or ""):
        raise HTTPException(400, "El identificador de la tarea no es válido")
    return s


def _validate_ai_base_url(value: str) -> str:
    if not isinstance(value, str):
        raise HTTPException(400, "La URL base de IA no es válida")
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(400, "La URL base de IA debe ser una URL HTTP(S) válida y sin credenciales")
    return value


def _resolve_ai_config(body: dict) -> tuple[object, str, object]:
    """Resolve BYOK settings without sending the server key to a new host."""
    requested_base_url = body.get("base_url")
    base_url = _validate_ai_base_url(requested_base_url or API_BASE_URL)
    api_key = body.get("api_key") or API_KEY
    has_request_key = isinstance(body.get("api_key"), str) and bool(body["api_key"].strip())
    has_request_url = requested_base_url not in (None, "")
    if has_request_url and not has_request_key:
        configured_url = _validate_ai_base_url(API_BASE_URL)
        if base_url != configured_url:
            raise HTTPException(400, "Una URL de IA personalizada requiere una clave BYOK explícita")
    return api_key, base_url, body.get("model") or MODEL


def _validate_generation_content(content: object) -> dict:
    if not isinstance(content, dict):
        raise HTTPException(400, "El contenido del curso no es válido")
    course = content.get("course")
    chunks = content.get("chunks")
    if not isinstance(course, dict) or not isinstance(chunks, list):
        raise HTTPException(400, "La estructura del curso no es válida")
    title = course.get("title")
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(400, "El título del curso es obligatorio")
    if len(title) > 200:
        raise HTTPException(400, "El título del curso es demasiado largo")
    if not isinstance(course.get("subject", ""), str) or len(course.get("subject", "")) > 200:
        raise HTTPException(400, "La materia no es válida")
    if course.get('gameplay', 'aventura') not in ('aventura', 'practica', 'world'):
        raise HTTPException(400, 'El estilo de juego no es válido')
    if course.get('difficulty', 'normal') not in ('normal', 'calm', 'study', 'hard'):
        raise HTTPException(400, 'El ritmo no es válido')
    if not chunks:
        raise HTTPException(400, "No se proporcionaron lecciones. Primero analiza el contenido.")
    if len(chunks) > MAX_GAME_CHUNKS:
        raise HTTPException(400, f"Un curso puede tener como máximo {MAX_GAME_CHUNKS} lecciones")
    total_chars = 0
    chunk_ids: set[str] = set()
    for index, chunk in enumerate(chunks, 1):
        if not isinstance(chunk, dict):
            raise HTTPException(400, f"La lección {index} no es válida")
        chunk_title = chunk.get("title")
        chunk_content = chunk.get("content", "")
        if chunk.get('world', '') not in ('', 'technology', 'laboratory', 'mathematics', 'biology'):
            raise HTTPException(400, 'El mundo de la lección no es válido')
        raw_chunk_id = chunk.get("id")
        if not isinstance(raw_chunk_id, str):
            raise HTTPException(400, f"La lección {index} necesita un identificador válido")
        chunk_id = _safe_chunk_id(raw_chunk_id)
        if chunk_id in chunk_ids:
            raise HTTPException(400, f"El identificador de la lección {index} está duplicado")
        chunk_ids.add(chunk_id)
        if not isinstance(chunk_title, str) or not chunk_title.strip():
            raise HTTPException(400, f"La lección {index} necesita un título")
        if len(chunk_title) > 200:
            raise HTTPException(400, f"El título de la lección {index} es demasiado largo")
        if not isinstance(chunk_content, str):
            raise HTTPException(400, f"El contenido de la lección {index} no es válido")
        if course.get('gameplay', 'aventura') in ('aventura', 'world') and len(chunk_content.strip()) < 60:
            raise HTTPException(400, f"La lección {index} necesita al menos 60 caracteres de material educativo")
        if len(chunk_content) > MAX_CHUNK_CHARS:
            raise HTTPException(400, f"La lección {index} supera {MAX_CHUNK_CHARS:,} caracteres")
        total_chars += len(chunk_content)
    if total_chars > MAX_MARKDOWN_CHARS:
        raise HTTPException(400, f"El curso supera {MAX_MARKDOWN_CHARS:,} caracteres")
    return content


# ── Registry (courses.json) ─────────────────────────────────────────────────
def _read_registry() -> list[dict]:
    if REGISTRY.exists():
        try: return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except: pass
    return []

def _write_registry(courses: list[dict]):
    payload = json.dumps(courses, ensure_ascii=False, indent=2)
    tmp = REGISTRY.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(REGISTRY)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        REGISTRY.write_text(payload, encoding="utf-8")

def _upsert_course(entry: dict):
    courses = _read_registry()
    idx = next((i for i, c in enumerate(courses) if c["id"] == entry["id"]), None)
    if idx is not None:
        courses[idx] = entry
    else:
        courses.insert(0, entry)
    _write_registry(courses)

def _remove_course(course_id: str):
    courses = [c for c in _read_registry() if c["id"] != course_id]
    _write_registry(courses)

def _prune_registry():
    courses = _read_registry()
    kept = [c for c in courses if (COURSES_DIR / c.get("id", "")).is_dir()]
    if len(kept) < len(courses):
        _write_registry(kept)

def _course_entry_from_manifest(course_id: str, manifest: dict) -> dict:
    meta = manifest.get("course", {})
    games = manifest.get("games", [])
    return {
        "id": course_id,
        "title": meta.get("title", course_id),
        "subtitle": meta.get("subtitle", ""),
        "description": meta.get("description", ""),
        "subject": meta.get("subject", ""),
        "level": meta.get("level", ""),
        "estimated_time": meta.get("estimated_time", ""),
        "learning_objectives": meta.get("learning_objectives", []),
        "total_lessons": len([g for g in games if g.get("status") == "success"]),
        "created_at": manifest.get("generated_at", ""),
        "tags": meta.get("tags", []),
    }

def _discover_courses_from_disk() -> list[dict]:
    result: list[dict] = []
    if not COURSES_DIR.exists():
        return result
    for d in sorted(COURSES_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        mp = d / "course-manifest.json"
        if not mp.exists():
            continue
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
            result.append(_course_entry_from_manifest(d.name, m))
        except Exception:
            pass
    return result


def _registry_needs_sync(disk: list[dict], reg: list[dict]) -> bool:
    reg_ids = [c.get("id") for c in reg if c.get("id")]
    disk_ids = [c["id"] for c in disk]
    if len(reg_ids) != len(disk_ids) or set(reg_ids) != set(disk_ids):
        return True
    reg_by = {c["id"]: c for c in reg if c.get("id")}
    for d in disk:
        rid = d["id"]
        r = reg_by.get(rid)
        if not r:
            return True
        if r.get("title") != d.get("title") or r.get("total_lessons") != d.get("total_lessons"):
            return True
    return False


def scan_courses() -> list[dict]:
    """List courses from disk manifests; keep courses.json in sync for external tools."""
    _prune_registry()
    disk = _discover_courses_from_disk()
    reg = _read_registry()
    if disk and _registry_needs_sync(disk, reg):
        _write_registry(disk)
    if disk:
        return disk
    return reg


# ── Markdown parser ─────────────────────────────────────────────────────────
def parse_markdown(md: str) -> dict:
    lines = md.splitlines()
    course = {
        "title": "", "subtitle": "", "description": "", "subject": "",
        "level": "", "estimated_time": "", "learning_objectives": [], "tags": [],
    }
    chunks, current = [], None
    in_desc = False

    def flush():
        nonlocal current
        if current:
            current["content"] = current["content"].strip()
            chunks.append(current)
            current = None

    for line in lines:
        raw = line.rstrip()
        if re.match(r'^# [^#]', raw):
            flush(); course["title"] = raw[2:].strip(); in_desc = True
        elif re.match(r'^## [^#]', raw):
            flush(); in_desc = False
            current = {
                "id": f"chunk-{len(chunks)+1}", "title": raw[3:].strip(),
                "subtitle": "", "theme": THEMES[len(chunks) % len(THEMES)],
                "learning_objectives": [], "content": "",
            }
        elif re.match(r'^### ', raw):
            title = raw[4:].strip()
            if current:
                if not current["subtitle"]: current["subtitle"] = title
                if current["content"]: current["content"] += "\n\n"
                current["content"] += f"**{title}**"
        elif re.match(r'^[-*] ', raw):
            item = raw[2:].strip()
            if current: current["content"] += f"\n• {item}"
            elif in_desc: course["learning_objectives"].append(item)
        elif not raw.strip():
            if current and current["content"] and not current["content"].endswith("\n\n"):
                current["content"] += "\n"
        else:
            if current:
                if current["content"] and not current["content"].endswith("\n"): current["content"] += "\n"
                current["content"] += raw
            elif in_desc and course["title"]:
                course["description"] = (course["description"] + " " + raw.strip()).strip()

    flush()
    if not course["subtitle"] and chunks:
        course["subtitle"] = " · ".join(c["title"] for c in chunks[:3])
        if len(chunks) > 3: course["subtitle"] += " ..."
    return {"course": course, "chunks": chunks}


# ── AI client (shared, persistent) ──────────────────────────────────────────
import socket
_orig_getaddrinfo = socket.getaddrinfo
_dns_cache: dict[tuple, list] = {}

def _cached_getaddrinfo(*args, **kwargs):
    key = args[:2]
    if key in _dns_cache:
        return _dns_cache[key]
    result = _orig_getaddrinfo(*args, **kwargs)
    if result:
        _dns_cache[key] = result
    return result

socket.getaddrinfo = _cached_getaddrinfo

_ai_client: httpx.AsyncClient | None = None

def _get_ai_client() -> httpx.AsyncClient:
    global _ai_client
    if _ai_client is None:
        _ai_client = httpx.AsyncClient(
            timeout=180, trust_env=False, http2=False,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _ai_client


# ── Generation background task ───────────────────────────────────────────────
async def _run_generation(
    jid: str, content: dict, locale: str = "es",
    api_key: str | None = None, base_url: str | None = None, model: str | None = None,
):
    locale = "es"
    old_err = _REAL_STDERR
    course_id = job_mgr.get(jid)["course_id"]
    out_dir = COURSES_DIR / course_id
    _current_job_id_ctx.set(jid)

    def _register_course():
        mp = out_dir / "course-manifest.json"
        if not mp.exists():
            return
        try:
            manifest = json.loads(mp.read_text(encoding="utf-8"))
            entry = _course_entry_from_manifest(course_id, manifest)
            _upsert_course(entry)
        except Exception as exc:
            print(f"  [AVISO] No se pudo registrar el curso: {exc}", file=old_err)

    def _rlog(msg: str):
        print(f"[{course_id}] {msg}", file=old_err, flush=True)
        job_mgr.log(jid, json.dumps({"type": "info", "label": "status", "value": msg}))

    try:
        from .generator import api as gen_api
        from .generator.course_pipeline import generate_course_with_platform

        gen_api._studio_usage_collector_ctx.set([])
        out_dir.mkdir(parents=True, exist_ok=True)

        content_path = out_dir / "_content.json"
        content_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")

        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        num_chunks = len(content.get("chunks", []))
        _rlog(f"Generando {num_chunks} juego(s)…")

        await generate_course_with_platform(
            str(content_path), str(out_dir),
            audio_base=str(AUDIO_DIR),
            locale=locale,
            api_key=api_key, base_url=base_url, model=model,
        )

        manifest_path = out_dir / "course-manifest.json"
        if not manifest_path.exists():
            raise RuntimeError("La generación terminó sin crear el manifiesto del curso")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        successful_games = [game for game in manifest.get("games", []) if game.get("status") == "success"]
        if not successful_games:
            raise RuntimeError("No se pudo generar ningún juego; revisa la configuración de IA y vuelve a intentar")

        _rlog("Proceso completado; registrando el curso…")
        _register_course()
        job_mgr.done(jid, result={"course_id": course_id,
            "first_game": successful_games[0]["chunk_id"],
            "boss_status": manifest.get('boss_status'),
            "partial": len(successful_games) != len(manifest.get("games", [])),
            "games": [{k: g.get(k) for k in ("chunk_id", "title", "status", "error", "world", "puzzle_count")} for g in manifest.get("games", [])]})
        _rlog("✅ ¡Listo! Abre el estudio para jugar tu curso.")

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[{course_id}] ❌ ERROR: {e}\n{tb}", file=old_err, flush=True)
        _register_course()
        job_mgr.done(jid, error=str(e))
        job_mgr.log(jid, f"❌ Error: {e}")
    finally:
        _current_job_id_ctx.set(None)


# ══════════════════════════════════════════════════════════════════════════════
# API Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
@app.get("/studio", response_class=HTMLResponse)
@app.get("/studio/", response_class=HTMLResponse)
async def studio():
    p = STATIC_DIR / "studio.html"
    if p.exists():
        return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>No se encontró el estudio</h1>", 404)

@app.get("/play", response_class=HTMLResponse)
@app.get("/play/", response_class=HTMLResponse)
async def play_page(request: Request):
    player_path = ENGINE_DIR / "player.html"
    if request.query_params.get("course") and not request.query_params.get("game"):
        course_id = _safe_course_id(request.query_params["course"])
        if (COURSES_DIR / course_id / "campaign" / "game.pkg.json").exists():
            player_path = ENGINE_DIR / "world" / "player.html"
    if request.query_params.get("course") and request.query_params.get("game"):
        course_id = _safe_course_id(request.query_params["course"])
        chunk_id = _safe_chunk_id(request.query_params["game"])
        package_path = COURSES_DIR / course_id / "games" / chunk_id / "game.pkg.json"
        if package_path.exists():
            try:
                package = json.loads(package_path.read_text(encoding="utf-8"))
                if package.get("config", {}).get("generationMode") == "world":
                    player_path = ENGINE_DIR / "world" / "player.html"
                elif package.get("config", {}).get("generationMode") == "aventura":
                    player_path = ENGINE_DIR / "adventure" / "player.html"
                elif package.get("config", {}).get("generationMode") == "practica":
                    player_path = ENGINE_DIR / "practice" / "player.html"
            except (ValueError, AttributeError):
                raise HTTPException(500, "El paquete del juego no es válido")
    if not player_path.exists():
        raise HTTPException(404, "No se encontró el reproductor")
    return HTMLResponse(player_path.read_text(encoding="utf-8"))


# ── Courses API ──────────────────────────────────────────────────────────────

@app.get("/api/courses")
async def list_courses():
    return scan_courses()

@app.get("/courses.json")
async def courses_json():
    return JSONResponse(content=scan_courses())

@app.get("/api/courses/{course_id}/manifest")
async def get_manifest(course_id: str):
    course_id = _safe_course_id(course_id)
    mp = COURSES_DIR / course_id / "course-manifest.json"
    if mp.exists():
        try:
            return json.loads(mp.read_text(encoding="utf-8"))
        except Exception as e:
            raise HTTPException(500, f"El manifiesto no es válido: {e}")
    raise HTTPException(404, "No se encontró el manifiesto del curso")

@app.delete("/api/courses/{course_id}")
async def delete_course(course_id: str):
    course_id = _safe_course_id(course_id)
    course_dir = COURSES_DIR / course_id
    if not course_dir.exists():
        raise HTTPException(404, "No se encontró el curso")
    shutil.rmtree(course_dir)
    _remove_course(course_id)
    return {"ok": True}


# ── Parse markdown ───────────────────────────────────────────────────────────

async def _read_limited_upload(request: Request, max_bytes: int, label: str) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(413, f"{label} supera el límite de {max_bytes // (1024 * 1024)} MB")
        except ValueError:
            raise HTTPException(400, "La longitud del archivo no es válida")
    data = await request.body()
    if len(data) > max_bytes:
        raise HTTPException(413, f"{label} supera el límite de {max_bytes // (1024 * 1024)} MB")
    return data

@app.post("/api/parse-md-text")
async def parse_md_text(body: dict):
    md = body.get("markdown", "")
    if not isinstance(md, str):
        raise HTTPException(400, "El contenido Markdown no es válido")
    if not md.strip():
        raise HTTPException(400, "El contenido Markdown está vacío")
    if len(md) > MAX_MARKDOWN_CHARS:
        raise HTTPException(400, f"El contenido supera {MAX_MARKDOWN_CHARS:,} caracteres")
    return parse_markdown(md)


@app.post("/api/import-pdf")
async def import_pdf_document(request: Request, filename: str = "documento.pdf"):
    """Recibe bytes PDF sin multipart y devuelve Markdown listo para revisar."""
    from .pdf_import import MAX_PDF_BYTES, PDFImportError, import_pdf

    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].lower()
    if content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(415, "El tipo de archivo debe ser application/pdf")
    data = await _read_limited_upload(request, MAX_PDF_BYTES, "El PDF")
    try:
        # pypdf is local and CPU-bound. Keeping it in the request avoids a
        # Python 3.14 executor-shutdown deadlock observed in some deployments.
        result = import_pdf(data, filename)
    except PDFImportError as exc:
        raise HTTPException(422, str(exc)) from exc
    return result.as_dict()


@app.post("/api/import-pptx")
async def import_pptx_document(request: Request, filename: str = "presentacion.pptx"):
    """Recibe una presentación PPTX y devuelve Markdown listo para revisar."""
    from .pptx_import import MAX_PPTX_BYTES, PPTXImportError, import_pptx

    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].lower()
    allowed = {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/octet-stream",
    }
    if content_type not in allowed:
        raise HTTPException(415, "El tipo de archivo debe corresponder a PowerPoint .pptx")
    data = await _read_limited_upload(request, MAX_PPTX_BYTES, "La presentación")
    try:
        result = import_pptx(data, filename)
    except PPTXImportError as exc:
        raise HTTPException(422, str(exc)) from exc
    return result.as_dict()


# ── Generate course ──────────────────────────────────────────────────────────

@app.post("/api/generate")
async def generate(body: dict):
    content = _validate_generation_content(body.get("content", {}))
    locale = "es"

    # API key: from body (BYOK) or server env
    api_key, base_url, model = _resolve_ai_config(body)

    if not isinstance(api_key, str) or not api_key.strip():
        raise HTTPException(400, "La clave de API es obligatoria. Configura API_KEY en .env o envíala en la solicitud.")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise HTTPException(400, "El modelo de IA no es válido")

    course_id = _safe_course_id(body.get("course_id") or f"course-{int(time.time())}")
    resumed = (COURSES_DIR / course_id / "games").exists()
    jid = job_mgr.create(course_id)
    status_msg = "Generando una nueva práctica para este curso…" if resumed else "Iniciando generación…"
    job_mgr.log(jid, json.dumps({"type": "info", "label": "status", "value": status_msg}))

    asyncio.create_task(_run_generation(
        jid, content, locale=locale,
        api_key=api_key, base_url=base_url, model=model,
    ))
    return {"job_id": jid, "course_id": course_id}


# ── Jobs ─────────────────────────────────────────────────────────────────────

@app.get("/api/jobs/{jid}")
async def get_job(jid: str):
    jid = _safe_job_id(jid)
    j = job_mgr.get(jid)
    if not j:
        raise HTTPException(404, "No se encontró la tarea")
    return j


# ── AI chat proxy (BYOK) ─────────────────────────────────────────────────────

@app.post("/api/ai-chat")
async def ai_chat(body: dict):
    api_key, base_url, model = _resolve_ai_config(body)
    messages = body.get("messages", [])
    max_tokens = body.get("max_tokens", 1024)

    if not isinstance(api_key, str) or not api_key.strip():
        raise HTTPException(400, "La clave de API es obligatoria")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(400, "Los mensajes son obligatorios")
    if len(messages) > 20 or sum(len(str(message.get("content", ""))) for message in messages if isinstance(message, dict)) > 100_000:
        raise HTTPException(400, "Los mensajes superan el límite permitido")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise HTTPException(400, "El modelo de IA no es válido")
    if not isinstance(max_tokens, int) or not 1 <= max_tokens <= 16_384:
        raise HTTPException(400, "max_tokens debe estar entre 1 y 16384")

    client = _get_ai_client()
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": 0.7, "max_tokens": max_tokens}

    try:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, f"Error de la API de IA: {resp.text[:500]}")
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"content": content}
    except httpx.ConnectError as e:
        _dns_cache.clear()
        raise HTTPException(502, f"No se pudo conectar con el proveedor de IA: {e}")
    except httpx.TimeoutException:
        raise HTTPException(504, "La solicitud a la IA agotó el tiempo de espera. Inténtalo de nuevo.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error en la solicitud a la IA: {type(e).__name__}: {e}")


@app.post("/api/report-minigame-error", status_code=201)
async def report_minigame_error(body: dict):
    """Guarda reportes locales del jugador para poder auditar juegos generados."""
    course_id = _safe_course_id(str(body.get("course_id", "")))
    chunk_id = _safe_chunk_id(str(body.get("chunk_id", "")))
    if not (COURSES_DIR / course_id / "games" / chunk_id).is_dir():
        raise HTTPException(404, "No se encontró el juego reportado")

    minigame_type = str(body.get("minigame_type", "")).strip()[:100]
    error = str(body.get("error", "")).strip()[:2_000]
    message = str(body.get("message", "")).strip()[:1_000]
    if not error and not message:
        message = "Reporte sin descripción"
    report = {
        "id": uuid.uuid4().hex,
        "course_id": course_id,
        "chunk_id": chunk_id,
        "minigame_type": minigame_type,
        "error": error,
        "message": message,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORTS_DIR / f"{report['id']}.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "report_id": report["id"]}


# ── Game player ──────────────────────────────────────────────────────────────

@app.get("/api/play/{course_id}/{chunk_id}/package")
async def get_game_package(course_id: str, chunk_id: str):
    course_id = _safe_course_id(course_id)
    chunk_id = _safe_chunk_id(chunk_id)

    game_dir = COURSES_DIR / course_id / "games" / chunk_id
    if not game_dir.exists():
        raise HTTPException(404, "No se encontró el juego")

    json_path = game_dir / "game.pkg.json"
    if not json_path.exists():
        raise HTTPException(404, "No se encontró el paquete del juego. Intenta generar el curso nuevamente.")

    try:
        pkg = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"El paquete no es válido: {e}")

    if "config" not in pkg:
        pkg["config"] = {}
    if pkg["config"].get("generationMode") == "world" and (COURSES_DIR / course_id / "campaign" / "game.pkg.json").exists():
        campaign = _read_campaign_package(course_id)
        if any(r["id"] == chunk_id and r["worldHash"] == pkg["config"].get("worldHash") for r in campaign["campaign"]["regions"]):
            return campaign
    pkg["config"]["courseId"] = course_id
    pkg["config"]["chunkId"] = chunk_id

    # Manifest order preserves custom IDs and excludes failed lessons.
    manifest_path = game_dir.parent.parent / "course-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        siblings = [g["chunk_id"] for g in manifest.get("games", []) if g.get("status") == "success"]
        pkg["config"].pop("nextGameUrl", None)
        if chunk_id in siblings:
            idx = siblings.index(chunk_id)
            if idx + 1 < len(siblings):
                next_chunk = _safe_chunk_id(siblings[idx + 1])
                pkg["config"]["nextGameUrl"] = f"/play?course={course_id}&game={next_chunk}"

    return pkg


def _read_campaign_package(course_id: str):
    path = COURSES_DIR / course_id / "campaign" / "game.pkg.json"
    if not path.exists():
        raise HTTPException(404, "No se encontró una campaña V2 para este curso")
    try:
        from .generator.world import schema_check
        from .generator.world_campaign import campaign_hash
        from .generator.world_schema import CAMPAIGN_SCHEMA
        package = json.loads(path.read_text(encoding="utf-8"))
        schema_check(package["campaign"], CAMPAIGN_SCHEMA)
        if package["config"]["worldHash"] != campaign_hash(package["campaign"]):
            raise ValueError("Hash de campaña inválido")
        package["config"]["courseId"] = course_id
        return package
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(500, "El paquete de campaña no es válido") from error


@app.get("/api/v2/campaigns/{course_id}/package")
async def get_campaign_package(course_id: str):
    return _read_campaign_package(_safe_course_id(course_id))


@app.get("/api/v2/campaigns/{course_id}")
async def get_campaign_manifest(course_id: str):
    package = _read_campaign_package(_safe_course_id(course_id))
    campaign = package["campaign"]
    return {"format": campaign["format"], "version": campaign["version"], "id": course_id,
            "title": campaign["title"], "hash": package["config"]["worldHash"],
            "regions": [{"id": r["id"], "title": r["world"]["title"]} for r in campaign["regions"]]}


@app.post("/api/v2/generate")
async def generate_v2(body: dict):
    from copy import deepcopy
    body = deepcopy(body)
    content = body.get("content")
    if isinstance(content, dict) and isinstance(content.get("course"), dict):
        content["course"]["gameplay"] = "world"
    return await generate(body)

# ── Config info endpoint ──────────────────────────────────────────────────────
@app.get("/api/config")
async def get_config():
    """Return public config info (no secrets)."""
    return {
        "has_api_key": bool(API_KEY),
        "model": MODEL,
        "base_url": API_BASE_URL,
    }


# ── Static file mounts ────────────────────────────────────────────────────────
if ENGINE_DIR.exists():
    app.mount("/engine", StaticFiles(directory=str(ENGINE_DIR)), name="engine")

if COURSES_DIR.exists():
    app.mount("/courses", StaticFiles(directory=str(COURSES_DIR), html=True), name="courses")

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
