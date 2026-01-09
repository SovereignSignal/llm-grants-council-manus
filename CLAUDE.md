# Grants Council - Technical Documentation

This document provides technical guidance for AI assistants and developers working on the Grants Council codebase.

## Project Overview

Grants Council is an agentic multi-LLM system for evaluating grant applications. Four specialized AI agents evaluate each application in parallel, deliberate on their findings, and produce recommendations that can be auto-executed or routed to human reviewers.

## Project Structure

```
llm-grants-council-manus/
├── backend/
│   ├── __init__.py          # Package initialization
│   ├── config.py            # Configuration, agent definitions, thresholds
│   ├── models.py            # Data models (Application, Decision, etc.)
│   ├── llm_client.py        # OpenRouter API client (OpenAI-compatible)
│   ├── storage.py           # JSON-based file persistence
│   ├── parser.py            # Application parsing (freeform & structured)
│   ├── agents.py            # Agent evaluation logic and prompt building
│   ├── council.py           # Deliberation, voting, and decision orchestration
│   ├── learning.py          # Observation generation from outcomes/overrides
│   └── main.py              # FastAPI application and all API endpoints
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main application component with state management
│   │   ├── api.js           # API client for backend communication
│   │   └── components/
│   │       ├── Sidebar.jsx      # Conversation list sidebar
│   │       ├── ChatInterface.jsx # Main evaluation chat UI
│   │       ├── Stage1.jsx       # Parsing stage display
│   │       ├── Stage2.jsx       # Agent evaluation display
│   │       └── Stage3.jsx       # Decision/synthesis display
│   ├── package.json         # React 19, Vite 7, react-markdown
│   └── vite.config.js       # Vite configuration
├── data/                    # Runtime data storage (created automatically)
│   ├── applications/        # Application JSON files
│   ├── evaluations/         # Decision JSON files
│   ├── observations/        # Agent observation files
│   ├── teams/               # Team profile files
│   └── conversations/       # UI conversation history
├── .env.example             # Environment variable template
├── requirements.txt         # Python dependencies
├── start.sh                 # Development startup script
├── test_backend.py          # Backend test suite
└── README.md                # User-facing documentation
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- OpenRouter API key (https://openrouter.ai/keys)

### Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# 3. Install frontend dependencies
cd frontend && npm install && cd ..

# 4. Start both servers
./start.sh
```

### Manual Startup

```bash
# Backend (from project root)
python3 -m uvicorn backend.main:app --reload --port 8001

# Frontend (in separate terminal)
cd frontend && npm run dev
```

### Access Points
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs (Swagger UI)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for LLM access |
| `DATABASE_URL` | No | Database connection (default: SQLite) |
| `VECTOR_DB_PATH` | No | Path for vector store (future use) |

## Core Components

### 1. Configuration (`config.py`)

Defines the four council agents:

| Agent ID | Name | Focus |
|----------|------|-------|
| `technical` | Technical Feasibility Agent | Can this be built? Timeline realistic? |
| `ecosystem` | Ecosystem Fit Agent | Aligns with program goals? Fills a gap? |
| `budget` | Budget Reasonableness Agent | Cost justified? Comparable to similar projects? |
| `impact` | Impact Assessment Agent | Lasting value? Measurable outcomes? |

Key thresholds:
```python
AUTO_APPROVE_THRESHOLD = 0.85   # Score needed for auto-approval
AUTO_REJECT_THRESHOLD = 0.15   # Score below which auto-reject
BUDGET_REVIEW_THRESHOLD = 50000 # USD amount requiring human review
MAX_DELIBERATION_ROUNDS = 2    # Maximum deliberation iterations
POSITION_CHANGE_THRESHOLD = 0.15 # Minimum score change for revision
```

All agents use `openai/gpt-4o-mini` via OpenRouter by default.

### 2. Data Models (`models.py`)

Core dataclasses with `to_dict()` serialization:

- **Application**: Grant application with team info, milestones, budget
- **AgentEvaluation**: Single agent's evaluation with score, recommendation, rationale
- **CouncilDecision**: Aggregated decision with evaluations, synthesis, feedback
- **Observation**: Learned pattern from an agent
- **TeamProfile**: Applicant team with history across applications

Key enums:
- `ApplicationStatus`: pending, evaluating, deliberating, auto_approved, auto_rejected, needs_review, approved, rejected
- `Recommendation`: approve, reject, needs_review
- `ObservationStatus`: draft, reviewed, active, deprecated

