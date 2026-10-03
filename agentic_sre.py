"""
Agentic Infra-Ops Assistant: Iterative Reasoning Version
------------------------------------------------------------
A LangGraph agent that proactively detects infrastructure incidents and
uses an iterative reasoning loop (Hypothesize -> Investigate -> Verify)
to identify root causes before proposing remediation.

Workflow:
Detect -> Initial Context -> Generate Hypothesis -> Gather Evidence ->
Evaluate Evidence -> (Loop if unclear) -> Propose Remediation -> Log Result
"""

import argparse
import json
import os
import time
import logging
from datetime import datetime, timezone
from typing import TypedDict, Union, List, Dict, Optional

import requests
import chromadb
from remediation.engine import engine as remediation_engine
from prompts import HYPOTHESIS_PROMPT, EVALUATE_PROMPT, REMEDIATION_PROMPT

# --- Configuration -----------------------------------------------------------
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100")
CHROMA_URL = os.environ.get("CHROMA_URL", "http://chromadb:8000")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
LOG_PATH = os.path.join(os.path.dirname(__file__), "incidents.jsonl")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentic-sre")

# --- Hybrid Log Tooling ------------------------------------------------------

class LogQueryTool:
    """
    Hybrid Log Tool: Interfaces with Grafana Loki (Structured)
    and ChromaDB (Semantic Vector Store).
    """
    def __init__(self):
        try:
            self.chroma_client = chromadb.HttpClient(host="chromadb", port=8000)
            self.collection = self.chroma_client.get_or_create_collection(name="incident_logs")
        except Exception as e:
            logger.warning(f"Could not connect to ChromaDB: {e}. Vector search will be unavailable.")
            self.collection = None

    def _get_embedding(self, text: str):
        """Helper to get embedding from Ollama nomic-embed-text model."""
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text}
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    def query_structured_logs(self, query_string: str, limit: int = 10):
        """Queries Loki for structured logs."""
        params = {"query": query_string, "limit": limit}
        try:
            response = requests.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params, timeout=5)
            response.raise_for_status()
            return response.json()["data"]["result"]
        except Exception as e:
            return f"Error querying Loki: {e}"

    def query_semantic_logs(self, text: str, n_results: int = 3):
        """Queries ChromaDB for semantically similar logs."""
        if not self.collection:
            return "ChromaDB unavailable"
        try:
            embedding = self._get_embedding(text)
            if not embedding:
                return f"Embedding failed for: {text[:50]}..."
            results = self.collection.query(query_embeddings=[embedding], n_results=n_results)
            return results["documents"]
        except Exception as e:
            return f"Error querying ChromaDB: {e}"

    def detect_anomalies(self, window_minutes: int = 5, threshold: int = 5):
        """Proactive detection: Checks for 'bursts' of similar error logs."""
        logs = self.query_structured_logs(
            query_string='{container_name="toy-service"} |= "ERROR"',
            limit=50
        )
        if isinstance(logs, str): return None

        lines = []
        for stream in logs:
            for val in stream["values"]:
                lines.append(val[1])

        if not lines: return None

        anomalies = []
        for line in lines:
            try:
                log_text = json.loads(line).get("message", line)
                emb = self._get_embedding(log_text)
                if not emb or not self.collection: continue

                similar = self.collection.query(query_embeddings=[emb], n_results=10)["documents"][0]
                if len(similar) >= threshold:
                    anomalies.append({"pattern": log_text, "count": len(similar), "example": line})
            except: continue

        return sorted(anomalies, key=lambda x: x["count"], reverse=True)[0] if anomalies else None

# Initialize global tool
log_tool = LogQueryTool()

# --- LangGraph State & Nodes --------------------------------------------------

class AgentState(TypedDict, total=False):
    trigger_type: str  # "PROMETHEUS", "LOG_ANOMALY", or "NONE"
    trigger_data: Union[dict, list]
    alerts: list
    context: dict
    logs: list
    hypothesis: dict
    evidence: list
    remediation: dict
    mock: bool
    iteration_count: int

