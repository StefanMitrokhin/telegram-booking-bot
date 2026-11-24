FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker/entrypoint.sh /entrypoint.sh

RUN pip install --upgrade pip && pip install .

RUN mkdir -p /app/data && chown -R appuser:appuser /app && chmod 0755 /entrypoint.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,sys,time; p='/tmp/bot.heartbeat'; sys.exit(0 if os.path.exists(p) and time.time()-os.path.getmtime(p)<180 else 1)"

ENTRYPOINT ["/entrypoint.sh"]