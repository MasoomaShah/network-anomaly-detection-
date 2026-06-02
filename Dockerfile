# ── Backend Dockerfile ────────────────────────────────────────────────
# Runs FastAPI + LSTM inference + LangChain agent on port 8001
# Deploy to: Railway, Render, or Hugging Face Spaces (Docker)
# ─────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# System deps: ping (for metrics), nmap (device scan), curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
        iputils-ping \
        nmap \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create data dir (process_manager writes logs/json here at runtime)
RUN mkdir -p data && \
    echo "[]" > data/alerts.json && \
    echo "{}" > data/agent_state.json && \
    echo "[]" > data/agent_log.json && \
    echo "{}" > data/live_metrics.json && \
    touch data/inference.log && \
    touch data/agent.log

# Expose API port
# HF Spaces uses PORT=7860 by default; Railway/Render use 8001.
# The shell form lets us read $PORT at runtime.
EXPOSE 7860

# Allow ping without root (needed for metrics collection)
RUN setcap cap_net_raw+ep /bin/ping 2>/dev/null || true

CMD uvicorn dashboard.server:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1