def detect_incidents(state: AgentState) -> AgentState:
    """Entry node: Checks Prometheus and Log patterns."""
    # Ensure iteration_count is initialized in state
    if "iteration_count" not in state:
        state["iteration_count"] = 0
    
    if state.get("mock"):
        state["trigger_type"] = "PROMETHEUS"
        state["alerts"] = [{
            "labels": {"alertname": "HighErrorRate", "severity": "critical"},
            "annotations": {"summary": "High HTTP 5xx error rate detected", "description": "Error rate 100%"},
            "state": "firing"
        }]
        return state

    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/alerts", timeout=5)
        resp.raise_for_status()
        alerts = [a for a in resp.json()["data"]["alerts"] if a.get("state") == "firing"]
        if alerts:
            state["trigger_type"] = "PROMETHEUS"
            state["alerts"] = alerts
            return state
    except Exception as e:
        logger.error(f"Prometheus check failed: {e}")

    anomaly = log_tool.detect_anomalies()
    if anomaly:
        state["trigger_type"] = "LOG_ANOMALY"
        state["trigger_data"] = anomaly
        state["alerts"] = [{
            "labels": {"alertname": "LogAnomalyDetected", "severity": "warning"},
            "annotations": {"summary": f"Log burst: {anomaly['pattern'][:50]}...", "description": f"Found {anomaly['count']} similar logs"},
            "state": "firing"
        }]
        return state

    state["trigger_type"] = "NONE"
    return state

def has_incident(state: AgentState) -> str:
    return "gather_context" if state.get("trigger_type") != "NONE" else "no_action"

def gather_context(state: AgentState) -> AgentState:
    """Gather basic Prometheus metrics."""
    if state.get("mock"):
        state["context"] = {"error_rate_pct": 100.0, "note": "mock context"}
        return state

    queries = {"error_rate_pct": '(sum(rate(http_requests_total{status=~"5.."}[1m])) / sum(rate(http_requests_total[1m]))) * 100'}
    context = {}
    for key, q in queries.items():
        try:
            resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": q}, timeout=5)
            result = resp.json()["data"]["result"]
            context[key] = float(result[0]["value"][1]) if result else None
        except Exception as e:
            context[key] = f"failed: {e}"
    state["context"] = context
    return state

def generate_hypothesis(state: AgentState) -> AgentState:
    """LLM creates a hypothesis and a verification plan."""
    alert = state["alerts"][0]
    
    prompt = HYPOTHESIS_PROMPT.format(
        trigger_type=state.get('trigger_type'),
        alert_name=alert['labels']['alertname'],
        summary=alert['annotations'].get('summary', ''),
        context=json.dumps(state.get('context')),
        evidence=json.dumps(state.get('evidence', []))
    )

    if state.get("mock"):
        state["hypothesis"] = {
            "hypothesis": "Database connection pool exhaustion",
            "reasoning": "High error rates paired with timeout patterns in logs.",
            "verification_steps": ["Connection timeout", "pool exhausted"]
        }
        return state

    try:
        import ollama
        response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        raw = response["message"]["content"].strip().strip("`").replace("json\n", "")
        state["hypothesis"] = json.loads(raw)
    except Exception as e:
        state["hypothesis"] = {"hypothesis": "Unknown error", "reasoning": str(e), "verification_steps": []}

    return state


def gather_evidence(state: AgentState) -> AgentState:
    """Targeted investigation based on the hypothesis."""
    hypothesis = state.get("hypothesis", {})
    steps = hypothesis.get("verification_steps", [])
    evidence = []
    
    # Increment iteration count here because conditional edges cannot update state
    count = state.get("iteration_count", 0)
    state["iteration_count"] = count + 1

    for step in steps:
        # Try structured search
        logs = log_tool.query_structured_logs(f'{{container_name="toy-service"}} |= "{step}"')
        if isinstance(logs, list) and logs:
            evidence.append(f"Structured Match for '{step}': Found {len(logs)} occurrences.")

        # Try semantic search
        semantic = log_tool.query_semantic_logs(text=step)
        if isinstance(semantic, list) and semantic:
            evidence.append(f"Semantic Match for '{step}': {semantic[0][:100]}...")

    state["evidence"] = evidence
    return state

def evaluate_hypothesis(state: AgentState) -> str:
    """Determine if the evidence supports the hypothesis."""
    evidence = state.get("evidence", [])
    
    # To prevent infinite recursion, check iteration count
    count = state.get("iteration_count", 0)
    if count >= 3:
        return "propose_remediation"

    if not evidence:
        # Avoid looping if no evidence can be gathered
        if count >= 1:
             return "propose_remediation"
        # LangGraph requires returning the updated state in a node, 
        # but this is a conditional edge. Conditional edges cannot update state.
        # We must update iteration_count in the 'gather_evidence' node instead.
        return "generate_hypothesis"

    # Use LLM to decide if evidence is sufficient
    hypothesis = state.get("hypothesis", {})
    prompt = f"""Does the following evidence support the hypothesis?
    Hypothesis: {hypothesis.get('hypothesis')}
    Evidence: {json.dumps(evidence)}

    Respond ONLY with 'CONFIRMED' or 'UNCONFIRMED'."""

    if state.get("mock"):
        return "propose_remediation"

    try:
        import ollama
        response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        decision = response["message"]["content"].strip().upper()

        if "CONFIRMED" in decision:
            return "propose_remediation"
        return "generate_hypothesis"
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return "propose_remediation"

