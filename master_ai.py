import json, os
from generate_pools import main as regenerate
from registry import load_registry, save_registry
from utils import log_info

TARGET = 30
TIMEOUT_LIMIT = 5
FAILURE_LIMIT = 5
LATENCY_LIMIT = 8000  # ms

def health_police():
    registry = load_registry()
    changed = False

    for agent in registry.get("agents", {}).values():  
        stats = agent.get("stats", {})
        health = agent.get("health", {})
        timeouts = stats.get("timeouts", 0)
        failures = stats.get("failures", 0)
        health_stat = health.get("status", "failing")
        avg_latency = stats.get("avg_latency_ms", 0)
        last_latency_ms = agent.get("last_latency_ms", 0) 

        # 🚫 Suspension rules
        if agent.get("active"):
            if (
                timeouts >= TIMEOUT_LIMIT
                or failures >= FAILURE_LIMIT
                or avg_latency >= LATENCY_LIMIT
                or last_latency_ms >= LATENCY_LIMIT
            ):
                agent["active"] = False
                agent["suspended"] = True
                log_info(f"🚫 Suspended agent: {agent['name']}")
                changed = True

        # ✅ Reactivation rules
        if agent.get("suspended"):
            if timeouts == 0 and failures == 0 and health_stat == "healthy":
                agent["active"] = True
                agent["suspended"] = False
                log_info(f"✅ Reactivated agent: {agent['name']}")
                changed = True

    if changed:
        save_registry(registry)


def maintain(case):
    for d in ["easy", "medium", "hard", "expert"]:
        path = f"pools/{d}.json"
        if not os.path.exists(path):
            continue
        pool = json.load(open(path))

        pool = [q for q in pool if q.get("quality", 1) >= 0.6]
        log_info(f"⚠️ 🛠 Checking Pool... {d}")
        if len(pool) < TARGET:
            log_info(f"🛠 Master AI topping up {d}")
            regenerate()

        json.dump(pool, open(path, "w"), indent=2)
    
    if case == "both":    
        log_info("🧹 Maintain: running health police")
        health_police()


if __name__ == "__main__":
    maintain()
