import json
import os
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from agentic_sre import build_graph, AgentState

# Setup logging for the API
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentic-api")

app = FastAPI(title="Agentic SRE API", description="API wrapper for the Infra-Ops AI Agent")

# Global agent instance
agent_app = build_graph()
LOG_PATH = os.path.join(os.path.dirname(__file__), "incidents.jsonl")

class ScanRequest(BaseModel):
    mock: bool = False

class IncidentEntry(BaseModel):
    timestamp: Optional[str] = None
    trigger: Optional[str] = None
    hypothesis: Optional[dict] = None
    evidence: Optional[list] = None
    remediation: Optional[dict] = None
    execution: Optional[dict] = None

def run_agent_task(mock: bool):
    """Background task to run the agent loop."""
    try:
        logger.info(f"Starting agent scan (mock={mock})...")
        agent_app.invoke({"mock": mock})
        logger.info("Agent scan completed successfully.")
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "ready"}

@app.post("/scan")
async def trigger_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Trigger the agent to check for incidents in the background."""
    background_tasks.add_task(run_agent_task, request.mock)
    return {"message": "Scan triggered successfully in background", "mock_mode": request.mock}

@app.get("/incidents")
async def get_incidents():
    """Retrieve the history of detected incidents and actions."""
    if not os.path.exists(LOG_PATH):
        return []
    
    incidents = []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        incidents.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.error(f"Skipping malformed JSON line: {line}")
                        continue
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading logs: {str(e)}")
    
    return incidents[::-1] # Return newest first

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
