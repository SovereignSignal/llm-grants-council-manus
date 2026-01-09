"""Council orchestration with deliberation and voting for the Grants Council."""

import json
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from .config import (
    COUNCIL_AGENTS, SYNTHESIS_MODEL,
    AUTO_APPROVE_THRESHOLD, AUTO_REJECT_THRESHOLD, BUDGET_REVIEW_THRESHOLD,
    MAX_DELIBERATION_ROUNDS, POSITION_CHANGE_THRESHOLD
)
from .models import (
    Application, AgentEvaluation, CouncilDecision,
    Recommendation, ApplicationStatus
)
from .llm_client import query_model, query_models_parallel, query_with_structured_output
from .agents import (
    evaluate_application, get_team_context,
    format_evaluations_for_deliberation
)
from .parser import format_application_for_evaluation
from .storage import (
    save_application, save_decision, update_application_status,
    get_application
)
from .learning import generate_observations_from_override


async def run_deliberation_round(
    application: Application,
    evaluations: List[AgentEvaluation],
    round_number: int
) -> List[AgentEvaluation]:
    """
    Run a deliberation round where agents can revise their positions.
    
    Each agent sees anonymized evaluations from others and can update
    their score, recommendation, and rationale.
    
    Args:
        application: The application being evaluated
        evaluations: Current evaluations from all agents
        round_number: Which deliberation round this is
    
    Returns:
        Updated list of evaluations (may include revisions)
    """
    # Format other evaluations for each agent to see
    all_evaluations_text = format_evaluations_for_deliberation(evaluations, anonymize=True)
    
    # Build deliberation prompts
    models_with_messages = []
    
    for eval_item in evaluations:
        agent_config = COUNCIL_AGENTS.get(eval_item.agent_id)
        if not agent_config:
            continue
        
        # Show this agent their own evaluation and others' (anonymized)
        prompt = f"""# Deliberation Round {round_number}

You previously evaluated this application. Now you can see how other evaluators assessed it.

## Your Previous Evaluation
**Score:** {eval_item.score:.2f} | **Recommendation:** {eval_item.recommendation.value} | **Confidence:** {eval_item.confidence:.0%}

**Rationale:** {eval_item.rationale}

**Strengths:** {', '.join(eval_item.strengths) if eval_item.strengths else 'None listed'}

**Concerns:** {', '.join(eval_item.concerns) if eval_item.concerns else 'None listed'}

---

## Other Evaluators' Assessments
{all_evaluations_text}

---

## Your Task

Review the other evaluations. Consider:
- Did others identify strengths or concerns you missed?
- Do their arguments change your assessment?
- Is there consensus or significant disagreement?

You may revise your position or maintain it. If revising, explain what changed your mind.

Respond with JSON:
{{
    "revised": true/false,
    "score": float 0-1,
    "recommendation": "approve" | "reject" | "needs_review",
    "confidence": float 0-1,
    "revision_rationale": "explanation of what changed (or why you're maintaining position)"
}}"""

        models_with_messages.append({
            "agent_id": eval_item.agent_id,
            "model": agent_config["model"],
            "messages": [
                {"role": "system", "content": "You are participating in a deliberation. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "original_eval": eval_item
        })
    
    # Query all agents in parallel
    responses = await query_models_parallel(
        models_with_messages,
        temperature=0.4,
        json_mode=True
    )
    
    # Process responses and update evaluations
    updated_evaluations = []
    
    for item in models_with_messages:
        agent_id = item["agent_id"]
        original_eval = item["original_eval"]
        response = responses.get(agent_id)
        
        if response is None:
            # Keep original evaluation
            updated_evaluations.append(original_eval)
            continue
        
        try:
            content = response['content']
            if '```' in content:
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            
            data = json.loads(content.strip())
            
            if data.get("revised", False):
                # Check if change is significant
                score_change = abs(data.get("score", original_eval.score) - original_eval.score)
                
                if score_change >= POSITION_CHANGE_THRESHOLD:
                    # Create revised evaluation
                    revised_eval = AgentEvaluation(
                        id=original_eval.id,
                        application_id=original_eval.application_id,
                        agent_id=original_eval.agent_id,
                        agent_name=original_eval.agent_name,
                        score=float(data.get("score", original_eval.score)),
                        recommendation=Recommendation(data.get("recommendation", original_eval.recommendation.value)),
                        confidence=float(data.get("confidence", original_eval.confidence)),
                        rationale=original_eval.rationale,  # Keep original rationale
                        strengths=original_eval.strengths,
                        concerns=original_eval.concerns,
                        questions=original_eval.questions,
                        observations_used=original_eval.observations_used,
                        is_revised=True,
                        original_score=original_eval.score,
                        revision_rationale=data.get("revision_rationale", ""),
                        deliberation_round=round_number,
                    )
                    updated_evaluations.append(revised_eval)
                else:
                    # Change too small, keep original
                    updated_evaluations.append(original_eval)
            else:
                # Agent chose not to revise
                updated_evaluations.append(original_eval)
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error parsing deliberation response for {agent_id}: {e}")
            updated_evaluations.append(original_eval)
    
    return updated_evaluations


def aggregate_evaluations(evaluations: List[AgentEvaluation]) -> Dict[str, Any]:
    """
    Aggregate individual evaluations into summary statistics.
    
    Args:
        evaluations: List of agent evaluations
    
    Returns:
        Dict with aggregated metrics
    """
    if not evaluations:
        return {
            "average_score": 0.5,
            "average_confidence": 0.0,
            "score_variance": 0.0,
            "recommendation_counts": {},
            "unanimous": False,
        }
    
    scores = [e.score for e in evaluations]
    confidences = [e.confidence for e in evaluations]
    recommendations = [e.recommendation.value for e in evaluations]
    
    avg_score = sum(scores) / len(scores)
    avg_confidence = sum(confidences) / len(confidences)
    
    # Calculate variance
    variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
    
    # Count recommendations
    rec_counts = {}
    for rec in recommendations:
        rec_counts[rec] = rec_counts.get(rec, 0) + 1
    
    # Check unanimity
    unanimous = len(set(recommendations)) == 1
    
    return {
        "average_score": avg_score,
        "average_confidence": avg_confidence,
        "score_variance": variance,
        "recommendation_counts": rec_counts,
        "unanimous": unanimous,
        "min_score": min(scores),
        "max_score": max(scores),
    }


def determine_routing(
    application: Application,
    aggregated: Dict[str, Any]
) -> Tuple[Recommendation, bool, List[str]]:
    """
    Determine whether to auto-execute or route to human review.
    
    Args:
        application: The application
        aggregated: Aggregated evaluation metrics
    
    Returns:
        Tuple of (recommendation, auto_execute, review_reasons)
    """
    review_reasons = []
    auto_execute = False
    
    avg_score = aggregated["average_score"]
    avg_confidence = aggregated["average_confidence"]
    unanimous = aggregated["unanimous"]
    variance = aggregated["score_variance"]
    
    # Determine base recommendation
    if avg_score >= AUTO_APPROVE_THRESHOLD:
        recommendation = Recommendation.APPROVE
    elif avg_score <= AUTO_REJECT_THRESHOLD:
        recommendation = Recommendation.REJECT
    else:
        recommendation = Recommendation.NEEDS_REVIEW
    
    # Check for auto-execution conditions
    if unanimous and avg_confidence >= 0.8:
        if recommendation == Recommendation.APPROVE:
            auto_execute = True
        elif recommendation == Recommendation.REJECT:
            auto_execute = True
    
    # Budget threshold check
    if application.funding_requested > BUDGET_REVIEW_THRESHOLD:
        auto_execute = False
        review_reasons.append(f"Budget exceeds ${BUDGET_REVIEW_THRESHOLD:,} threshold")
    
    # High variance check
    if variance > 0.1:
        auto_execute = False
        review_reasons.append("Significant disagreement among evaluators")
    
    # Low confidence check
    if avg_confidence < 0.6:
        auto_execute = False
        review_reasons.append("Low overall confidence in evaluation")
    
    # Split decision check
    rec_counts = aggregated["recommendation_counts"]
    if len(rec_counts) > 1:
        auto_execute = False
        review_reasons.append("Split recommendation from evaluators")
    
    # Edge case: borderline score
    if 0.4 <= avg_score <= 0.6:
        auto_execute = False
        if "Borderline score" not in review_reasons:
            review_reasons.append("Borderline score requires human judgment")
    
    return recommendation, auto_execute, review_reasons


async def synthesize_decision(
    application: Application,
    evaluations: List[AgentEvaluation],
    aggregated: Dict[str, Any],
    recommendation: Recommendation
) -> Tuple[str, str]:
    """
    Synthesize a final summary and applicant feedback.
    
    Args:
        application: The application
        evaluations: All agent evaluations
        aggregated: Aggregated metrics
        recommendation: Final recommendation
    
    Returns:
        Tuple of (synthesis, feedback_for_applicant)
    """
    # Build synthesis prompt
    evals_text = format_evaluations_for_deliberation(evaluations, anonymize=False)
    
    synthesis_prompt = f"""# Council Decision Synthesis

## Application Summary
**Title:** {application.title}
**Team:** {application.team_name}
**Funding Requested:** {application.funding_requested:,.2f} {application.funding_currency}

## Aggregated Results
- Average Score: {aggregated['average_score']:.2f}
- Average Confidence: {aggregated['average_confidence']:.0%}
- Recommendation: {recommendation.value.upper()}
- Unanimous: {"Yes" if aggregated['unanimous'] else "No"}

## Individual Evaluations
{evals_text}

---

Generate two outputs:

1. **SYNTHESIS**: A 2-3 paragraph summary of the council's assessment for program managers. Include:
   - Key points of agreement
   - Notable concerns raised
   - Any significant disagreements
   - Overall rationale for the recommendation

2. **APPLICANT_FEEDBACK**: Constructive feedback for the applicant (whether approved or rejected). Include:
   - Specific strengths identified
   - Areas for improvement
   - Questions that would strengthen future applications
   - If rejected, what would need to change for reconsideration

Respond with JSON:
{{
    "synthesis": "...",
    "applicant_feedback": "..."
}}"""

    messages = [
        {"role": "system", "content": "You are synthesizing a grants council decision. Be thorough but concise."},
        {"role": "user", "content": synthesis_prompt}
    ]
    
    result = await query_with_structured_output(
        SYNTHESIS_MODEL,
        messages,
        {"synthesis": "string", "applicant_feedback": "string"},
        temperature=0.5
    )
    
    if result and result.get('data'):
        return (
            result['data'].get('synthesis', 'Synthesis unavailable.'),
            result['data'].get('applicant_feedback', 'Feedback unavailable.')
        )
    
    # Fallback
    return (
        f"The council evaluated this application with an average score of {aggregated['average_score']:.2f}. Recommendation: {recommendation.value}.",
        "Thank you for your application. Please contact the program for detailed feedback."
    )


async def run_full_council(
    application: Application,
    max_deliberation_rounds: int = MAX_DELIBERATION_ROUNDS
) -> CouncilDecision:
    """
    Run the complete council evaluation process.
    
    1. Initial parallel evaluation by all agents
    2. Deliberation rounds where agents can revise
    3. Aggregation and routing decision
    4. Synthesis of final decision
    
    Args:
        application: The application to evaluate
        max_deliberation_rounds: Maximum deliberation rounds
    
    Returns:
        CouncilDecision object
    """
    # Update application status
    application.status = ApplicationStatus.EVALUATING
    save_application(application)
    
    # Get team context
    team_context = await get_team_context(application)
    
    # Stage 1: Initial evaluation
    evaluations = await evaluate_application(
        application,
        team_context=team_context,
        similar_applications=None  # TODO: Implement vector search
    )
    
    # Stage 2: Deliberation
    application.status = ApplicationStatus.DELIBERATING
    save_application(application)
    
    for round_num in range(1, max_deliberation_rounds + 1):
        evaluations = await run_deliberation_round(
            application,
            evaluations,
            round_num
        )
        
        # Check if positions have stabilized
        revisions = sum(1 for e in evaluations if e.is_revised and e.deliberation_round == round_num)
        if revisions == 0:
            break  # No changes, stop deliberating
    
    # Stage 3: Aggregate and route
    aggregated = aggregate_evaluations(evaluations)
    recommendation, auto_execute, review_reasons = determine_routing(application, aggregated)
    
    # Stage 4: Synthesize
    synthesis, feedback = await synthesize_decision(
        application,
        evaluations,
        aggregated,
        recommendation
    )
    
    # Build decision
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
    
    # Update application status
    if auto_execute:
        if recommendation == Recommendation.APPROVE:
            application.status = ApplicationStatus.AUTO_APPROVED
        else:
            application.status = ApplicationStatus.AUTO_REJECTED
        decision.decided_at = datetime.utcnow()
    else:
        application.status = ApplicationStatus.NEEDS_REVIEW
    
    save_application(application)
    save_decision(decision)
    
    return decision


async def record_human_decision(
    decision_id: str,
    human_decision: str,
    human_rationale: str,
    reviewer: str
) -> CouncilDecision:
    """
    Record a human override or confirmation of a council decision.
    
    Args:
        decision_id: The decision ID
        human_decision: "approve" or "reject"
        human_rationale: Explanation for the decision
        reviewer: Who made the decision
    
    Returns:
        Updated CouncilDecision
    """
    from .storage import get_decision
    
    decision = get_decision(decision_id)
    if not decision:
        raise ValueError(f"Decision {decision_id} not found")
    
    decision.human_decision = human_decision
    decision.human_rationale = human_rationale
    decision.human_reviewer = reviewer
    decision.decided_at = datetime.utcnow()
    
    # Update application status
    application = get_application(decision.application_id)
    if application:
        if human_decision == "approve":
            application.status = ApplicationStatus.APPROVED
        else:
            application.status = ApplicationStatus.REJECTED
        save_application(application)
    
    save_decision(decision)

    # Trigger learning loop if this was an override
    council_recommendation = decision.recommendation.value
    is_override = (
        (council_recommendation == "approve" and human_decision == "reject") or
        (council_recommendation == "reject" and human_decision == "approve") or
        (council_recommendation == "needs_review" and human_decision in ["approve", "reject"])
    )

    if is_override:
        # Generate observations from agents who were wrong
        # Run async in background - don't block the response
        import asyncio
        asyncio.create_task(
            generate_observations_from_override(decision, human_decision, human_rationale)
        )

    return decision


# ============ Title Generation ============

async def generate_evaluation_title(application: Application) -> str:
    """Generate a short title for an evaluation conversation."""
    prompt = f"""Generate a very short title (3-5 words) for this grant application evaluation.
    
Application: {application.title}
Team: {application.team_name}
Funding: ${application.funding_requested:,.0f}

Title:"""

    messages = [{"role": "user", "content": prompt}]
    
    response = await query_model(SYNTHESIS_MODEL, messages, timeout=30.0)
    
    if response is None:
        return f"Eval: {application.title[:30]}"
    
    title = response.get('content', '').strip().strip('"\'')
    return title[:50] if title else f"Eval: {application.title[:30]}"
