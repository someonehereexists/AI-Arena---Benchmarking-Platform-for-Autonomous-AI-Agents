from arena_agents import GroqAgent, OpenAIAgent, HttpAgent
#from arena_agents import GroqAgent, OpenAIAgent
from registry import load_registry, save_registry, find_agent
from utils import log_info

def create_agent(agent_config):
    t = agent_config["type"]

    if t == "groq":
        return GroqAgent(agent_config)
    elif t == "openai":
        return OpenAIAgent(agent_config)
    elif t == "http":
        return HttpAgent(agent_config)
    else:
        raise ValueError(f"Unknown agent type: {t}")


def deactivate_agent(factory_failures):
    registry = load_registry()

    for cfg, error_msg in factory_failures:
        agent = find_agent(registry, agent_id=cfg["id"])
        if agent:
            agent["active"] = False
            agent["suspended"] = True
            agent.setdefault("suspend_reason", None)
            agent["suspend_reason"] = f"Factory error: {error_msg}"
            log_info(f"🚫 Suspended (factory): {agent['name']} → {error_msg}")

    save_registry(registry)
    
    