FROM python:3.11-slim

WORKDIR /app

COPY agentops-core/ agentops-core/
RUN pip install --no-cache-dir -e agentops-core/

ARG SERVICE
COPY $SERVICE/ $SERVICE/
RUN pip install --no-cache-dir -e $SERVICE/
