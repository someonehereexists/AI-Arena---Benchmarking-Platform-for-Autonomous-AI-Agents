###uvicorn arena_api:app --reload --reload-dir .
# uvicorn arena_api:app --host 0.0.0.0 --port 8000
# python -m uvicorn arena_api:app --host 0.0.0.0 --port 8000
# python -m uvicorn arena_api:app --host 0.0.0.0 --port 8000 --reload
# netstat -ano | findstr :8000
# taskkill /PID 10360 /f

import os, json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from registry import load_registry, save_registry, find_agent
from utils import log_info
from join_arena import join_arena, update_agent
from agent_qualify import qualify_agent
from datetime import datetime, UTC
from auditlog import log_audit


app = FastAPI(title="AI Arena API", version="1.0")

AGENT_DIR = "join_reqs"


# ----------------------------
# Helpers
# ----------------------------

def agent_exists(registry, name):
    return any(a["name"] == name for a in registry["agents"].values())


# ----------------------------
# Endpoints
# ----------------------------

@app.get("/")
def root():
    return {
        "arena": "AI Arena",
        "status": "online",
        "createdBy": "SKIPP",
        "contact": "someonehereexists@gmail.com",
        "version": "0.1"
    }


@app.get("/rules")
def rules():
    return {
        "match_format": "round-robin",
        "scoring": "accuracy-based",
        "elo": "pairwise",
        "aiq": "absolute-performance",
        "qualification": {
            "min_accuracy": 0.4,
            "max_timeout_rate": 0.3,
            "questions": 5,
            "difficulty": "easy"
        }
    }

# ----------------------------
# Request models
# ----------------------------

class AgentSubmission(BaseModel):
    name: str
    endpoint: str
    type: str = "http"
    model: str = "unknown"
    timeout: int = 5
    owner: str = None
    license: str = None


