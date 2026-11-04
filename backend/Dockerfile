FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# Download the embedding model at build time so the first request after a cold start doesn't wait for it.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2', cache_dir='.model_cache')"

CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
