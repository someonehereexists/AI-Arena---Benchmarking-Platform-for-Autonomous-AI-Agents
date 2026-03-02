#Add New Agents to registry
import json, uuid
from registry import load_registry, save_registry, normalize_agent, find_agent
from datetime import datetime, UTC


REQUIRED_FIELDS = ["id", "name", "type", "model", "api_key_env"]

def validate_agent(new_agent):
    for f in REQUIRED_FIELDS:
        if f not in new_agent:
            raise ValueError(f"Missing field: {f}")


REGISTRY_FILE = "agents_registry.json"

def join_arena(
    name: str,
    endpoint: str,
    agent_type: str = "http",
    model: str | None = None,
    timeout: int = 5,
    owner: str = "external",
    license: str = "None",
):
    if agent_type in ["groq", "openai"]:
        raise ValueError(
            "External agents must use type='http'. "
            "Groq/OpenAI types are reserved for internal agents."
        )

    if agent_type not in ["http"]:
        raise ValueError(
            "External agents must use type='http'. "
        )

    registry = load_registry()
    
    existing = None

#    if agent_id:
#        existing = find_agent(registry, agent_id=agent_id)
         
    if existing:
        raise ValueError(
            "Agent already exists, use update service to update."
        )
        
    # 🔁 CREATE FLOW
    # --- Generate ID if missing ---
    agent_id = str(uuid.uuid4())
#    agent_id = agent_id or str(uuid.uuid4())
    
    
    # --- Create agent entry ---
    new_agent = {
        "id": agent_id,
        "name": name,
        "type": agent_type,
        "model": model,
        "endpoint": endpoint,
        "active": False,
        "pending": True,
        "owner": owner,
        "license": license,
        "submitted_by": "external",
        "matches_played": 0,
        "elo": 1000,
        "aiq": 0.0,
    }
    
    normalize_agent(new_agent)

    registry["agents"][agent_id] = new_agent
    
    msg = "Agent created. Submitted for qualification."
        
    save_registry(registry)

    return {
        "status": "pending",
        "agent_id": agent_id,
        "message": msg
    }
    
def update_agent(
    name: str | None = None,
    endpoint: str | None = None,
    agent_id: str | None = None,
    type: str | None = None,
    model: str | None = None,
    timeout: int | None = None,
    owner: str | None = None,
    license: str | None = None,
):
    if type in ["groq", "openai"]:
        raise ValueError(
            "External agents must use type='http'. "
            "Groq/OpenAI types are reserved for internal agents."
        )

    if type is not None and type not in ["http"]:
        raise ValueError(
            "External agents must use type='http'. "
        )

    registry = load_registry()
    
    existing = None

    if agent_id:
        existing = find_agent(registry, agent_id=agent_id)
    else:
        raise ValueError("id is required to update the details")
         
    if not existing:
        raise ValueError(f"Agent not found: {agent_id}")

    if agent_id in registry["baseline_agent"]:
        raise ValueError(f"Can't change baseline agent")

#    if existing.get("baseline", False):
#        raise ValueError(f"Can't change baseline agent")
    
    requal = False
    
    # 🔁 UPDATE FLOW
    if name is not None:
        existing["name"] = name
    if endpoint is not None:
        if endpoint != existing["endpoint"]:
            requal = True
        existing["endpoint"] = endpoint
    if model is not None:
        if model != existing["model"]:
            requal = True
        existing["model"] = model
    if type is not None:
        if type != existing["type"]:
            requal = True
        existing["type"] = type
    if owner is not None:
        existing["owner"] = owner
    if license is not None:
        existing["license"] = license
    if timeout is not None:
        existing["timeout"] = timeout
    if not existing["active"]:
        requal = True
        
    existing["last_updated"] = datetime.now(UTC).isoformat()
    
    if requal:
        existing["pending"] = True
        existing["active"] = False
        existing["suspended"] = False
        msg = "🔄 Agent details updated. Re-qualification required."
    else:    
        msg = "🔄 Agent details updated"

    print(f"Updated Agent id: {existing['id']}")
    
    save_registry(registry)

    return {
        "update":{
          "status": "updated",
          "agent_id": agent_id,
          "message": msg,
          "requal" : requal
        }  
    }
    

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Join AI Arena")
    parser.add_argument("--name", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--type", default="http")
    parser.add_argument("--model", default=None)
    parser.add_argument("--owner", default="external")

    args = parser.parse_args()
    #validate_agent(new_agent)
    result = join_arena(
        name=args.name,
        endpoint=args.endpoint,
        agent_type=args.type,
        model=args.model,
        owner=args.owner,
    )

    print("✅ Agent submitted for qualification")
    print(result)
