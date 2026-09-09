#!/bin/bash
# MindCrafted — Inicio rápido

set -e

cd "$(dirname "$0")"
ROOT_DIR="$(pwd)"

# Cargar .env si existe
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

BIND_HOST="${BIND_HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo ""
echo "  🐸 MindCrafted — Estudio de aprendizaje basado en juegos con IA"
echo "  ─────────────────────────────────────────────"
echo "  Estudio: http://$BIND_HOST:$PORT/"
echo ""

# Buscar uvicorn: priorizar el entorno virtual y luego el PATH del sistema
if [ -f "$ROOT_DIR/.venv/bin/uvicorn" ]; then
  UVICORN="$ROOT_DIR/.venv/bin/uvicorn"
elif command -v uvicorn >/dev/null 2>&1; then
  UVICORN="uvicorn"
else
  echo "  ERROR: no se encontró uvicorn. Activa primero tu entorno virtual:"
  echo "    source .venv/bin/activate"
  exit 1
fi

# Iniciar el servidor Python con la raíz del proyecto en PYTHONPATH
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
"$UVICORN" mindcrafted.server:app --host "$BIND_HOST" --port "$PORT"
