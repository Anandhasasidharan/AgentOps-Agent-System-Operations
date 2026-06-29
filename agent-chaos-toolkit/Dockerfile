FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . .

RUN python -m pip install --upgrade pip && python -m pip install -e "."

FROM base AS production
CMD ["uvicorn", "chaos_toolkit.api:app", "--host", "0.0.0.0", "--port", "8002"]

FROM base AS dev
RUN python -m pip install -e ".[dev]"
CMD ["uvicorn", "chaos_toolkit.api:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]
