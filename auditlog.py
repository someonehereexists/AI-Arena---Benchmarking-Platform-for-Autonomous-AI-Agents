import json
from datetime import datetime, UTC

AUDIT_FILE = "audit_log.jsonl"
ADMIN_LOG = "admin_log.jsonl"

def log_audit(action: str, agent_id: str, details: dict | None = None):
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "action": action,
        "agent_id": agent_id,
        "details": details or {}
    }

    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
        
def admin_log(action: str, agent_id: str, details: dict | None = None):
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "action": action,
        "agent_id": agent_id,
        "details": details or {}
    }

    with open(ADMIN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")        