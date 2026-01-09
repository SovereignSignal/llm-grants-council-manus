"""FastAPI backend for the Grants Council."""

from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of backend/)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
from datetime import datetime

from . import storage
from .models import Application, ApplicationStatus, Recommendation
from .parser import parse_freeform_application, parse_structured_application
from .council import (
    run_full_council, record_human_decision, generate_evaluation_title
)

app = FastAPI(
    title="Grants Council API",
    description="AI-powered grant application evaluation system",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Request/Response Models ============

class SubmitApplicationRequest(BaseModel):
    """Request to submit a new application."""
    # Freeform text submission
    text: Optional[str] = None
    
    # Or structured submission
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    team_name: Optional[str] = None
    team_members: Optional[List[Dict[str, Any]]] = None
    problem_statement: Optional[str] = None
    proposed_solution: Optional[str] = None
    technical_approach: Optional[str] = None
    prior_work: Optional[str] = None
    funding_requested: Optional[float] = None
    funding_currency: Optional[str] = "USD"
    budget_breakdown: Optional[List[Dict[str, Any]]] = None
    milestones: Optional[List[Dict[str, Any]]] = None
    website: Optional[str] = None
    github: Optional[str] = None
    demo: Optional[str] = None
    
    # Metadata
    program_id: Optional[str] = None
    round_id: Optional[str] = None


class HumanDecisionRequest(BaseModel):
    """Request to record a human decision."""
    decision: str = Field(..., pattern="^(approve|reject)$")
    rationale: str
    reviewer: str


class ApplicationResponse(BaseModel):
    """Response with application details."""
    id: str
    title: str
    team_name: str
    funding_requested: float
    funding_currency: str
    status: str
    submitted_at: str


class DecisionResponse(BaseModel):
    """Response with decision details."""
    id: str
    application_id: str
    average_score: float
    average_confidence: float
    recommendation: str
    auto_executed: bool
    requires_human_review: bool
    review_reasons: List[str]
    synthesis: str
    feedback_for_applicant: str
    evaluations: List[Dict[str, Any]]


# ============ Health Check ============

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Grants Council API",
        "version": "1.0.0"
    }


# ============ Applications ============

@app.post("/api/applications", response_model=ApplicationResponse)
async def submit_application(
    request: SubmitApplicationRequest,
    background_tasks: BackgroundTasks
):
    """
    Submit a new grant application.
    
    Accepts either freeform text or structured data.
    """
    if request.text:
        # Parse freeform submission
        application = await parse_freeform_application(
            request.text,
            metadata={
                "program_id": request.program_id,
                "round_id": request.round_id,
            }
        )
    else:
        # Parse structured submission
        application = parse_structured_application(request.model_dump())
    
    # Save application
    storage.save_application(application)
    
    return ApplicationResponse(
        id=application.id,
        title=application.title,
        team_name=application.team_name,
        funding_requested=application.funding_requested,
        funding_currency=application.funding_currency,
        status=application.status.value,
        submitted_at=application.submitted_at.isoformat(),
    )


@app.get("/api/applications", response_model=List[ApplicationResponse])
async def list_applications(
    status: Optional[str] = None,
    program_id: Optional[str] = None,
    limit: int = 100
):
    """List applications with optional filters."""
    status_enum = ApplicationStatus(status) if status else None
    applications = storage.list_applications(
        status=status_enum,
        program_id=program_id,
        limit=limit
    )
    
    return [
        ApplicationResponse(
            id=app.id,
            title=app.title,
            team_name=app.team_name,
            funding_requested=app.funding_requested,
            funding_currency=app.funding_currency,
            status=app.status.value,
            submitted_at=app.submitted_at.isoformat(),
        )
        for app in applications
    ]


@app.get("/api/applications/{application_id}")
async def get_application(application_id: str):
    """Get a specific application with full details."""
    application = storage.get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    return application.to_dict()


# ============ Evaluations ============

