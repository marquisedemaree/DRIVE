# syntax=docker/dockerfile:1

# ---------------------------------------------------------
# Stage 1: Build the React frontend
# ---------------------------------------------------------
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci

COPY frontend/ ./

RUN npm run build


# ---------------------------------------------------------
# Stage 2: Run FastAPI and the DRIVE analytics pipeline
# ---------------------------------------------------------
FROM python:3.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system drive \
    && adduser --system --ingroup drive drive

COPY requirements.txt ./

RUN pip install \
    --no-cache-dir \
    --upgrade pip \
    && pip install \
    --no-cache-dir \
    -r requirements.txt

COPY . .

COPY --from=frontend-builder \
    /frontend/dist \
    /app/frontend/dist

RUN mkdir -p \
    /app/input/tesla-model3 \
    /app/runtime \
    && chown -R drive:drive /app

USER drive

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=60s \
    --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
