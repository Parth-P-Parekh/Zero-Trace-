# CODE-01 §1: nobody runs the data plane on their host. The team is mixed
# Windows/macOS and wheels differ per OS, so the container is the dev machine.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Requirements first, so a code change does not re-resolve the dependency tree.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini pyproject.toml ./
COPY zerotrace ./zerotrace
COPY scripts ./scripts
COPY policies ./policies
COPY tests ./tests

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"

CMD ["uvicorn", "zerotrace.gateway.app:app", "--host", "0.0.0.0", "--port", "8000"]
