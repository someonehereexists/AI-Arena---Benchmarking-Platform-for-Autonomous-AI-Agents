# Qualify pending Agents
import uuid
from utils import log_info
from competition import run_competition, determine_winner, MatchResult, export_match, load_brand_meta, MatchBuilder
from datetime import datetime, UTC
from arena_agents import GroqAgent, OpenAIAgent, HttpAgent



MIN_SCORE = 0.5   # 50%
MAX_TIMEOUT_RATE = 0.3

def pending_agents(registry):
    return [a for a in registry["agents"].values() if a.get("pending")]

def qualify_pending_agents(registry):
    
    result_summary = {}

    pending = pending_agents(registry)   #agent_configs

    if not pending:
        return

    from agent_factory import create_agent
    
    builder = MatchBuilder(
        match_id=str(uuid.uuid4()),
        difficulty="easy",
        timestamp=datetime.now(UTC).isoformat()
    )
    
    agent_fns = {}
    
    for cfg in pending:
        try:
            # try instantiating to validate type/support
            agent = create_agent(cfg)
            a_id = cfg["id"]
            builder.ensure_agent(a_id)
            builder.agents[a_id]["name"] = cfg["name"]
            builder.agents[a_id]["platform"] = {
                "type": cfg.get("type"),
                "model": cfg.get("model"),
            }
            agent_fns[agent.id] = agent.answer
            log_info(f"🚫 Agent accepted for qualification: {cfg['name']}")
            
        except Exception as e:
            log_info(f"🚫 Agent rejected: {cfg['name']} → {e}")
    

    if len(agent_fns):
        run_competition(
            agents=agent_fns,
            builder=builder
        )
    
    
    result_summary = {}
    for a_id, b_agent in builder.agents.items():
    
        log_info(f"🧪 Analyzing result for {b_agent['name']}, {a_id}")
        agent = registry.get("agents", {}).get(a_id)

        if not agent:
            # optional: log missing agent (should not happen)
            continue
        
        score = b_agent["score"]
        total = len(builder.questions)
        b_stats = b_agent.get("stats", {})
        timeouts = b_stats.get("timeouts", 0)
        accuracy = score / max(total,1)
        timeout_rate = timeouts / max(total, 1)
        
        if accuracy >= MIN_SCORE and timeout_rate <= MAX_TIMEOUT_RATE:
            agent["active"] = True
            agent["pending"] = False
            agent["qual"]["status"] = "passed"
            agent["qual"]["reason"] = None
            log_info(f"✅ ****** {agent['name']} qualified")
            result_summary[agent["name"]] = "qualified"
        else:
            log_info(f"❌ ****** {agent['name']} rejected")
            result_summary[agent["name"]] = "rejected"


        print("---------------------------")    
    print(result_summary)

#if __name__ == "__main__":
#    qualify_pending_agents()
