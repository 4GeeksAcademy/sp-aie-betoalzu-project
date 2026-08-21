# ──────────────────────────────────────────────────────────────────
# Dockerfile del backend (/services/Dockerfile)
# Basado en la especificación: dockerizacion-prompt.md
# Build context = raíz del proyecto (para incluir server.py)
# ──────────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# ------------------------------------------------------------------
# Instalar uv
# ------------------------------------------------------------------
RUN pip install --no-cache-dir uv

# ------------------------------------------------------------------
# Copiar dependencias e instalarlas con uv
# ------------------------------------------------------------------
COPY services/requirements.txt .
RUN uv pip install --system -r requirements.txt

# ------------------------------------------------------------------
# Copiar el código fuente (server.py en raíz + services/)
# ------------------------------------------------------------------
COPY server.py .
COPY services/ ./services/

# ------------------------------------------------------------------
# Puerto y comando de arranque con --reload habilitado
# ------------------------------------------------------------------
EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]