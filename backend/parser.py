"""Proposal parsing and ingestion for the Grants Council."""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from .models import (
    Application, TeamMember, BudgetItem, Milestone, ApplicationStatus
)
from .llm_client import query_with_structured_output
from .config import SYNTHESIS_MODEL


async def parse_freeform_application(
    raw_text: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Application:
    """
    Parse a freeform application submission into structured data.
    
    Uses LLM to extract structured information from unstructured text.
    
    Args:
        raw_text: The raw application text
        metadata: Optional metadata (program_id, round_id, etc.)
    
    Returns:
        Structured Application object
    """
    extraction_prompt = """Extract structured information from this grant application.

APPLICATION TEXT:
{raw_text}

Extract the following information. If a field is not mentioned, use null or empty values.
Be thorough - extract all team members, budget items, and milestones mentioned."""

    output_schema = {
        "title": "string - project title",
        "summary": "string - one paragraph summary",
        "team_name": "string - name of the team/organization",
        "team_members": "array of {name, role, bio, github, twitter}",
        "problem_statement": "string - what problem does this solve",
        "proposed_solution": "string - how they plan to solve it",
        "technical_approach": "string - technical details and architecture",
        "prior_work": "string - relevant experience and past work",
        "funding_requested": "number - total funding amount",
        "funding_currency": "string - USD, ETH, etc.",
        "budget_breakdown": "array of {category, description, amount, justification}",
        "milestones": "array of {title, description, deliverables, timeline, funding_amount}",
        "website": "string or null",
        "github": "string or null",
        "demo": "string or null"
    }

    messages = [
        {"role": "system", "content": "You are an expert at extracting structured data from grant applications."},
        {"role": "user", "content": extraction_prompt.format(raw_text=raw_text)}
    ]

    result = await query_with_structured_output(
        SYNTHESIS_MODEL,
        messages,
        output_schema,
        temperature=0.3
    )

    if result is None:
        # Fallback to basic parsing
        return _basic_parse(raw_text, metadata)

    data = result['data']
    
    # Build Application object
    app = Application(
        title=data.get("title", "Untitled Application"),
        summary=data.get("summary", ""),
        description=raw_text[:2000],  # Store truncated raw text
        team_name=data.get("team_name", "Unknown Team"),
        problem_statement=data.get("problem_statement", ""),
        proposed_solution=data.get("proposed_solution", ""),
        technical_approach=data.get("technical_approach", ""),
        prior_work=data.get("prior_work", ""),
        funding_requested=float(data.get("funding_requested", 0) or 0),
        funding_currency=data.get("funding_currency", "USD"),
        website=data.get("website"),
        github=data.get("github"),
        demo=data.get("demo"),
        raw_submission={"text": raw_text, "metadata": metadata},
        status=ApplicationStatus.PENDING,
    )

    # Parse team members
    for member_data in data.get("team_members", []):
        if isinstance(member_data, dict):
            app.team_members.append(TeamMember(
                name=member_data.get("name", "Unknown"),
                role=member_data.get("role", "Team Member"),
                bio=member_data.get("bio"),
                github=member_data.get("github"),
                twitter=member_data.get("twitter"),
            ))

    # Parse budget
    for budget_data in data.get("budget_breakdown", []):
        if isinstance(budget_data, dict):
            app.budget_breakdown.append(BudgetItem(
                category=budget_data.get("category", "General"),
                description=budget_data.get("description", ""),
                amount=float(budget_data.get("amount", 0) or 0),
                justification=budget_data.get("justification"),
            ))

    # Parse milestones
    for ms_data in data.get("milestones", []):
        if isinstance(ms_data, dict):
            deliverables = ms_data.get("deliverables", [])
            if isinstance(deliverables, str):
                deliverables = [deliverables]
            
            app.milestones.append(Milestone(
                title=ms_data.get("title", "Milestone"),
                description=ms_data.get("description", ""),
                deliverables=deliverables,
                timeline=ms_data.get("timeline", ""),
                funding_amount=float(ms_data.get("funding_amount", 0) or 0),
            ))

    # Apply metadata
    if metadata:
        app.program_id = metadata.get("program_id")
        app.round_id = metadata.get("round_id")

    return app


def _basic_parse(raw_text: str, metadata: Optional[Dict[str, Any]] = None) -> Application:
    """Fallback basic parsing without LLM."""
    # Extract title from first line
    lines = raw_text.strip().split('\n')
    title = lines[0][:100] if lines else "Untitled"
    
    # Try to find funding amount
    funding_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)\s*(?:USD|dollars?)?', raw_text, re.IGNORECASE)
    funding = float(funding_match.group(1).replace(',', '')) if funding_match else 0
    
    app = Application(
        title=title,
        description=raw_text,
        funding_requested=funding,
        raw_submission={"text": raw_text, "metadata": metadata},
        status=ApplicationStatus.PENDING,
    )
    
    if metadata:
        app.program_id = metadata.get("program_id")
        app.round_id = metadata.get("round_id")
    
    return app


