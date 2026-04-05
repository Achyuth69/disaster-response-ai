# ── Disaster Response AI System — Production Dockerfile ─────────────────────
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY agents/ ./agents/
COPY api/ ./api/
COPY ui/ ./ui/
COPY knowledge_base/ ./knowledge_base/
COPY run_api.py demo.py main.py ./
RUN mkdir -p output checkpoints faiss_index logs && \
    useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
# Use shell form so $PORT env var is expanded by the shell
CMD python run_api.py --host 0.0.0.0 --prod
