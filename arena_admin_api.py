# $env:ARENA_ADMIN_TOKEN="dev-secret"
# uvicorn arena_admin_api:app --host 127.0.0.1 --port 8001
# python -m uvicorn arena_admin_api:app --host 127.0.0.1 --port 8001
# python -m uvicorn arena_admin_api:app --host 127.0.0.1 --port 8001 --reload
# netstat -ano | findstr :8001
# taskkill /PID 10360 /f

import os, sys, threading, signal, subprocess
from fastapi import FastAPI, APIRouter, Request, HTTPException, BackgroundTasks
from registry import load_registry, save_registry, find_agent
from master_ai import health_police
from ai_arena_mvp_groq import run_ai_arena
from time import sleep
from auditlog import admin_log

arena_thread = None
arena_running = False
arena_stop = False

app = FastAPI(title="AI Arena ADMIN API", version="1.0")

ADMIN_TOKEN = os.getenv("ARENA_ADMIN_TOKEN", "dev-secret")

#create admin router 
#admin = APIRouter(prefix="/admin", tags=["admin"])

def _verify_admin(request: Request):
    client_ip = request.client.host

    if client_ip not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="Forbidden")

    token = request.headers.get("X-Admin-Token")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")


#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/shutdown -Headers $headers
#  or curl
#  curl -X POST http://127.0.0.1:8001/shutdown -H "X-Admin-Token: dev-secret"
#  


def _shutdown():
    os.kill(os.getpid(), signal.SIGINT)

@app.post("/admin/shutdown")
def shutdown(background_tasks: BackgroundTasks, request: Request):
    _verify_admin(request)
    
    background_tasks.add_task(_shutdown)
    return {"status": "shutting down"}


#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod http://127.0.0.1:8001/admin/registry -Headers $headers

@app.get("/admin/registry")
def get_registry(request: Request):
    _verify_admin(request)
    return load_registry()


#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/agents/AGENT_ID/suspend -Headers $headers

@app.post("/admin/agents/{agent_id}/suspend")
def suspend_agent(agent_id: str, request: Request):
    _verify_admin(request)

    registry = load_registry()
    agent = find_agent(registry, agent_id=agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent_id in registry["baseline_agent"]:
        raise HTTPException(status_code=403, detail="Can't Suspend Baseline Agent")

    agent["active"] = False
    agent["pending"] = False
    agent["suspended"] = True

    save_registry(registry)

    admin_log(
        action="suspend",
        agent_id=agent_id,
        details={"status" : "suspended"}
    )

    return {"status": "suspended", "agent_id": agent_id}


#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/agents/AGENT_ID/activate -Headers $headers

@app.post("/admin/agents/{agent_id}/activate")
def activate_agent(agent_id: str, request: Request):
    _verify_admin(request)

    registry = load_registry()
    agent = find_agent(registry, agent_id=agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent["active"] = True
    agent["pending"] = False
    agent["suspended"] = False

    save_registry(registry)

    admin_log(
        action="reactivate",
        agent_id=agent_id,
        details={"status" : "success"}
    )

    return {"status": "activated", "agent_id": agent_id}


#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/health/run -Headers $headers

@app.post("/admin/health/run")
def run_health(request: Request):
    _verify_admin(request)

    result = health_police()

    admin_log(
        action="health_run",
        agent_id=None,
        details={"status" : "success"}
    )

    return {"status": "health_check_completed", "result":result}



def run_arena(interval: int, loop: bool):
    while True:
        if arena_stop:
            print("Arena loop stop requested")
            break
            
        run_ai_arena()
        
        for _ in range(interval):
            if arena_stop:
                print("Stop requested during sleep")
                return
            sleep(1)    


#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/start/30 -Headers $headers

@app.post("/admin/start/{interval}")
def start_arena(request: Request, interval: int):
    _verify_admin(request)

    global arena_thread, arena_running

    if arena_running:
        return {"status": "already_running"}

    def _run():
        global arena_running, arena_stop
        arena_running = True
        arena_stop = False
        
        try:
            run_arena(interval, loop=True)  # your loop mode
        finally:
            arena_running = False

    arena_thread = threading.Thread(target=_run, daemon=True)
    arena_thread.start()

    return {"status": "arena_started"}


#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/stop-loop -Headers $headers

@app.post("/admin/stop-loop")
def stop_loop(request: Request):
    _verify_admin(request)
    
    global arena_stop, arena_running

    if not arena_running:
        return {"status": "not_running"}

    arena_stop = True
    return {"status": "stop_requested"}


#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/match/run_once -Headers $headers

@app.post("/admin/match/run_once")
def run_one_match(request: Request):
    _verify_admin(request)

    result = run_ai_arena()   # must return MatchResult dict
    return {"status": "match_completed", "result": result}


#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/match/run_batch/2 -Headers $headers

@app.post("/admin/match/run_batch/{run}")
def run_batch(request: Request, run: int):
    _verify_admin(request)

    results = []
    for _ in range(run):
        results.append(run_ai_arena())

    return {
        "status": "batch_completed",
        "matches": len(results),
        "results": results
    }


#router = APIRouter()
#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/restart -Headers $headers

def _restart():
    # Start new server
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "arena_admin_api:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8001",
        ],
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
    )

    # Stop current server
    os.kill(os.getpid(), signal.SIGINT)


@app.post("/admin/restart")
def restart(background_tasks: BackgroundTasks, request: Request):
    _verify_admin(request)
    
    background_tasks.add_task(_restart)
    return {"status": "restarting"}



#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod http://127.0.0.1:8001/admin/agents -Headers $headers

@app.get("/admin/agents")
def agent_status(request: Request):
    _verify_admin(request)
    registry = load_registry()

    agents_view = []

    for a in registry["agents"].values():
        if a.get("active"):
            state = "active"
        elif a.get("pending"):
            state = "pending"
        else:
            state = "suspended"

        agents_view.append({
            "id": a["id"],
            "name": a["name"],
            "state": state,
            "elo": a.get("elo", 1000),
            "matches_played": a.get("matches_played", 0),
            "last_played": a.get("last_played"),
            "owner": a.get("owner"),
        })

    return {
        "total": len(agents_view),
        "agents": agents_view
    }

#  Call locally from PowerShell
#  set token
#  $headers = @{ "X-Admin-Token" = "dev-secret" }
#  Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/set-baseline/groq_llama3_70b -Headers $headers

@app.post("/admin/set-baseline/{agent_id}")
def set_baseline(request: Request, agent_id: str):
    _verify_admin(request)
    registry = load_registry()

    if agent_id not in registry["agents"]:
        raise HTTPException(404, "Agent not found")

    old_baseline = registry.get("baseline_agent", None)

    registry["baseline_agent"] = []
        
    registry["baseline_agent"].append(agent_id)
    
    save_registry(registry)

    admin_log(
        action="baseline_update",
        agent_id=agent_id,
        details={"old_baseline" : old_baseline}
    )

    return {"status": "baseline_updated", "agent_id": agent_id}

#app.include_router(admin)