def parse_structured_application(data: Dict[str, Any]) -> Application:
    """
    Parse a pre-structured application (e.g., from API or form).
    
    Args:
        data: Dictionary with application fields
    
    Returns:
        Application object
    """
    app = Application(
        title=data.get("title", "Untitled"),
        summary=data.get("summary", ""),
        description=data.get("description", ""),
        team_name=data.get("team_name", data.get("teamName", "")),
        problem_statement=data.get("problem_statement", data.get("problemStatement", "")),
        proposed_solution=data.get("proposed_solution", data.get("proposedSolution", "")),
        technical_approach=data.get("technical_approach", data.get("technicalApproach", "")),
        prior_work=data.get("prior_work", data.get("priorWork", "")),
        funding_requested=float(data.get("funding_requested", data.get("fundingRequested", 0)) or 0),
        funding_currency=data.get("funding_currency", data.get("fundingCurrency", "USD")),
        program_id=data.get("program_id", data.get("programId")),
        round_id=data.get("round_id", data.get("roundId")),
        website=data.get("website"),
        github=data.get("github"),
        demo=data.get("demo"),
        raw_submission=data,
        status=ApplicationStatus.PENDING,
    )

    # Parse team members
    team_members = data.get("team_members", data.get("teamMembers", []))
    for member in team_members:
        if isinstance(member, dict):
            app.team_members.append(TeamMember(
                name=member.get("name", ""),
                role=member.get("role", ""),
                wallet_address=member.get("wallet_address", member.get("walletAddress")),
                github=member.get("github"),
                twitter=member.get("twitter"),
                linkedin=member.get("linkedin"),
                bio=member.get("bio"),
            ))

    # Parse budget
    budget = data.get("budget_breakdown", data.get("budgetBreakdown", data.get("budget", [])))
    for item in budget:
        if isinstance(item, dict):
            app.budget_breakdown.append(BudgetItem(
                category=item.get("category", ""),
                description=item.get("description", ""),
                amount=float(item.get("amount", 0) or 0),
                justification=item.get("justification"),
            ))

    # Parse milestones
    milestones = data.get("milestones", [])
    for ms in milestones:
        if isinstance(ms, dict):
            deliverables = ms.get("deliverables", [])
            if isinstance(deliverables, str):
                deliverables = [d.strip() for d in deliverables.split(',')]
            
            app.milestones.append(Milestone(
                title=ms.get("title", ""),
                description=ms.get("description", ""),
                deliverables=deliverables,
                timeline=ms.get("timeline", ms.get("duration", "")),
                funding_amount=float(ms.get("funding_amount", ms.get("fundingAmount", 0)) or 0),
            ))

    return app


def format_application_for_evaluation(application: Application) -> str:
    """
    Format an application into a readable string for agent evaluation.
    
    Args:
        application: The Application object
    
    Returns:
        Formatted string representation
    """
    sections = []
    
    # Header
    sections.append(f"# {application.title}")
    sections.append(f"**Team:** {application.team_name}")
    sections.append(f"**Funding Requested:** {application.funding_requested:,.2f} {application.funding_currency}")
    sections.append("")
    
    # Summary
    if application.summary:
        sections.append("## Summary")
        sections.append(application.summary)
        sections.append("")
    
    # Problem & Solution
    if application.problem_statement:
        sections.append("## Problem Statement")
        sections.append(application.problem_statement)
        sections.append("")
    
    if application.proposed_solution:
        sections.append("## Proposed Solution")
        sections.append(application.proposed_solution)
        sections.append("")
    
    # Technical Approach
    if application.technical_approach:
        sections.append("## Technical Approach")
        sections.append(application.technical_approach)
        sections.append("")
    
    # Team
    if application.team_members:
        sections.append("## Team Members")
        for member in application.team_members:
            member_info = f"- **{member.name}** ({member.role})"
            if member.bio:
                member_info += f": {member.bio}"
            sections.append(member_info)
        sections.append("")
    
    # Prior Work
    if application.prior_work:
        sections.append("## Prior Work & Experience")
        sections.append(application.prior_work)
        sections.append("")
    
    # Budget
    if application.budget_breakdown:
        sections.append("## Budget Breakdown")
        for item in application.budget_breakdown:
            line = f"- **{item.category}**: {item.amount:,.2f} {application.funding_currency}"
            if item.description:
                line += f" - {item.description}"
            sections.append(line)
        sections.append("")
    
    # Milestones
    if application.milestones:
        sections.append("## Milestones")
        for i, ms in enumerate(application.milestones, 1):
            sections.append(f"### Milestone {i}: {ms.title}")
            if ms.description:
                sections.append(ms.description)
            if ms.timeline:
                sections.append(f"**Timeline:** {ms.timeline}")
            if ms.funding_amount:
                sections.append(f"**Funding:** {ms.funding_amount:,.2f} {application.funding_currency}")
            if ms.deliverables:
                sections.append("**Deliverables:**")
                for d in ms.deliverables:
                    sections.append(f"  - {d}")
            sections.append("")
    
    # Links
    links = []
    if application.website:
        links.append(f"Website: {application.website}")
    if application.github:
        links.append(f"GitHub: {application.github}")
    if application.demo:
        links.append(f"Demo: {application.demo}")
    
    if links:
        sections.append("## Links")
        sections.append(" | ".join(links))
    
    return "\n".join(sections)
