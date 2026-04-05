# agent.py
# this is the file needs to be cloned by agents to register themselve

import os
import time
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

# =====================
# CONFIG
# =====================

ARENA_URL = "https://ai-arena-benchmarking-platform-for.onrender.com/join"

AGENT_CONFIG = {
    "id": "auto_agent_1",
    "name": "Auto Agent 1",
    "type": "http",
    "endpoint": "http://localhost:8001/answer",  # update after deploy
    "model": "gpt-4o-mini",
    "timeout": 5
}

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# =====================
# REQUEST MODEL
# =====================

class QuestionRequest(BaseModel):
    question: str
    timeout: int | None = None


# =====================
# ANSWER ENDPOINT
# =====================

@app.post("/answer")
def answer(req: QuestionRequest):
    try:
        r = client.responses.create(
            model=AGENT_CONFIG["model"],
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a quiz contestant. "
                        "Answer ONLY the final answer. "
                        "No explanation. "
                        "1 to 4 words maximum."
                    )
                },
                {"role": "user", "content": req.question}
            ],
            timeout=AGENT_CONFIG["timeout"] - 1
        )

        ans = r.output_text.strip()

        # enforce arena rules
        ans = ans.split("\n")[0].strip()
        ans = " ".join(ans.split()[:4])

        return {"answer": ans}

    except Exception as e:
        print(f"❌ Answer error: {e}")
        return {"answer": ""}


# =====================
# AUTO REGISTER
# =====================

def register_with_retry():
    for i in range(5):
        try:
            res = requests.post(ARENA_URL, json=AGENT_CONFIG, timeout=5)
            if res.status_code == 200:
                print("✅ Registered")
                return
        except Exception as e:
            print(f"Retry {i+1} failed:", e)

        time.sleep(3)

    print("❌ Could not register")

# =====================
# STARTUP HOOK
# =====================

@app.on_event("startup")
def startup_event():
    # wait a bit so server is ready
    time.sleep(2)
    register_with_retry()
