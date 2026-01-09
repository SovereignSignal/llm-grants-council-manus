#!/usr/bin/env python3
"""Test script to validate the Grants Council backend modules."""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from backend import config
        print("  ✓ config")
    except Exception as e:
        print(f"  ✗ config: {e}")
        return False
    
    try:
        from backend import models
        print("  ✓ models")
    except Exception as e:
        print(f"  ✗ models: {e}")
        return False
    
    try:
        from backend import llm_client
        print("  ✓ llm_client")
    except Exception as e:
        print(f"  ✗ llm_client: {e}")
        return False
    
    try:
        from backend import storage
        print("  ✓ storage")
    except Exception as e:
        print(f"  ✗ storage: {e}")
        return False
    
    try:
        from backend import parser
        print("  ✓ parser")
    except Exception as e:
        print(f"  ✗ parser: {e}")
        return False
    
    try:
        from backend import agents
        print("  ✓ agents")
    except Exception as e:
        print(f"  ✗ agents: {e}")
        return False
    
    try:
        from backend import council
        print("  ✓ council")
    except Exception as e:
        print(f"  ✗ council: {e}")
        return False
    
    try:
        from backend import learning
        print("  ✓ learning")
    except Exception as e:
        print(f"  ✗ learning: {e}")
        return False
    
    try:
        from backend import main
        print("  ✓ main (FastAPI)")
    except Exception as e:
        print(f"  ✗ main: {e}")
        return False
    
    return True


def test_models():
    """Test model creation and serialization."""
    print("\nTesting models...")
    
    from backend.models import (
        Application, ApplicationStatus, Recommendation,
        AgentEvaluation, CouncilDecision, Observation, ObservationStatus,
        TeamProfile, TeamMember, Milestone, BudgetItem
    )
    
    # Test Application
    app = Application(
        title="Test Grant Application",
        summary="A test application for validation",
        description="This is a detailed description of the test application.",
        team_name="Test Team",
        team_members=[
            TeamMember(name="Alice", role="Lead Developer", github="alice"),
            TeamMember(name="Bob", role="Designer"),
        ],
        problem_statement="There is a problem that needs solving.",
        proposed_solution="We propose to solve it this way.",
        technical_approach="Using modern technology stack.",
        funding_requested=50000.0,
        funding_currency="USD",
        milestones=[
            Milestone(title="Phase 1", description="Initial work", funding_percentage=30),
            Milestone(title="Phase 2", description="Main development", funding_percentage=50),
            Milestone(title="Phase 3", description="Completion", funding_percentage=20),
        ],
    )
    
    assert app.id is not None
    assert app.status == ApplicationStatus.PENDING
    assert len(app.team_members) == 2
    print("  ✓ Application model")
    
    # Test serialization
    app_dict = app.to_dict()
    assert app_dict['title'] == "Test Grant Application"
    assert app_dict['funding_requested'] == 50000.0
    print("  ✓ Application serialization")
    
    # Test AgentEvaluation
    eval_obj = AgentEvaluation(
        application_id=app.id,
        agent_id="technical",
        agent_name="Technical Feasibility Agent",
        score=0.75,
        recommendation=Recommendation.APPROVE,
        confidence=0.85,
        rationale="The technical approach is sound.",
        strengths=["Clear architecture", "Experienced team"],
        concerns=["Timeline might be tight"],
    )
    
    assert eval_obj.score == 0.75
    assert eval_obj.recommendation == Recommendation.APPROVE
    print("  ✓ AgentEvaluation model")
    
    # Test CouncilDecision
    decision = CouncilDecision(
        application_id=app.id,
        average_score=0.72,
        average_confidence=0.80,
        recommendation=Recommendation.APPROVE,
        evaluations=[eval_obj],
        auto_executed=False,
        requires_human_review=True,
        review_reasons=["Budget exceeds threshold"],
        synthesis="The council recommends approval with conditions.",
        feedback_for_applicant="Strong application with minor concerns.",
    )
    
    assert decision.requires_human_review == True
    assert len(decision.evaluations) == 1
    print("  ✓ CouncilDecision model")
    
    # Test Observation
    obs = Observation(
        agent_id="technical",
        pattern="Teams with prior open-source contributions tend to deliver on time.",
        evidence=["app1", "app2", "app3"],
        tags=["technical", "team", "delivery"],
        confidence=0.8,
        status=ObservationStatus.ACTIVE,
    )
    
    assert obs.status == ObservationStatus.ACTIVE
    assert len(obs.evidence) == 3
    print("  ✓ Observation model")
    
    return True


