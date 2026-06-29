FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && apt-get clean

COPY . .

RUN python -m pip install --upgrade pip && python -m pip install -e "."

FROM base AS production
RUN alembic upgrade head || true
CMD ["uvicorn", "agent_slo.api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS dev
RUN python -m pip install -e ".[dev]"
CMD ["uvicorn", "agent_slo.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
