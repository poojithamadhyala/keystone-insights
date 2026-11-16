FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy FASTEMBED_CACHE_PATH=/app/.models
COPY pyproject.toml uv.lock .python-version ./
# Core + search deps (fastembed/ONNX, pinecone). No torch (D-030).
RUN uv sync --frozen --no-dev --group rag
ENV PATH="/app/.venv/bin:$PATH"
# Bake both models into the image so a cold start never downloads ~100 MB on the first question.
RUN python -c "from fastembed import TextEmbedding; \
from fastembed.rerank.cross_encoder import TextCrossEncoder; \
TextEmbedding('BAAI/bge-small-en-v1.5'); TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2')"
COPY common ./common
COPY api ./api
COPY data ./data
COPY rag ./rag
COPY prompts ./prompts
EXPOSE 8000
# Migrations are idempotent, so running them on every boot keeps a hosted DB (Neon) current.
# Render sets $PORT; locally it defaults to 8000.
CMD ["sh", "-c", "alembic -c data/alembic.ini upgrade head && exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