def propose_remediation(state: AgentState) -> AgentState:
    """Final step: propose fix based on verified hypothesis."""
    alert = state["alerts"][0]
    
    prompt = REMEDIATION_PROMPT.format(
        alert_name=alert['labels']['alertname'],
        hypothesis=state['hypothesis'].get('hypothesis'),
        evidence=json.dumps(state.get('evidence'))
    )

    if state.get("mock"):
        state["remediation"] = {"analysis": "Verified DB pool issue", "recommended_action": "scale db", "risk": "low", "dry_run_command": "docker compose scale db=2"}
        return state

    try:
        import ollama
        response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        raw = response["message"]["content"].strip().strip("`").replace("json\n", "")
        state["remediation"] = json.loads(raw)
    except Exception as e:
        state["remediation"] = {"analysis": f"Error: {e}", "recommended_action": "manual", "risk": "unknown", "dry_run_command": None}

    return state


def log_decision(state: AgentState) -> AgentState:
    """Persist the reasoning chain and execute the remediation if approved."""
    alert = state["alerts"][0]
    remediation = state.get("remediation", {})
    cmd = remediation.get("dry_run_command")

    # Human-in-the-loop approval
    print(f"\n{'='*60}\nPROPOSED REMEDIATION: {alert['labels']['alertname']}")
    print(f"Analysis: {remediation.get('analysis')}")
    print(f"Action:   {remediation.get('recommended_action')}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    # Handle non-interactive environments (like tests or API)
    try:
        # We only ask for input if we are running in a TTY (interactive terminal)
        import sys
        if sys.stdin.isatty():
            user_input = input("Execute this command? (yes/no): ").strip().lower()
        else:
            user_input = "no"
    except (EOFError, Exception):
        user_input = "no"
    
    execution_result = {"status": "skipped", "output": None, "error": None}
    if user_input == "yes" and cmd:
        print(f"Executing: {cmd}...")
        res = remediation_engine.execute(cmd)
        execution_result = {
            "status": "executed",
            "output": res.get("output"),
            "error": res.get("error"),
            "success": res.get("success")
        }
        if res.get("success"):
            print("✅ Execution successful!")
        else:
            print(f"❌ Execution failed: {res.get('error')}")
    else:
        print("Action skipped or denied.")

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": state.get("trigger_type"),
        "hypothesis": state.get("hypothesis"),
        "evidence": state.get("evidence"),
        "remediation": remediation,
        "execution": execution_result
    }
    
    print(f"\n{'='*60}\nINCIDENT LOGGED\nTrigger: {state.get('trigger_type')}\nHypothesis: {state['hypothesis'].get('hypothesis')}\nAction Result: {execution_result['status']}\n{'='*60}")

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return state


def no_action(state: AgentState) -> AgentState:
    print(f"[{datetime.now(timezone.utc).isoformat()}] All clear.")
    return state

def build_graph():
    from langgraph.graph import StateGraph, END
    graph = StateGraph(AgentState)

    graph.add_node("detect_incidents", detect_incidents)
    graph.add_node("gather_context", gather_context)
    graph.add_node("generate_hypothesis", generate_hypothesis)
    graph.add_node("gather_evidence", gather_evidence)
    graph.add_node("propose_remediation", propose_remediation)
    graph.add_node("log_decision", log_decision)
    graph.add_node("no_action", no_action)

    graph.set_entry_point("detect_incidents")
    graph.add_conditional_edges("detect_incidents", has_incident, {"gather_context": "gather_context", "no_action": "no_action"})
    graph.add_edge("gather_context", "generate_hypothesis")
    graph.add_edge("generate_hypothesis", "gather_evidence")
    graph.add_conditional_edges("gather_evidence", evaluate_hypothesis, {
        "propose_remediation": "propose_remediation",
        "generate_hypothesis": "generate_hypothesis"
    })
    graph.add_edge("propose_remediation", "log_decision")
    graph.add_edge("log_decision", END)
    graph.add_edge("no_action", END)

    return graph.compile()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    app = build_graph()
    if args.watch:
        while True:
            app.invoke({"mock": args.mock})
            time.sleep(args.interval)
    else:
        app.invoke({"mock": args.mock})

if __name__ == "__main__":
    main()
