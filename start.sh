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

# Cerrar cualquier proceso que esté usando el puerto 3100
if lsof -ti :3100 >/dev/null 2>&1; then
  echo "  Liberando el puerto 3100..."
  lsof -ti :3100 | xargs kill -9 2>/dev/null || true
  sleep 0.5
fi

# Iniciar en segundo plano el servicio de estado del motor Node
if [ -d "$ROOT_DIR/mindcrafted/node" ]; then
  echo "  Iniciando el motor Node en el puerto 3100..."
  (cd "$ROOT_DIR/mindcrafted/node" && PORT=3100 node server.js) &
  NODE_PID=$!
fi

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

# Limpieza
if [ -n "$NODE_PID" ]; then
  kill "$NODE_PID" 2>/dev/null || true
fi