def test_config():
    """Test configuration values."""
    print("\nTesting configuration...")
    
    from backend.config import (
        COUNCIL_AGENTS, SYNTHESIS_MODEL,
        AUTO_APPROVE_THRESHOLD, AUTO_REJECT_THRESHOLD,
        BUDGET_REVIEW_THRESHOLD, MAX_DELIBERATION_ROUNDS
    )
    
    # Check agents are defined
    assert len(COUNCIL_AGENTS) == 4
    assert "technical" in COUNCIL_AGENTS
    assert "ecosystem" in COUNCIL_AGENTS
    assert "budget" in COUNCIL_AGENTS
    assert "impact" in COUNCIL_AGENTS
    print(f"  ✓ {len(COUNCIL_AGENTS)} council agents defined")
    
    # Check each agent has required fields
    for agent_id, agent in COUNCIL_AGENTS.items():
        assert "name" in agent
        assert "model" in agent
        assert "character" in agent
        assert "tags" in agent
        print(f"    - {agent['name']}")
    
    # Check thresholds
    assert 0 <= AUTO_APPROVE_THRESHOLD <= 1
    assert 0 <= AUTO_REJECT_THRESHOLD <= 1
    assert AUTO_REJECT_THRESHOLD < AUTO_APPROVE_THRESHOLD
    print(f"  ✓ Thresholds: approve={AUTO_APPROVE_THRESHOLD}, reject={AUTO_REJECT_THRESHOLD}")
    
    assert BUDGET_REVIEW_THRESHOLD > 0
    print(f"  ✓ Budget review threshold: ${BUDGET_REVIEW_THRESHOLD:,}")
    
    assert MAX_DELIBERATION_ROUNDS >= 1
    print(f"  ✓ Max deliberation rounds: {MAX_DELIBERATION_ROUNDS}")
    
    return True


def test_storage():
    """Test storage operations."""
    print("\nTesting storage...")
    
    from backend import storage
    from backend.models import Application, ApplicationStatus
    
    # Initialize storage
    storage.init_storage()
    print("  ✓ Storage initialized")
    
    # Create and save an application
    app = Application(
        title="Storage Test Application",
        summary="Testing storage functionality",
        description="This tests the storage module.",
        team_name="Storage Test Team",
        funding_requested=25000.0,
    )
    
    storage.save_application(app)
    print(f"  ✓ Application saved: {app.id}")
    
    # Retrieve the application
    retrieved = storage.get_application(app.id)
    assert retrieved is not None
    assert retrieved.title == "Storage Test Application"
    print("  ✓ Application retrieved")
    
    # List applications
    apps = storage.list_applications()
    assert len(apps) >= 1
    print(f"  ✓ Listed {len(apps)} application(s)")
    
    # Update status
    storage.update_application_status(app.id, ApplicationStatus.EVALUATING)
    updated = storage.get_application(app.id)
    assert updated.status == ApplicationStatus.EVALUATING
    print("  ✓ Application status updated")
    
    return True


async def test_parser():
    """Test application parsing."""
    print("\nTesting parser...")
    
    from backend.parser import parse_structured_application, format_application_for_evaluation
    from backend.models import Application
    
    # Test structured parsing
    data = {
        "title": "DeFi Analytics Dashboard",
        "summary": "A comprehensive analytics platform for DeFi protocols",
        "description": "We will build a dashboard that aggregates data from multiple DeFi protocols.",
        "team_name": "Analytics Labs",
        "team_members": [
            {"name": "Carol", "role": "Data Engineer"},
            {"name": "Dave", "role": "Frontend Developer"},
        ],
        "problem_statement": "DeFi data is fragmented across protocols.",
        "proposed_solution": "Unified dashboard with real-time analytics.",
        "technical_approach": "Using The Graph for indexing and React for frontend.",
        "funding_requested": 75000,
        "funding_currency": "USD",
        "milestones": [
            {"title": "MVP", "description": "Basic dashboard", "funding_percentage": 40},
            {"title": "Launch", "description": "Full launch", "funding_percentage": 60},
        ],
        "github": "https://github.com/analytics-labs",
        "website": "https://analytics-labs.io",
    }
    
    app = parse_structured_application(data)
    assert app.title == "DeFi Analytics Dashboard"
    assert app.funding_requested == 75000
    assert len(app.team_members) == 2
    assert len(app.milestones) == 2
    print("  ✓ Structured application parsed")
    
    # Test formatting for evaluation
    formatted = format_application_for_evaluation(app)
    assert "DeFi Analytics Dashboard" in formatted
    assert "Analytics Labs" in formatted
    assert "75,000" in formatted
    print("  ✓ Application formatted for evaluation")
    
    return True


