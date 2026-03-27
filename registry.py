import os, json, psycopg2
from datetime import datetime, UTC
from utils import log_info
from qualification import qualify_pending_agents
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")

#REGISTRY_FILE = "agents_registry.json"

BASELINE_AGENT = "baseline_agent.json"

BASELINE_DEFAULT = {
  "agents": {
    "groq_llama3_70b": {
      "id": "groq_llama3_70b",
      "name": "LLaMA-3 70B (Groq)",
      "type": "groq",
      "model": "llama-3.3-70b-versatile",
      "api_key_env": "GROQ_API_KEY",
      "owner": "someonehereexists@gmail.com",
      "submitted_by": "internal",
      "pending": True
    },
    "groq_llama3_8b": {
      "id": "groq_llama3_8b",
      "name": "LLaMA-3 8B (Groq)",
      "type": "groq",
      "model": "llama-3.1-8b-instant",
      "api_key_env": "GROQ_API_KEY",
      "owner": "someonehereexists@gmail.com",
      "submitted_by": "internal",
      "pending": True
    }
  }
}

# ----------------------------
# Normalization
# ----------------------------

def normalize_agent(agent):
    now = datetime.now(UTC).isoformat()
    agent.setdefault("matches_played", 0)
    agent.setdefault("last_played", None)
    agent.setdefault("registeredOn", now)
    agent.setdefault("elo", 1000)
    agent.setdefault("aiq", 0.0)
    agent.setdefault("timeout", 5)

    agent.setdefault("qual", {
        "status": "pending",
        "score": 0.0,
        "reason": None,
        "last_run": None
    })
    
    agent.setdefault("health", {
        "status": "unknown",
        "last_check": None,
        "fail_count": 0,
        "last_error": None
    })
    
    agent.setdefault("active", False)
    agent.setdefault("pending", False)
    agent.setdefault("suspended", False)

    # Branding / ownership metadata (optional)
    agent.setdefault("owner", "external")
    agent.setdefault("submitted_by", "external")
    agent.setdefault("license", "evaluation-only")
    agent.setdefault("notes", "")
    agent.setdefault("suspend_reason", None)
    return agent

def normalize_registry(registry):

    registry.setdefault("platform", {})
    registry["platform"].setdefault("name", "AI Arena")
    registry["platform"].setdefault("brand", "SKKIPP")
    registry["platform"].setdefault("version", "1.0")
    registry["platform"].setdefault("aiq_owner", "someonehereexists@gmail.com")

    for id, agent in registry["agents"].items():
        agent = normalize_agent(agent)
        if not len(registry["baseline_agent"]):
            registry["baseline_agent"].append(id)
    
    return registry

def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS registry (
        id SERIAL PRIMARY KEY,
        data JSONB
    )
    """)

    cur.execute("SELECT COUNT(*) FROM registry")
    count = cur.fetchone()[0]

    if count == 0:
        baseline = BASELINE_DEFAULT
        registry = {"platform": {}, "baseline_agent": [], "agents": baseline["agents"]}
        normalize_registry(registry)

        cur.execute(
            "INSERT INTO registry (data) VALUES (%s)",
            [json.dumps(registry)]
        )

    conn.commit()
    cur.close()
    conn.close()

# ----------------------------
# Load / Save / Retrieve
# ----------------------------

def load_registry():
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT data FROM registry LIMIT 1")
        row = cur.fetchone()

        cur.close()
        conn.close()

        if row:
            return row["data"]

    except Exception as e:
        log_info(f"DB load failed: {e}")

    # fallback (first run)
    log_info("Initializing DB registry...")

    init_db()

    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT data FROM registry LIMIT 1")
    row = cur.fetchone()

    cur.close()
    conn.close()

    return row["data"]
  
#def load_registry():
#    try:
#        with open(REGISTRY_FILE) as f:
#            registry = json.load(f)
#    except Exception:
#        log_info(f"Registry not found")
#        log_info(f"Creating default registry...")
#        try:
#            with open(BASELINE_AGENT) as f:
#                baseline = json.load(f)
#        except Exception:
#            log_info(f"Baseline Agents not found")
#            log_info(f"Creating default baseline agents...")
#            baseline = BASELINE_DEFAULT
#             
#        baseline_agents = baseline.get("agents", {})
#
#        registry = {"platform":{}, "baseline_agent": [], "agents":baseline_agents}
#        normalize_registry(registry)
#        save_registry(registry)
#        qualify_pending_agents(registry)
#        save_registry(registry)
#   
#    return registry            

def save_registry(registry):
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            "UPDATE registry SET data = %s WHERE id = 1",
            [json.dumps(registry)]
        )

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        log_info(f"DB save failed: {e}")
      
#def save_registry(registry):
#    with open(REGISTRY_FILE, "w") as f:
#        json.dump(registry, f, indent=2)

def get_agent(registry, agent_id: str):
    return registry.get("agents", {}).get(agent_id)

def save_agent(registry, agent):
    registry["agents"][agent["id"]] = agent


def all_agents(registry):
    return registry.get("agents", {}).values()

# ----------------------------
# Updates
# ----------------------------

def update_registry_after_match(registry, builder):
    assert "agents" in registry, "Registry not normalized"

    now = datetime.now(UTC).isoformat()

    for a_id, b_agent in builder.agents.items():
        agent = find_agent(registry, agent_id=a_id)
    
        if not agent:
            # optional: log missing agent (should not happen)
            continue
    
        # --- matches played ---
        agent["matches_played"] = agent.get("matches_played", 0) + 1
        agent["last_played"] = now
    
        # --- stats accumulation ---
        b_stats = b_agent.get("stats", {})
        agent.setdefault("stats", {})
    
        agent["stats"]["timeouts"] = (
            agent["stats"].get("timeouts", 0) + b_stats.get("timeouts", 0)
        )
    
        agent["stats"]["failures"] = (
            agent["stats"].get("failures", 0) + b_stats.get("failures", 0)
        )
        
        if "health" in b_agent:
            update_health(agent, b_agent["health"]["success"], b_agent["health"]["error"])
        

def find_agent(registry, *, name=None, agent_id=None):
    if agent_id:
        return registry.get("agents", {}).get(agent_id)
    if name:    
        for agent in registry.get("agents", []).values():
            if agent.get("name") == name:
                return agent
    return None


def find_baseline_agent(registry):
#  (a for a in registry["agents"].values() if a.get("baseline")),
    return next(
        (a for a in registry["agents"].values() if a["id"] in registry["baseline_agent"]),
        None
    )

def update_health(agent, success: bool, error: str | None = None):
    h = agent["health"]
    h["last_check"] = datetime.now(UTC).isoformat()

    if success:
        h["status"] = "healthy"
        h["fail_count"] = 0
        h["last_error"] = None
        if agent.get("suspended"):
            agent["suspended"] = False
            agent["pending"] = True  # trigger requalify
    else:
        h["fail_count"] += 1
        h["last_error"] = error
        h["status"] = "failing"

        if h["fail_count"] >= 3:
            agent["suspended"] = True
            agent["active"] = False

            h["status"] = "suspended"   
