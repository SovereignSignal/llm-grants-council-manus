"""Agent evaluation logic for the Grants Council."""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .config import COUNCIL_AGENTS, EVALUATION_SCHEMA
from .models import (
    Application, AgentEvaluation, Observation, TeamProfile,
    Recommendation, ObservationStatus
)
from .llm_client import query_with_structured_output, query_models_parallel
from .storage import (
    get_observations_for_agent, get_team, find_team_by_name,
    find_team_by_wallet, save_observation
)
from .parser import format_application_for_evaluation


def get_agent_tags_for_application(application: Application) -> Dict[str, List[str]]:
    """
    Determine relevant tags for each agent based on application content.
    
    Args:
        application: The application to analyze
    
    Returns:
        Dict mapping agent_id to list of relevant tags
    """
    tags = {
        "technical": ["technical", "feasibility"],
        "ecosystem": ["ecosystem", "strategy"],
        "budget": ["budget", "cost"],
        "impact": ["impact", "value"],
    }
    
    # Add context-specific tags based on application content
    text = f"{application.title} {application.description} {application.technical_approach}".lower()
    
    if "infrastructure" in text or "sdk" in text or "api" in text:
        tags["technical"].append("infrastructure")
        tags["ecosystem"].append("infrastructure")
    
    if "defi" in text or "finance" in text or "trading" in text:
        tags["technical"].append("defi")
        tags["ecosystem"].append("defi")
        tags["impact"].append("defi")
    
    if "nft" in text or "gaming" in text or "metaverse" in text:
        tags["ecosystem"].append("consumer")
        tags["impact"].append("consumer")
    
    if "security" in text or "audit" in text:
        tags["technical"].append("security")
    
    if "education" in text or "documentation" in text:
        tags["ecosystem"].append("education")
        tags["impact"].append("education")
    
    return tags


async def get_team_context(application: Application) -> Optional[Dict[str, Any]]:
    """
    Retrieve team profile and history for context.
    
    Args:
        application: The application
    
    Returns:
        Team context dict or None
    """
    team = None
    
    # Try to find by team_id first
    if application.team_id:
        team = get_team(application.team_id)
    
    # Try by team name
    if not team and application.team_name:
        team = find_team_by_name(application.team_name)
    
    # Try by wallet addresses
    if not team:
        for member in application.team_members:
            if member.wallet_address:
                team = find_team_by_wallet(member.wallet_address)
                if team:
                    break
    
    if not team:
        return None
    
    return {
        "team_id": team.id,
        "canonical_name": team.canonical_name,
        "previous_applications": len(team.application_ids),
        "successful_grants": team.successful_grants,
        "failed_grants": team.failed_grants,
        "total_funded": team.total_funded,
        "milestone_completion_rate": team.milestone_completion_rate,
        "reputation_signals": team.reputation_signals,
    }


