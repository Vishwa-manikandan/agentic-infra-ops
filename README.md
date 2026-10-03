# 🤖 Agentic Infra-Ops Assistant

An autonomous, production-grade SRE agent built with **LangGraph**, **Ollama**, and the **Prometheus/Grafana** stack. This system transcends simple monitoring by proactively detecting incidents and using an iterative reasoning loop to identify root causes and execute safe remediations.

## 🌟 Key Features
- **Proactive Detection**: Monitors both Prometheus firing alerts and semantic log anomalies (via ChromaDB vector search).
- **Iterative Reasoning**: Implements a professional SRE workflow: `Detect` $\rightarrow$ `Hypothesize` $\rightarrow$ `Investigate` $\rightarrow$ `Verify` $\rightarrow$ `Remediate`.
- **Semantic Log Analysis**: Uses vector embeddings to find "similar" historical errors, allowing the agent to recognize patterns even if log messages vary slightly.
- **Safe Auto-Remediation**: A dedicated engine that blocks dangerous commands and enforces **Human-in-the-Loop (HITL)** approval before any infrastructure change.
- **REST Interface**: Fully decoupled API for triggering scans and auditing the agent's "thought process" and action history.

## 🏗️ Architecture

### System Flow
`Toy App` $\rightarrow$ `Prometheus/Loki` $\rightarrow$ `LangGraph Agent` $\rightarrow$ `Remediation Engine` $\rightarrow$ `Infrastructure`

### Core Components
- **Observability Stack**: Prometheus (metrics) & Grafana Loki (structured logs).
- **Reasoning Engine (LangGraph)**:
  - **Detection**: Scrapes Prometheus alerts and searches for log bursts.
  - **Hypothesizing**: LLM generates a theory and a verification plan.
  - **Investigation**: Targeted queries to Loki/ChromaDB to gather evidence.
  - **Verification**: LLM evaluates if evidence confirms the hypothesis.
- **Safety Layer**: An execution engine that filters forbidden keywords and manages dry-runs.
- **Interface**: FastAPI wrapper for asynchronous execution and incident tracking.

## 🚀 Getting Started

### Local Setup
1. **Start the Infrastructure**:
   ```bash
   docker compose up --build -d
   ```
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the API**:
   ```bash
   python main.py
   ```

### API Usage
- **Trigger Scan**: `POST http://localhost:8080/scan` $\rightarrow$ Starts background reasoning loop.
- **View Incidents**: `GET http://localhost:8080/incidents` $\rightarrow$ Returns reasoning chain and results.
- **Health Check**: `GET http://localhost:8080/health` $\rightarrow$ Checks system readiness.

## 🛠️ Tech Stack
- **LLM**: Ollama (Llama 3.2 for reasoning, Nomic Embed for logs)
- **Orchestration**: LangGraph (Stateful Multi-Agent Workflows)
- **API**: FastAPI & Uvicorn
- **Monitoring**: Prometheus, Grafana, Loki
- **Vector DB**: ChromaDB
- **CI/CD**: GitHub Actions

## 🛡️ Safety & Governance
To prevent "AI hallucinations" from destroying infrastructure, the system implements:
1. **Forbidden Command List**: Hard-blocks commands like `rm -rf /` or `mkfs`.
2. **HITL Approval**: Every command is presented to a human operator for a `yes/no` confirmation.
3. **Dry-Run Defaults**: The engine defaults to dry-run mode unless explicitly configured otherwise.

## 🧪 Testing
```bash
# Verify the iterative reasoning and state transitions
python test_reasoning_loop.py

# Verify the remediation safety and execution engine
python test_remediation.py
```
