from registry import find_agent
from utils import log_info

DEFAULT_AIQ = 1000.0
SCALE = 100.0  # growth speed


def update_aiq(agent_id, score, max_score, difficulty, registry, stats=None):
    stats = stats or {}

    agent = find_agent(registry, agent_id=agent_id)
    if not agent:
        return

    accuracy = score / max(max_score, 1)

    # stats is now per-agent (not nested)
    timeouts = stats.get("timeouts", 0)
    failures = stats.get("failures", 0)

    reliability = 1.0 - min(
        0.5,
        (timeouts + failures) / max(max_score, 1)
    )

    difficulty_weight = {
        "easy": 1.0,
        "medium": 1.2,
        "hard": 1.5
    }.get(difficulty, 1.0)

    aiq_delta = SCALE * accuracy * reliability * difficulty_weight

    agent["aiq"] = agent.get("aiq", 0.0) + aiq_delta


def record_winner(winner, registry):
    if not winner:
        return

    agent = find_agent(registry, agent_id=next(iter(winner)))
    if not agent:
        return
        
    agent["wins"] = agent.get("wins", 0) + 1


def print_leaderboard(registry):
    agents = registry.get("agents", {}).values()

    print("\n")
    log_info("📊 AIQ LEADERBOARD")
    print("-" * 65)

    for agent in sorted(
        agents,
        key=lambda a: -a.get("aiq", 0.0)
    ):
        print(
            f"{agent['name']:<20} | "
            f"AIQ {agent.get('aiq', 0.0):7.2f} | "
            f"ELO {agent.get('elo', 1000):7.2f} | "
            f"Matches {agent.get('matches_played', 0):3d} | "
            f"Wins {agent.get('wins', 0):3d}"
        )

    print("-" * 65)
    print("\n")
