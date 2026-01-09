# Grants Council - Technical Documentation

This document provides technical details for developers working on the Grants Council codebase.

## Project Structure

```
grants-council/
├── backend/
│   ├── __init__.py          # Package initialization
│   ├── config.py            # Configuration and agent definitions
│   ├── models.py            # Data models (Application, Decision, etc.)
│   ├── llm_client.py        # OpenAI-compatible API client
│   ├── storage.py           # JSON-based persistence layer
│   ├── parser.py            # Application parsing (freeform & structured)
│   ├── agents.py            # Agent evaluation logic
│   ├── council.py           # Deliberation and voting orchestration
│   ├── learning.py          # Observation generation and learning loop
│   └── main.py              # FastAPI application and endpoints
├── frontend/                 # React frontend (from original llm-council)
├── data/                     # Runtime data storage
│   ├── applications/         # Application JSON files
│   ├── evaluations/          # Decision JSON files
│   ├── observations/         # Agent observation files
│   ├── teams/                # Team profile files
│   └── conversations/        # UI conversation history
├── test_backend.py          # Backend test suite
└── README.md                # User-facing documentation
```

## Core Components

### 1. Configuration (`config.py`)

Defines the four council agents with their character prompts:

- **Technical Feasibility Agent**: Evaluates whether projects can be built
- **Ecosystem Fit Agent**: Assesses alignment with program goals
- **Budget Reasonableness Agent**: Analyzes cost justification
- **Impact Assessment Agent**: Evaluates potential lasting value

Key thresholds:
- `AUTO_APPROVE_THRESHOLD = 0.85`: Score needed for auto-approval
- `AUTO_REJECT_THRESHOLD = 0.15`: Score below which auto-reject
- `BUDGET_REVIEW_THRESHOLD = 50000`: USD amount requiring human review
- `MAX_DELIBERATION_ROUNDS = 2`: Maximum deliberation iterations

### 2. Data Models (`models.py`)

Core dataclasses:

```python
@dataclass
class Application:
    id: str
    title: str
    team_name: str
    funding_requested: float
    status: ApplicationStatus
    # ... full application fields

@dataclass
class AgentEvaluation:
    agent_id: str
    score: float  # 0-1
    recommendation: Recommendation  # approve/reject/needs_review
    confidence: float  # 0-1
    rationale: str
    strengths: List[str]
    concerns: List[str]
    # ... deliberation tracking

@dataclass
class CouncilDecision:
    application_id: str
    average_score: float
    recommendation: Recommendation
    evaluations: List[AgentEvaluation]
    auto_executed: bool
    requires_human_review: bool
    synthesis: str
    feedback_for_applicant: str

@dataclass
class Observation:
    agent_id: str
    pattern: str  # The learned insight
    evidence: List[str]  # Application IDs supporting this
    tags: List[str]  # For retrieval
    status: ObservationStatus  # draft/reviewed/active/deprecated
```

### 3. LLM Client (`llm_client.py`)

Async client for OpenAI-compatible APIs:

```python
async def query_model(model: str, messages: List[Dict], ...) -> Dict
async def query_models_parallel(models_with_messages: List[Dict], ...) -> Dict
async def query_with_structured_output(model: str, messages: List[Dict], schema: Dict, ...) -> Dict
```

Uses `OPENAI_API_KEY` environment variable. Compatible with any OpenAI-compatible endpoint.

### 4. Storage (`storage.py`)

JSON file-based persistence:

```python
# Applications
save_application(application: Application) -> str
get_application(application_id: str) -> Optional[Application]
list_applications(status: Optional[ApplicationStatus] = None) -> List[Application]

# Decisions
save_decision(decision: CouncilDecision) -> str
get_decision(decision_id: str) -> Optional[CouncilDecision]
list_decisions(requires_review: Optional[bool] = None) -> List[CouncilDecision]

# Observations
save_observation(observation: Observation) -> str
get_observations_for_agent(agent_id: str, tags: List[str] = None) -> List[Observation]

# Teams
save_team(team: TeamProfile) -> str
get_team(team_id: str) -> Optional[TeamProfile]
find_team_by_name(name: str) -> Optional[TeamProfile]
find_team_by_wallet(wallet: str) -> Optional[TeamProfile]
```

