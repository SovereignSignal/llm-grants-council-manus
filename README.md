# Grants Council

An agentic multi-LLM system for evaluating grant applications. Built on the foundation of [llm-council](https://github.com/karpathy/llm-council), this project transforms the general-purpose LLM deliberation framework into a specialized grants evaluation system.

## Overview

Grants Council uses four specialized AI agents to evaluate grant applications:

| Agent | Focus | Key Questions |
|-------|-------|---------------|
| **Technical Feasibility** | Can this be built? | Is the technical approach sound? Does the team have relevant experience? Are timelines realistic? |
| **Ecosystem Fit** | Does this belong? | Does it align with program goals? Fill a gap? Avoid duplication? |
| **Budget Reasonableness** | Is the ask justified? | How does cost compare to similar projects? Are line items reasonable? |
| **Impact Assessment** | Will this matter? | What's the reach? Will it last? Would it happen without funding? |

## Key Features

### Multi-Agent Deliberation
- Four specialized agents evaluate each application in parallel
- Agents see anonymized peer evaluations and can revise their positions
- Configurable deliberation rounds until positions stabilize

### Decision Routing
- **Auto-approve**: Unanimous high-confidence approvals under budget threshold
- **Auto-reject**: Unanimous high-confidence rejections
- **Human review**: Split decisions, borderline scores, large budgets, or low confidence

### Persistent Memory
- Agents accumulate observations from outcomes and overrides
- Patterns are tagged and retrieved for relevant future applications
- Human validation before observations become active

### Team Profiling
- Track applicant teams across multiple applications
- Surface prior grant history and milestone completion rates
- Link wallet addresses and aliases to canonical team identities

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Ingestion                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Freeform   │  │ Structured  │  │   Webhook   │              │
│  │    Text     │  │    JSON     │  │   Payload   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         └────────────────┼────────────────┘                     │
│                          ▼                                       │
│                    ┌───────────┐                                 │
│                    │  Parser   │                                 │
│                    └─────┬─────┘                                 │
└──────────────────────────┼──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Context Retrieval                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │    Team     │  │   Similar   │  │   Agent     │              │
│  │   History   │  │    Apps     │  │Observations │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         └────────────────┼────────────────┘                     │
└──────────────────────────┼──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Parallel Evaluation                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │Technical │  │Ecosystem │  │  Budget  │  │  Impact  │        │
│  │  Agent   │  │  Agent   │  │  Agent   │  │  Agent   │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       └─────────────┼─────────────┼─────────────┘              │
│                     ▼             ▼                             │
│              ┌─────────────────────────┐                        │
│              │    Deliberation Loop    │                        │
│              │  (agents revise views)  │                        │
│              └───────────┬─────────────┘                        │
└──────────────────────────┼──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Decision & Routing                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Aggregation │─▶│   Routing   │─▶│  Synthesis  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                          │                                       │
│         ┌────────────────┼────────────────┐                     │
│         ▼                ▼                ▼                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │Auto-Approve │  │Auto-Reject  │  │Human Review │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- OpenAI API key (or compatible endpoint)

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/grants-council.git
cd grants-council

# Set up environment
export OPENAI_API_KEY="your-api-key"

# Install dependencies
pip install fastapi uvicorn httpx openai

# Run the backend
cd backend
uvicorn main:app --reload --port 8001
```

### Frontend Setup

```bash
# Install dependencies
cd frontend
pnpm install

# Run development server
pnpm dev
```

### API Usage

#### Submit an Application

```bash
# Structured submission
curl -X POST http://localhost:8001/api/applications \
  -H "Content-Type: application/json" \
  -d '{
    "title": "DeFi Analytics Dashboard",
    "summary": "Comprehensive analytics for DeFi protocols",
    "team_name": "Analytics Labs",
    "funding_requested": 50000,
    "funding_currency": "USD",
    "technical_approach": "Using The Graph for indexing...",
    "milestones": [
      {"title": "MVP", "description": "Basic dashboard", "funding_percentage": 40},
      {"title": "Launch", "description": "Full release", "funding_percentage": 60}
    ]
  }'

# Freeform text submission
curl -X POST http://localhost:8001/api/applications \
  -H "Content-Type: application/json" \
  -d '{
    "text": "We are Analytics Labs requesting $50,000 to build a DeFi analytics dashboard..."
  }'
