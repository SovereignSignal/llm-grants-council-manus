"""Learning loop for agent observation generation and refinement."""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from .config import COUNCIL_AGENTS, SYNTHESIS_MODEL
from .models import (
    Observation, ObservationStatus, AgentEvaluation,
    CouncilDecision, Application
)
from .llm_client import query_with_structured_output
from .storage import (
    save_observation, get_observations_for_agent,
    get_application, get_decision, list_all_observations
)


async def generate_observations_from_override(
    decision: CouncilDecision,
    human_decision: str,
    human_rationale: str
) -> List[Observation]:
    """
    Generate new observations when a human overrides the council's decision.
    
    Each agent reflects on what they might have missed.
    
    Args:
        decision: The council decision that was overridden
        human_decision: The human's decision (approve/reject)
        human_rationale: The human's explanation
    
    Returns:
        List of draft observations for review
    """
    application = get_application(decision.application_id)
    if not application:
        return []
    
    observations = []
    
    for evaluation in decision.evaluations:
        agent_config = COUNCIL_AGENTS.get(evaluation.agent_id)
        if not agent_config:
            continue
        
        # Check if this agent's recommendation matched the human decision
        agent_agreed = (
            (evaluation.recommendation.value == "approve" and human_decision == "approve") or
            (evaluation.recommendation.value == "reject" and human_decision == "reject")
        )
        
        if agent_agreed:
            # Agent was correct, no need to reflect
            continue
        
        # Agent was wrong - generate reflection
        prompt = f"""# Learning from Override

You are the {agent_config['name']}. Your evaluation was overridden by a human reviewer.

## Your Original Evaluation
**Score:** {evaluation.score:.2f}
**Recommendation:** {evaluation.recommendation.value}
**Rationale:** {evaluation.rationale}
**Concerns:** {', '.join(evaluation.concerns) if evaluation.concerns else 'None'}

## Human Decision
**Decision:** {human_decision}
**Rationale:** {human_rationale}

## Application Summary
**Title:** {application.title}
**Team:** {application.team_name}
**Funding:** ${application.funding_requested:,.2f}

## Your Task

Reflect on what you might have missed or misjudged. Generate a pattern/observation that would help you make better decisions in similar future cases.

The observation should be:
- Specific and actionable
- Based on what the human reviewer saw that you missed
- Applicable to future similar applications

Respond with JSON:
{{
    "pattern": "A clear statement of the pattern or insight learned",
    "tags": ["list", "of", "relevant", "tags"],
    "confidence": 0.0-1.0
}}"""

        messages = [
            {"role": "system", "content": "You are reflecting on a decision to improve future evaluations."},
            {"role": "user", "content": prompt}
        ]
        
        result = await query_with_structured_output(
            agent_config["model"],
            messages,
            {"pattern": "string", "tags": "list", "confidence": "float"},
            temperature=0.5
        )
        
        if result and result.get('data'):
            data = result['data']
            observation = Observation(
                agent_id=evaluation.agent_id,
                pattern=data.get('pattern', ''),
                evidence=[decision.application_id],
                tags=data.get('tags', []),
                confidence=float(data.get('confidence', 0.5)),
                status=ObservationStatus.DRAFT,
            )
            save_observation(observation)
            observations.append(observation)
    
    return observations


async def generate_observations_from_outcome(
    application_id: str,
    outcome: str,
    outcome_notes: str
) -> List[Observation]:
    """
    Generate observations when we learn the outcome of a funded grant.
    
    Args:
        application_id: The application ID
        outcome: "success" or "failure"
        outcome_notes: Details about the outcome
    
    Returns:
        List of draft observations
    """
    application = get_application(application_id)
    decision = None
    
    # Find the decision for this application
    from .storage import get_decision_for_application
    decision = get_decision_for_application(application_id)
    
    if not application or not decision:
        return []
    
    observations = []
    
    for evaluation in decision.evaluations:
        agent_config = COUNCIL_AGENTS.get(evaluation.agent_id)
        if not agent_config:
            continue
        
        # Check if agent's prediction was correct
        agent_predicted_success = evaluation.recommendation.value == "approve"
        actual_success = outcome == "success"
        
        if agent_predicted_success == actual_success:
            # Agent was correct - reinforce their reasoning
            prompt_type = "reinforcement"
        else:
            # Agent was wrong - learn from mistake
            prompt_type = "correction"
        
        prompt = f"""# Learning from Outcome

You are the {agent_config['name']}. A grant you evaluated has completed, and we now know the outcome.

## Your Original Evaluation
**Score:** {evaluation.score:.2f}
**Recommendation:** {evaluation.recommendation.value}
**Confidence:** {evaluation.confidence:.0%}
**Rationale:** {evaluation.rationale}

## Actual Outcome
**Result:** {outcome.upper()}
**Notes:** {outcome_notes}

## Application Summary
**Title:** {application.title}
**Team:** {application.team_name}
**Funding:** ${application.funding_requested:,.2f}

## Your Task

{"You predicted correctly. What pattern in the application helped you make the right call? Articulate this so you can recognize similar patterns in the future." if prompt_type == "reinforcement" else "You predicted incorrectly. What did you miss? What pattern should you watch for in similar future applications?"}

Respond with JSON:
{{
    "pattern": "A clear statement of the pattern or insight",
    "tags": ["list", "of", "relevant", "tags"],
    "confidence": 0.0-1.0
}}"""

        messages = [
            {"role": "system", "content": "You are learning from grant outcomes to improve future evaluations."},
            {"role": "user", "content": prompt}
        ]
        
        result = await query_with_structured_output(
            agent_config["model"],
            messages,
            {"pattern": "string", "tags": "list", "confidence": "float"},
            temperature=0.5
        )
        
        if result and result.get('data'):
            data = result['data']
            observation = Observation(
                agent_id=evaluation.agent_id,
                pattern=data.get('pattern', ''),
                evidence=[application_id],
                tags=data.get('tags', []),
                confidence=float(data.get('confidence', 0.5)),
                status=ObservationStatus.DRAFT,
            )
            save_observation(observation)
            observations.append(observation)
    
    return observations