### 3. LLM Client (`llm_client.py`)

Async client using OpenAI SDK with OpenRouter base URL:

```python
# Single model query
await query_model(model, messages, temperature=0.7, json_mode=False)

# Parallel queries to multiple agents
await query_models_parallel(models_with_messages, temperature=0.7, json_mode=True)

# Query with JSON schema enforcement
await query_with_structured_output(model, messages, output_schema, temperature=0.7)
```

### 4. Storage (`storage.py`)

JSON file-based persistence in `data/` directory:

```python
# Applications
save_application(application) -> str
get_application(application_id) -> Optional[Application]
list_applications(status=None, program_id=None, limit=100)

# Decisions
save_decision(decision) -> str
get_decision(decision_id) -> Optional[CouncilDecision]
get_decision_for_application(application_id) -> Optional[CouncilDecision]
list_decisions(requires_review=None, limit=100)

# Observations
save_observation(observation) -> str
get_observation(observation_id) -> Optional[Observation]
get_observations_for_agent(agent_id, tags=None, status=ACTIVE, limit=10)
list_all_observations(agent_id=None, status=None)

# Teams
save_team(team) -> str
get_team(team_id) -> Optional[TeamProfile]
find_team_by_name(name) -> Optional[TeamProfile]
find_team_by_wallet(wallet_address) -> Optional[TeamProfile]

# Conversations (UI state)
create_conversation(conversation_id) -> Dict
get_conversation(conversation_id) -> Optional[Dict]
list_conversations() -> List[Dict]
add_message_to_conversation(conversation_id, role, content)
```

### 5. Agents (`agents.py`)

Agent evaluation logic:

```python
async def evaluate_application(
    application: Application,
    team_context: Optional[Dict] = None,
    similar_applications: Optional[List[Dict]] = None
) -> List[AgentEvaluation]

def build_agent_prompt(agent_id, application, observations, team_context, similar_applications) -> str

def format_evaluations_for_deliberation(evaluations, anonymize=True) -> str

async def get_team_context(application) -> Optional[Dict]
```

Agents receive:
- Their character prompt from config
- Up to 5 relevant observations (active status, matching tags)
- Team history if available
- The formatted application

### 6. Council (`council.py`)

Orchestrates the evaluation pipeline:

```python
async def run_full_council(application, max_deliberation_rounds=2) -> CouncilDecision

async def run_deliberation_round(application, evaluations, round_number) -> List[AgentEvaluation]

def aggregate_evaluations(evaluations) -> Dict[str, Any]

def determine_routing(application, aggregated) -> Tuple[Recommendation, bool, List[str]]

async def synthesize_decision(application, evaluations, aggregated, recommendation) -> Tuple[str, str]

async def record_human_decision(decision_id, human_decision, human_rationale, reviewer) -> CouncilDecision
```

### 7. Learning (`learning.py`)

Generates observations for agent improvement:

```python
# When human overrides council decision
async def generate_observations_from_override(decision, human_decision, human_rationale) -> List[Observation]

# When funded grant succeeds or fails
async def generate_observations_from_outcome(application_id, outcome, outcome_notes) -> List[Observation]

# Bootstrap from historical data
async def bootstrap_agent_observations(agent_id, historical_applications, target_observations=30) -> List[Observation]

# Identify stale observations
def prune_stale_observations(min_evidence=5, max_age_days=180) -> List[str]
```

## API Endpoints

### Applications
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/applications` | Submit new application (freeform or structured) |
| GET | `/api/applications` | List applications (filter: status, program_id) |
| GET | `/api/applications/{id}` | Get full application details |
| POST | `/api/applications/{id}/evaluate` | Trigger council evaluation |
| POST | `/api/applications/{id}/evaluate/stream` | Stream evaluation via SSE |
| POST | `/api/applications/{id}/outcome` | Record grant outcome (success/failure) |

### Decisions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/decisions` | List decisions (filter: requires_review) |
| GET | `/api/decisions/{id}` | Get full decision details |
| POST | `/api/decisions/{id}/human-decision` | Record human approval/rejection |

### Observations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/observations` | List observations (filter: agent_id, status) |
| POST | `/api/observations/{id}/activate` | Activate a draft observation |
| POST | `/api/observations/{id}/helpful` | Mark observation as helpful |
| POST | `/api/observations/{id}/deprecate` | Deprecate an observation |
| POST | `/api/observations/prune` | Identify stale observations |