```

#### Trigger Evaluation

```bash
# Start evaluation
curl -X POST http://localhost:8001/api/applications/{application_id}/evaluate

# Stream evaluation progress
curl -X POST http://localhost:8001/api/applications/{application_id}/evaluate/stream
```

#### Record Human Decision

```bash
curl -X POST http://localhost:8001/api/decisions/{decision_id}/human-decision \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approve",
    "rationale": "Strong team with proven track record",
    "reviewer": "alice@example.com"
  }'
```

## Configuration

Key configuration options in `backend/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `AUTO_APPROVE_THRESHOLD` | 0.85 | Minimum avg score for auto-approval |
| `AUTO_REJECT_THRESHOLD` | 0.15 | Maximum avg score for auto-rejection |
| `BUDGET_REVIEW_THRESHOLD` | 50000 | USD amount requiring human review |
| `MAX_DELIBERATION_ROUNDS` | 2 | Maximum deliberation iterations |
| `POSITION_CHANGE_THRESHOLD` | 0.15 | Minimum score change to count as revision |

## Agent Customization

Each agent is defined in `backend/config.py` with:

- **name**: Display name
- **model**: LLM model to use (e.g., `gpt-4.1-mini`)
- **character**: System prompt defining the agent's perspective
- **tags**: Categories for observation retrieval

Example customization:

```python
COUNCIL_AGENTS["security"] = {
    "name": "Security Assessment Agent",
    "model": "gpt-4.1-mini",
    "character": """You are the Security Assessment Agent...
    
Your evaluation focuses on:
- Smart contract security patterns
- Audit history and plans
- Known vulnerability classes
...""",
    "tags": ["security", "audit", "smart-contracts"]
}
```

## API Reference

### Applications

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/applications` | POST | Submit new application |
| `/api/applications` | GET | List applications |
| `/api/applications/{id}` | GET | Get application details |
| `/api/applications/{id}/evaluate` | POST | Trigger evaluation |
| `/api/applications/{id}/evaluate/stream` | POST | Stream evaluation |

### Decisions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/decisions` | GET | List decisions |
| `/api/decisions/{id}` | GET | Get decision details |
| `/api/decisions/{id}/human-decision` | POST | Record human decision |

### Observations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/observations` | GET | List agent observations |
| `/api/observations/{id}/activate` | POST | Activate draft observation |

### Teams

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/teams/{id}` | GET | Get team profile |

## Data Model

### Application

```json
{
  "id": "uuid",
  "title": "string",
  "summary": "string",
  "description": "string",
  "team_name": "string",
  "team_members": [{"name": "string", "role": "string", ...}],
  "problem_statement": "string",
  "proposed_solution": "string",
  "technical_approach": "string",
  "funding_requested": 50000,
  "funding_currency": "USD",
  "milestones": [...],
  "status": "pending|evaluating|deliberating|approved|rejected|..."
}
```

### Council Decision

```json
{
  "id": "uuid",
  "application_id": "uuid",
  "average_score": 0.75,
  "average_confidence": 0.82,
  "recommendation": "approve|reject|needs_review",
  "evaluations": [...],
  "auto_executed": false,
  "requires_human_review": true,
  "review_reasons": ["Budget exceeds threshold"],
  "synthesis": "The council recommends...",
  "feedback_for_applicant": "Strong application with..."
}
```

### Agent Evaluation

```json
{
  "agent_id": "technical",
  "agent_name": "Technical Feasibility Agent",
  "score": 0.8,
  "recommendation": "approve",
  "confidence": 0.85,
  "rationale": "The technical approach is sound...",
  "strengths": ["Clear architecture", "Experienced team"],
  "concerns": ["Timeline might be tight"],
  "questions": ["What's the fallback if X fails?"]
}
```

## Learning Loop

The system learns from outcomes:

1. **Override Learning**: When humans override council decisions, agents reflect on what they missed
2. **Outcome Learning**: When funded grants succeed or fail, agents update their patterns
3. **Observation Lifecycle**: Draft → Reviewed → Active → Deprecated

Observations are tagged and retrieved based on relevance to new applications.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python test_backend.py`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Original [llm-council](https://github.com/karpathy/llm-council) by Andrej Karpathy
- Inspired by real-world grants programs and their evaluation challenges
