# 🧠 InsightClue — Autonomous AI Data Detective

> **Autonomous Enterprise Root Cause Analysis (RCA) & FinTech Intelligence Multi-Agent Engine**

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Package Manager: uv](https://img.shields.io/badge/Package%20Manager-uv-blueviolet.svg)](https://github.com/astral-sh/uv)
[![Database: PostgreSQL 16 + pgvector](https://img.shields.io/badge/Database-PostgreSQL%2016%20%2B%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Cache: Redis 7](https://img.shields.io/badge/Cache-Redis%207-red.svg)](https://redis.io/)
[![Embeddings: Gemini Embedding 2](https://img.shields.io/badge/Embeddings-Gemini%20Embedding%202-4285F4.svg)](https://ai.google.dev/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)

---

## 📌 Executive Summary

Traditional Business Intelligence (BI) dashboards (Tableau, PowerBI) only tell teams **what** happened (*"Corporate Credit Card spend dropped 32% in South Region"*). Data engineers and financial analysts then spend days manually writing SQL queries, checking bank switch logs, and parsing customer tickets to determine **why**.

**InsightClue** bridges this gap by functioning as an **Autonomous AI Data Detective**:
1. **Continuous Anomaly Monitoring**: Scans time-series transaction and spend metrics using statistical algorithms (Rolling Z-score, IQR) and machine learning (**Isolation Forests**).
2. **Multi-Agent Deep Investigation**: Deploys a specialized multi-agent squad to isolate the exact root cause:
   - **SQL Analytics Agent**: Generates and executes parameterized queries on relational infrastructure logs (`payment_gateway_logs`).
   - **Semantic RAG Agent**: Searches customer dispute tickets and escalation notes using native PostgreSQL **`pgvector` cosine similarity (`<=>`)**.
   - **Statistical Validation Agent**: Calculates hypothesis p-values and correlations to eliminate hallucinations.
3. **Automated RCA Synthesis**: Compiles a comprehensive executive Root Cause Analysis (RCA) report containing numerical proof, technical logs, customer impact citations, and actionable mitigation plans.

---

## 🏗️ End-to-End System Architecture

```
                                 ┌─────────────────────────────────┐
                                 │   Daily FinTech Transactions   │
                                 │ (21,840 Daily Slices, 7,280 GW) │
                                 └────────────────┬────────────────┘
                                                  │
                                                  ▼
                                 ┌─────────────────────────────────┐
                                 │  Statistical & ML Anomaly Engine │
                                 │   - Rolling 14-day Z-Score      │
                                 │   - Multi-Metric Isolation Forest│
                                 └────────────────┬────────────────┘
                                                  │ (Anomaly Flagged!)
                                                  ▼
                                 ┌─────────────────────────────────┐
                                 │  Lead Detective Agent (Planner) │
                                 │    - Decomposes Anomaly         │
                                 │    - Spawns Investigation Hypo  │
                                 └────────┬───────────────┬────────┘
                                          │               │
                 ┌────────────────────────┘               └────────────────────────┐
                 ▼                                                                 ▼
┌─────────────────────────────────┐                             ┌─────────────────────────────────┐
│        SQL Analytics Tool       │                             │      Semantic RAG Search Tool   │
│  - Queries `payment_gateway_logs`│                             │  - Queries `dispute_tickets`    │
│  - Discovers: HDFC 3DS Switch   │                             │  - Vector: Gemini Embedding 2   │
│    threw 380 HTTP 504 Timeouts! │                             │  - Proof: Enterprise AWS OTP    │
└────────────────┬────────────────┘                             │    delivery failure escalation! │
                 │                                              └────────────────┬────────────────┘
                 └────────────────────────┬──────────────────────────────────────┘
                                          │
                                          ▼
                                 ┌─────────────────────────────────┐
                                 │    Statistical Hypothesis Check  │
                                 │  (Rejects False Correlations)   │
                                 └────────────────┬────────────────┘
                                                  │
                                                  ▼
                                 ┌─────────────────────────────────┐
                                 │  Executive RCA Report Generator │
                                 │  - What Happened + Tech Cause   │
                                 │  - Customer Impact + Mitigation │
                                 └─────────────────────────────────┘
```

---

## 🛠️ Technology Stack & Engineering Highlights

| Component | Technology | Technical Rationale |
| :--- | :--- | :--- |
| **Virtual Environment** | `uv` | Instantaneous dependency resolution and deterministic lockfiles. |
| **Relational & Vector DB** | `PostgreSQL 16` + `pgvector` | Storing structured FinTech tables and 768-dim embeddings in the **same database transaction** without distributed sync issues. |
| **In-Memory Cache** | `Redis 7` | Sub-millisecond query caching, session persistence, and agent message queue. |
| **Async ORM Engine** | `SQLAlchemy 2.0 (AsyncIO)` + `asyncpg` | Non-blocking database I/O with connection pooling (`pool_size=10, max_overflow=20`) and `expire_on_commit=False`. |
| **Type Validation** | `Pydantic v2 BaseSettings` | Strict startup environment variable validation with `@lru_cache` parsing. |
| **Vector Embeddings** | `Google Gemini Embedding 2` + `FastEmbed` | 768-dimensional native embeddings via Gemini API, with automatic local FastEmbed (ONNX CPU) fallback for high-speed bulk ingestion. |
| **Anomaly Detection** | `Scikit-learn` & `SciPy` | Isolation Forests on composite multi-metric feature vectors + rolling time-series Z-scores. |
| **Multi-Agent Reasoning** | `LangGraph` & `FastAPI` | State-machine multi-agent workflows with tool-calling sandboxes. |

---

## 📂 Project Directory Layout

```
Major project/
├── docker-compose.yml              # PostgreSQL 16 (pgvector) & Redis 7 containers
├── pyproject.toml                  # uv package & dependency definitions
├── .env.example / .env             # Environment configuration (DB, Redis, Gemini API)
├── src/
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py             # Strongly-typed Pydantic BaseSettings
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py                 # DeclarativeBase with auto-timestamping
│   │   └── session.py              # Async connection pool & get_db() session generator
│   ├── models/
│   │   ├── __init__.py
│   │   ├── fintech_metrics.py      # DailySpendMetric ORM Model (21,840 records)
│   │   ├── gateway_logs.py         # PaymentGatewayLog ORM Model (7,280 records)
│   │   ├── dispute_tickets.py      # DisputeSupportTicket ORM Model (Vector(768))
│   │   └── investigations.py       # AnomalyEvent & InvestigationReport ORM Models
│   ├── services/
│   │   ├── __init__.py
│   │   └── embedding_service.py    # Unified Gemini Embedding 2 + FastEmbed engine
│   ├── agents/                     # LangGraph Multi-Agent investigation workflows
│   └── api/                        # FastAPI REST API endpoints
└── scripts/
    ├── __init__.py
    ├── test_db_connection.py       # DB & pgvector cosine distance diagnostic script
    └── seed_database.py            # 90-day simulation dataset generator with planted anomalies
```

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- **Python 3.11+** installed (or let `uv` download it automatically)
- **Docker Desktop** installed and running
- **`uv` package manager**: `curl -LsSf https://astral.sh/uv/install.ps1 | iex` (Windows)

### 2. Clone and Configure Environment
```bash
# Copy template environment file
cp .env.example .env
```
Edit `.env` and add your **Gemini API Key** (optional for cloud embeddings, local FastEmbed works 100% offline automatically):
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Start Database & Cache Containers
```bash
docker compose up -d
```

### 4. Install Dependencies via `uv`
```bash
uv sync
```

### 5. Run Database Connectivity & pgvector Diagnostic
```bash
uv run python scripts/test_db_connection.py
```

### 6. Populate 90-Day FinTech Simulation Dataset
```bash
uv run python scripts/seed_database.py
```
*Generates and inserts 21,840 spend metric records, 7,280 gateway health logs, and 699 dispute tickets with 768-dimensional vector embeddings.*

---

## 🎯 Planted Root-Cause Anomaly Scenarios

The seeded dataset includes two real-world operational anomalies to test detection and investigation:

### 1. Partner Bank 3DS OTP Degradation (Scenario C)
- **Target**: Days 65–72 in `South Region` for `Corporate Credit Card` (`Enterprise Tier`).
- **Structured Symptoms**: Success rate plunges from 98.8% down to **79.2%**, daily spend drops by **32%**, latency spikes to **1,850ms**.
- **Gateway Evidence**: HDFC 3DS switch shows `DEGRADED` status with over **380 HTTP 504 timeouts/day**.
- **Unstructured Evidence (RAG)**: Wave of critical customer tickets reporting OTP delivery failure on corporate supplier invoice payments.

### 2. Cross-Border Remittance FX Compliance Hold
- **Target**: Days 80–84 in `West Region` for `Cross-Border Remittance`.
- **Symptoms**: Dispute rate surges to **8.5%**, spend volume drops 45%, and automated compliance tickets spike.

---

## 📄 License
MIT License. Built for advanced hands-on AI Engineering mastery.
