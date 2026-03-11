FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl

RUN addgroup --system appuser && adduser --system --group appuser

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY . .

RUN chown -R appuser:appuser /app

USER appuser

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0"]
