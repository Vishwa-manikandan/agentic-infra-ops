import json
import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from agentic_sre import build_graph, AgentState

app = FastAPI(title="Agentic SRE API", description="API wrapper for the Infra-Ops AI Agent")

# Global agent instance
agent_app = build_graph()
LOG_PATH = os.path.join(os.path.dirname(__file__), "incidents.jsonl")

class ScanRequest(BaseModel):
    mock: bool = False

class IncidentEntry(BaseModel):
    timestamp: str
    trigger: str
    hypothesis: Optional[dict]
    evidence: Optional[list]
    remediation: Optional[dict]
    execution: Optional[dict]

def run_agent_task(mock: bool):
    """Background task to run the agent loop."""
    # In API mode, we cannot use input(), so we must force dry_run or 
    # handle approval via another API call. For Phase 6, we'll default to dry_run.
    agent_app.invoke({"mock": mock})

@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "ready"}

@app.post("/scan")
async def trigger_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Trigger the agent to check for incidents in the background."""
    background_tasks.add_task(run_agent_task, request.mock)
    return {"message": "Scan triggered successfully in background", "mock_mode": request.mock}

@app.get("/incidents", response_model=List[IncidentEntry])
async def get_incidents():
    """Retrieve the history of detected incidents and actions."""
    if not os.path.exists(LOG_PATH):
        return []
    
    incidents = []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                incidents.append(json.loads(line))
    
    return incidents[::-1] # Return newest first

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