async def test_council_aggregation():
    """Test council aggregation logic."""
    print("\nTesting council aggregation...")
    
    from backend.council import aggregate_evaluations, determine_routing
    from backend.models import AgentEvaluation, Recommendation, Application
    
    # Create test evaluations
    evaluations = [
        AgentEvaluation(
            application_id="test",
            agent_id="technical",
            agent_name="Technical Agent",
            score=0.8,
            recommendation=Recommendation.APPROVE,
            confidence=0.9,
            rationale="Good technical approach",
        ),
        AgentEvaluation(
            application_id="test",
            agent_id="ecosystem",
            agent_name="Ecosystem Agent",
            score=0.75,
            recommendation=Recommendation.APPROVE,
            confidence=0.85,
            rationale="Good ecosystem fit",
        ),
        AgentEvaluation(
            application_id="test",
            agent_id="budget",
            agent_name="Budget Agent",
            score=0.7,
            recommendation=Recommendation.APPROVE,
            confidence=0.8,
            rationale="Budget is reasonable",
        ),
        AgentEvaluation(
            application_id="test",
            agent_id="impact",
            agent_name="Impact Agent",
            score=0.85,
            recommendation=Recommendation.APPROVE,
            confidence=0.88,
            rationale="High potential impact",
        ),
    ]
    
    # Test aggregation
    aggregated = aggregate_evaluations(evaluations)
    
    assert 0.7 <= aggregated["average_score"] <= 0.85
    assert aggregated["unanimous"] == True
    assert aggregated["recommendation_counts"]["approve"] == 4
    print(f"  ✓ Aggregation: avg_score={aggregated['average_score']:.2f}, unanimous={aggregated['unanimous']}")
    
    # Test routing with small budget (should auto-execute)
    app_small = Application(
        title="Small Grant",
        summary="Test",
        description="Test",
        team_name="Test",
        funding_requested=10000,
    )
    
    rec, auto_exec, reasons = determine_routing(app_small, aggregated)
    # With avg_score=0.78, below AUTO_APPROVE_THRESHOLD=0.85, so recommendation is NEEDS_REVIEW
    assert rec == Recommendation.NEEDS_REVIEW
    print(f"  ✓ Small budget routing: recommendation={rec.value}, auto_execute={auto_exec}, reasons={reasons}")
    
    # Test routing with large budget (should require review)
    app_large = Application(
        title="Large Grant",
        summary="Test",
        description="Test",
        team_name="Test",
        funding_requested=200000,
    )
    
    rec, auto_exec, reasons = determine_routing(app_large, aggregated)
    assert auto_exec == False
    assert len(reasons) > 0
    print(f"  ✓ Large budget routing: auto_execute={auto_exec}, reasons={reasons}")
    
    return True


def test_fastapi_app():
    """Test FastAPI app initialization."""
    print("\nTesting FastAPI app...")
    
    from backend.main import app
    
    # Check routes are registered
    routes = [route.path for route in app.routes]
    
    assert "/" in routes
    assert "/api/applications" in routes
    assert "/api/applications/{application_id}" in routes
    assert "/api/applications/{application_id}/evaluate" in routes
    assert "/api/decisions" in routes
    assert "/api/decisions/{decision_id}" in routes
    assert "/api/observations" in routes
    
    print(f"  ✓ {len(routes)} routes registered")
    print("    Key routes:")
    for route in sorted(routes):
        if route.startswith("/api/"):
            print(f"      - {route}")
    
    return True


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Grants Council Backend Tests")
    print("=" * 60)
    
    all_passed = True
    
    # Run tests
    if not test_imports():
        all_passed = False
    
    if not test_models():
        all_passed = False
    
    if not test_config():
        all_passed = False
    
    if not test_storage():
        all_passed = False
    
    if not await test_parser():
        all_passed = False
    
    if not await test_council_aggregation():
        all_passed = False
    
    if not test_fastapi_app():
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed! ✓")
    else:
        print("Some tests failed! ✗")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
