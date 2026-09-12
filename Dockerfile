# VARUNA / OilTrace — CPU reference image.
#
# GPU/torch is NOT part of this image: the served app (detection results,
# hindcast, attribution, NLP, API, UI) only needs the packages in
# requirements.txt. torch is only used for the OPTIONAL offline U-Net
# training script (scripts/train_unet.py), which you'd run on your own
# machine — see that file's header. This keeps the served image small and
# avoids pulling multi-gigabyte CUDA dependencies for a container that
# never touches a GPU.

# ---- stage 1: build the frontend -------------------------------------------
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app

# Disable any accidental network use at runtime beyond localhost; the app
# itself makes no outbound calls (no LLM API, no tile server, no CDN fonts).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install from the lock, never from requirements.txt: the lock pins every
# direct and transitive dependency to an exact version, so a rebuild months
# from now produces the same environment the demo was recorded against
# (masterplan p.13, Appendix C). requirements.txt is a declaration only.
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY backend/ ./backend/
COPY varuna_core/ ./varuna_core/
COPY scripts/startup_check.py ./scripts/startup_check.py
COPY scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh
# Bake in the synthetic demo case so a fresh container has something to show
# immediately — the "incident capsule" idea from the masterplan (p.6): data,
# results, and launch instructions travel together.
COPY data/cases/ ./data/cases/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN chmod +x ./scripts/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=5 \
  CMD python3 -c "import urllib.request as u; u.urlopen('http://localhost:8000/api/health', timeout=3)" || exit 1

ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
