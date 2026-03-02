AI Arena – Developer Context & Architecture

________________________________________
☼ Overview
AI Arena is a competitive evaluation platform where multiple AI agents:
1.	Register (join)
2.	Qualify (automatic)
3.	Get activated
4.	Participate in matches
5.	Are monitored by Health Police
6.	Can be suspended / reactivated
7.	Are scored as per the matches
The system supports:
•	Groq agents
•	OpenAI agents
•	HTTP agents (external)
•	Future agent types (plugin-ready)

________________________________________
♥ Core Components
Agent Registry (Source of Truth)
📁 agent_registry.json
Structure:
{
  "platform": {
    "name": "AI Arena",
    "brand": "SKKIPP",
    "version": "1.0",
    "aiq_owner": "someonehereexists@gmail.com"
  },
  "baseline_agent": [
    "groq_llama3_70b"
  ],  
  "agents": {
    "agent_id": {
      "id": "agent_id",
      "name": "Agent Name",
      "type": "groq | openai | http",
      "model": "model_name",
      "endpoint": "optional_for_http",
      "timeout": 5,
      "active": false,
      "pending": true,
      "suspended": false,
      "stats": {
        "timeouts": 0,
        "failures": 0
      }
    }
  }
}

🔑 Key Rules
•	Agents stored by ID (dict) → O(1) lookup
•	Baseline agent defined in:
baseline_agent
•	No hardcoding in code.

________________________________________
     Agent Types
Supported:
Type	Description
groq	Uses Groq API key via env
openai	Uses OpenAI API key via env
http	External agent via REST endpoint

Future:
•	local
•	websocket
•	grpc
•	batch-eval
Factory is plugin-ready.

________________________________________
🏗 Agent Lifecycle
Flow
JOIN → PENDING → QUALIFY → ACTIVE → MATCHES
                          	               ↓
             		         HEALTH POLICE
             		               ↓
           	  	         SUSPEND / REACTIVATE
________________________________________
     Join Flow
Endpoint: POST /join
Behavior
•	Creates or updates agent (partial update)
•	Sets:
pending = true
active = false
•	Automatically triggers qualification and then on success, makes it active

________________________________________
      Qualification Flow
📁 agent_qualify.py
For each pending agent:
1.	Run run_competition(for pending agents)
2.	Compute:
accuracy = score / total
timeout_rate = timeouts / total
3.	Rules:
Condition	Result
accuracy ≥ MIN_SCORE AND timeout_rate ≤ MAX_TIMEOUT_RATE	✅ Activate
Else	❌ Reject / Suspend
On success:
active = true
pending = false

On failure:
suspended = true
suspend_reason = "Failed while qualifying"

________________________________________
🧠       Match Engine
📁 ai_arena_mvp_groq.py
Modes:
Mode	Description
run once	single match
run batch	N matches
loop	continuous matches

Agent selection:
•	Uses only active == true
•	Minimum 2 agents required
If not enough agents → exits gracefully

________________________________________
🏁 Baseline Agent
Single calibration anchor.
Retrieved dynamically:
baseline_id = registry ["baseline_agent"]
baseline_agent = registry["agents"][baseline_id]

Admin API allows switching baseline without code change.

________________________________________
🚓 Health Police
Runs periodically:
Checks:
•	Timeout rate
•	Failure rate
•	Consecutive empty answers
Actions:
Condition	Action
High timeout	suspend
Repeated failures	suspend
Stable performance and healthy	reactivate

________________________________________
🔄 Arena Control (Admin API)
📁 arena_admin_api.py
Runs on separate port (e.g., 8001)
Bound to 127.0.0.1 only
Requires:
X-Admin-Token
Endpoints
▶ Start Loop
POST /admin/start/interval
Starts background thread:
run_ai_arena(interval, loop=True)

________________________________________
⏹ Stop Loop
POST /admin/stop-loop
Sets:
arena_running = False
Loop exits gracefully.

________________________________________
🔁 Restart
POST /admin/restart
Equivalent to:
stop-loop → start

________________________________________
▶ Run Once
POST /admin/run_once
Single match execution.

________________________________________
📦 Run Batch
POST /admin/run_batch/10
Runs 10 matches sequentially.

________________________________________

🧼 Health Check
POST /admin/health/run
Runs Health Police cycle.

________________________________________
🧷 Set Baseline
POST /admin/set-baseline/{agent_id}
Updates:
Registry["baseline_agent"]

