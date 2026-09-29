#!/bin/sh
# ──────────────────────────────────────────────────────────────────
# start.sh — Arranca ambas aplicaciones en modo producción
# backoffice (Next.js build) + website (estático con Tailwind compilado)
# ──────────────────────────────────────────────────────────────────

echo "=== Construyendo backoffice (Next.js) ==="
cd /app/backoffice
npm run build

echo "=== Iniciando backoffice (Next.js producción) en el puerto 3001 ==="
npm start -- -p 3001 &
BACKOFFICE_PID=$!

echo "=== Construyendo CSS del website (Tailwind) ==="
cd /app/website
if [ -f "package.json" ]; then
  # Intentar instalar tailwindcss si no está disponible
  if ! command -v tailwindcss >/dev/null 2>&1 && [ -f "node_modules/.bin/tailwindcss" ]; then
    export PATH="$PWD/node_modules/.bin:$PATH"
  fi
  if command -v tailwindcss >/dev/null 2>&1 || [ -f "node_modules/.bin/tailwindcss" ]; then
    tailwindcss --input ./src/styles.css --output ./dist/styles.css --minify 2>&1 || echo "[WARN] Falló build de CSS del website"
  else
    echo "[WARN] tailwindcss no encontrado, instalando dependencias del website..."
    npm install --silent 2>&1
    if [ -f "node_modules/.bin/tailwindcss" ]; then
      ./node_modules/.bin/tailwindcss --input ./src/styles.css --output ./dist/styles.css --minify 2>&1 || echo "[WARN] Falló build de CSS del website"
    else
      echo "[WARN] No se pudo instalar tailwindcss. El website se servirá sin CSS compilado."
    fi
  fi
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