@app.post("/api/applications/{application_id}/evaluate")
async def evaluate_application(application_id: str):
    """
    Trigger evaluation of an application by the council.
    
    This runs the full evaluation pipeline:
    1. Initial evaluation by all agents
    2. Deliberation rounds
    3. Aggregation and routing decision
    4. Synthesis of final decision
    """
    application = storage.get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    if application.status not in [ApplicationStatus.PENDING, ApplicationStatus.NEEDS_REVIEW]:
        raise HTTPException(
            status_code=400,
            detail=f"Application cannot be evaluated in status: {application.status.value}"
        )
    
    # Run the council evaluation
    decision = await run_full_council(application)
    
    return {
        "decision_id": decision.id,
        "application_id": application_id,
        "recommendation": decision.recommendation.value,
        "average_score": decision.average_score,
        "average_confidence": decision.average_confidence,
        "auto_executed": decision.auto_executed,
        "requires_human_review": decision.requires_human_review,
        "review_reasons": decision.review_reasons,
        "evaluations": [e.to_dict() for e in decision.evaluations],
        "synthesis": decision.synthesis,
        "feedback_for_applicant": decision.feedback_for_applicant,
    }


@app.post("/api/applications/{application_id}/evaluate/stream")
async def evaluate_application_stream(application_id: str):
    """
    Trigger evaluation with streaming progress updates.
    
    Returns Server-Sent Events as each stage completes.
    """
    application = storage.get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    async def event_generator():
        try:
            from .agents import evaluate_application as eval_app, get_team_context
            from .council import (
                run_deliberation_round, aggregate_evaluations,
                determine_routing, synthesize_decision
            )
            from .config import MAX_DELIBERATION_ROUNDS
            
            # Update status
            application.status = ApplicationStatus.EVALUATING
            storage.save_application(application)
            yield f"data: {json.dumps({'type': 'status', 'status': 'evaluating'})}\n\n"
            
            # Get team context
            team_context = await get_team_context(application)
            yield f"data: {json.dumps({'type': 'context', 'has_team_history': team_context is not None})}\n\n"
            
            # Stage 1: Initial evaluation
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'initial_evaluation', 'status': 'started'})}\n\n"
            evaluations = await eval_app(application, team_context=team_context)
            
            eval_summary = [
                {
                    "agent": e.agent_name,
                    "score": e.score,
                    "recommendation": e.recommendation.value,
                    "confidence": e.confidence,
                    "rationale": e.rationale,
                    "strengths": e.strengths,
                    "concerns": e.concerns,
                    "questions": e.questions
                }
                for e in evaluations
            ]
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'initial_evaluation', 'status': 'complete', 'evaluations': eval_summary})}\n\n"

            # Stage 2: Deliberation
            application.status = ApplicationStatus.DELIBERATING
            storage.save_application(application)

            for round_num in range(1, MAX_DELIBERATION_ROUNDS + 1):
                yield f"data: {json.dumps({'type': 'stage', 'stage': f'deliberation_round_{round_num}', 'status': 'started'})}\n\n"

                evaluations = await run_deliberation_round(application, evaluations, round_num)
                
                revisions = sum(1 for e in evaluations if e.is_revised and e.deliberation_round == round_num)
                yield f"data: {json.dumps({'type': 'stage', 'stage': f'deliberation_round_{round_num}', 'status': 'complete', 'revisions': revisions})}\n\n"
                
                if revisions == 0:
                    break
            
            # Stage 3: Aggregate and route
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'aggregation', 'status': 'started'})}\n\n"
            aggregated = aggregate_evaluations(evaluations)
            recommendation, auto_execute, review_reasons = determine_routing(application, aggregated)
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'aggregation', 'status': 'complete', 'recommendation': recommendation.value, 'auto_execute': auto_execute})}\n\n"
            
            # Stage 4: Synthesis
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'synthesis', 'status': 'started'})}\n\n"
            synthesis, feedback = await synthesize_decision(application, evaluations, aggregated, recommendation)
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'synthesis', 'status': 'complete'})}\n\n"
            
            # Build and save decision
            from .models import CouncilDecision
            decision = CouncilDecision(
                application_id=application.id,
                average_score=aggregated["average_score"],
                average_confidence=aggregated["average_confidence"],
                recommendation=recommendation,
                evaluations=evaluations,
                auto_executed=auto_execute,
                requires_human_review=not auto_execute,
                review_reasons=review_reasons,
                synthesis=synthesis,
                feedback_for_applicant=feedback,
            )
            
            if auto_execute:
                if recommendation == Recommendation.APPROVE:
                    application.status = ApplicationStatus.AUTO_APPROVED
                else:
                    application.status = ApplicationStatus.AUTO_REJECTED
                decision.decided_at = datetime.utcnow()
            else:
                application.status = ApplicationStatus.NEEDS_REVIEW
            
            storage.save_application(application)
            storage.save_decision(decision)
            
            # Final result
            yield f"data: {json.dumps({'type': 'complete', 'decision_id': decision.id, 'recommendation': recommendation.value})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============ Decisions ============

