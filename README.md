<div align="center">

# ⚡ Renvue
### Autonomous Revenue Recovery & Smart Dunning Agent for Indian FinTech

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20Orchestration-blueviolet.svg)](https://langchain-ai.github.io/langgraph/)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-v4-38B2AC.svg)](https://tailwindcss.com)

<p align="center">
  <b>Renvue</b> is an intelligent, multi-channel revenue recovery agent designed to recover lost subscription and checkout payments in India. Combining deterministic financial guardrails with LLM conversational intelligence, Renvue recovers revenue across WhatsApp, Email, and AI Voice Notes without alienating customers.
</p>

</div>

---

## 📌 Problem & Context

In India, recurring subscription payments and high-value checkouts face significant churn due to:
1. **Strict RBI E-Mandate Regulations:** Transactions above ₹15,000 mandate Additional Factor Authentication (AFA/OTP).
2. **Soft Declines:** Insufficient balances around mid-month before payroll dates.
3. **UPI Auto-Pay & Bank Friction:** Technical downtime, mandate expirations, and bank server timeouts.
4. **Clunky Traditional Dunning:** Static, impersonal emails that get marked as spam or alienate customers with tone-deaf retries.

**Renvue** replaces traditional dunning workflows with an adaptive agent that understands payment decline semantics, respects Indian payroll cycles, strictly obeys banking compliance, and negotiates recovery via WhatsApp and email.

---

## 🚀 Key Features & Recovery Archetypes

### 1. Hard Card & Bank Declines
* **Automatic Detection:** Distinguishes between permanent failures (Expired, Stolen, Fraud) vs. transient bank glitches.
* **Instant Recovery Links:** Dispatches secure Razorpay card update links directly via WhatsApp and email.
* **Circuit-Breaker:** Halts retries immediately on unresolvable errors (e.g. frozen accounts) to preserve brand reputation and communication costs.

### 2. Soft Declines & Salary Milestones
* **Payroll-Aware Scheduling:** For insufficient funds declines, aligns retries to the upcoming **1st, 15th, or last Friday** of the month.
* **Progressive Cadence:** Moves from helpful concierge tone $\to$ urgent warning $\to$ statutory notice across scheduled milestones.

### 3. RBI 2026 E-Mandate Thresholds (> ₹15,000)
* **AFA Enforcement:** Automatically routes transactions exceeding ₹15,000 to OTP-authorization payment links instead of failing recurring auto-debits silently.

### 4. Abandoned Checkout Recovery & Bounded Negotiation
* **Smart Concessions:** Engages hesitant customers over WhatsApp, with dynamic discount negotiation strictly bounded between **5% and 30%**.

### 5. B2B Commercial Invoicing
* **Accounts Payable Dunning:** Formal finance communication with Accounts Payable desks.
* **Tax Compliance:** Recognizes and logs TDS deductions (Section 194C @ 2%, Section 194J @ 10%) and requests challan certificates.
* **Promise-to-Pay (PTP):** Automatically parses commitments like *"Our CFO will release payments next Friday"* and pauses chasers until the promised date.

### 6. Regulatory Stopping Rules & Compliance
* **Max 3-Touch Policy:** Never contacts a customer more than 3 times; escalates to human operations if unresolved.
* **TRAI/RBI Consent Opt-Out:** Instantly closes cases upon receiving keywords like `STOP`, `UNSUBSCRIBE`, or opt-out phrases.
* **Dispute Freeze:** Instantly freezes dunning when a customer files a chargeback or payment dispute.

---

## 🏗️ Architecture Overview

Renvue utilizes a **Hybrid Agent Architecture**:
* **Deterministic Fast-Path:** Evaluates banking rules, RBI thresholds, and decline classifications in **< 1ms** without LLM latency.
* **Conversational Agent Loop:** Powered by **Mistral AI** via **LangGraph** to process unstructured inbound customer replies (discount negotiations, objection handling, promise-to-pay extraction).
* **Taskiq Task Engine:** Powered by Redis for delay timers, background execution, and automated follow-ups.
* **Live Operations Dashboard:** Real-time Server-Sent Events (SSE) pushing recovery telemetry directly to a modern React 19 UI.

```mermaid
flowchart TD
    WH["Razorpay / Stripe Webhook"] --> FP["Deterministic Fast-Path<br/>(RBI Rules, Decline Codes, Payroll Milestones)"]
    FP -->|Outbound Outreach| COMMS["Multi-Channel Dispatch<br/>(Twilio WhatsApp, Resend Email, ElevenLabs Voice)"]
    
    CUST["Customer Reply<br/>(WhatsApp / Email)"] --> AGENT["Mistral LangGraph Agent<br/>(Natural Language Reasoning & Negotiation)"]
    AGENT --> TOOLS["Recovery Tools<br/>(Promise-to-Pay, Payment Links, Concessions)"]
    
    COMMS --> SCHED["Taskiq Background Worker & Scheduler<br/>(+3 Day Cadence / Payroll Timers)"]
    SCHED -->|Trigger Follow-up| FP
    
    FP --> AUDIT["PostgreSQL Audit Log & State Storage"]
    AGENT --> AUDIT
    AUDIT --> SSE["Redis Pub/Sub -> FastAPI SSE Stream"]
    SSE --> UI["React 19 Real-Time Recovery Dashboard"]
```

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend Framework** | Python 3.12+, FastAPI, Uvicorn, AsyncIO |
| **Agentic Framework** | LangGraph, LangChain Core, ChatMistralAI |
| **Database & ORM** | PostgreSQL 16+, SQLModel, SQLAlchemy Async, Alembic |
| **Task Queue & Cache** | Taskiq (Async Distributed Queue), Redis 7+ |
| **Communication Stack** | Twilio (WhatsApp Business API), Resend (Transactional Email), ElevenLabs (Multilingual TTS) |
| **Payment Gateway** | Razorpay Python SDK |
| **Frontend Framework** | React 19, TypeScript, Vite 8 |
| **Styling & Components** | Tailwind CSS v4, shadcn/ui, Radix UI, Lucide Icons, Zustand (State Management) |

---

## ⚡ Quick Start & Installation

### Prerequisites
* **Python 3.12+** & [uv](https://docs.astral.sh/uv/) (fast Python package manager)
* **Node.js 20+** & `npm`
* **Docker** (for local PostgreSQL & Redis)

### 1. Clone the Repository
```bash
git clone https://github.com/DineshThumma9/Razor.git renvue
cd renvue
```

### 2. Start Infrastructure (PostgreSQL & Redis)
Ensure Docker is running, then launch local database and cache services:
```bash
# Example local docker run for Postgres
docker run --name renvue-postgres -e POSTGRES_USER=renvue -e POSTGRES_PASSWORD=renvue -e POSTGRES_DB=renvuedb -p 5432:5432 -d postgres:16

# Local Redis
docker run --name renvue-redis -p 6379:6379 -d redis:7-alpine
```

### 3. Configure Environment Variables
Copy and update environment files in `backend/`:
```bash
cp backend/.env.example backend/.env
```
Key environment variables required:
```ini
POSTGRES_URL=postgresql+psycopg://renvue:renvue@localhost:5432/renvuedb
REDIS_URL=redis://localhost:6379
MISTRAL_API_KEY=your_mistral_api_key
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_WHATSAPP_NUMBER=+14155238886
RESEND_API_KEY=your_resend_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
DEMO_MODE=True
```

### 4. Start the Backend Services
Open three terminal tabs (or process manager) inside `backend/`:

**Tab 1: FastAPI Web API Server**
```bash
cd backend
uv run uvicorn src.main:app --reload --port 8000
```

**Tab 2: Taskiq Background Worker**
```bash
cd backend
uv run taskiq worker background.worker:broker
```

**Tab 3: Taskiq Follow-up Scheduler**
```bash
cd backend
uv run taskiq scheduler background.worker:scheduler
```

### 5. Start the Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser to access the live Recovery Operations Dashboard.

---

## 📊 Evaluation & Benchmark Suite

Renvue includes an end-to-end evaluation harness across **30 curated scenarios** testing hard declines, soft declines, e-mandates, cart abandonments, B2B invoices, and safety stopping rules.

To run the batch evaluation:
```bash
cd backend/batch_demo
uv run run_batch.py
```

### Benchmark Results (30 Scenarios)
```text
==========================================================================================
  EXECUTIVE BATCH SCORECARD:
    • Total Revenue at Risk     : ₹311,187.00
    • Gross Revenue Recovered   : ₹255,203.40 (82.0% Recovery Rate)
    • Discounts & Concessions   : ₹2,484.60 (Strictly bounded between 5% - 30%)
    • Multi-Channel Comm Cost   : ₹9.45 (Twilio + Resend + ElevenLabs)
    • NET REALIZED ROI          : ₹252,709.35 (99.0% Realized Efficiency)
    • Case Breakdown            : 23 Recovered | 3 Escalated | 4 Closed
    • Stopping Rules Compliance : 100% (0 Runaway Retries, 0 Compliance Violations)
==========================================================================================
```

Execution logs and summary reports are persisted to `backend/batch_demo/results/`.

---

## 🖥️ Live Simulation Testbench

From the frontend dashboard, you can trigger live test scenarios and follow-ups:
1. **Configure Scenario:** Set customer name, amount, failure reason, and contact details.
2. **Preview Agent Outreach:** View the outbound message generated for WhatsApp.
3. **Fast-Forward (+3 Days):** Accelerate recovery retries across Attempt 1 $\to$ Attempt 2 $\to$ Attempt 3 $\to$ Human Escalation.
4. **Interactive Chat:** Simulate customer inbound objections or confirm payments to observe real-time agent responses and state updates.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
