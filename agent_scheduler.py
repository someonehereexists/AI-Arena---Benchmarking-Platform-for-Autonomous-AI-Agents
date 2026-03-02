import json
import random
from datetime import datetime, timedelta, UTC

REGISTRY_FILE = "agents_registry.json"

def load_agents():
    with open(REGISTRY_FILE) as f:
        return json.load(f)["agents"].values()


def compute_weight(agent):
    """
    Higher weight = more likely to be selected
    """

    # Base weight
    weight = 1.0

    # Prefer agents with fewer matches
    matches = agent.get("matches_played", 0)
    weight *= max(1.0, 10.0 - matches)

    # Prefer agents not played recently
    last_played = agent.get("last_played")
    if last_played:
        try:
            last_time = datetime.fromisoformat(last_played)
            hours_ago = (datetime.now(UTC) - last_time).total_seconds() / 3600
            weight *= min(5.0, max(1.0, hours_ago / 6))
        except Exception:
            # Bad timestamp should never kill scheduling
            pass

    # Slight randomness to avoid lock-in
    return weight
    
def select_agents(n=2):
    agents = [
        a for a in load_agents()
            if a.get("active") and not a.get("pending")
    ]

    if len(agents) < n:
        raise ValueError(
            f"Not enough eligible agents: required={n}, available={len(agents)}"
        )

    weights = [compute_weight(a) for a in agents]

    selected = []
    attempts = 0

    while len(selected) < n and attempts < 10 * n:
        pick = random.choices(agents, weights=weights, k=1)[0]
        if pick["id"] not in {a["id"] for a in selected}:
            selected.append(pick)
        attempts += 1

    if len(selected) < n:
        raise RuntimeError("Failed to select unique agents")

    return selected
