#!/bin/sh
# ──────────────────────────────────────────────────────────────────
# start.sh — Arranca ambas aplicaciones en modo producción
# backoffice (Next.js build) + website (estático con Tailwind compilado)
# ──────────────────────────────────────────────────────────────────
set -e

echo "=== Construyendo backoffice (Next.js) ==="
cd /app/backoffice
npm run build

echo "=== Iniciando backoffice (Next.js producción) en el puerto 3001 ==="
npm start -- -p 3001 &
BACKOFFICE_PID=$!

echo "=== Construyendo CSS del website (Tailwind) ==="
cd /app/website
if [ -f "package.json" ]; then
  npm install --silent
  npm run build:css
fi

echo "=== Sirviendo website estático en el puerto 3000 ==="
npx serve -p 3000 ./ &
WEBSITE_PID=$!

# Capturar señales para parar ambos procesos
trap "kill $BACKOFFICE_PID $WEBSITE_PID 2>/dev/null; exit" SIGTERM SIGINT

echo "=== Backoffice corriendo en http://localhost:3001 ==="
echo "=== Website corriendo en http://localhost:3000 ==="

# Esperar cualquier proceso hijo
wait