def build_agent_prompt(
    agent_id: str,
    application: Application,
    observations: List[Observation],
    team_context: Optional[Dict[str, Any]] = None,
    similar_applications: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Build the evaluation prompt for an agent.
    
    Args:
        agent_id: The agent identifier
        application: The application to evaluate
        observations: Relevant learned observations
        team_context: Team history if available
        similar_applications: Similar past applications with outcomes
    
    Returns:
        Complete prompt string
    """
    agent_config = COUNCIL_AGENTS[agent_id]
    
    sections = []
    
    # Character prompt
    sections.append("# Your Role")
    sections.append(agent_config["character"])
    sections.append("")
    
    # Learned observations
    if observations:
        sections.append("# Patterns You've Learned")
        sections.append("Based on your experience reviewing applications, you've observed:")
        for obs in observations[:5]:  # Top 5 most relevant
            sections.append(f"- {obs.pattern} (confidence: {obs.confidence:.0%})")
        sections.append("")
    
    # Team context
    if team_context:
        sections.append("# Team History")
        sections.append(f"This team ({team_context['canonical_name']}) has applied before:")
        sections.append(f"- Previous applications: {team_context['previous_applications']}")
        sections.append(f"- Successful grants: {team_context['successful_grants']}")
        sections.append(f"- Failed grants: {team_context['failed_grants']}")
        if team_context['total_funded'] > 0:
            sections.append(f"- Total previously funded: ${team_context['total_funded']:,.2f}")
        if team_context['milestone_completion_rate'] > 0:
            sections.append(f"- Milestone completion rate: {team_context['milestone_completion_rate']:.0%}")
        sections.append("")
    
    # Similar applications
    if similar_applications:
        sections.append("# Similar Past Applications")
        sections.append("For reference, here are similar applications and their outcomes:")
        for sim in similar_applications[:3]:
            outcome = "✓ Approved" if sim.get("approved") else "✗ Rejected"
            sections.append(f"- **{sim.get('title')}**: {outcome}")
            if sim.get("outcome_notes"):
                sections.append(f"  Outcome: {sim['outcome_notes']}")
        sections.append("")
    
    # The application
    sections.append("# Application to Evaluate")
    sections.append(format_application_for_evaluation(application))
    sections.append("")
    
    # Output instructions
    sections.append("# Your Evaluation")
    sections.append("""Provide your evaluation as JSON with these fields:
- score: float 0-1 (0 = strong reject, 0.5 = uncertain, 1 = strong approve)
- recommendation: "approve" | "reject" | "needs_review"
- confidence: float 0-1 (how confident you are in your assessment)
- rationale: string (2-3 paragraphs explaining your reasoning)
- strengths: list of strings (specific positives you identified)
- concerns: list of strings (specific issues or red flags)
- questions: list of strings (questions you'd want answered before deciding)

Be specific. Reference concrete details from the application. Explain your reasoning.""")
    
    return "\n".join(sections)


async def evaluate_application(
    application: Application,
    team_context: Optional[Dict[str, Any]] = None,
    similar_applications: Optional[List[Dict[str, Any]]] = None
) -> List[AgentEvaluation]:
    """
    Run all agents in parallel to evaluate an application.
    
    Args:
        application: The application to evaluate
        team_context: Team history if available
        similar_applications: Similar past applications
    
    Returns:
        List of AgentEvaluation objects
    """
    # Get relevant tags for each agent
    agent_tags = get_agent_tags_for_application(application)
    
    # Build prompts for each agent
    models_with_messages = []
    
    for agent_id, agent_config in COUNCIL_AGENTS.items():
        # Get relevant observations for this agent
        observations = get_observations_for_agent(
            agent_id,
            tags=agent_tags.get(agent_id, []),
            status=ObservationStatus.ACTIVE,
            limit=5
        )

        # Track observation usage
        for obs in observations:
            obs.times_used = (obs.times_used or 0) + 1
            save_observation(obs)

        prompt = build_agent_prompt(
            agent_id,
            application,
            observations,
            team_context,
            similar_applications
        )
        
        models_with_messages.append({
            "agent_id": agent_id,
            "model": agent_config["model"],
            "messages": [
                {"role": "system", "content": "You are an expert grant evaluator. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "observations_used": [o.id for o in observations]
        })
    
    # Query all agents in parallel
    responses = await query_models_parallel(
        models_with_messages,
        temperature=0.5,
        json_mode=True
    )
    
    # Parse responses into evaluations
    evaluations = []
    
    for agent_id, response in responses.items():
        agent_config = COUNCIL_AGENTS[agent_id]
        
        if response is None:
            # Agent failed - create placeholder evaluation
            evaluations.append(AgentEvaluation(
                application_id=application.id,
                agent_id=agent_id,
                agent_name=agent_config["name"],
                score=0.5,
                recommendation=Recommendation.NEEDS_REVIEW,
                confidence=0.0,
                rationale="Agent failed to respond.",
                concerns=["Evaluation could not be completed"],
            ))
            continue
        
        try:
            content = response['content']
            # Handle markdown code blocks
            if '```' in content:
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            
            data = json.loads(content.strip())

            # Debug: print the parsed data
            print(f"[DEBUG] Agent {agent_id} evaluation data:")
            print(f"  - rationale: {str(data.get('rationale', 'MISSING'))[:100]}...")
            print(f"  - strengths: {data.get('strengths', 'MISSING')}")
            print(f"  - concerns: {data.get('concerns', 'MISSING')}")
            print(f"  - questions: {data.get('questions', 'MISSING')}")

            # Find observations used
            obs_used = []
            for item in models_with_messages:
                if item["agent_id"] == agent_id:
                    obs_used = item.get("observations_used", [])
                    break
            
            evaluation = AgentEvaluation(
                application_id=application.id,
                agent_id=agent_id,
                agent_name=agent_config["name"],
                score=float(data.get("score", 0.5)),
                recommendation=Recommendation(data.get("recommendation", "needs_review")),
                confidence=float(data.get("confidence", 0.5)),
                rationale=data.get("rationale", ""),
                strengths=data.get("strengths", []),
                concerns=data.get("concerns", []),
                questions=data.get("questions", []),
                observations_used=obs_used,
                deliberation_round=0,
            )
            
            evaluations.append(evaluation)
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error parsing {agent_id} response: {e}")
            evaluations.append(AgentEvaluation(
                application_id=application.id,
                agent_id=agent_id,
                agent_name=agent_config["name"],
                score=0.5,
                recommendation=Recommendation.NEEDS_REVIEW,
                confidence=0.0,
                rationale=f"Error parsing evaluation: {str(e)}",
                concerns=["Evaluation parsing failed"],
            ))
    
    return evaluations


def format_evaluations_for_deliberation(
    evaluations: List[AgentEvaluation],
    anonymize: bool = True
) -> str:
    """
    Format evaluations for the deliberation round.
    
    Args:
        evaluations: List of agent evaluations
        anonymize: Whether to hide agent identities
    
    Returns:
        Formatted string of all evaluations
    """
    sections = []
    
    labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    
    for i, eval in enumerate(evaluations):
        if anonymize:
            header = f"## Evaluator {labels[i]}"
        else:
            header = f"## {eval.agent_name}"
        
        sections.append(header)
        sections.append(f"**Score:** {eval.score:.2f} | **Recommendation:** {eval.recommendation.value} | **Confidence:** {eval.confidence:.0%}")
        sections.append("")
        sections.append("### Rationale")
        sections.append(eval.rationale)
        sections.append("")
        
        if eval.strengths:
            sections.append("### Strengths")
            for s in eval.strengths:
                sections.append(f"- {s}")
            sections.append("")
        
        if eval.concerns:
            sections.append("### Concerns")
            for c in eval.concerns:
                sections.append(f"- {c}")
            sections.append("")
        
        if eval.questions:
            sections.append("### Questions")
            for q in eval.questions:
                sections.append(f"- {q}")
            sections.append("")
        
        sections.append("---")
        sections.append("")
    
    return "\n".join(sections)
