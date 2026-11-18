# ──────────────────────────────────────────────────────────────────
# Dockerfile de interfaces (/uis/Dockerfile)
# Basado en la especificación: dockerizacion-prompt.md
# ──────────────────────────────────────────────────────────────────

FROM node:20-alpine AS base

# ------------------------------------------------------------------
# Stage 1: Instalar dependencias del backoffice
# ------------------------------------------------------------------
FROM base AS backoffice-deps
WORKDIR /app/backoffice
COPY backoffice/package.json ./
RUN npm install

# ------------------------------------------------------------------
# Stage 2: Instalar dependencias del website (Tailwind build)
# ------------------------------------------------------------------
FROM base AS website-deps
WORKDIR /app/website
COPY website/package.json ./
RUN npm install

# ------------------------------------------------------------------
# Stage 3: Imagen final con ambas apps
# ------------------------------------------------------------------
FROM base AS final
WORKDIR /app

# Copiar dependencias instaladas
COPY --from=backoffice-deps --chown=node:node /app/backoffice/node_modules ./backoffice/node_modules
COPY --from=website-deps --chown=node:node /app/website/node_modules ./website/node_modules

# Copiar código fuente (incluye dist/styles.css si ya existe)
COPY --chown=node:node backoffice ./backoffice
COPY --chown=node:node website ./website

# Copiar script de arranque
COPY start.sh /start.sh
RUN chmod 0555 /start.sh
USER node

EXPOSE 3000 3001

CMD ["/start.sh"]