async def bootstrap_agent_observations(
    agent_id: str,
    historical_applications: List[Dict[str, Any]],
    target_observations: int = 30
) -> List[Observation]:
    """
    Bootstrap an agent's observations from historical data.
    
    Used during initial setup to give agents a foundation of knowledge.
    
    Args:
        agent_id: The agent to bootstrap
        historical_applications: List of past applications with outcomes
        target_observations: Target number of observations to generate
    
    Returns:
        List of draft observations
    """
    agent_config = COUNCIL_AGENTS.get(agent_id)
    if not agent_config:
        return []
    
    # Format historical data
    history_text = ""
    for i, app in enumerate(historical_applications[:50], 1):  # Limit to 50 for context
        outcome = "✓ Approved & Delivered" if app.get("success") else "✗ Failed/Rejected"
        history_text += f"""
{i}. **{app.get('title', 'Unknown')}**
   - Team: {app.get('team_name', 'Unknown')}
   - Funding: ${app.get('funding_requested', 0):,.0f}
   - Outcome: {outcome}
   - Notes: {app.get('outcome_notes', 'N/A')}
"""
    
    prompt = f"""# Bootstrap Your Expertise

You are the {agent_config['name']}. You're being initialized with historical grant data to develop your evaluation expertise.

## Your Role
{agent_config['character']}

## Historical Applications
{history_text}

## Your Task

Analyze these historical applications and their outcomes. Identify {target_observations} distinct patterns that would help you evaluate future applications.

Focus on patterns relevant to your role:
- {', '.join(agent_config['tags'])}

Each pattern should be:
- Specific and actionable
- Supported by at least 2-3 examples from the history
- Useful for predicting success or failure

Respond with JSON:
{{
    "observations": [
        {{
            "pattern": "Clear statement of the pattern",
            "evidence_indices": [1, 5, 12],
            "tags": ["relevant", "tags"],
            "confidence": 0.0-1.0
        }},
        ...
    ]
}}"""

    messages = [
        {"role": "system", "content": "You are developing expertise from historical data."},
        {"role": "user", "content": prompt}
    ]
    
    result = await query_with_structured_output(
        agent_config["model"],
        messages,
        {"observations": "list"},
        temperature=0.6
    )
    
    observations = []
    
    if result and result.get('data'):
        for obs_data in result['data'].get('observations', []):
            # Map evidence indices to application IDs
            evidence_indices = obs_data.get('evidence_indices', [])
            evidence_ids = []
            for idx in evidence_indices:
                if 0 < idx <= len(historical_applications):
                    app = historical_applications[idx - 1]
                    if app.get('id'):
                        evidence_ids.append(app['id'])
            
            observation = Observation(
                agent_id=agent_id,
                pattern=obs_data.get('pattern', ''),
                evidence=evidence_ids,
                tags=obs_data.get('tags', []),
                confidence=float(obs_data.get('confidence', 0.5)),
                status=ObservationStatus.DRAFT,
            )
            save_observation(observation)
            observations.append(observation)
    
    return observations


def prune_stale_observations(
    min_evidence: int = 5,
    max_age_days: int = 180
) -> List[str]:
    """
    Identify observations that should be deprecated.
    
    Args:
        min_evidence: Minimum evidence count to keep
        max_age_days: Maximum age in days
    
    Returns:
        List of observation IDs to review for deprecation
    """
    from datetime import timedelta
    
    stale_ids = []
    cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
    
    all_observations = list_all_observations(status=ObservationStatus.ACTIVE)
    
    for obs in all_observations:
        # Check evidence count
        if len(obs.evidence) < min_evidence:
            stale_ids.append(obs.id)
            continue
        
        # Check age without recent use
        if obs.created_at < cutoff_date and obs.times_used < 10:
            stale_ids.append(obs.id)
    
    return stale_ids