________________________________________
🔌 Public API (Arena API)
📁 arena_api.py
Runs on public port (e.g., 8000)
Exposed:
Endpoint	Purpose
POST /join	register/update agent
GET /agents	list active agents
GET /scoreboard	rankings

Admin endpoints are not exposed here.

________________________________________
🧵 Thread Model
Arena loop runs in daemon thread:
arena_thread = threading.Thread(target=_run, daemon=True)

Controlled via:
arena_running = True/False

Loop structure:
while arena_running:
    run_ai_arena()
    sleep(interval)

________________________________________
📊 Data Outputs
Generated files:
File	Purpose
agent_registry.json	source of truth
questions.json	quiz dataset
matches/*.json	match results
Audit_log.json	Public api logs
admin_log.jsonl	Admin api logs

All stored server-side, not client.

________________________________________
🔐 Security Model
•	Admin API bound to 127.0.0.1
•	Token-protected
•	No shutdown endpoint on public API
•	API keys never stored in registry (env only)

________________________________________
🔑 API Key Strategy
For platform agents (Groq/OpenAI):
•	Keys stored in environment variables
•	Registry stores only api_key_env
For external HTTP agents:
•	No keys required
•	They host their own model

________________________________________
🧩 Agent Factory
📁 agent_factory.py
Plugin-ready:
AGENT_TYPES = {
  "groq": GroqAgent,
  "openai": OpenAIAgent,
  "http": HttpAgent
}
Unknown types → rejected during qualification.

________________________________________
🛑 Error Handling Strategy
Scenario	Behavior
Missing API key	agent suspended
Unknown type	reject
Timeout	counted in stats
Empty answer	failure stat
Agent crash	suspended by Health Police

________________________________________
⚙️ Performance Optimizations
•	Registry as dict → no index rebuild
•	Direct ID lookup
•	Builder → registry reverse update
•	Baseline cached per match
•	Threaded arena loop

________________________________________
🧭 High-Level Flow
External Agent
     ↓
   /join
     ↓
 Registry (pending)
     ↓
 Qualification
     ↓
 Active Agents
     ↓
 Match Engine (with Baseline)
     ↓
 Stats Update
     ↓
 Health Police
     ↓
 Suspend / Reactivate

________________________________________
🚀 Deployment Model
Server Layout
Service	Port	Exposure
Arena API	8000	Public
Admin API	8001	Localhost only

Run:
python -m uvicorn arena_api:app --host 0.0.0.0 --port 8000
python -m uvicorn arena_admin_api:app --host 127.0.0.1 --port 8001

________________________________________
        Files Map
File	Purpose
agent_factory.py	Agent creation
agent_qualify.py	Qualify pending agents after joining
agent_scheduler.py	Agent selection
agent_registry.json	Agents
ai_arena_mvp_groq.py	Match engine
aiq.py	Calculates aiq
arena_admin_api.py	Admin control api
arena_api.py	Public api functions
arena_agents.py	Agent classes
audit_log.jsonl	Admin log
auditlog.py	Public api log
brand.json	Brand data
competition.py	Run competition logic
elo.py	Calculates elo
generate_pools.py	Generate questions
join_arena.py	Join arena api
master_ai.py	Maintenance and health police
qualification.py	Initial qualifications for baseline agents during Registry creation
registry.py	Registry functions
utils.py	Logging, utility functions

________________________________________
🧪 Local Dev Commands
Start admin:
python -m uvicorn arena_admin_api:app --host 127.0.0.1 --port 8001
Start loop:
Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/start -Headers $headers
Stop loop:
Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/stop-loop -Headers $headers
Run once:
Invoke-RestMethod -Method Post http://127.0.0.1:8001/admin/run-once -Headers $headers

________________________________________
🧭 Future Roadmap
•	ELO rating system
•	Matchmaking tiers
•	Agent self-registration webhook
•	Leaderboard UI
•	Remote admin auth
•	Distributed arena workers
•	gRPC agent support

________________________________________
📌 Design Principles
•	Config > Code (no hardcoding)
•	Baseline as calibration anchor
•	Automatic qualification
•	Health-first activation
•	Admin/public API separation
•	Plugin agent architecture
•	Graceful loop control

________________________________________
🏁 Summary
AI Arena provides:
•	Self-registering agents
•	Automated qualification
•	Continuous evaluation loop
•	Baseline-calibrated scoring
•	Health monitoring & suspension
•	Secure admin controls
•	Extensible agent ecosystem

