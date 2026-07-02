FROM python:3.11-slim

WORKDIR /app

COPY agentops-core/ agentops-core/
COPY agentops-events/ agentops-events/
RUN pip install --no-cache-dir -e agentops-core/ && pip install --no-cache-dir -e agentops-events/

ARG SERVICE
COPY $SERVICE/ $SERVICE/
RUN pip install --no-cache-dir -e $SERVICE/
