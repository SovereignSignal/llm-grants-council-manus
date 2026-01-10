"""SQLAlchemy database models with pgvector support for the Grants Council."""

import os
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    create_engine, Column, String, Float, Integer, Boolean,
    DateTime, Text, ForeignKey, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.dialects.postgresql import ARRAY

# Conditionally import pgvector
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None

from .models import ApplicationStatus, Recommendation, ObservationStatus


# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/grants_council.db")

# Handle Railway's postgres:// URL format (needs postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_uuid():
    """Generate a new UUID string."""
    return str(uuid.uuid4())


# ============ Database Models ============

class ApplicationDB(Base):
    """SQLAlchemy model for grant applications."""
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Basic info
    title = Column(String(500), nullable=False, default="")
    summary = Column(Text, default="")
    description = Column(Text, default="")

    # Team info
    team_name = Column(String(255), default="")
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=True)
    team_members = Column(JSON, default=list)  # List of TeamMember dicts

    # Project details
    problem_statement = Column(Text, default="")
    proposed_solution = Column(Text, default="")
    technical_approach = Column(Text, default="")
    prior_work = Column(Text, default="")

    # Funding
    funding_requested = Column(Float, default=0.0)
    funding_currency = Column(String(10), default="USD")
    budget_breakdown = Column(JSON, default=list)  # List of BudgetItem dicts
    milestones = Column(JSON, default=list)  # List of Milestone dicts

    # Metadata
    program_id = Column(String(100), nullable=True)
    round_id = Column(String(100), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default=ApplicationStatus.PENDING.value)

    # Raw data
    raw_submission = Column(JSON, default=dict)

    # Links
    website = Column(String(500), nullable=True)
    github = Column(String(500), nullable=True)
    demo = Column(String(500), nullable=True)

    # Vector embedding for similarity search (pgvector)
    # Only added if pgvector is available
    # embedding = Column(Vector(1536), nullable=True)  # OpenAI embedding dimension

    # Outcome tracking
    outcome = Column(String(50), nullable=True)  # success, failure
    outcome_notes = Column(Text, nullable=True)
    outcome_recorded_at = Column(DateTime, nullable=True)

    # Relationships
    team = relationship("TeamDB", back_populates="applications")
    decisions = relationship("DecisionDB", back_populates="application")

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "description": self.description,
            "team_name": self.team_name,
            "team_id": self.team_id,
            "team_members": self.team_members or [],
            "problem_statement": self.problem_statement,
            "proposed_solution": self.proposed_solution,
            "technical_approach": self.technical_approach,
            "prior_work": self.prior_work,
            "funding_requested": self.funding_requested,
            "funding_currency": self.funding_currency,
            "budget_breakdown": self.budget_breakdown or [],
            "milestones": self.milestones or [],
            "program_id": self.program_id,
            "round_id": self.round_id,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "status": self.status,
            "raw_submission": self.raw_submission or {},
            "website": self.website,
            "github": self.github,
            "demo": self.demo,
            "outcome": self.outcome,
            "outcome_notes": self.outcome_notes,
        }


