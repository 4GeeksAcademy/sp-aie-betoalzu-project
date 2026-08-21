#!/bin/sh
# ──────────────────────────────────────────────────────────────────
# start.sh — Arranca ambas aplicaciones (backoffice + website)
# ──────────────────────────────────────────────────────────────────
set -e

echo "=== Iniciando backoffice (Next.js) en el puerto 3001 ==="
cd /app/backoffice
npm run dev -- -p 3001 &
BACKOFFICE_PID=$!

echo "=== Iniciando website (Next.js / estático) en el puerto 3000 ==="
cd /app/website
# Si website tiene package.json con Next.js, usamos dev; si no, servimos estático
if [ -f "package.json" ]; then
  npm run dev -- -p 3000 &
else
  npx serve -p 3000 . &
fi
WEBSITE_PID=$!

# Capturar señales para parar ambos procesos
trap "kill $BACKOFFICE_PID $WEBSITE_PID 2>/dev/null; exit" SIGTERM SIGINT

echo "=== Backoffice corriendo en http://localhost:3001 ==="
echo "=== Website corriendo en http://localhost:3000 ==="

# Esperar cualquier proceso hijo
wait