import random, os, json, uuid
from registry import load_registry, save_registry, find_agent, find_baseline_agent
from agent_factory import create_agent
#from competition import run_competition, determine_winner
from competition import run_competition, determine_winner, MatchResult, export_match, load_brand_meta, MatchBuilder
from utils import log_info
from datetime import datetime, UTC
from auditlog import log_audit


#BASELINE_AGENT_ID = "groq_llama3_70b"
QUALIFY_ROUNDS = 5
QUALIFY_MIN_SCORE = 0.5


def qualify_agent(agent_id: str):
    registry = load_registry()

    candidate = find_agent(registry, agent_id=agent_id)
    if not candidate:
        return {"status": "error", "message": "Agent not found"}

    if not candidate.get("pending"):
        details = {"status": "skipped", "message": "Agent not pending"}
        log_audit(
            action="qualification",
            agent_id=agent_id,
            details=details
        )
        return details

    baseline = find_baseline_agent(registry)
        
    if baseline is None:
        details = {"status": "error", "message": "Baseline agent missing"}
        log_audit(
            action="qualification",
            agent_id=agent_id,
            details=details
        )
        return details

    log_info(f"🎯 Qualification started for {candidate['name']}")

    agents_cfg = [candidate, baseline]

    agents = [create_agent(cfg) for cfg in agents_cfg]

    agent_fns = {a.id: a.answer for a in agents}

    # -------------------------------------------------
    # Create Match Builder
    # -------------------------------------------------
    builder = MatchBuilder(
        match_id=str(uuid.uuid4()),
        difficulty="easy",
        timestamp=datetime.now(UTC).isoformat()
    )

    for cfg in agents_cfg:
        a_id = cfg["id"]
        builder.ensure_agent(a_id)
        builder.agents[a_id]["name"] = cfg["name"]

        builder.agents[a_id]["platform"] = {
            "type": cfg.get("type"),
            "model": cfg.get("model"),
        }


    run_competition(
        agents=agent_fns,
        builder=builder
    )

    name = candidate["name"]
    qual = {"name": name}

    if "last_error" not in candidate:
        score = builder.agents[agent_id]["score"]
        accuracy = score / QUALIFY_ROUNDS
        candidate["qual"]["score"] = score
        
        if accuracy >= QUALIFY_MIN_SCORE:
            candidate["active"] = True
            candidate["pending"] = False
            status = "passed"
            log_info(f"✅ {candidate['name']} QUALIFIED ({accuracy:.2f})")
            candidate["qual"]["status"] = "passed"
            candidate["qual"]["reason"] = None
        else:
            status = "failed"
            log_info(f"❌ {candidate['name']} FAILED ({accuracy:.2f})")
            candidate["qual"]["status"] = "failed"
            candidate["active"] = False
            candidate["pending"] = True
            candidate["qual"]["reason"] = "failed while qualifying"
            
        qual["status"] = status
        qual["accuracy"] = accuracy
        qual["score"] = score
    else:
        log_info(f"❌ {candidate['name']} SUSPENDED")
        candidate["suspended"] = True
        candidate["active"] = False
        candidate["pending"] = False
        candidate["suspend_reason"] = "Failed while qualifying"
        status = "suspended"
        candidate["qual"]["status"] = status
        qual["status"] = status
    
    candidate["qual"]["last_run"] = datetime.now(UTC).isoformat()
    if "last_error" in candidate:
        qual["error"] = candidate["last_error"]
        candidate["qual"]["reason"] = candidate["last_error"]
    
    details = {"status": status}
    if "last_error" in candidate:
        details["reason"] = candidate["last_error"]
    
    log_audit(
        action="qualification",
        agent_id=agent_id,
        details=details
    )
        
    save_registry(registry)

    return qual
    
