# 🤖 Agentic Infra-Ops Assistant

An autonomous SRE agent built with **LangGraph**, **Ollama**, and the **Prometheus/Grafana** stack. This system proactively detects infrastructure incidents, reasons over logs and metrics to identify root causes, and proposes/executes safe remediation actions.

## 🏗️ Architecture

### System Flow
`Toy App` $\rightarrow$ `Prometheus/Loki` $\rightarrow$ `LangGraph Agent` $\rightarrow$ `Remediation Engine` $\rightarrow$ `Infrastructure`

### Components
- **Observability**: Prometheus (metrics) & Grafana Loki (logs).
- **Reasoning Engine**: A LangGraph-based agent using an iterative loop:
  - **Detect**: Monitors firing alerts or log anomalies.
  - **Hypothesize**: Generates a theory based on initial context.
  - **Investigate**: Queries logs/metrics to gather evidence for the hypothesis.
  - **Verify**: Evaluates if evidence confirms the theory.
  - **Remediate**: Proposes and executes a safe fix.
- **Safety Layer**: A remediation engine that blocks forbidden commands (e.g., `rm -rf /`) and requires human-in-the-loop (HITL) approval.
- **Interface**: FastAPI REST API for triggering scans and auditing incident history.

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
- **Trigger Scan**: `POST http://localhost:8080/scan`
- **View Incidents**: `GET http://localhost:8080/incidents`
- **Health Check**: `GET http://localhost:8080/health`

## 🛠️ Tech Stack
- **LLM**: Ollama (Llama 3.2 / Nomic Embed)
- **Orchestration**: LangGraph
- **API**: FastAPI
- **Monitoring**: Prometheus, Grafana, Loki
- **Vector DB**: ChromaDB
- **CI/CD**: GitHub Actions

## 🛡️ Safety & Governance
The agent follows a **Dry-Run First** philosophy. Every proposed command is logged and requires explicit human approval via the terminal or API logs before being executed on the host system.

## 🧪 Testing
```bash
# Test the reasoning loop
python test_reasoning_loop.py

# Test the remediation safety engine
python test_remediation.py
```
