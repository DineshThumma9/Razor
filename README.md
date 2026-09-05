<div align="center">

# ⚡ Renvue
### Autonomous Revenue Recovery & Smart Dunning for Indian FinTech

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20Orchestration-blueviolet.svg)](https://langchain-ai.github.io/langgraph/)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-v4-38B2AC.svg)](https://tailwindcss.com)

<p align="center">
  <b>Renvue</b> is an intelligent, multi-channel revenue recovery agent designed to recover lost subscription, invoice, and checkout payments in India. Combining sub-millisecond deterministic banking rules with LLM conversational intelligence, Renvue recovers revenue across WhatsApp, Email, and Voice without alienating customers.
</p>

</div>

---

## 📌 Problem & Context

In India, recurring subscriptions and high-ticket checkouts face severe revenue drop-offs due to structural payment barriers:

1. **RBI E-Mandate Regulations:** Recurring debits exceeding ₹15,000 mandate customer Additional Factor Authentication (AFA/OTP) rather than silent auto-debits.
2. **Payroll Rhythms & Soft Declines:** Insufficient balances peak mid-month before corporate salary disbursement dates.
3. **Card Expiry & Mandate Degradation:** Expired cards cause silent subscription halt without automated instrument migration.
4. **Checkout Abandonment:** Customers drop off during OTP entry or payment method selection without timely intervention.
5. **Traditional Dunning Spam:** Static, impersonal email sequences get ignored, marked as spam, and damage brand trust.

**Renvue** replaces traditional dunning with an adaptive recovery agent that understands Indian payment decline semantics, aligns with payroll cycles, strictly enforces banking compliance, and resolves payment objections through natural conversation.

---

## 🏗️ System Architecture & Agent Workflow

<div align="center">

### System Architecture
![Renvue System Architecture](ArchRenvue.svg)

<br/>

### Agent Recovery & Decision Graph
![Renvue Agent Workflow](agent_workflow.png)

</div>

Renvue utilizes a **Two-Tier Hybrid Architecture**:

* **Deterministic Fast-Path (< 1ms):** Evaluates banking decline codes, RBI thresholds, and payroll milestones instantly without LLM latency or inference cost.
* **Conversational Agent Loop (LangGraph + Mistral):** Wakes up when inbound customer replies arrive (WhatsApp, email) to parse intent, negotiate concessions within policy, and extract promise-to-pay dates.
* **Asynchronous Task Engine (Taskiq + Redis):** Manages milestone timers, payroll-aligned delay schedules, and progressive retry cadences.
* **Real-Time Operations Dashboard (React 19 + SSE):** Streams live recovery status transitions, audit trails, and financial telemetry over Server-Sent Events.

---

## 🚀 Key Recovery Pillars

### 1. Payment Degradation & Smart Retries
* **Decline Semantics:** Distinguishes between permanent failures (card expired, lost, stolen) and transient bank timeouts.
* **Payroll-Aware Scheduling:** Insufficient funds retries automatically align to upcoming salary milestones (**1st, 15th, or last Friday**).
* **Payment Links:** Generates secure Razorpay payment links directly hydrated into customer messages.

### 2. Abandoned Checkout Recovery
* **Drop-Step Awareness:** Detects whether drop-off occurred during OTP verification or method selection.
* **Bounded Concession Policy:** Autonomously negotiates discounts strictly bounded between **5% and 30%** based on customer lifetime value, with strict anti-gaming ceilings.

### 3. Recurring Subscription Mandates
* **RBI Section 10(2) Compliance:** Automatically issues mandatory **24-hour pre-debit intimation notices** before executing recurring debits.
* **Mandate Re-Authorization:** Dispatches `sub_card_change` links so customers can update payment instruments without losing recurring tenure.

### 4. B2B Commercial Invoices & Receivables
* **Accounts Payable Decorum:** Professional, formal finance tone adhering to Net-30 enterprise terms.
* **Tax Compliance (TDS):** Understands Section 194C (2%) and Section 194J (10%) deductions and proactively requests Form 16A TDS certificates.
* **Promise-to-Pay (PTP) Tracker:** Parses natural language commitments (*"CFO will clear it on the 10th"*), validates date sanity, enforces a **7-day cumulative grace cap**, and pauses dunning.

### 5. Regulatory Stopping Rules & Compliance
* **Max 3-Touch Stopping Rule:** Never contacts a customer more than 3 times; escalates to human operations if unresolved.
* **TRAI/RBI Consent Opt-Out:** Instantly closes cases and freezes communications upon receiving `STOP`, `UNSUBSCRIBE`, or opt-out phrases.
* **Dispute Freeze Kill-Switch:** Instantly freezes dunning when a customer files a chargeback or payment dispute.

---

## 📊 Benchmark Evaluation (30 Scenarios)

Renvue includes an end-to-end evaluation harness across **30 curated Indian payment scenarios** testing hard declines, salary milestone backoffs, RBI 2026 e-mandate rules, abandoned checkouts, B2B invoices, and compliance stopping rules.


User load_dotenv  at top of config.config
in case of demo to run run_batch.py else wont work prolly 


To run the benchmark suite:
```bash
cd backend
uv run python batch_demo/run_batch.py
```

### Measured A/B Incremental Lift Scorecard
```text
==========================================================================================
  RENVUE REVENUE RECOVERY — BATCH EXECUTION MATRIX (30 SCENARIOS)
==========================================================================================
  • Total Revenue at Risk     : ₹311,187.00
  • Passive Baseline (Control): ₹82,464.56 (26.5% organic recovery)
  • Gross Recovered (Agent)   : ₹255,202.33 (82.0% treatment recovery)
  ----------------------------------------------------------------------------------------
  • NET INCREMENTAL LIFT      : +₹172,737.77 (+55.5% lift over control)
  • Incremental ROI Multiplier: 8,973x operational efficiency
  • Discounts & Concessions   : ₹2,485.67 (Strictly bounded between 5% - 30%)
  • Multi-Channel Comm Cost   : ₹19.25 (Twilio + Resend + ElevenLabs + LLM)
  • NET REALIZED ROI          : ₹252,697.41 (99.0% net efficiency)
  • Case Breakdown            : 23 Recovered | 6 Escalated | 1 Closed
  • Stopping Rules Compliance : 100% (0 Runaway Retries, 0 Compliance Violations)
==========================================================================================
```
*Full execution logs and summary markdown are persisted to [`backend/batch_demo/results/`](backend/batch_demo/results/).*

---

## 🧪 Automated Test Suites

Renvue includes 6 domain-specific test suites in [`backend/src/tests/`](backend/src/tests/):

| Test Suite | File | What It Validates |
| :--- | :--- | :--- |
| **1. Lifecycle & Escalation** | `src/tests/test_lifecycle.py` | Progressive follow-ups, turn-level state persistence, strict auto-escalation at attempt $\ge 3$. |
| **2. Promise-to-Pay (PTP)** | `src/tests/test_promise_to_pay.py` | Multi-format date parsing, cumulative 7-day grace cap, anti-exploitation, vague reply handling. |
| **3. B2B Invoices** | `src/tests/test_b2b_invoices.py` | Accounts Payable tone, Net-30 terms, TDS deductions (194C/194J), Form 16A request. |
| **4. Subscriptions** | `src/tests/test_subscriptions.py` | Mandate re-auth links (`sub_card_change`) and RBI Section 10(2) 24h pre-debit intimation notice. |
| **5. Checkout Concessions** | `src/tests/test_checkout_concessions.py` | Bell-curve concession ceiling (5%–30%), LLM negotiation bounds, and anti-gaming guardrails. |
| **6. Webhook Security** | `src/tests/test_webhook_security.py` | Razorpay HMAC-SHA256 signature verification, demo bypass, and strict production rejection. |

**Run all 6 suites:**
```bash
cd backend
uv run python src/tests/runner.py
```

**Run an individual suite:**
```bash
uv run python src/tests/test_lifecycle.py
uv run python src/tests/test_promise_to_pay.py
uv run python src/tests/test_b2b_invoices.py
uv run python src/tests/test_subscriptions.py
uv run python src/tests/test_checkout_concessions.py
uv run python src/tests/test_webhook_security.py
```

---

## 🎮 Unified Case Generator & Live Demo Simulator

To populate the frontend dashboard with live cases during presentations or testing, use the unified seeder in [`backend/src/data/generate.py`](backend/src/data/generate.py):

```bash
cd backend

# 1. Live Interactive Demo (fires 7 cases across all categories with real-time UI transitions)
uv run python src/data/generate.py --demo

# 2. Custom Batch Generation (exports to backend/data/sample_cases.json)
uv run python src/data/generate.py --payment 3 --checkout 2 --subscription 2 --invoice 2

# 3. Offline Export Only (no server required)
uv run python src/data/generate.py --no-webhook --all
```

---

## 📁 Repository Structure

```
renvue/
├── README.md                     # Project documentation & architecture
├── ArchRenvue.svg                # Vector architecture diagram (high-DPI zoomable)
├── agent_workflow.png            # LangGraph agent recovery & decision graph
├── supervisord.conf              # Process supervisor configuration
├── backend/
│   ├── pyproject.toml            # Dependencies managed via uv
│   ├── .env.example              # Sample environment configuration
│   ├── batch_demo/               # 30-Scenario Benchmark Suite
│   │   ├── run_batch.py          # Benchmark evaluation harness (+55.5% lift)
│   │   ├── payload_builder.py    # Authentic Razorpay 2026 banking payloads
│   │   ├── scenarios.json        # Curated benchmark scenarios
│   │   └── results/              # Execution telemetry & recovery_summary.md
│   ├── data/
│   │   └── sample_cases.json     # Sample synthetic dataset
│   └── src/                      # Production application code
│       ├── agent/                # LangGraph state graph, nodes, prompts, tools
│       ├── background/           # Taskiq async worker and retry scheduler
│       ├── config/               # Settings, DB session, Razorpay/Twilio/Resend clients
│       ├── data/
│       │   └── generate.py       # Unified dataset seeder & demo simulator
│       ├── models/               # Pydantic schemas & SQLModel ORM models
│       ├── router/               # Razorpay webhooks & WhatsApp listeners
│       ├── service/              # Compliance, downtime circuit-breaker, recovery logic
│       └── tests/                # 6 modular domain test suites & runner.py
└── frontend/                     # React 19 + Vite + Tailwind Operations Dashboard
    ├── package.json
    └── src/                      # Real-time SSE dashboard, case drawer, timeline
```

---

## ⚡ Quick Start & Installation

### Prerequisites
* **Python 3.12+** & [uv](https://docs.astral.sh/uv/)
* **Node.js 20+** & `npm`
* **Docker** (for local PostgreSQL & Redis)

### 1. Clone the Repository
```bash
git clone https://github.com/DineshThumma9/Razor.git renvue
cd renvue
```

### 2. Start Infrastructure (PostgreSQL & Redis)
```bash
docker run --name renvue-postgres -e POSTGRES_USER=renvue -e POSTGRES_PASSWORD=renvue -e POSTGRES_DB=renvuedb -p 5432:5432 -d postgres:16
docker run --name renvue-redis -p 6379:6379 -d redis:7-alpine
```

### 3. Configure Environment Variables
```bash
cp backend/.env.example backend/.env
```
Key variables in `backend/.env`:
```ini
POSTGRES_URL=postgresql+psycopg://renvue:renvue@localhost:5432/renvuedb
REDIS_URL=redis://localhost:6379
MISTRAL_API_KEY=your_mistral_api_key
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_WHATSAPP_NUMBER=+14155238886
RESEND_API_KEY=your_resend_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
DEMO_MODE=True
```

### 4. Start Backend Services
In `backend/`:

**Tab 1 — FastAPI Server:**
```bash
cd backend
uv run uvicorn src.main:app --reload --port 8000
```

**Tab 2 — Taskiq Worker:**
```bash
cd backend
uv run taskiq worker -d src background.worker:broker
```

**Tab 3 — Taskiq Scheduler:**
```bash
cd backend
uv run taskiq scheduler -d src background.worker:scheduler
```

### 5. Start Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** to access the live Recovery Operations Dashboard.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
