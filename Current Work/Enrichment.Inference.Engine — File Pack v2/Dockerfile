FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.4

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false &&     poetry install --only main --no-interaction --no-ansi

# ── Runtime image ────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY app/       ./app/
COPY domains/   ./domains/
COPY kb/        ./kb/

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3   CMD python -c "import httpx; httpx.get('http://localhost:8000/v1/health').raise_for_status()"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000",      "--workers", "4", "--access-log"]
