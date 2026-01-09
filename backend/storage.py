"""JSON-based storage for the Grants Council."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from .config import (
    DATA_DIR, APPLICATIONS_DIR, OBSERVATIONS_DIR, 
    EVALUATIONS_DIR, TEAMS_DIR, CONVERSATIONS_DIR
)
from .models import (
    Application, TeamProfile, AgentEvaluation, 
    Observation, CouncilDecision, ApplicationStatus,
    Recommendation, ObservationStatus, TeamMember, BudgetItem, Milestone
)


def ensure_dirs():
    """Ensure all data directories exist."""
    for dir_path in [DATA_DIR, APPLICATIONS_DIR, OBSERVATIONS_DIR, 
                     EVALUATIONS_DIR, TEAMS_DIR, CONVERSATIONS_DIR]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)


def init_storage():
    """Initialize storage (alias for ensure_dirs)."""
    ensure_dirs()


# ============ Applications ============

def save_application(application: Application) -> str:
    """Save an application to storage."""
    ensure_dirs()
    path = os.path.join(APPLICATIONS_DIR, f"{application.id}.json")
    with open(path, 'w') as f:
        json.dump(application.to_dict(), f, indent=2)
    return application.id


def get_application(application_id: str) -> Optional[Application]:
    """Load an application from storage."""
    path = os.path.join(APPLICATIONS_DIR, f"{application_id}.json")
    if not os.path.exists(path):
        return None
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    return _dict_to_application(data)


def _dict_to_application(data: Dict[str, Any]) -> Application:
    """Convert dictionary to Application object."""
    app = Application(
        id=data.get("id"),
        title=data.get("title", ""),
        summary=data.get("summary", ""),
        description=data.get("description", ""),
        team_name=data.get("team_name", ""),
        team_id=data.get("team_id"),
        problem_statement=data.get("problem_statement", ""),
        proposed_solution=data.get("proposed_solution", ""),
        technical_approach=data.get("technical_approach", ""),
        prior_work=data.get("prior_work", ""),
        funding_requested=data.get("funding_requested", 0.0),
        funding_currency=data.get("funding_currency", "USD"),
        program_id=data.get("program_id"),
        round_id=data.get("round_id"),
        status=ApplicationStatus(data.get("status", "pending")),
        raw_submission=data.get("raw_submission", {}),
        website=data.get("website"),
        github=data.get("github"),
        demo=data.get("demo"),
    )
    
    # Parse team members
    app.team_members = [
        TeamMember(**m) for m in data.get("team_members", [])
    ]
    
    # Parse budget
    app.budget_breakdown = [
        BudgetItem(**b) for b in data.get("budget_breakdown", [])
    ]
    
    # Parse milestones
    app.milestones = [
        Milestone(**m) for m in data.get("milestones", [])
    ]
    
    # Parse datetime
    if data.get("submitted_at"):
        app.submitted_at = datetime.fromisoformat(data["submitted_at"])
    
    return app


def list_applications(
    status: Optional[ApplicationStatus] = None,
    program_id: Optional[str] = None,
    limit: int = 100
) -> List[Application]:
    """List applications with optional filters."""
    ensure_dirs()
    applications = []
    
    if not os.path.exists(APPLICATIONS_DIR):
        return []
    
    for filename in os.listdir(APPLICATIONS_DIR):
        if not filename.endswith('.json'):
            continue
        
        path = os.path.join(APPLICATIONS_DIR, filename)
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Apply filters
        if status and data.get("status") != status.value:
            continue
        if program_id and data.get("program_id") != program_id:
            continue
        
        applications.append(_dict_to_application(data))
    
    # Sort by submission date, newest first
    applications.sort(key=lambda x: x.submitted_at, reverse=True)
    
    return applications[:limit]


def update_application_status(application_id: str, status: ApplicationStatus):
    """Update the status of an application."""
    app = get_application(application_id)
    if app:
        app.status = status
        save_application(app)


# ============ Team Profiles ============

def save_team(team: TeamProfile) -> str:
    """Save a team profile to storage."""
    ensure_dirs()
    team.updated_at = datetime.utcnow()
    path = os.path.join(TEAMS_DIR, f"{team.id}.json")
    
    data = {
        "id": team.id,
        "canonical_name": team.canonical_name,
        "aliases": team.aliases,
        "members": [vars(m) for m in team.members],
        "wallet_addresses": team.wallet_addresses,
        "application_ids": team.application_ids,
        "successful_grants": team.successful_grants,
        "failed_grants": team.failed_grants,
        "total_funded": team.total_funded,
        "milestone_completion_rate": team.milestone_completion_rate,
        "reputation_signals": team.reputation_signals,
        "created_at": team.created_at.isoformat(),
        "updated_at": team.updated_at.isoformat(),
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return team.id


def get_team(team_id: str) -> Optional[TeamProfile]:
    """Load a team profile from storage."""
    path = os.path.join(TEAMS_DIR, f"{team_id}.json")
    if not os.path.exists(path):
        return None
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    team = TeamProfile(
        id=data["id"],
        canonical_name=data.get("canonical_name", ""),
        aliases=data.get("aliases", []),
        wallet_addresses=data.get("wallet_addresses", []),
        application_ids=data.get("application_ids", []),
        successful_grants=data.get("successful_grants", 0),
        failed_grants=data.get("failed_grants", 0),
        total_funded=data.get("total_funded", 0.0),
        milestone_completion_rate=data.get("milestone_completion_rate", 0.0),
        reputation_signals=data.get("reputation_signals", {}),
    )
    
    team.members = [TeamMember(**m) for m in data.get("members", [])]
    
    if data.get("created_at"):
        team.created_at = datetime.fromisoformat(data["created_at"])
    if data.get("updated_at"):
        team.updated_at = datetime.fromisoformat(data["updated_at"])
    
    return team


def find_team_by_wallet(wallet_address: str) -> Optional[TeamProfile]:
    """Find a team by wallet address."""
    ensure_dirs()
    
    if not os.path.exists(TEAMS_DIR):
        return None
    
    for filename in os.listdir(TEAMS_DIR):
        if not filename.endswith('.json'):
            continue
        
        path = os.path.join(TEAMS_DIR, filename)
        with open(path, 'r') as f:
            data = json.load(f)
        
        if wallet_address in data.get("wallet_addresses", []):
            return get_team(data["id"])
    
    return None


def find_team_by_name(name: str) -> Optional[TeamProfile]:
    """Find a team by name or alias (fuzzy match)."""
    ensure_dirs()
    name_lower = name.lower()
    
    if not os.path.exists(TEAMS_DIR):
        return None
    
    for filename in os.listdir(TEAMS_DIR):
        if not filename.endswith('.json'):
            continue
        
        path = os.path.join(TEAMS_DIR, filename)
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Check canonical name
        if data.get("canonical_name", "").lower() == name_lower:
            return get_team(data["id"])
        
        # Check aliases
        for alias in data.get("aliases", []):
            if alias.lower() == name_lower:
                return get_team(data["id"])
    
    return None


# ============ Observations ============

def save_observation(observation: Observation) -> str:
    """Save an observation to storage."""
    ensure_dirs()
    path = os.path.join(OBSERVATIONS_DIR, f"{observation.id}.json")
    with open(path, 'w') as f:
        json.dump(observation.to_dict(), f, indent=2)
    return observation.id


def get_observation(observation_id: str) -> Optional[Observation]:
    """Load an observation from storage."""
    path = os.path.join(OBSERVATIONS_DIR, f"{observation_id}.json")
    if not os.path.exists(path):
        return None
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    obs = Observation(
        id=data["id"],
        agent_id=data.get("agent_id", ""),
        pattern=data.get("pattern", ""),
        evidence=data.get("evidence", []),
        tags=data.get("tags", []),
        confidence=data.get("confidence", 0.0),
        status=ObservationStatus(data.get("status", "draft")),
        times_used=data.get("times_used", 0),
        times_helpful=data.get("times_helpful", 0),
    )
    
    if data.get("created_at"):
        obs.created_at = datetime.fromisoformat(data["created_at"])
    if data.get("validated_at"):
        obs.validated_at = datetime.fromisoformat(data["validated_at"])
    obs.validated_by = data.get("validated_by")
    
    return obs


def get_observations_for_agent(
    agent_id: str,
    tags: Optional[List[str]] = None,
    status: ObservationStatus = ObservationStatus.ACTIVE,
    limit: int = 10
) -> List[Observation]:
    """Get relevant observations for an agent."""
    ensure_dirs()
    observations = []
    
    if not os.path.exists(OBSERVATIONS_DIR):
        return []
    
    for filename in os.listdir(OBSERVATIONS_DIR):
        if not filename.endswith('.json'):
            continue
        
        path = os.path.join(OBSERVATIONS_DIR, filename)
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Filter by agent
        if data.get("agent_id") != agent_id:
            continue
        
        # Filter by status
        if data.get("status") != status.value:
            continue
        
        # Filter by tags if provided
        if tags:
            obs_tags = set(data.get("tags", []))
            if not obs_tags.intersection(set(tags)):
                continue
        
        obs = get_observation(data["id"])
        if obs:
            observations.append(obs)
    
    # Sort by confidence and usage
    observations.sort(
        key=lambda x: (x.confidence, x.times_helpful),
        reverse=True
    )
    
    return observations[:limit]


def list_all_observations(
    agent_id: Optional[str] = None,
    status: Optional[ObservationStatus] = None
) -> List[Observation]:
    """List all observations with optional filters."""
    ensure_dirs()
    observations = []
    
    if not os.path.exists(OBSERVATIONS_DIR):
        return []
    
    for filename in os.listdir(OBSERVATIONS_DIR):
        if not filename.endswith('.json'):
            continue
        
        path = os.path.join(OBSERVATIONS_DIR, filename)
        with open(path, 'r') as f:
            data = json.load(f)
        
        if agent_id and data.get("agent_id") != agent_id:
            continue
        
        if status and data.get("status") != status.value:
            continue
        
        obs = get_observation(data["id"])
        if obs:
            observations.append(obs)
    
    return observations


# ============ Evaluations & Decisions ============

def save_decision(decision: CouncilDecision) -> str:
    """Save a council decision to storage."""
    ensure_dirs()
    path = os.path.join(EVALUATIONS_DIR, f"{decision.id}.json")
    with open(path, 'w') as f:
        json.dump(decision.to_dict(), f, indent=2)
    return decision.id


def get_decision(decision_id: str) -> Optional[CouncilDecision]:
    """Load a council decision from storage."""
    path = os.path.join(EVALUATIONS_DIR, f"{decision_id}.json")
    if not os.path.exists(path):
        return None
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    return _dict_to_decision(data)


def get_decision_for_application(application_id: str) -> Optional[CouncilDecision]:
    """Get the decision for a specific application."""
    ensure_dirs()
    
    if not os.path.exists(EVALUATIONS_DIR):
        return None
    
    for filename in os.listdir(EVALUATIONS_DIR):
        if not filename.endswith('.json'):
            continue
        
        path = os.path.join(EVALUATIONS_DIR, filename)
        with open(path, 'r') as f:
            data = json.load(f)
        
        if data.get("application_id") == application_id:
            return _dict_to_decision(data)
    
    return None


def _dict_to_decision(data: Dict[str, Any]) -> CouncilDecision:
    """Convert dictionary to CouncilDecision object."""
    decision = CouncilDecision(
        id=data["id"],
        application_id=data.get("application_id", ""),
        average_score=data.get("average_score", 0.0),
        average_confidence=data.get("average_confidence", 0.0),
        recommendation=Recommendation(data.get("recommendation", "needs_review")),
        auto_executed=data.get("auto_executed", False),
        requires_human_review=data.get("requires_human_review", True),
        review_reasons=data.get("review_reasons", []),
        human_decision=data.get("human_decision"),
        human_rationale=data.get("human_rationale"),
        human_reviewer=data.get("human_reviewer"),
        synthesis=data.get("synthesis", ""),
        feedback_for_applicant=data.get("feedback_for_applicant", ""),
    )
    
    # Parse evaluations
    decision.evaluations = [
        _dict_to_evaluation(e) for e in data.get("evaluations", [])
    ]
    
    if data.get("created_at"):
        decision.created_at = datetime.fromisoformat(data["created_at"])
    if data.get("decided_at"):
        decision.decided_at = datetime.fromisoformat(data["decided_at"])
    
    return decision


def _dict_to_evaluation(data: Dict[str, Any]) -> AgentEvaluation:
    """Convert dictionary to AgentEvaluation object."""
    eval_obj = AgentEvaluation(
        id=data.get("id"),
        application_id=data.get("application_id", ""),
        agent_id=data.get("agent_id", ""),
        agent_name=data.get("agent_name", ""),
        score=data.get("score", 0.0),
        recommendation=Recommendation(data.get("recommendation", "needs_review")),
        confidence=data.get("confidence", 0.0),
        rationale=data.get("rationale", ""),
        strengths=data.get("strengths", []),
        concerns=data.get("concerns", []),
        questions=data.get("questions", []),
        observations_used=data.get("observations_used", []),
        similar_applications=data.get("similar_applications", []),
        is_revised=data.get("is_revised", False),
        original_score=data.get("original_score"),
        revision_rationale=data.get("revision_rationale"),
        deliberation_round=data.get("deliberation_round", 0),
    )
    
    if data.get("created_at"):
        eval_obj.created_at = datetime.fromisoformat(data["created_at"])
    
    return eval_obj


def list_decisions(
    requires_review: Optional[bool] = None,
    limit: int = 100
) -> List[CouncilDecision]:
    """List decisions with optional filters."""
    ensure_dirs()
    decisions = []
    
    if not os.path.exists(EVALUATIONS_DIR):
        return []
    
    for filename in os.listdir(EVALUATIONS_DIR):
        if not filename.endswith('.json'):
            continue
        
        path = os.path.join(EVALUATIONS_DIR, filename)
        with open(path, 'r') as f:
            data = json.load(f)
        
        if requires_review is not None:
            if data.get("requires_human_review") != requires_review:
                continue
        
        decisions.append(_dict_to_decision(data))
    
    decisions.sort(key=lambda x: x.created_at, reverse=True)
    return decisions[:limit]


# ============ Conversations (for Discord/UI) ============

def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """Create a new conversation."""
    ensure_dirs()
    
    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Evaluation",
        "messages": [],
        "application_id": None,
    }
    
    path = os.path.join(CONVERSATIONS_DIR, f"{conversation_id}.json")
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)
    
    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Load a conversation from storage."""
    path = os.path.join(CONVERSATIONS_DIR, f"{conversation_id}.json")
    
    if not os.path.exists(path):
        return None
    
    with open(path, 'r') as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """Save a conversation to storage."""
    ensure_dirs()
    path = os.path.join(CONVERSATIONS_DIR, f"{conversation['id']}.json")
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    """List all conversations (metadata only)."""
    ensure_dirs()
    conversations = []
    
    if not os.path.exists(CONVERSATIONS_DIR):
        return []
    
    for filename in os.listdir(CONVERSATIONS_DIR):
        if not filename.endswith('.json'):
            continue
        
        path = os.path.join(CONVERSATIONS_DIR, filename)
        with open(path, 'r') as f:
            data = json.load(f)
        
        conversations.append({
            "id": data["id"],
            "created_at": data["created_at"],
            "title": data.get("title", "New Evaluation"),
            "message_count": len(data.get("messages", [])),
            "application_id": data.get("application_id"),
        })
    
    conversations.sort(key=lambda x: x["created_at"], reverse=True)
    return conversations


def add_message_to_conversation(
    conversation_id: str,
    role: str,
    content: Any
):
    """Add a message to a conversation."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    
    conversation["messages"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    })
    
    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """Update conversation title."""
    conversation = get_conversation(conversation_id)
    if conversation:
        conversation["title"] = title
        save_conversation(conversation)
