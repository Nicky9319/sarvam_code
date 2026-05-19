# Stage 1: Base
FROM python:3.13-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv

# Stage 2: Dependencies
FROM base AS deps

WORKDIR /app

# Copy lock file and project files for dependency installation
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Stage 3: Development
FROM base AS dev

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY . .

# Install all dependencies (including dev)
RUN uv sync --frozen

# Stage 4: Production build
FROM base AS build

WORKDIR /app

# Copy only dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies without dev
RUN uv sync --frozen --no-dev

# Copy source code
COPY engine/ engine/
COPY classes/ classes/
COPY main.py ./

# Stage 5: Production runtime
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install production dependencies only
COPY --from=build /app /app

# Run as non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port (FastAPI default)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command (can be overridden)
CMD ["python", "main.py"]