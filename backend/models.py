"""Data models for the Grants Council."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid


class ApplicationStatus(Enum):
    """Status of a grant application."""
    PENDING = "pending"
    EVALUATING = "evaluating"
    DELIBERATING = "deliberating"
    AUTO_APPROVED = "auto_approved"
    AUTO_REJECTED = "auto_rejected"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Recommendation(Enum):
    """Agent recommendation types."""
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"


class ObservationStatus(Enum):
    """Status of learned observations."""
    DRAFT = "draft"
    REVIEWED = "reviewed"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass
class TeamMember:
    """A member of an applicant team."""
    name: str
    role: str
    wallet_address: Optional[str] = None
    github: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None
    bio: Optional[str] = None


@dataclass
class TeamProfile:
    """Profile of an applicant team with history."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    canonical_name: str = ""
    aliases: List[str] = field(default_factory=list)
    members: List[TeamMember] = field(default_factory=list)
    wallet_addresses: List[str] = field(default_factory=list)
    application_ids: List[str] = field(default_factory=list)
    successful_grants: int = 0
    failed_grants: int = 0
    total_funded: float = 0.0
    milestone_completion_rate: float = 0.0
    reputation_signals: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Milestone:
    """A project milestone."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    deliverables: List[str] = field(default_factory=list)
    timeline: str = ""
    funding_amount: float = 0.0
    funding_percentage: float = 0.0
    status: str = "pending"
    completion_date: Optional[datetime] = None


@dataclass
class BudgetItem:
    """A line item in the budget."""
    category: str
    description: str
    amount: float
    justification: Optional[str] = None


@dataclass
class Application:
    """A grant application."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Basic info
    title: str = ""
    summary: str = ""
    description: str = ""
    
    # Team info
    team_name: str = ""
    team_id: Optional[str] = None
    team_members: List[TeamMember] = field(default_factory=list)
    
    # Project details
    problem_statement: str = ""
    proposed_solution: str = ""
    technical_approach: str = ""
    prior_work: str = ""
    
    # Funding
    funding_requested: float = 0.0
    funding_currency: str = "USD"
    budget_breakdown: List[BudgetItem] = field(default_factory=list)
    milestones: List[Milestone] = field(default_factory=list)
    
    # Metadata
    program_id: Optional[str] = None
    round_id: Optional[str] = None
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    status: ApplicationStatus = ApplicationStatus.PENDING
    
    # Raw data
    raw_submission: Dict[str, Any] = field(default_factory=dict)
    
    # Links
    website: Optional[str] = None
    github: Optional[str] = None
    demo: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "description": self.description,
            "team_name": self.team_name,
            "team_id": self.team_id,
            "team_members": [vars(m) for m in self.team_members],
            "problem_statement": self.problem_statement,
            "proposed_solution": self.proposed_solution,
            "technical_approach": self.technical_approach,
            "prior_work": self.prior_work,
            "funding_requested": self.funding_requested,
            "funding_currency": self.funding_currency,
            "budget_breakdown": [vars(b) for b in self.budget_breakdown],
            "milestones": [vars(m) for m in self.milestones],
            "program_id": self.program_id,
            "round_id": self.round_id,
            "submitted_at": self.submitted_at.isoformat(),
            "status": self.status.value,
            "raw_submission": self.raw_submission,
            "website": self.website,
            "github": self.github,
            "demo": self.demo,
        }


@dataclass
class AgentEvaluation:
    """An evaluation from a single agent."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    application_id: str = ""
    agent_id: str = ""
    agent_name: str = ""
    
    # Core evaluation
    score: float = 0.0  # 0-1
    recommendation: Recommendation = Recommendation.NEEDS_REVIEW
    confidence: float = 0.0  # 0-1
    
    # Reasoning
    rationale: str = ""
    strengths: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    questions: List[str] = field(default_factory=list)
    
    # Context used
    observations_used: List[str] = field(default_factory=list)
    similar_applications: List[str] = field(default_factory=list)
    
    # Deliberation
    is_revised: bool = False
    original_score: Optional[float] = None
    revision_rationale: Optional[str] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    deliberation_round: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "application_id": self.application_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "score": self.score,
            "recommendation": self.recommendation.value,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "strengths": self.strengths,
            "concerns": self.concerns,
            "questions": self.questions,
            "observations_used": self.observations_used,
            "similar_applications": self.similar_applications,
            "is_revised": self.is_revised,
            "original_score": self.original_score,
            "revision_rationale": self.revision_rationale,
            "created_at": self.created_at.isoformat(),
            "deliberation_round": self.deliberation_round,
        }


@dataclass
class Observation:
    """A learned pattern from an agent."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    
    # Pattern
    pattern: str = ""  # The learned insight
    evidence: List[str] = field(default_factory=list)  # Application IDs supporting this
    
    # Classification
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0
    status: ObservationStatus = ObservationStatus.DRAFT
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    validated_at: Optional[datetime] = None
    validated_by: Optional[str] = None
    
    # Performance tracking
    times_used: int = 0
    times_helpful: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "pattern": self.pattern,
            "evidence": self.evidence,
            "tags": self.tags,
            "confidence": self.confidence,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "validated_by": self.validated_by,
            "times_used": self.times_used,
            "times_helpful": self.times_helpful,
        }


@dataclass
class CouncilDecision:
    """Final decision from the council."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    application_id: str = ""
    
    # Aggregated results
    average_score: float = 0.0
    average_confidence: float = 0.0
    recommendation: Recommendation = Recommendation.NEEDS_REVIEW
    
    # Individual evaluations
    evaluations: List[AgentEvaluation] = field(default_factory=list)
    
    # Decision routing
    auto_executed: bool = False
    requires_human_review: bool = True
    review_reasons: List[str] = field(default_factory=list)
    
    # Human override
    human_decision: Optional[str] = None
    human_rationale: Optional[str] = None
    human_reviewer: Optional[str] = None
    
    # Synthesis
    synthesis: str = ""  # Combined rationale from all agents
    feedback_for_applicant: str = ""
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "application_id": self.application_id,
            "average_score": self.average_score,
            "average_confidence": self.average_confidence,
            "recommendation": self.recommendation.value,
            "evaluations": [e.to_dict() for e in self.evaluations],
            "auto_executed": self.auto_executed,
            "requires_human_review": self.requires_human_review,
            "review_reasons": self.review_reasons,
            "human_decision": self.human_decision,
            "human_rationale": self.human_rationale,
            "human_reviewer": self.human_reviewer,
            "synthesis": self.synthesis,
            "feedback_for_applicant": self.feedback_for_applicant,
            "created_at": self.created_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
        }
