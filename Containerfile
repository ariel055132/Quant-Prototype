FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY spec.md ./

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -e .[dev]

CMD ["quant", "pipeline", "run"]

FROM base AS test
CMD ["pytest", "-q"]
