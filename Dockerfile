FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY pyproject.toml ./
RUN mkdir -p price_monitor \
    && touch price_monitor/__init__.py \
    && touch README.md \
    && pip install . \
    && python -m playwright install --with-deps chromium

COPY README.md ./
COPY price_monitor ./price_monitor
COPY alembic.ini ./
COPY alembic ./alembic
RUN pip install --no-deps --force-reinstall .

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app /ms-playwright

USER appuser

EXPOSE 8000
CMD ["uvicorn", "price_monitor.api:app", "--host", "0.0.0.0", "--port", "8000"]
