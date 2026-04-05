import json
from datetime import datetime, UTC
from registry import get_conn

AUDIT_FILE = "audit_log.jsonl"
ADMIN_LOG = "admin_log.jsonl"

#def log_audit(action: str, agent_id: str, details: dict | None = None):
#    record = {
#        "ts": datetime.now(UTC).isoformat(),
#        "action": action,
#        "agent_id": agent_id,
#        "details": details or {}
#    }
#
#    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
#        f.write(json.dumps(record) + "\n")
#        
#def admin_log(action: str, agent_id: str, details: dict | None = None):
#    record = {
#        "ts": datetime.now(UTC).isoformat(),
#        "action": action,
#        "agent_id": agent_id,
#        "details": details or {}
#    }

#    with open(ADMIN_LOG, "a", encoding="utf-8") as f:
#        f.write(json.dumps(record) + "\n")        

def log_audit(
    action: str,
    agent_id: str | None = None,
    details: dict | None = None,
    event_type: str = "AUDIT",
    status: str = "success",
    entity_type: str = "agent",
    message: str | None = None,
    trace_id: str | None = None,
):
    conn = get_conn()
    db = conn.cursor()
    record = {
        "event_type": event_type,
        "entity_type": "agent",
        "entity_id": agent_id,
        "action": action,
        "status": status,
        "message": None,
        "metadata": json.dumps(details or {}),
        "created_at": datetime.now(UTC)
    }

    db.execute(
        """
        INSERT INTO audit_logs 
        (event_type, entity_type, entity_id, action, status, message, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            record["event_type"],
            record["entity_type"],
            record["entity_id"],
            record["action"],
            record["status"],
            record["message"],
            record["metadata"],
            record["created_at"]
        )
    )
    conn.commit()
    db.close()
    conn.close()

def log_migrate():
    try:
        conn = get_conn()
        db = conn.cursor()
        with open(AUDIT_FILE) as f:
            for line in f:
                try:
                    record = json.loads(line)
                except:
                    continue
                db.execute(
                    """
                    INSERT INTO audit_logs 
                    (action, entity_id, metadata, event_type)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        record["action"],
                        record["agent_id"],
                        record["details"],
                        "AUDIT"
                    )
                )
#                log_audit(
#                    db,
#                    action=record["action"],
#                    agent_id=record["agent_id"],
#                    details=record["details"],
#                    event_type="AUDIT"
#                )
        audit_stat = "success"        
    except Exception as e:
        audit_stat = str(e)
        
    try:
        with open(ADMIN_LOG) as f:
            for line in f:
                try:
                    record = json.loads(line)
                except:
                    continue
                db.execute(
                    """
                    INSERT INTO audit_logs 
                    (action, entity_id, metadata, event_type)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        record["action"],
                        record["agent_id"],
                        record["details"],
                        "ADMIN"
                    )
                )
#                log_audit(
##                    db,
 #                   action=record["action"],
 #                   agent_id=record["agent_id"],
 #                   details=record["details"],
 #                   event_type="ADMIN"
 #               )                
        admin_stat = "success"        
    except Exception as e:
        admin_stat = str(e)
    
    conn.commit()
    db.close()
    conn.close()
    
    return{"audit": audit_stat, "admin": admin_stat}