### Conversations (UI)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/conversations` | List all conversations |
| POST | `/api/conversations` | Create new conversation |
| GET | `/api/conversations/{id}` | Get conversation with messages |
| POST | `/api/conversations/{id}/message/stream` | Send message with streaming evaluation |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/api/teams/{id}` | Get team profile |
| POST | `/api/webhook/application` | Receive external applications |

## Evaluation Flow

1. **Ingestion**: Application submitted via API, webhook, or UI
2. **Parsing**: Freeform text parsed to structured format (if needed)
3. **Context Retrieval**:
   - Look up team history by name/wallet
   - Retrieve active observations for each agent
4. **Parallel Evaluation**: All four agents evaluate simultaneously
5. **Deliberation**:
   - Agents see anonymized peer evaluations
   - Can revise scores if change exceeds threshold (0.15)
   - Continues until positions stabilize or max rounds reached
6. **Aggregation**: Compute average score, confidence, variance
7. **Routing Decision**:
   - Auto-approve: unanimous + high confidence + score >= 0.85 + budget < $50k
   - Auto-reject: unanimous rejection + high confidence
   - Human review: anything else
8. **Synthesis**: Generate summary and applicant feedback

## Testing

```bash
# Run the test suite from project root
python test_backend.py
```

Tests cover:
- Module imports
- Model creation and serialization
- Configuration validation
- Storage operations (creates test data in data/)
- Parser functionality
- Council aggregation logic
- FastAPI route registration

## Frontend Architecture

Built with React 19 + Vite 7:

- **App.jsx**: Main state management, API calls, SSE handling
- **Sidebar**: Conversation list navigation
- **ChatInterface**: Message display and input
- **Stage components**: Progressive disclosure of evaluation stages

Key patterns:
- Streaming evaluation updates via Server-Sent Events
- Optimistic UI updates for user messages
- Progressive rendering of evaluation stages

## Development Patterns

### Adding a New Agent

1. Add agent definition to `COUNCIL_AGENTS` in `config.py`:
```python
COUNCIL_AGENTS["security"] = {
    "name": "Security Assessment Agent",
    "model": "openai/gpt-4o-mini",
    "character": """Your character prompt here...""",
    "tags": ["security", "audit", "smart-contracts"]
}
```

2. The agent will automatically participate in evaluations.

### Customizing Decision Routing

Modify `determine_routing()` in `council.py`:
```python
# Example: Always require review for DeFi
if "defi" in application.description.lower():
    auto_execute = False
    review_reasons.append("DeFi applications require manual review")
```

### Adding New API Endpoints

1. Define Pydantic request/response models in `main.py`
2. Add endpoint function with appropriate decorators
3. Update this documentation

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m uvicorn backend.main:app` from project root
2. **Missing API Key**: Set `OPENROUTER_API_KEY` in `.env` file
3. **CORS Issues**: Frontend origins are whitelisted in `main.py` (localhost:5173, localhost:3000, *)
4. **JSON Parsing**: LLM responses may include markdown code blocks - parser handles this
5. **Data Directory**: Created automatically on first storage operation

## Key Design Decisions

### Agent Character Prompts
Each agent has a detailed character prompt that:
- Defines their evaluation focus and expertise
- Specifies what they look for (red flags, positive signals)
- Establishes their personality (skeptical, holistic, etc.)
- Instructs them to cite specific evidence from applications

### Deliberation Mechanism
- Agents see anonymized peer evaluations (prevents favoritism)
- Position changes require minimum threshold to count as revisions
- Stops early if no agents revise their positions

### Auto-Execution Criteria
All conditions must be met:
- Unanimous recommendation
- High average confidence (>= 0.8)
- Score above/below threshold
- Budget under review threshold

### Observation Lifecycle
1. **Draft**: Generated from outcomes/overrides
2. **Reviewed**: Human has validated the pattern (not currently enforced)
3. **Active**: Used in agent prompts
4. **Deprecated**: No longer used

## File Conventions

- Backend code: Python 3.11+, dataclasses, async/await
- Frontend code: React 19, ES modules, CSS modules
- Data files: JSON with 2-space indentation
- No TypeScript in frontend (plain JSX)

## Future Enhancement Ideas

- [ ] Vector similarity search for similar applications
- [ ] Batch evaluation mode
- [ ] Webhook notifications for decisions
- [ ] Dashboard for observation management
- [ ] Integration with on-chain voting systems
- [ ] Multi-program support with isolated agent memories
- [ ] Configurable agent weights for different programs
- [ ] Appeal/reconsideration workflow