### 5. Parser (`parser.py`)

Handles application ingestion:

```python
async def parse_freeform_application(text: str, metadata: Dict = None) -> Application
def parse_structured_application(data: Dict) -> Application
def format_application_for_evaluation(application: Application) -> str
```

Freeform parsing uses LLM to extract structured fields from natural language.

### 6. Agents (`agents.py`)

Agent evaluation logic:

```python
async def evaluate_application(
    application: Application,
    team_context: Optional[Dict] = None,
    similar_applications: Optional[List[Dict]] = None
) -> List[AgentEvaluation]

def build_agent_prompt(
    agent_id: str,
    application: Application,
    observations: List[Observation],
    team_context: Optional[Dict] = None,
    similar_applications: Optional[List[Dict]] = None
) -> str

def format_evaluations_for_deliberation(
    evaluations: List[AgentEvaluation],
    anonymize: bool = True
) -> str
```

### 7. Council (`council.py`)

Orchestrates the full evaluation pipeline:

```python
async def run_full_council(
    application: Application,
    max_deliberation_rounds: int = MAX_DELIBERATION_ROUNDS
) -> CouncilDecision

async def run_deliberation_round(
    application: Application,
    evaluations: List[AgentEvaluation],
    round_number: int
) -> List[AgentEvaluation]

def aggregate_evaluations(evaluations: List[AgentEvaluation]) -> Dict[str, Any]

def determine_routing(
    application: Application,
    aggregated: Dict[str, Any]
) -> Tuple[Recommendation, bool, List[str]]

async def synthesize_decision(
    application: Application,
    evaluations: List[AgentEvaluation],
    aggregated: Dict[str, Any],
    recommendation: Recommendation
) -> Tuple[str, str]  # (synthesis, feedback)
```

### 8. Learning (`learning.py`)

Generates observations from outcomes:

```python
async def generate_observations_from_override(
    decision: CouncilDecision,
    human_decision: str,
    human_rationale: str
) -> List[Observation]

async def generate_observations_from_outcome(
    application_id: str,
    outcome: str,  # "success" or "failure"
    outcome_notes: str
) -> List[Observation]

async def bootstrap_agent_observations(
    agent_id: str,
    historical_applications: List[Dict[str, Any]],
    target_observations: int = 30
) -> List[Observation]
```

## API Endpoints

### Application Management

```
POST /api/applications
  - Submit new application (freeform text or structured JSON)
  - Returns: ApplicationResponse

GET /api/applications
  - List applications with optional filters
  - Query params: status, program_id, limit
  - Returns: List[ApplicationResponse]

GET /api/applications/{application_id}
  - Get full application details
  - Returns: Application dict

POST /api/applications/{application_id}/evaluate
  - Trigger council evaluation
  - Returns: Decision summary

POST /api/applications/{application_id}/evaluate/stream
  - Stream evaluation progress via SSE
  - Returns: Server-Sent Events
```

### Decision Management

```
GET /api/decisions
  - List decisions with optional filters
  - Query params: requires_review, limit
  - Returns: List of decision summaries

GET /api/decisions/{decision_id}
  - Get full decision details
  - Returns: CouncilDecision dict

POST /api/decisions/{decision_id}/human-decision
  - Record human approval/rejection
  - Body: {decision: "approve"|"reject", rationale: str, reviewer: str}
  - Returns: Updated decision
```

### Observations

```
GET /api/observations
  - List agent observations
  - Query params: agent_id, status
  - Returns: List[Observation]

POST /api/observations/{observation_id}/activate
  - Activate a draft observation
  - Query params: reviewer
  - Returns: Updated observation
```

### Webhooks

```
POST /api/webhook/application
  - Receive applications from external systems
  - Accepts various payload formats
  - Returns: {status, application_id, title}
```

