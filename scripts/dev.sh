#!/usr/bin/env bash
# Levanta la app INSEVIG en local de forma ESTABLE (un solo puerto, sin recarga
# en caliente que en algunos entornos entra en bucle).
#   ./scripts/dev.sh            -> http://localhost:3000  (admin / admin)
set -e
cd "$(dirname "$0")/.."
pkill -9 -f "reflex run" 2>/dev/null || true
pkill -9 -f "bun run dev" 2>/dev/null || true
sleep 2
.venv/bin/python -m insevig_web.seed >/dev/null 2>&1 || true
exec .venv/bin/reflex run --env prod --single-port --frontend-port 3000
