# 🚨 Disaster Response AI System

> *"This isn't just one AI. It's a team of AI agents working under pressure, with limited resources, constantly adapting to chaos — just like a real disaster response unit."*

[![CI](https://github.com/your-org/disaster-response-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/disaster-response-ai/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An **enterprise-grade, security-hardened, multi-agent AI system** for real-time disaster response coordination. Deployable anywhere in the world. Powered by Groq (ultra-fast LLM inference) + RAG + Adaptive Chaos Simulation.

---

## 🌐 Live Demo

```
http://localhost:8000/ui/index.html   ← 3D Animated Dashboard
http://localhost:8000/api/docs        ← Interactive API Docs
http://localhost:8000/api/health      ← Health Check
```

---

## 🧠 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              3D Web Dashboard (Three.js + Chart.js)             │
│                    WebSocket Real-Time Updates                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket / REST
┌──────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Server (async)                        │
│              Rate Limiting · CORS · GZip · Health               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                       Orchestrator                              │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Audit    │  │ Checkpoint   │  │ Circuit Breakers         │  │
│  │ Chain    │  │ (Encrypted)  │  │ (per agent)              │  │
│  │ (HMAC)   │  │              │  │                          │  │
│  └──────────┘  └──────────────┘  └──────────────────────────┘  │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
Data      Rescue     Resource   Comms      Chaos
Agent     Planner    Allocator  Agent      Simulator
(RAG)   (Consensus) (Consensus)          (Adaptive)
   │
   ▼
FAISS + sentence-transformers
Knowledge Base (Hyderabad + Global)
```

---

## 🎭 Agents

| Agent | Role | Tech |
|---|---|---|
| **Data Agent** | RAG-powered retrieval of maps, hospitals, flood zones, population data | FAISS + sentence-transformers |
| **Rescue Planner** | Priority zone ranking + team assignment | Groq LLM + Consensus Voting |
| **Resource Allocator** | Optimal resource distribution with depletion tracking | Groq LLM + Consensus Voting |
| **Communication Agent** | Public alerts + internal tactical messages | Groq LLM |
| **Chaos Simulator** | Adaptive difficulty chaos injection | Deterministic/Random |
| **Orchestrator** | Central coordinator, conflict resolution, audit | Python |

---

## 🔥 Features

### Security
- **Cryptographic Audit Chain** — HMAC-SHA256 hash-linked log, tamper-evident
- **Prompt Injection Defense** — Sanitizes all LLM inputs against 8+ attack patterns
- **API Key Redaction** — Keys never appear in logs or error messages
- **Fernet-Encrypted Checkpoints** — AES-128-CBC encrypted state files

### Resilience
- **Circuit Breakers** — Auto-bypass failing agents after N consecutive failures
- **Multi-LLM Fallback** — Groq primary → Gemini secondary → cached output
- **State Checkpointing** — Resume from crash without losing progress
- **Token Bucket Rate Limiting** — Prevents API rate limit hits

### Intelligence
- **Consensus Voting** — Two LLMs vote on critical decisions
- **Agent Memory** — Cross-cycle learning (cleared zones, blocked routes, consumption rates)
- **Adaptive Chaos** — Difficulty scales with agent confidence scores
- **Compound Events** — Multiple simultaneous chaos events at high severity

### Observability
- **Structured Logging** — JSON logs in production, colored in development
- **Real-Time WebSocket** — Live cycle updates streamed to dashboard
- **3D Animated Dashboard** — Three.js globe, Chart.js charts, GSAP animations
- **Lives Saved Metric** — Estimates lives saved per cycle
- **Agent Disagreement Scoring** — Tracks inter-agent conflicts

---

## 🚀 Quick Start

### Option 1: Direct Python

```bash
cd AGENT

# Install dependencies
pip install -r requirements.txt

# Configure API key
echo "GROQ_API_KEY=your_key_here" >> .env
# Get free key at: https://console.groq.com

# Start API server + dashboard
python run_api.py

# Open dashboard
# http://localhost:8000/ui/index.html
```

### Option 2: Docker

```bash
cd AGENT

# Set your API key
export GROQ_API_KEY=your_key_here

# Build and run
docker-compose up --build

# Open dashboard
# http://localhost:8000/ui/index.html
```

### Option 3: CLI Demo (no server)

```bash
cd AGENT
pip install -r requirements.txt
echo "GROQ_API_KEY=your_key_here" >> .env

# Run Hyderabad flood demo (3 cycles, severity 8)
python demo.py --seed 42

# Custom scenario
python main.py \
  --disaster-type earthquake \
  --location Mumbai \
  --severity 9 \
  --cycles 5 \
  --dashboard
```

---

## 📡 API Reference

### Start a Run
```http
POST /api/run
Content-Type: application/json

{
  "disaster_type": "flood",
  "location": "Hyderabad",
  "severity": 8,
  "num_cycles": 3,
  "rescue_teams": 10,
  "boats": 5,
  "medical_kits": 100,
  "food_supply_units": 200,
  "chaos_enabled": true
}
```

### Start Demo
```http
POST /api/demo
```

### Get Status
```http
GET /api/status/{session_token}
```

### Get Report
```http
GET /api/report/{session_token}
```

### WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/{session_token}');
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  // msg.type: "run_start" | "cycle_start" | "cycle_complete" | "run_complete" | "error"
};
```

---

## 📁 Project Structure

```
AGENT/
├── main.py                    # CLI entry point
├── demo.py                    # Hyderabad flood demo
├── run_api.py                 # FastAPI server launcher
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env                       # API keys (never commit)
├── .env.example               # Safe template
├── .github/workflows/ci.yml   # GitHub Actions CI/CD
│
├── agents/                    # Core AI system
│   ├── models.py              # All dataclasses + exceptions
│   ├── schemas.py             # Pydantic API schemas
│   ├── llm_client.py          # Groq + Gemini + circuit breaker
│   ├── security.py            # Audit chain + prompt sanitizer
│   ├── memory.py              # Agent cross-cycle memory
│   ├── checkpoint.py          # Encrypted state checkpointing
│   ├── dashboard.py           # Rich terminal dashboard
│   ├── logger.py              # Structured logging
│   ├── rate_limiter.py        # Token bucket rate limiting
│   ├── data_agent.py          # RAG pipeline (FAISS)
│   ├── rescue_planner.py      # Rescue planning + consensus
│   ├── resource_allocator.py  # Resource distribution + consensus
│   ├── communication_agent.py # Messaging
│   ├── chaos_simulator.py     # Adaptive chaos
│   └── orchestrator.py        # Central coordinator
│
├── api/                       # FastAPI REST + WebSocket
│   └── server.py
│
├── ui/                        # 3D Web Dashboard
│   └── index.html             # Three.js + Chart.js + GSAP
│
├── knowledge_base/            # RAG documents
│   ├── hyderabad_maps.txt
│   ├── hospitals.txt
│   ├── flood_zones.txt
│   └── population_density.txt
│
└── tests/                     # Test suite
    ├── test_models.py
    ├── test_chaos_simulator.py
    ├── test_security.py
    ├── test_orchestrator.py
    └── test_properties.py     # 18 property-based tests (Hypothesis)
```

---

## 🧪 Testing

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=agents --cov-report=html

# Property-based tests only (18 correctness properties)
pytest tests/test_properties.py -v

# Deterministic (reproducible)
pytest tests/test_properties.py --hypothesis-seed=42
```

### 18 Correctness Properties

| # | Property |
|---|---|
| P1 | Severity validation rejects out-of-range values |
| P2 | Agent execution order always enforced |
| P3 | DataSummary always has required fields |
| P4 | Priority zones sorted descending by score |
| P5 | Team assignments are injective (no duplicates) |
| P6 | Allocation never exceeds available supply |
| P7 | Depleted resources flagged at zero |
| P8 | Communication messages have required content |
| P9 | Fallback messages ≤ 50 words |
| P10 | Chaos events from defined categories only |
| P11 | No consecutive identical chaos categories |
| P12 | Disabled chaos passes context unchanged |
| P13 | Conflict resolution picks higher-severity zone |
| P14 | Audit log grows exactly one entry per agent per cycle |
| P15 | Orchestrator runs exactly configured cycle count |
| P16 | Final report contains all required sections |
| P17 | Audit chain detects any single-entry mutation |
| P18 | Sanitizer removes all known injection patterns |

---

## 🌍 Global Deployment

The system works for **any disaster, any location worldwide**:

```bash
# Japan earthquake
python main.py --disaster-type earthquake --location Tokyo --severity 9 --cycles 5

# Bangladesh cyclone
python main.py --disaster-type cyclone --location Dhaka --severity 8 --cycles 4

# California wildfire
python main.py --disaster-type wildfire --location "Los Angeles" --severity 7 --cycles 3

# Indonesia tsunami
python main.py --disaster-type tsunami --location Jakarta --severity 10 --cycles 6
```

---

## 🔒 Security

- API keys loaded from `.env` only — never hardcoded
- All LLM inputs sanitized against prompt injection (8 pattern types)
- Audit chain is cryptographically tamper-evident (HMAC-SHA256)
- Checkpoints encrypted with Fernet (AES-128-CBC)
- API keys redacted from all logs and error messages
- Non-root Docker user
- CORS configured for production deployment

---

## 📊 Performance

- **Groq inference**: ~100-500ms per LLM call (fastest available)
- **FAISS retrieval**: <10ms for top-k search
- **Full cycle**: ~5-15s per response cycle (depends on LLM latency)
- **WebSocket latency**: <50ms for live updates
- **Concurrent sessions**: Supported via FastAPI async background tasks

---

## 📄 License

MIT License — free to use, modify, and deploy anywhere in the world.
