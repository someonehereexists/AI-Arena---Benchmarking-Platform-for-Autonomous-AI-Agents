import json, random, uuid, os
from utils import normalize
from utils import log_info
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
#from registry import update_health
#import uuid

MATCH_DIR = "matches"
BRAND_DATA = f"brand.json"
POOL_PATH = f"pools/"
ROUNDS = 5

@dataclass
class WinStat:
    winner: dict
    scores: dict
    is_draw: bool
    
    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class BrandMeta:
    name: str
    owner: str
    website: Optional[str] = None
    contact: Optional[str] = None
    license: Optional[str] = None
    arena_version: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class EloData:
    before: float | None = None
    after: float | None = None
    delta: float | None = None


@dataclass
class PlatformInfo:
    type: str | None = None
    model: str | None = None


@dataclass
class AgentMatchData:
    name: str
    score: float = 0.0
    avg_latency_ms: float | None = None
    platform: PlatformInfo | None = None
    elo: EloData | None = None

    def to_dict(self):
        data = asdict(self)

        # remove None blocks for clean JSON
        if self.platform is None:
            data.pop("platform")

        if self.elo is None:
            data.pop("elo")

        return data


@dataclass
class MatchResult:
    match_id: str
    timestamp: str
    win_stat: WinStat
    questions: list[str]
    difficulty: str

    agents: list[AgentMatchData]

    createdBy: BrandMeta | dict

    @classmethod
    def from_builder(cls, builder: "MatchBuilder", brand_meta):
        agents_list = []

        for name, data in builder.agents.items():
            agents_list.append({
                "name": name,
                "score": data["score"],
                "avg_latency_ms": data["avg_latency_ms"],
                "stats": data["stats"],
                "platform": data["platform"],
                "elo": data["elo"],
                "responses": data["responses"],
            })

        return cls(
            match_id=builder.match_id,
            timestamp=builder.timestamp,
            difficulty=builder.difficulty,
            questions=builder.questions,
            agents=agents_list,
            win_stat=builder.win_stat,
            createdBy=brand_meta,
        )

    def to_dict(self) -> dict:
        data = asdict(self)

        if isinstance(self.win_stat, dict):
            data["win_stat"] = self.win_stat.to_dict()

        if isinstance(self.createdBy, dict):
            data["createdBy"] = self.createdBy
        else:
            data["createdBy"] = self.createdBy.to_dict()

        return data


@dataclass
class MatchBuilder:
    match_id: str
    timestamp: str
    difficulty: str

    questions: list = None
    agents: dict = None
    createdBy: dict | None = None
    win_stat: WinStat | None = None

    def __post_init__(self):
        self.questions = []
        self.agents = {}

    def ensure_agent(self, agent_id: str):
        if agent_id not in self.agents:
            self.agents[agent_id] = {
                "name": str,
                "score": 0.0,
                "latency_sum": 0,
                "avg_latency_ms": 0.0,
                "responses": [],
                "stats": {
                    "attempts": 0,
                    "timeouts": 0,
                    "failures": 0,
                    "correct": 0,
                    "partial": 0,
                    "wrong": 0,
                },
                "platform": None,
                "elo": {"before": None, "after": None, "delta": None},
            }

    def finalize_latencies(self):
        for a in self.agents.values():
            attempts = a["stats"]["attempts"]
            a["avg_latency_ms"] = (
                a["latency_sum"] / attempts if attempts else 0
            )
            
            
    def set_win_stat(self, win_stat: WinStat):
        self.win_stat = win_stat

        

def score(agent, correct, aliases):
    if not agent or not agent.strip():
        return 0.0

    a = normalize(agent)
    c = normalize(correct)

    if a == c:
        return 1.0
    if a in [normalize(x) for x in aliases]:
        return 0.9
    if c in a or a in c:
        return 0.7
    return 0.0


def load_pool(diff):
    return json.load(open(f"pools/{diff}.json"))