class TeamDB(Base):
    """SQLAlchemy model for team profiles."""
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    canonical_name = Column(String(255), nullable=False, default="")
    aliases = Column(JSON, default=list)  # List of name aliases
    members = Column(JSON, default=list)  # List of TeamMember dicts
    wallet_addresses = Column(JSON, default=list)  # List of wallet addresses
    application_ids = Column(JSON, default=list)  # List of application IDs

    # Performance tracking
    successful_grants = Column(Integer, default=0)
    failed_grants = Column(Integer, default=0)
    total_funded = Column(Float, default=0.0)
    milestone_completion_rate = Column(Float, default=0.0)

    # Reputation signals
    reputation_signals = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    applications = relationship("ApplicationDB", back_populates="team")

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "canonical_name": self.canonical_name,
            "aliases": self.aliases or [],
            "members": self.members or [],
            "wallet_addresses": self.wallet_addresses or [],
            "application_ids": self.application_ids or [],
            "successful_grants": self.successful_grants,
            "failed_grants": self.failed_grants,
            "total_funded": self.total_funded,
            "milestone_completion_rate": self.milestone_completion_rate,
            "reputation_signals": self.reputation_signals or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ObservationDB(Base):
    """SQLAlchemy model for agent observations/learnings."""
    __tablename__ = "observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(50), nullable=False)

    # Pattern
    pattern = Column(Text, nullable=False)  # The learned insight
    evidence = Column(JSON, default=list)  # Application IDs supporting this

    # Classification
    tags = Column(JSON, default=list)
    confidence = Column(Float, default=0.0)
    status = Column(String(20), default=ObservationStatus.DRAFT.value)

    # Validation
    validated_at = Column(DateTime, nullable=True)
    validated_by = Column(String(100), nullable=True)

    # Performance tracking
    times_used = Column(Integer, default=0)
    times_helpful = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "pattern": self.pattern,
            "evidence": self.evidence or [],
            "tags": self.tags or [],
            "confidence": self.confidence,
            "status": self.status,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "validated_by": self.validated_by,
            "times_used": self.times_used,
            "times_helpful": self.times_helpful,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EvaluationDB(Base):
    """SQLAlchemy model for individual agent evaluations."""
    __tablename__ = "evaluations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    decision_id = Column(String(36), ForeignKey("decisions.id"), nullable=False)
    application_id = Column(String(36), nullable=False)
    agent_id = Column(String(50), nullable=False)
    agent_name = Column(String(100), default="")

    # Core evaluation
    score = Column(Float, default=0.0)  # 0-1
    recommendation = Column(String(20), default=Recommendation.NEEDS_REVIEW.value)
    confidence = Column(Float, default=0.0)  # 0-1

    # Reasoning
    rationale = Column(Text, default="")
    strengths = Column(JSON, default=list)
    concerns = Column(JSON, default=list)
    questions = Column(JSON, default=list)

    # Context used
    observations_used = Column(JSON, default=list)
    similar_applications = Column(JSON, default=list)

    # Deliberation
    is_revised = Column(Boolean, default=False)
    original_score = Column(Float, nullable=True)
    revision_rationale = Column(Text, nullable=True)
    deliberation_round = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    decision = relationship("DecisionDB", back_populates="evaluations")

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "decision_id": self.decision_id,
            "application_id": self.application_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "score": self.score,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "strengths": self.strengths or [],
            "concerns": self.concerns or [],
            "questions": self.questions or [],
            "observations_used": self.observations_used or [],
            "similar_applications": self.similar_applications or [],
            "is_revised": self.is_revised,
            "original_score": self.original_score,
            "revision_rationale": self.revision_rationale,
            "deliberation_round": self.deliberation_round,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DecisionDB(Base):
    """SQLAlchemy model for council decisions."""
    __tablename__ = "decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False)

    # Aggregated results
    average_score = Column(Float, default=0.0)
    average_confidence = Column(Float, default=0.0)
    recommendation = Column(String(20), default=Recommendation.NEEDS_REVIEW.value)

    # Decision routing
    auto_executed = Column(Boolean, default=False)
    requires_human_review = Column(Boolean, default=True)
    review_reasons = Column(JSON, default=list)

    # Human override
    human_decision = Column(String(20), nullable=True)  # approve, reject
    human_rationale = Column(Text, nullable=True)
    human_reviewer = Column(String(100), nullable=True)

    # Synthesis
    synthesis = Column(Text, default="")
    feedback_for_applicant = Column(Text, default="")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)

    # Relationships
    application = relationship("ApplicationDB", back_populates="decisions")
    evaluations = relationship("EvaluationDB", back_populates="decision", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "application_id": self.application_id,
            "average_score": self.average_score,
            "average_confidence": self.average_confidence,
            "recommendation": self.recommendation,
            "auto_executed": self.auto_executed,
            "requires_human_review": self.requires_human_review,
            "review_reasons": self.review_reasons or [],
            "human_decision": self.human_decision,
            "human_rationale": self.human_rationale,
            "human_reviewer": self.human_reviewer,
            "synthesis": self.synthesis,
            "feedback_for_applicant": self.feedback_for_applicant,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "evaluations": [e.to_dict() for e in self.evaluations] if self.evaluations else [],
        }


class ConversationDB(Base):
    """SQLAlchemy model for UI conversations."""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), default="New Evaluation")
    application_id = Column(String(36), nullable=True)
    messages = Column(JSON, default=list)  # List of message dicts
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "application_id": self.application_id,
            "messages": self.messages or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ============ Database Initialization ============

def init_db():
    """Initialize the database, creating all tables."""
    # Enable pgvector extension if using PostgreSQL
    if not DATABASE_URL.startswith("sqlite") and PGVECTOR_AVAILABLE:
        from sqlalchemy import text
        with engine.connect() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
            except Exception as e:
                print(f"Note: Could not create pgvector extension: {e}")

    Base.metadata.create_all(bind=engine)
    print(f"Database initialized: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")


def is_postgres():
    """Check if we're using PostgreSQL."""
    return not DATABASE_URL.startswith("sqlite")


# ============ Helper Functions ============

def get_or_create_session():
    """Get a new database session."""
    return SessionLocal()
