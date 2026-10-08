# ============================================================================
# CreditCast — single-container deploy (self-hosted at dhyyraj.in / any Docker host).
# FastAPI serves the API under /api and the pre-built static Next.js cockpit at
# /. Model artifacts are baked at build time by running the full pipeline once
# in the trainer stage, then copied into a slim runtime image (no train at boot).
# ============================================================================

# ---- Stage 1: build the static Next.js cockpit -----------------------------
FROM node:20-slim AS web
WORKDIR /web
COPY app/dashboard/package.json app/dashboard/package-lock.json ./
RUN npm ci
COPY app/dashboard/ ./
# NEXT_PUBLIC_API_URL="" -> the cockpit calls the same-origin /api
RUN npm run build

# ---- Stage 2: train models + generate artifacts (full deps) -----------------
FROM python:3.11-slim AS trainer
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
# Pinned + hash-checked lock (generated from requirements.in by scripts/lock-deps.sh)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY creditcast/ ./creditcast/
ENV PYTHONPATH=/app
# the data/artifact dirs are .dockerignored (regenerable) — create them fresh
RUN mkdir -p creditcast/data/bronze creditcast/data/silver \
             creditcast/data/gold creditcast/artifacts creditcast/reports
# generate -> Silver -> Gold -> train -> validate -> governance -> monitor -> gates
# (a failing gate fails the build — exactly what we want)
RUN python -m creditcast.cli all

# ---- Stage 3: slim runtime image -------------------------------------------
FROM python:3.11-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
# Serve lock is constrained by the training lock: the runtime unpickles the
# models with exactly the library versions that trained them.
COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

# application code
COPY creditcast/ ./creditcast/
COPY app/ ./app/
# baked artifacts + the Gold matrix (serving needs it for the vintage rate lookup)
COPY --from=trainer /app/creditcast/artifacts/ ./creditcast/artifacts/
COPY --from=trainer /app/creditcast/data/gold/ ./creditcast/data/gold/
COPY --from=trainer /app/creditcast/governance/model_card.md ./creditcast/governance/model_card.md
# static cockpit
COPY --from=web /web/out/ ./static/

ENV PYTHONPATH=/app \
    STATIC_DIR=/app/static \
    PORT=8000
EXPOSE 8000

# Healthy = every model artifact exists and loads (GET /api/ready).
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/ready' % os.environ.get('PORT', '8000'), timeout=8)" || exit 1

# Serves API + cockpit on one port; put a TLS reverse proxy in front (see deploy/).
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT}"]