def run_competition(agents, builder):

    pool = json.load(open(POOL_PATH+builder.difficulty+".json"))
    log_info(f"📦 Loaded {len(pool)} questions from {builder.difficulty} pool")

    if not pool:
        raise RuntimeError("Question pool empty")

    questions = random.sample(pool, k=min(ROUNDS, len(pool)))

    for i, q in enumerate(questions, start=1):
        q_text = q["question"]
        q_correct = q["correct_answer"]
        q_aliases = q.get("aliases", [])

        log_info(f"🧠 Question {i}/{len(questions)}: {q_text}")

        builder.questions.append({
            "id": i,
            "question": q_text,
            "correct_answer": q_correct
        })

        for agent_id, fn in agents.items():
            agent = builder.agents[agent_id]
            name = agent["name"]
            stats = agent["stats"]

            stats["attempts"] += 1

            raw_answer = ""
            norm_answer = ""
            s = 0.0
            latency = 0
            status = "error"
            is_correct = False

            try:
                result = fn(q_text)
            except Exception as e:
                log_info(f"⚠️ {name} exception: {e}")
                stats["failures"] += 1
                result = {}
                success = False
                err_msg = str(e)
            except ValueError as ve:
                log_info(f"⚠️ {name} Value Error: {ve}")
                
            if not isinstance(result, dict):
                log_info(f"⚠️ Invalid response from {name}")
                stats["failures"] += 1
                success = False
                err_msg = "Invalid json response"
                
            else:
                status = result.get("status", "error").lower()
                latency = result.get("latency_ms", 0)

                if status == "timeout":
                    stats["timeouts"] += 1
                    success = False
                    err_msg = "timeout"

                elif status == "error":
                    stats["failures"] += 1
                    success = False
                    err_msg = result.get("error", "error received")

                else:
                    raw_answer = result.get("answer", "").strip()

                    if raw_answer:
                        s = score(raw_answer, q_correct, q_aliases)
                        norm_answer = normalize(raw_answer)
                        success = True
                        err_msg = None

                        if s == 1.0:
                            stats["correct"] += 1
                            is_correct = True
                        elif s > 0:
                            stats["partial"] += 1
                        else:
                            stats["wrong"] += 1
                    else:
                        stats["wrong"] += 1
                        success = False
                        err_msg = "empty answer"

            # aggregate into builder
            agent["score"] += s
            agent["latency_sum"] += latency

            agent["responses"].append({
                "question_id": i,
                "answer": raw_answer,
                "normalized_answer": norm_answer,
                "correct": is_correct,
                "score": s,
                "latency_ms": latency,
                "status": status
            })
            if "health" not in agent:
                agent["health"] = {}
                
            agent["health"]["success"] = success
            agent["health"]["error"] = err_msg
#            print("agent with health", agent)
            
            log_info(f"{name}: {raw_answer} ({latency}ms) → {s}")

    builder.finalize_latencies()

    # leaderboard log
    log_info("🏆 MATCH - LEADERBOARD")
    for agent_id, a in sorted(builder.agents.items(), key=lambda x: -x[1]["score"]):
        print(f"                        id: {agent_id}, name: {a['name']} - {round(a['score'], 2)}")



def determine_winner(builder) -> WinStat:
    top_score = 0
    scores = {}
    top_agents = {}
    for a_id, a in builder.agents.items():
        if a["score"] > top_score and a["score"] > 0:
            top_score = a["score"]
            top_agents.clear()
            top_agents[a_id] = a["name"]
        elif a["score"] == top_score and a["score"] > 0:
            top_agents[a_id] = a["name"]
            
        scores[a_id] = {a["name"]: a["score"]}   
 
    if not scores:
        raise ValueError("No scores found")

    is_draw = len(top_agents) > 1
    winner = None if is_draw else top_agents
    
    return WinStat(
        winner=winner,
        scores=scores,
        is_draw=is_draw,
    )


def export_match(match_result: dict):
    date = match_result["timestamp"][:10]

    path = os.path.join(MATCH_DIR, date)
    os.makedirs(path, exist_ok=True)

    filename = f'match_{match_result["match_id"]}.json'
    filepath = os.path.join(path, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(match_result, f, indent=2)

    return filepath


def load_brand_meta(path=BRAND_DATA) -> BrandMeta:
    with open(path, "r") as f:
        data = json.load(f)

    return BrandMeta(**data)


from datetime import datetime
import uuid

def build_match_result(
    *,
    task,
    scores,
    stats,
    agent_snapshots,
    aiq_deltas,
    elo_deltas,
    platform
):
    match_id = str(uuid.uuid4())

    return {
        "match_id": match_id,
        "timestamp": datetime.now(UTC).isoformat() + "Z",

        "platform": platform,
        "task": task,

        "agents": agent_snapshots,

        "scores": scores,
        "stats": stats,

        "rating_updates": {
            "aiq": aiq_deltas,
            "elo": elo_deltas
        }
    }

