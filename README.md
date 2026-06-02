# Network Troubleshooter — Agentic AI

> Real-time network anomaly detection powered by an LSTM Autoencoder, with autonomous remediation driven by a LangChain AI agent.

**🌐 Live Demo → [networktroubleshooter.vercel.app](https://networktroubleshooter-4gh8xjm7a-mominazd12-4665s-projects.vercel.app/)**

---

## Overview

Network Troubleshooter continuously monitors 8 network metrics, uses a trained LSTM Autoencoder to detect anomalies through reconstruction error, and dispatches an LLM-powered agent to investigate and remediate issues — all in real time.

The system separates concerns cleanly:

- **The LSTM decides *if* there is an anomaly** — via reconstruction error vs adaptive threshold
- **The rule-based classifier decides *what kind*** — DNS failure, packet loss, bandwidth saturation, etc.
- **The LangChain agent decides *what to do*** — investigates with tools, proposes fixes, logs a diagnosis

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Next.js Dashboard                       │
│          (Live Metrics · Agent Reasoning · Anomaly Feed)     │
└───────────────────────┬─────────────────────────────────────┘
                        │ REST API (FastAPI)
┌───────────────────────▼─────────────────────────────────────┐
│                     FastAPI Backend                          │
│                                                              │
│  ┌─────────────────────┐    ┌──────────────────────────┐    │
│  │   LSTM Inference     │    │    LangChain Agent        │    │
│  │                      │    │                           │    │
│  │  Collector (8 metrics│    │  • Investigates alerts    │    │
│  │  every 3 seconds)    │───▶│  • Runs diagnostic tools  │    │
│  │                      │    │  • Generates diagnosis    │    │
│  │  LSTM Autoencoder    │    │  • Logs remediation steps │    │
│  │  Reconstruction Error│    │                           │    │
│  │  Adaptive Threshold  │    │  LLM: OpenAI / Groq /     │    │
│  └─────────────────────┘    │       Ollama               │    │
│                              └──────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Features

### 🔍 LSTM Anomaly Detection
- Trained LSTM Autoencoder on 8 network features
- Adaptive threshold calibration (mean + 4σ) — adjusts to your network baseline automatically
- 60-sample rolling window (3 min of history) for accurate reconstruction
- Rule-based classifier labels anomaly type: `dns_failure`, `high_packet_loss`, `gateway_unreachable`, `bandwidth_saturation`, `high_latency`, `high_jitter`

### 🤖 Autonomous AI Agent
- LangChain agent with diagnostic tools: ping, DNS lookup, speed test, port scan, traceroute
- Investigates each anomaly, reasons through likely causes, proposes remediation
- Full step-by-step reasoning visible in the dashboard in real time
- Supports OpenAI, Groq (free), or local Ollama models

### 📊 Real-Time Dashboard
- Live KPI cards: Latency, Packet Loss, Download, Upload, Devices, DNS, Gateway, Jitter
- Agent Reasoning panel — see every thought, action, and observation
- Anomaly Feed with severity classification
- Action Log with session history
- Log Streams (Inference + Agent output, live)

### 🎭 Demo Scenarios
Inject realistic anomalies with one click — or trigger them manually:

| Scenario | Demo Button | Real Trigger |
|---|---|---|
| Bandwidth Flood | ✅ | `curl.exe -o NUL https://speed.hetzner.de/10GB.bin` |
| Packet Loss | ✅ | Clumsy tool — outbound drop 70% |
| DNS Failure | ✅ | Set DNS to dead server + `net stop dnscache` |
| Unknown Device | ✅ | Connect new device / `arp -s` |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16 (App Router), React 19, TypeScript, Tailwind v4 |
| **3D Visualization** | Three.js, React Three Fiber — animated globe with network arcs |
| **Backend API** | FastAPI, Uvicorn |
| **ML Model** | TensorFlow / Keras — LSTM Autoencoder |
| **AI Agent** | LangChain, LangGraph |
| **LLM** | OpenAI GPT-4.1 / Groq Llama / Ollama |
| **Data Polling** | SWR (stale-while-revalidate) |
| **Charts** | Recharts |
| **Deployment** | Vercel (frontend) + Hugging Face Spaces Docker (backend) |
| **CI/CD** | GitHub Actions — lint, test, model validation, Docker build, auto-deploy |

---

## Monitored Metrics

| Metric | Method |
|---|---|
| `latency_ms` | ICMP ping to 8.8.8.8 |
| `packet_loss_pct` | Ping batch (4 packets) |
| `download_mbps` | psutil byte counter (1s window) |
| `upload_mbps` | psutil byte counter (1s window) |
| `connected_devices` | nmap subnet scan / ARP table |
| `dns_response_ms` | `socket.gethostbyname("google.com")` |
| `gateway_ping_ms` | ICMP ping to default gateway |
| `jitter_ms` | Std deviation of ping RTTs |

---

## Getting Started (Local)

### Prerequisites
- Python 3.11+
- Node.js 20+
- nmap installed (`choco install nmap` on Windows)

### 1 — Clone & configure

```bash
git clone https://github.com/MasoomaShah/network-anomaly-detection-.git
cd network-anomaly-detection-
```

Copy the env template and add your API key:

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY and LLM_PROVIDER
```

### 2 — Install Python deps

```bash
pip install -r requirements.txt
```

### 3 — Install frontend deps

```bash
cd web && npm install && cd ..
```

### 4 — Run both servers

**Terminal 1 — Backend (FastAPI + LSTM + Agent):**
```bash
python -m uvicorn dashboard.server:app --host 0.0.0.0 --port 8001 --reload --reload-dir dashboard --reload-dir agent
```

**Terminal 2 — Frontend (Next.js):**
```bash
cd web && npm run dev
```

Open **http://localhost:3000**

Or use the Makefile shortcut:
```bash
make dev
```

---

## Environment Variables

### Backend (`.env`)

```env
LLM_PROVIDER=openai          # openai | groq | ollama
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1

# Free alternative — Groq
# LLM_PROVIDER=groq
# GROQ_API_KEY=gsk_...
# GROQ_MODEL=llama-3.3-70b-versatile

GATEWAY=192.168.1.1          # your router IP
NETWORK=192.168.1.0/24
PING_HOST=8.8.8.8
ALLOWED_ORIGINS=http://localhost:3000
```

### Frontend (`web/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8001
```

---

## Project Structure

```
network-anomaly-detection-/
├── agent/                  # LangChain agent, tools, memory, config
│   ├── agent.py            # Agent runner + fallback diagnosis
│   ├── tools.py            # Diagnostic tools (ping, DNS, speed test...)
│   ├── trigger.py          # LSTM watcher + demo injector
│   ├── memory.py           # State persistence (JSON files)
│   └── config.py           # LLM provider factory
├── collector/
│   └── metrics.py          # 8-metric network collector
├── inference/
│   └── inference.py        # LSTM inference + rule-based classifier
├── dashboard/
│   ├── server.py           # FastAPI REST API
│   └── process_manager.py  # Subprocess manager for inference + agent
├── models/
│   ├── lstm_autoencoder.h5 # Trained model
│   ├── scaler.pkl          # StandardScaler from training
│   └── threshold.npy       # Baseline reconstruction threshold
├── web/                    # Next.js frontend
│   ├── app/                # App Router pages + global CSS
│   ├── components/         # UI components
│   │   ├── three/          # 3D globe (Three.js)
│   │   ├── metrics/        # KPI cards + sparklines
│   │   ├── agent/          # Reasoning panel + step cards
│   │   ├── feed/           # Anomaly feed + action log
│   │   └── layout/         # Sidebar + top bar
│   └── lib/                # SWR hooks, API client, types
├── tests/                  # pytest test suite
├── Dockerfile              # Backend container for HF Spaces
├── Makefile                # Dev shortcuts
└── .github/workflows/      # CI/CD pipeline
```

---

## CI/CD Pipeline

GitHub Actions runs on every push to `main`:

```
Code Quality → Unit Tests (Ubuntu + Windows) → Model Validation
                     ↓
              Integration Tests
                     ↓
         Docker Build ←→ Next.js Build  (parallel)
                     ↓
    Deploy Backend         Deploy Frontend
    (HF Spaces)            (Vercel)
```

---

## Deployment

| Service | URL |
|---|---|
| Frontend | [networktroubleshooter.vercel.app](https://networktroubleshooter-4gh8xjm7a-mominazd12-4665s-projects.vercel.app/) |
| Backend API | [mominazahid-networkagentic.hf.space](https://mominazahid-networkagentic.hf.space/api/status) |

---

## License

MIT
