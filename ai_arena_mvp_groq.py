"""
AI ARENA – Master Orchestrator

This file is the ONLY place where:
- agents are selected
- competitions are run
- scores are updated
- registries are mutated

Everything else is a service.
"""
import random, os, json, uuid

from agent_scheduler import select_agents
from agent_factory import create_agent, deactivate_agent
from generate_pools import build_pool
from competition import run_competition, determine_winner, MatchResult, export_match, load_brand_meta, MatchBuilder
from aiq import update_aiq, record_winner, print_leaderboard
from registry import load_registry, save_registry, update_registry_after_match, find_baseline_agent
from utils import log_info
from master_ai import maintain
from elo import pairwise_elo_update
from datetime import datetime, UTC


# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

NUM_AGENTS = 2
DIFFICULTY = ["easy", "expert", "hard", "medium"]
ATTEMPTS = 100
    
# ---------------------------------------------------------
# MAIN ARENA FLOW
# ---------------------------------------------------------

def run_ai_arena(force_agents: list[str] | None = None):

    log_info("🏟️ AI ARENA STARTED")

    if os.getenv("ARENA_SEED"):
        random.seed(int(os.getenv("ARENA_SEED")))

    # -------------------------------------------------
    # 1️⃣ Select agents
    # -------------------------------------------------
    agents = []
    
    if force_agents:
        maintain("one")   # only questions pool
        difficulty = "easy"
        registry = load_registry()
        valid_agent_configs = [registry[force_agent]] 
        for cfg in valid_agent_configs:
            try:
                # try instantiating to validate type/support
                agent = create_agent(cfg)
                agents.append(agent)
                log_info(f"✅ Agent accepted for qualification run: {cfg['name']}")
            except Exception as e:
                log_info(f"🚫 Agent rejected: {cfg['name']} → {e}")
                return
    else:
        maintain("both")    # questions pool and agents registry health police
        difficulty = random.choice(DIFFICULTY)

        valid_agent_configs = []

        saved_ids = set()
        attmps = 0  
        while len(valid_agent_configs) < NUM_AGENTS and attmps < ATTEMPTS: 
            attmps += 1 
            agent_configs = select_agents(NUM_AGENTS)  # get two at a time
            log_info(f"ATTEMPT [{attmps}]: ")

            if not agent_configs:
                break  # no more agents in scheduler
                
            log_info(f"Analyzing agents: {[a['name'] for a in agent_configs]}")
        
            for cfg in agent_configs:
                if cfg["id"] in saved_ids:
                    continue
                
                if len(valid_agent_configs) == NUM_AGENTS:
                    break
                factory_failures = []    
                try:
                    # try instantiating to validate type/support
                    agent = create_agent(cfg)
                    agents.append(agent)
                    valid_agent_configs.append(cfg)
                    log_info(f"✅ Agent accepted: {cfg['name']}")
                    saved_ids.add(cfg["id"])
                except Exception as e:
                    log_info(f"🚫 Agent rejected: {cfg['name']} → {e}")
                    factory_failures.append((cfg, str(e)))
                    deactivate_agent(factory_failures)
        
        # ❌ Not enough agents → exit arena
        if len(valid_agent_configs) < 2:
            log_info("❌ Not enough valid agents to run match. Exiting.")
            global arena_stop, arena_running
            if arena_running:
                print("ARENA loop is running, stopping as no sufficient agents")
                arena_stop = True
                
            return
        
    log_info(f"Selected agents: {[a['name'] for a in valid_agent_configs]}")
        
    # -------------------------------------------------
    # 2️⃣ Load questions
    # -------------------------------------------------
    
    log_info(f"🛠Selected Difficulty: {difficulty}")

    # -------------------------------------------------
    # 3️⃣ Create Match Builder
    # -------------------------------------------------
    builder = MatchBuilder(
        match_id=str(uuid.uuid4()),
        difficulty=difficulty,
        timestamp=datetime.now(UTC).isoformat()
    )

    for cfg in valid_agent_configs:
        a_id = cfg["id"]
        builder.ensure_agent(a_id)
        builder.agents[a_id]["name"] = cfg["name"]
    
        builder.agents[a_id]["platform"] = {
            "type": cfg.get("type"),
            "model": cfg.get("model"),
        }

    # convert agents to callable map
    agent_fns = {agent.id: agent.answer for agent in agents}

    # -------------------------------------------------
    # 4️⃣ Run competition → populates builder
    # -------------------------------------------------
    run_competition(
        agents=agent_fns,
        builder=builder
    )

    if not force_agents:
        # -------------------------------------------------
        # 5️⃣ Determine winner → stored in builder
        # -------------------------------------------------
        win_stat = determine_winner(builder)
        builder.set_win_stat(win_stat)
    
        if win_stat.is_draw:
            log_info("*** Draw ***")
        else:
            log_info(f"*** Winner *** {win_stat.winner}")
            
        
        # -------------------------------------------------
        # 6️⃣ Load registry
        # -------------------------------------------------
        registry = load_registry()

    # -------------------------------------------------
    # 7️⃣ Update AIQ (uses builder)
    # -------------------------------------------------
    for agent_id in builder.agents:
        update_aiq(
            agent_id=agent_id,
            score=builder.agents[agent_id]["score"],
            max_score=len(builder.questions),
            difficulty=builder.difficulty,
            registry=registry,
            stats={agent_id: builder.agents[agent_id]["stats"]}
        )

    if not force_agents:
        record_winner(win_stat.winner, registry)
    
        # -------------------------------------------------
        # 8️⃣ Update ELO (mutates registry + builder elo block)
        # -------------------------------------------------
        pairwise_elo_update(registry, builder)

    # -------------------------------------------------
    # 9️⃣ Update registry participation stats
    # -------------------------------------------------
    update_registry_after_match(registry, builder)

    save_registry(registry)

    if not force_agents:
        print_leaderboard(registry)

    # -------------------------------------------------
    # 🔟 Export Match Result
    # -------------------------------------------------
    brand_meta = load_brand_meta()
    match_result = MatchResult.from_builder(builder, brand_meta)


    export_match(match_result.to_dict())

    log_info("✅ AI ARENA COMPLETED\n")
    
    if force_agents:
        # --- Build lightweight return payload for runner / qualification ---
        return_payload = {
            "match_id": builder.match_id,
            "difficulty": builder.difficulty,
            "total_questions": len(builder.questions),
            "agents": {},
        }
        for a_id, data in builder.agents.items():
            stats = data["stats"]
    
            return_payload["agents"][a_id] = {
                "score": data["score"],
                "accuracy": (
                    data["score"] / max(len(builder.questions), 1)
                ),
                "timeouts": stats["timeouts"],
                "failures": stats["failures"],
                "attempts": stats["attempts"],
            }
        return return_payload
    else:
        return match_result    


# ---------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------

if __name__ == "__main__":
    run_ai_arena()
