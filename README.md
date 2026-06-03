---
title: Network Troubleshooter
emoji: 🌐
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

<div align="center">

# 🌐 Network Troubleshooter — Agentic AI

**Real-time network anomaly detection powered by LSTM autoencoders and autonomous LangChain agents**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Vercel-black?style=for-the-badge&logo=vercel)](https://networktroubleshooter-4gh8xjm7a-mominazd12-4665s-projects.vercel.app/)
[![Backend](https://img.shields.io/badge/Backend-HuggingFace%20Spaces-yellow?style=for-the-badge&logo=huggingface)](https://huggingface.co/spaces/mominazahid/networkagentic)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue?style=for-the-badge&logo=githubactions)](https://github.com/MasoomaShah/network-anomaly-detection-/actions)
[![Python](https://img.shields.io/badge/Python-3.11-green?style=for-the-badge&logo=python)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js)](https://nextjs.org)

</div>

---

## 🔍 What It Does

Network Troubleshooter continuously monitors live network metrics, detects anomalies using a trained LSTM Autoencoder, and dispatches an autonomous AI agent to diagnose and attempt remediation — all in real time.

```
Live Metrics → LSTM Autoencoder → Anomaly Detected → LangChain Agent → Diagnosis + Fix
     ↑               ↑                   ↑                   ↑                ↑
  collector      TensorFlow         Rule-based          OpenAI /          Dashboard
  (8 features)   inference          classifier           Groq LLM          (Next.js)
```

---

## ✨ Features

| Feature | Description |
|---|---|
| 🧠 **LSTM Anomaly Detection** | Autoencoder trained on real network data detects anomalies via reconstruction error |
| 🤖 **Autonomous Agent** | LangChain + LangGraph agent investigates and attempts automated fixes |
| 📊 **Live Dashboard** | Real-time Next.js dashboard with KPI cards, sparklines, agent reasoning panel, and log streams |
| 🌐 **3D Globe** | Interactive Three.js globe visualizing network arcs in the background |
| 🎭 **Demo Scenarios** | Inject real anomalies: bandwidth flood, DNS failure, packet loss, unknown device |
| 🔧 **Manual Trigger Guides** | Copy-paste commands for each scenario (Clumsy, PowerShell, netsh) |
| 📡 **Multi-LLM Support** | Swap between OpenAI, Groq (free), or Ollama via `.env` |
| 🐳 **Dockerized** | Full Docker deployment to Hugging Face Spaces |
| ⚙️ **CI/CD Pipeline** | GitHub Actions: lint → test → model validation → Docker build → deploy |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                      │
│         (Vercel) — Real-time dashboard + 3D globe        │
└──────────────────────────┬──────────────────────────────┘
                           │ REST API (SWR polling)
┌──────────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                          │
│              (Hugging Face Spaces)                       │
│                                                          │
│  ┌─────────────────┐    ┌──────────────────────────┐    │
│  │ LSTM Inference  │    │    LangChain Agent        │    │
│  │                 │    │                           │    │
│  │ • 8 features    │───▶│ • OpenAI / Groq LLM      │    │
│  │ • Autoencoder   │    │ • Network tools           │    │
│  │ • Adaptive thr  │    │ • Autonomous remediation  │    │
│  └────────┬────────┘    └──────────────────────────┘    │
│           │                                              │
│  ┌────────▼────────────────────────┐                    │
│  │        Metric Collector         │                    │
│  │  ping · nmap · psutil · socket  │                    │
│  └─────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

---

## 📈 Detected Anomaly Types

| Anomaly | Detection Method | Trigger |
|---|---|---|
| `gateway_unreachable` | LSTM + gateway ping > 300ms | Router down / network loss |
| `dns_failure` | LSTM + DNS response > 1000ms | DNS server unreachable |
| `high_packet_loss` | LSTM + packet loss > 5% | Network congestion |
| `bandwidth_saturation` | LSTM + throughput spike | Large downloads / floods |
| `high_latency` | LSTM + latency > 150ms | Network congestion |
| `high_jitter` | LSTM + jitter > 80ms | Unstable connection |
| `unknown_device` | LSTM + device count change | New device on network |

---

## 🎯 Two Ways to Run

### ☁️ Live Demo (no setup)
**[Open the live app](https://networktroubleshooter-4gh8xjm7a-mominazd12-4665s-projects.vercel.app/)** → click **Start Monitoring** → use the **inject buttons** in the sidebar to trigger any scenario → watch the LSTM alert appear and the AI agent diagnose it in real time.

> The cloud backend measures its own server network. Inject buttons simulate anomalies directly so the full AI pipeline runs for everyone with no setup.

### 🖥️ Local Mode (real network detection)
Run everything on your own machine. The LSTM monitors **your actual network** — run the manual trigger commands and watch it detect real conditions.

```bash
git clone https://github.com/NetworksTeam/network-anomaly-detection-.git
cd network-anomaly-detection-
cp .env.example .env   # add OPENAI_API_KEY
docker compose up
# open http://localhost:3000
```

Then use the manual trigger commands in the sidebar (bandwidth flood, DNS failure, packet loss) — the LSTM will detect them for real on your network.

---

## 🚀 Quick Start (Local — without Docker)

### Prerequisites
- Python 3.11+
- Node.js 20+
- OpenAI API key (or Groq — free)

### 1. Clone & configure

```bash
git clone https://github.com/MasoomaShah/network-anomaly-detection-.git
cd network-anomaly-detection-
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY
```

### 2. Start the backend

```bash
pip install -r requirements.txt
python -m uvicorn dashboard.server:app --host 0.0.0.0 --port 8001 --reload --reload-dir dashboard --reload-dir agent
```

### 3. Start the frontend

```bash
cd web
npm install
npm run dev
```

Open **http://localhost:3000**

---

## 🎭 Demo Scenarios

Click the **⌘** icon next to each scenario in the sidebar for real trigger commands, or use the inject button to simulate instantly:

| Scenario | What It Simulates |
|---|---|
| **Bandwidth Flood** | Saturate bandwidth with a 10 GB download |
| **DNS Failure** | Point DNS to a dead server via `netsh` |
| **Packet Loss** | Use Clumsy tool — 70% outbound drop |
| **Unknown Device** | New MAC address appears on network |

---

## 🛠️ Tech Stack

**Backend**
- Python 3.11 · FastAPI · TensorFlow/Keras · LangChain · LangGraph
- LSTM Autoencoder (trained on real network data)
- psutil · python-nmap · socket (metric collection)

**Frontend**
- Next.js 16 (App Router) · React 19 · TypeScript
- Tailwind CSS v4 · Three.js · @react-three/fiber
- Recharts · Lucide React · SWR

**Infrastructure**
- 🐳 Docker · Hugging Face Spaces (backend)
- ▲ Vercel (frontend)
- ⚙️ GitHub Actions CI/CD (lint → test → model validation → build → deploy)

---

## 📦 Project Structure

```
network-anomaly-detection-/
├── agent/              # LangChain agent, tools, memory, prompts
├── collector/          # Network metric collection (ping, DNS, bandwidth)
├── dashboard/          # FastAPI server + process manager
├── inference/          # LSTM inference + rule-based classifier
├── models/             # Trained model artifacts (.h5, scaler, threshold)
├── tests/              # Unit + integration tests
├── web/                # Next.js frontend dashboard
│   ├── app/            # App Router pages + globals.css
│   ├── components/     # UI components (KPI, globe, feeds, sidebar)
│   └── lib/            # API client, SWR hooks, types
├── Dockerfile          # Backend container (HF Spaces)
├── main.py             # Entry point
└── .github/workflows/  # CI/CD pipeline
```

---

## ⚙️ Environment Variables

### Backend (`.env` or HF Spaces secrets)

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | `openai` / `groq` / `ollama` | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `OPENAI_MODEL` | Model name | `gpt-4.1` |
| `GROQ_API_KEY` | Groq API key (free alternative) | — |
| `GATEWAY` | Router / host IP to ping | `192.168.1.1` |
| `PING_HOST` | Public host for latency check | `8.8.8.8` |
| `ALLOWED_ORIGINS` | CORS — your frontend URL | `http://localhost:3000` |

### Frontend (Vercel environment variables)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend URL (HF Spaces) |

---

## 🧪 Running Tests

```bash
pytest tests/ -v --timeout=60
```

The CI/CD pipeline runs on every push:
1. 🔍 Code quality (flake8, black, bandit)
2. 🧪 Unit tests (Ubuntu + Windows)
3. 🧠 Model validation
4. 🔗 Integration tests
5. 🏗️ Docker + Next.js build check
6. 🚀 Deploy → HF Spaces + Vercel

---

## 👥 Team

A project demonstrating agentic AI applied to real-world network operations.

---

<div align="center">

**[🌐 Live Demo](https://networktroubleshooter-4gh8xjm7a-mominazd12-4665s-projects.vercel.app/) · [🤗 HF Space](https://huggingface.co/spaces/mominazahid/networkagentic) · [📁 GitHub](https://github.com/MasoomaShah/network-anomaly-detection-)**

</div>
