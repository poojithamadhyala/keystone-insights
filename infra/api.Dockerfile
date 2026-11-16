FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock .python-version ./
# Only core deps: heavy groups (torch, ray, feast...) stay out of the API image (D-002).
RUN uv sync --frozen --no-dev
COPY common ./common
COPY api ./api
COPY data ./data
COPY prompts ./prompts
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