## Evaluation Flow

1. **Ingestion**: Application submitted via API or webhook
2. **Context Retrieval**: 
   - Look up team history
   - Retrieve relevant agent observations
   - (Future: Find similar past applications)
3. **Parallel Evaluation**: All four agents evaluate simultaneously
4. **Deliberation**: 
   - Agents see anonymized peer evaluations
   - Can revise scores/recommendations
   - Continues until positions stabilize or max rounds
5. **Aggregation**: Compute average score, confidence, variance
6. **Routing Decision**:
   - Auto-approve if unanimous, high confidence, under budget threshold
   - Auto-reject if unanimous rejection
   - Route to human review otherwise
7. **Synthesis**: Generate summary and applicant feedback

## Extending the System

### Adding a New Agent

1. Add agent definition to `COUNCIL_AGENTS` in `config.py`:

```python
COUNCIL_AGENTS["security"] = {
    "name": "Security Assessment Agent",
    "model": "gpt-4.1-mini",
    "character": """Your character prompt here...""",
    "tags": ["security", "audit", "smart-contracts"]
}
```

2. The agent will automatically participate in evaluations.

### Customizing Decision Routing

Modify `determine_routing()` in `council.py` to add custom logic:

```python
# Example: Always require review for certain categories
if "defi" in application.tags:
    auto_execute = False
    review_reasons.append("DeFi applications require manual review")
```

### Integrating External Data

1. Add retrieval functions to `storage.py`
2. Call them in `agents.py` when building prompts
3. Include relevant context in the agent prompt

## Testing

Run the test suite:

```bash
cd grants-council
python test_backend.py
```

Tests cover:
- Module imports
- Model creation and serialization
- Configuration validation
- Storage operations
- Parser functionality
- Council aggregation logic
- FastAPI route registration

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | API key for LLM access |
| `DATABASE_URL` | No | Database connection (default: SQLite) |
| `VECTOR_DB_PATH` | No | Path for vector store (future use) |

## Key Design Decisions

### Agent Character Prompts

Each agent has a detailed character prompt that:
- Defines their evaluation focus and expertise
- Specifies what they look for (red flags, positive signals)
- Establishes their personality (skeptical, holistic, etc.)
- Instructs them to cite specific evidence from applications

### Deliberation Mechanism

The deliberation loop allows agents to:
- See anonymized peer evaluations (prevents favoritism)
- Revise their positions based on new arguments
- Converge toward consensus or surface genuine disagreements

Position changes require a minimum threshold (`POSITION_CHANGE_THRESHOLD`) to count as revisions, preventing noise from minor adjustments.

### Auto-Execution Criteria

Auto-execution requires ALL of:
- Unanimous recommendation (all agents agree)
- High average confidence (≥0.8)
- Score above/below threshold (0.85 approve, 0.15 reject)
- Budget under review threshold

Any of these failing triggers human review with specific reasons.

### Observation Lifecycle

Observations follow a lifecycle:
1. **Draft**: Generated from outcomes/overrides
2. **Reviewed**: Human has validated the pattern
3. **Active**: Used in agent prompts
4. **Deprecated**: No longer used (stale or incorrect)

This prevents agents from learning incorrect patterns without human oversight.

## Common Gotchas

1. **Module Import Errors**: Run backend as `python -m backend.main` from project root
2. **Missing API Key**: Set `OPENAI_API_KEY` environment variable
3. **CORS Issues**: Frontend must match allowed origins in `main.py`
4. **JSON Parsing**: LLM responses may include markdown code blocks - parser handles this

## Future Enhancement Ideas

- [ ] Vector similarity search for similar applications
- [ ] Batch evaluation mode
- [ ] Webhook notifications for decisions
- [ ] Dashboard for observation management
- [ ] Integration with on-chain voting systems
- [ ] Multi-program support with isolated agent memories
- [ ] Configurable agent weights for different programs
- [ ] Appeal/reconsideration workflow