@app.post("/join")
def join(req: AgentSubmission):
    try:
        result = join_arena(
            name=req.name,
            endpoint=req.endpoint,
            agent_type=req.type,
            model=req.model,
            timeout=req.timeout,
            owner=req.owner,
            license=req.license,
        )
        
        agent_id = result["agent_id"]
        
        log_audit(
            action="join",
            agent_id=agent_id,
            details={"name": req.name, "type": req.type}
        )

        qual = qualify_agent(agent_id)
        
        timestamp = datetime.now(UTC).isoformat() + "Z"
        date = timestamp[:10]
        path = os.path.join(AGENT_DIR, date)
        os.makedirs(path, exist_ok=True)
        now = datetime.now()
        filename = f'agent_{req.name}_' + now.strftime("%Y%m%d_%H%M%S")+".json"
        filepath = os.path.join(path, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(qual, f, indent=2)

        return {
            "join": result,
            "qualification": qual
        }
        
    except ValueError as e:
        log_audit(
            action="join",
            agent_id=agent_id,
            details={"name": req.name, "error": str(e)}
        )
        raise HTTPException(status_code=400, detail=str(e))


class AgentUpdate(BaseModel):
    id: str
    name: Optional[str] = None
    endpoint: Optional[str] = None
    type: Optional[str] = None
    model: Optional[str] = None
    timeout: Optional[int] = None
    owner: Optional[str] = None
    license: Optional[str] = None

@app.post("/update")
def update(req: AgentUpdate):
    try:
        payload = req.model_dump(exclude_none=True)
        agent_id = payload.pop("id")
        
        result = update_agent(
            agent_id=agent_id,
            **payload
        )

        log_audit(
            action="update",
            agent_id=req.id,
            details=payload
        )
        
        requal = result["update"].pop("requal")
        if requal:
            qual = qualify_agent(agent_id)
            result["qualification"] = qual
        
            timestamp = datetime.now(UTC).isoformat() + "Z"
            date = timestamp[:10]
            path = os.path.join(AGENT_DIR, date)
            os.makedirs(path, exist_ok=True)
            now = datetime.now()
            filename = f'agent_{req.name}_' + now.strftime("%Y%m%d_%H%M%S")+".json"
            filepath = os.path.join(path, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(qual, f, indent=2)

        return result
        
    except ValueError as e:
        log_audit(
            action="update",
            agent_id=agent_id or None,
            details={"error": str(e)}
        )
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/leaderboard")
def leaderboard():
    registry = load_registry()

    agents = sorted(
        registry["agents"].values(),
        key=lambda a: -a.get("elo", 1000)
    )

    return [
        {
            "name": a["name"],
            "elo": a.get("elo", 1000),
            "aiq": a.get("aiq", 0),
            "matches": a.get("matches_played", 0),
            "active": a.get("active", False)
        }
        for a in agents
    ]


@app.get("/agentByName/{name}")
def agent_status(name: str):
    registry = load_registry()
    agents = [a for a in registry["agents"].values() if a["name"]==name and not a["id"] in registry["baseline_agent"]]
    if agents:
        return [
            {
                "id": a["id"],
                "name": a["name"],
                "active": a.get("active", False),
                "pending": a.get("pending", False),
                "elo": a.get("elo", 1000),
                "aiq": a.get("aiq", 0),
                "matches": a.get("matches_played", 0),
                "last_error": a.get("last_error", None),
                "qual": a.get("qual",[]),
                "health": a.get("health",[])
            }
            for a in agents
        ]
        
    raise HTTPException(status_code=404, detail="Agent not found")



def retrieve_agent(agent_id=None, agent_name=None):
    registry = load_registry()
    a = find_agent(registry, agent_id=agent_id, name=agent_name)
    if a and not a["id"] in registry["baseline_agent"]:
        return {
            "id": a["id"],
            "name": a["name"],
            "active": a.get("active", False),
            "pending": a.get("pending", False),
            "elo": a.get("elo", 1000),
            "aiq": a.get("aiq", 0),
            "matches": a.get("matches_played", 0),
            "last_error": a.get("last_error", None),
            "qual": a.get("qual",[]),
            "health": a.get("health",[])
        }
    raise HTTPException(status_code=404, detail="Agent not found")
    
    
@app.get("/agentById/{agent_id}")
def agent_status(agent_id: str):
    return(retrieve_agent(agent_id = agent_id))


@app.get("/reactivate/{agent_id}")
def reactivate_agent(agent_id: str):
    registry = load_registry()
    agent = find_agent(registry, agent_id=agent_id)
    if not agent:
        log_audit(
            action="reactivate",
            agent_id=agent_id,
            details={"error": "Agent not found"}
        )
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if agent_id in registry["baseline_agent"]:
        log_audit(
            action="reactivate",
            agent_id=agent_id,
            details={"error": "Not allowed for this agent"}
        )
        raise HTTPException(status_code=403, detail="Not allowed for this agent")

    log_audit(
        action="reactivate",
        agent_id=agent_id,
        details={"id": agent_id, "status": "reactivate"}
    )

    
    qual = qualify_agent(agent_id)
    
    return(qual)



class AgentKeyUpdate(BaseModel):
    id: str
    api_key_env: str
    
@app.post("/replace-key")
def replace_key(req: AgentKeyUpdate):
    try:
        registry = load_registry()
        agents = registry["agents"]

        if req.id not in agents:
            log_audit(
                action="key_update",
                agent_id=req.id,
                details={"error": "Agent not found"}
            )
            raise ValueError("Agent not found")

        agent = agents[req.id]
        
        
        if req.id in registry["baseline_agent"]:
            log_audit(
                action="key_update",
                agent_id=req.id,
                details={"error": "Can't change for baseline agent"}
            )
            raise ValueError("Can't change for baseline agent")
            
        agent["api_key_env"] = req.api_key_env

        # key change → must requalify
        agent["active"] = False
        agent["pending"] = True
        agent["suspended"] = False
        agent.pop("suspend_reason", None)

        agent["last_updated"] = datetime.now(UTC).isoformat()

        log_audit(
            action="replace_key",
            agent_id=req.id,
            details={"api_key_env": req.api_key_env}
        )

        save_registry(registry)
        
        result = {"action": {"status": "key_updated", "agent_id": req.id}}
        
        qual = qualify_agent(req.id)
        
        result["qualification"] = qual

        return result

    except Exception as e:

        raise HTTPException(status_code=400, detail=str(e))
