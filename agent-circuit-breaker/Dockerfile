FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && apt-get clean

COPY . .

RUN python -m pip install --upgrade pip && python -m pip install -e "."

FROM base AS production
CMD ["uvicorn", "circuit_breaker.api:app", "--host", "0.0.0.0", "--port", "8001"]

FROM base AS dev
RUN python -m pip install -e ".[dev]"
CMD ["uvicorn", "circuit_breaker.api:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
