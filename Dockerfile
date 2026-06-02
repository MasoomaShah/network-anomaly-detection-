# ── Backend Dockerfile ────────────────────────────────────────────────
# Hugging Face Spaces (Docker) — port 7860, non-root user required
# Also works on Railway / Render (PORT env var overrides 7860)
# ─────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        iputils-ping \
        nmap \
        curl \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces requires a non-root user with uid 1000
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Install Python deps (as user, into ~/.local)
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy source
COPY --chown=user . .

# Create data dir with empty default files
RUN mkdir -p data && \
    echo "[]" > data/alerts.json && \
    echo "{}" > data/agent_state.json && \
    echo "[]" > data/agent_log.json && \
    echo "{}" > data/live_metrics.json && \
    touch data/inference.log && \
    touch data/agent.log

EXPOSE 7860

# PORT env var is injected by HF Spaces (7860) / Railway / Render
CMD uvicorn dashboard.server:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1
