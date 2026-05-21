# =========================
# Base
# =========================
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app


# =========================
# Dependencies
# =========================
FROM base AS deps

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev


# =========================
# Runtime
# =========================
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY --from=deps /app /app

COPY engine/ engine/
COPY classes/ classes/
COPY main.py ./

RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uv", "run", "main.py"]