@app.get("/api/decisions")
async def list_decisions(
    requires_review: Optional[bool] = None,
    limit: int = 100
):
    """List decisions with optional filters."""
    decisions = storage.list_decisions(
        requires_review=requires_review,
        limit=limit
    )
    
    return [
        {
            "id": d.id,
            "application_id": d.application_id,
            "recommendation": d.recommendation.value,
            "average_score": d.average_score,
            "requires_human_review": d.requires_human_review,
            "auto_executed": d.auto_executed,
            "human_decision": d.human_decision,
            "created_at": d.created_at.isoformat(),
        }
        for d in decisions
    ]


@app.get("/api/decisions/{decision_id}")
async def get_decision(decision_id: str):
    """Get a specific decision with full details."""
    decision = storage.get_decision(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    return decision.to_dict()


@app.post("/api/decisions/{decision_id}/human-decision")
async def submit_human_decision(decision_id: str, request: HumanDecisionRequest):
    """
    Record a human decision (approval or rejection).
    
    This is used when the council routes a decision for human review,
    or when a human wants to override an auto-executed decision.
    """
    try:
        decision = await record_human_decision(
            decision_id,
            request.decision,
            request.rationale,
            request.reviewer
        )
        
        return {
            "id": decision.id,
            "application_id": decision.application_id,
            "human_decision": decision.human_decision,
            "human_rationale": decision.human_rationale,
            "human_reviewer": decision.human_reviewer,
            "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============ Outcome Recording ============

class OutcomeRequest(BaseModel):
    """Request to record the outcome of a funded grant."""
    outcome: str = Field(..., pattern="^(success|failure)$")
    notes: str = Field(..., min_length=10)


@app.post("/api/applications/{application_id}/outcome")
async def record_outcome(application_id: str, request: OutcomeRequest):
    """
    Record the outcome of a funded grant.

    This triggers the learning loop - agents reflect on whether their
    predictions were correct and generate observations accordingly.

    Args:
        application_id: The application ID
        outcome: "success" or "failure"
        notes: Details about the outcome (at least 10 characters)
    """
    from .learning import generate_observations_from_outcome

    application = storage.get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Check that application was approved
    if application.status not in [ApplicationStatus.APPROVED, ApplicationStatus.AUTO_APPROVED]:
        raise HTTPException(
            status_code=400,
            detail=f"Can only record outcomes for approved applications. Current status: {application.status.value}"
        )

    # Generate observations from agents based on outcome
    observations = await generate_observations_from_outcome(
        application_id,
        request.outcome,
        request.notes
    )

    return {
        "application_id": application_id,
        "outcome": request.outcome,
        "observations_generated": len(observations),
        "observation_ids": [o.id for o in observations],
        "message": f"Outcome recorded. {len(observations)} draft observations generated for review."
    }


# ============ Observations (Agent Learning) ============

@app.get("/api/observations")
async def list_observations(
    agent_id: Optional[str] = None,
    status: Optional[str] = None
):
    """List agent observations (learned patterns)."""
    from .models import ObservationStatus
    
    status_enum = ObservationStatus(status) if status else None
    observations = storage.list_all_observations(
        agent_id=agent_id,
        status=status_enum
    )
    
    return [o.to_dict() for o in observations]


@app.post("/api/observations/{observation_id}/activate")
async def activate_observation(observation_id: str, reviewer: str):
    """Activate a draft observation after human review."""
    from .models import ObservationStatus
    
    observation = storage.get_observation(observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")
    
    observation.status = ObservationStatus.ACTIVE
    observation.validated_at = datetime.utcnow()
    observation.validated_by = reviewer
    storage.save_observation(observation)
    
    return observation.to_dict()


@app.post("/api/observations/{observation_id}/helpful")
async def mark_observation_helpful(observation_id: str):
    """Mark an observation as helpful (used in a successful evaluation)."""
    observation = storage.get_observation(observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")

    observation.times_helpful = (observation.times_helpful or 0) + 1
    storage.save_observation(observation)

    return {
        "id": observation.id,
        "times_used": observation.times_used,
        "times_helpful": observation.times_helpful,
    }


@app.post("/api/observations/{observation_id}/deprecate")
async def deprecate_observation(observation_id: str, reason: str = ""):
    """Deprecate an observation (mark as no longer useful)."""
    from .models import ObservationStatus

    observation = storage.get_observation(observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")

    observation.status = ObservationStatus.DEPRECATED
    storage.save_observation(observation)

    return {"id": observation.id, "status": "deprecated", "reason": reason}


@app.post("/api/observations/prune")
async def prune_observations(
    min_evidence: int = 5,
    max_age_days: int = 180,
    auto_deprecate: bool = False
):
    """
    Identify stale observations that should be deprecated.

    Args:
        min_evidence: Minimum evidence count to keep (default: 5)
        max_age_days: Maximum age in days without sufficient usage (default: 180)
        auto_deprecate: If True, automatically deprecate stale observations
    """
    from .learning import prune_stale_observations
    from .models import ObservationStatus

    stale_ids = prune_stale_observations(min_evidence, max_age_days)

    if auto_deprecate:
        for obs_id in stale_ids:
            observation = storage.get_observation(obs_id)
            if observation:
                observation.status = ObservationStatus.DEPRECATED
                storage.save_observation(observation)

    return {
        "stale_observation_count": len(stale_ids),
        "stale_observation_ids": stale_ids,
        "auto_deprecated": auto_deprecate,
    }


# ============ Teams ============

@app.get("/api/teams/{team_id}")
async def get_team(team_id: str):
    """Get a team profile."""
    team = storage.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return {
        "id": team.id,
        "canonical_name": team.canonical_name,
        "aliases": team.aliases,
        "members": [vars(m) for m in team.members],
        "application_ids": team.application_ids,
        "successful_grants": team.successful_grants,
        "failed_grants": team.failed_grants,
        "total_funded": team.total_funded,
        "milestone_completion_rate": team.milestone_completion_rate,
    }


# ============ Conversations (for UI) ============

@app.get("/api/conversations")
async def list_conversations():
    """List all conversations."""
    return storage.list_conversations()


@app.post("/api/conversations")
async def create_conversation():
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    return storage.create_conversation(conversation_id)


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a conversation with all messages."""
    conversation = storage.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


class MessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: MessageRequest):
    """
    Send a message and receive streaming evaluation updates.

    The message can be:
    - A URL to a grant application (will be fetched and parsed)
    - Plain text describing a grant application
    """
    import httpx
    import re

    conversation = storage.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    content = request.content.strip()

    async def event_generator():
        try:
            # Save user message
            storage.add_message_to_conversation(conversation_id, "user", content)
            yield f"data: {json.dumps({'type': 'message_received', 'content': content})}\n\n"

            # Check if content is a URL
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, content)

            application_text = content

            if urls:
                # Fetch content from URL
                yield f"data: {json.dumps({'type': 'status', 'message': 'Fetching application from URL...'})}\n\n"

                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(urls[0], follow_redirects=True)
                        response.raise_for_status()

                        # Extract text content (basic HTML stripping)
                        html_content = response.text
                        # Simple HTML tag removal
                        import re as re_module
                        text_content = re_module.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re_module.DOTALL)
                        text_content = re_module.sub(r'<style[^>]*>.*?</style>', '', text_content, flags=re_module.DOTALL)
                        text_content = re_module.sub(r'<[^>]+>', ' ', text_content)
                        text_content = re_module.sub(r'\s+', ' ', text_content).strip()

                        application_text = text_content[:15000]  # Limit size

                        yield f"data: {json.dumps({'type': 'status', 'message': 'Application content fetched successfully'})}\n\n"

                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to fetch URL: {str(e)}'})}\n\n"
                    return

            # Parse as application
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'parsing', 'status': 'started'})}\n\n"

            try:
                application = await parse_freeform_application(
                    application_text,
                    metadata={"source_url": urls[0] if urls else None}
                )
                storage.save_application(application)

                # Update conversation with application
                conv = storage.get_conversation(conversation_id)
                conv["application_id"] = application.id
                conv["title"] = application.title[:50] if application.title else "Grant Evaluation"
                storage.save_conversation(conv)

                yield f"data: {json.dumps({'type': 'stage', 'stage': 'parsing', 'status': 'complete', 'application': {'id': application.id, 'title': application.title, 'team': application.team_name, 'funding': application.funding_requested}})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to parse application: {str(e)}'})}\n\n"
                return

            # Run council evaluation
            from .agents import evaluate_application as eval_app, get_team_context
            from .council import (
                run_deliberation_round, aggregate_evaluations,
                determine_routing, synthesize_decision
            )
            from .config import MAX_DELIBERATION_ROUNDS

            # Update status
            application.status = ApplicationStatus.EVALUATING
            storage.save_application(application)
            yield f"data: {json.dumps({'type': 'status', 'message': 'Starting council evaluation...'})}\n\n"

            # Get team context
            team_context = await get_team_context(application)

            # Stage 1: Initial evaluation
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'initial_evaluation', 'status': 'started'})}\n\n"
            evaluations = await eval_app(application, team_context=team_context)

            eval_summary = [
                {
                    "agent": e.agent_name,
                    "score": e.score,
                    "recommendation": e.recommendation.value,
                    "confidence": e.confidence,
                    "rationale": e.rationale,
                    "strengths": e.strengths,
                    "concerns": e.concerns,
                    "questions": e.questions
                }
                for e in evaluations
            ]
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'initial_evaluation', 'status': 'complete', 'evaluations': eval_summary})}\n\n"

            # Stage 2: Deliberation
            application.status = ApplicationStatus.DELIBERATING
            storage.save_application(application)

            for round_num in range(1, MAX_DELIBERATION_ROUNDS + 1):
                yield f"data: {json.dumps({'type': 'stage', 'stage': f'deliberation_round_{round_num}', 'status': 'started'})}\n\n"

                evaluations = await run_deliberation_round(application, evaluations, round_num)

                revisions = sum(1 for e in evaluations if e.is_revised and e.deliberation_round == round_num)
                yield f"data: {json.dumps({'type': 'stage', 'stage': f'deliberation_round_{round_num}', 'status': 'complete', 'revisions': revisions})}\n\n"

                if revisions == 0:
                    break

            # Stage 3: Aggregate and route
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'aggregation', 'status': 'started'})}\n\n"
            aggregated = aggregate_evaluations(evaluations)
            recommendation, auto_execute, review_reasons = determine_routing(application, aggregated)
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'aggregation', 'status': 'complete', 'recommendation': recommendation.value, 'auto_execute': auto_execute})}\n\n"

            # Stage 4: Synthesis
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'synthesis', 'status': 'started'})}\n\n"
            synthesis, feedback = await synthesize_decision(application, evaluations, aggregated, recommendation)
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'synthesis', 'status': 'complete'})}\n\n"

            # Build and save decision
            from .models import CouncilDecision
            decision = CouncilDecision(
                application_id=application.id,
                average_score=aggregated["average_score"],
                average_confidence=aggregated["average_confidence"],
                recommendation=recommendation,
                evaluations=evaluations,
                auto_executed=auto_execute,
                requires_human_review=not auto_execute,
                review_reasons=review_reasons,
                synthesis=synthesis,
                feedback_for_applicant=feedback,
            )

            if auto_execute:
                if recommendation == Recommendation.APPROVE:
                    application.status = ApplicationStatus.AUTO_APPROVED
                else:
                    application.status = ApplicationStatus.AUTO_REJECTED
                decision.decided_at = datetime.utcnow()
            else:
                application.status = ApplicationStatus.NEEDS_REVIEW

            storage.save_application(application)
            storage.save_decision(decision)

            # Save assistant message with full results
            result_message = {
                "decision_id": decision.id,
                "recommendation": recommendation.value,
                "average_score": aggregated["average_score"],
                "synthesis": synthesis,
                "feedback": feedback,
                "evaluations": [e.to_dict() for e in evaluations],
            }
            storage.add_message_to_conversation(conversation_id, "assistant", result_message)

            # Final result
            yield f"data: {json.dumps({'type': 'complete', 'decision_id': decision.id, 'application_id': application.id, 'recommendation': recommendation.value, 'average_score': aggregated['average_score'], 'synthesis': synthesis, 'feedback': feedback})}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============ Webhook Endpoint ============

@app.post("/api/webhook/application")
async def webhook_application(payload: Dict[str, Any]):
    """
    Webhook endpoint for receiving applications from external systems.
    
    Accepts various payload formats and attempts to parse them.
    """
    # Try to extract application data from common webhook formats
    application_data = payload.get("application") or payload.get("data") or payload
    
    if "text" in application_data or "description" in application_data:
        text = application_data.get("text") or application_data.get("description", "")
        application = await parse_freeform_application(
            text,
            metadata=application_data.get("metadata", {})
        )
    else:
        application = parse_structured_application(application_data)
    
    storage.save_application(application)
    
    return {
        "status": "received",
        "application_id": application.id,
        "title": application.title,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
