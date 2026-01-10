#!/usr/bin/env python3
"""
Migration script to import existing JSON data into PostgreSQL.

Usage:
    python -m backend.migrate_to_postgres

This script:
1. Creates all database tables
2. Imports existing JSON files from data/ directories
3. Validates the migration
"""

import os
import json
from datetime import datetime
from pathlib import Path

from .database import (
    init_db, get_or_create_session,
    ApplicationDB, TeamDB, ObservationDB, DecisionDB, EvaluationDB, ConversationDB
)
from .config import (
    APPLICATIONS_DIR, TEAMS_DIR, OBSERVATIONS_DIR,
    EVALUATIONS_DIR, CONVERSATIONS_DIR
)


def parse_datetime(dt_str):
    """Parse datetime string to datetime object."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        return datetime.utcnow()


def migrate_applications(session):
    """Migrate applications from JSON files."""
    if not os.path.exists(APPLICATIONS_DIR):
        print("  No applications directory found")
        return 0

    count = 0
    for filename in os.listdir(APPLICATIONS_DIR):
        if not filename.endswith('.json'):
            continue

        path = os.path.join(APPLICATIONS_DIR, filename)
        try:
            with open(path, 'r') as f:
                data = json.load(f)

            # Check if already exists
            existing = session.query(ApplicationDB).filter_by(id=data["id"]).first()
            if existing:
                print(f"    Skipping {data['id']} - already exists")
                continue

            app = ApplicationDB(
                id=data["id"],
                title=data.get("title", ""),
                summary=data.get("summary", ""),
                description=data.get("description", ""),
                team_name=data.get("team_name", ""),
                team_id=data.get("team_id"),
                team_members=data.get("team_members", []),
                problem_statement=data.get("problem_statement", ""),
                proposed_solution=data.get("proposed_solution", ""),
                technical_approach=data.get("technical_approach", ""),
                prior_work=data.get("prior_work", ""),
                funding_requested=data.get("funding_requested", 0.0),
                funding_currency=data.get("funding_currency", "USD"),
                budget_breakdown=data.get("budget_breakdown", []),
                milestones=data.get("milestones", []),
                program_id=data.get("program_id"),
                round_id=data.get("round_id"),
                submitted_at=parse_datetime(data.get("submitted_at")),
                status=data.get("status", "pending"),
                raw_submission=data.get("raw_submission", {}),
                website=data.get("website"),
                github=data.get("github"),
                demo=data.get("demo"),
                outcome=data.get("outcome"),
                outcome_notes=data.get("outcome_notes"),
            )
            session.add(app)
            count += 1
            print(f"    Migrated: {data.get('title', data['id'])[:50]}")
        except Exception as e:
            print(f"    Error migrating {filename}: {e}")

    session.commit()
    return count


def migrate_teams(session):
    """Migrate team profiles from JSON files."""
    if not os.path.exists(TEAMS_DIR):
        print("  No teams directory found")
        return 0

    count = 0
    for filename in os.listdir(TEAMS_DIR):
        if not filename.endswith('.json'):
            continue

        path = os.path.join(TEAMS_DIR, filename)
        try:
            with open(path, 'r') as f:
                data = json.load(f)

            # Check if already exists
            existing = session.query(TeamDB).filter_by(id=data["id"]).first()
            if existing:
                print(f"    Skipping {data['id']} - already exists")
                continue

            team = TeamDB(
                id=data["id"],
                canonical_name=data.get("canonical_name", ""),
                aliases=data.get("aliases", []),
                members=data.get("members", []),
                wallet_addresses=data.get("wallet_addresses", []),
                application_ids=data.get("application_ids", []),
                successful_grants=data.get("successful_grants", 0),
                failed_grants=data.get("failed_grants", 0),
                total_funded=data.get("total_funded", 0.0),
                milestone_completion_rate=data.get("milestone_completion_rate", 0.0),
                reputation_signals=data.get("reputation_signals", {}),
                created_at=parse_datetime(data.get("created_at")),
                updated_at=parse_datetime(data.get("updated_at")),
            )
            session.add(team)
            count += 1
            print(f"    Migrated: {data.get('canonical_name', data['id'])}")
        except Exception as e:
            print(f"    Error migrating {filename}: {e}")

    session.commit()
    return count


def migrate_observations(session):
    """Migrate observations from JSON files."""
    if not os.path.exists(OBSERVATIONS_DIR):
        print("  No observations directory found")
        return 0

    count = 0
    for filename in os.listdir(OBSERVATIONS_DIR):
        if not filename.endswith('.json'):
            continue

        path = os.path.join(OBSERVATIONS_DIR, filename)
        try:
            with open(path, 'r') as f:
                data = json.load(f)

            # Check if already exists
            existing = session.query(ObservationDB).filter_by(id=data["id"]).first()
            if existing:
                print(f"    Skipping {data['id']} - already exists")
                continue

            obs = ObservationDB(
                id=data["id"],
                agent_id=data.get("agent_id", ""),
                pattern=data.get("pattern", ""),
                evidence=data.get("evidence", []),
                tags=data.get("tags", []),
                confidence=data.get("confidence", 0.0),
                status=data.get("status", "draft"),
                validated_at=parse_datetime(data.get("validated_at")),
                validated_by=data.get("validated_by"),
                times_used=data.get("times_used", 0),
                times_helpful=data.get("times_helpful", 0),
                created_at=parse_datetime(data.get("created_at")),
            )
            session.add(obs)
            count += 1
            print(f"    Migrated: {data.get('agent_id', 'unknown')} - {data.get('pattern', '')[:40]}...")
        except Exception as e:
            print(f"    Error migrating {filename}: {e}")

    session.commit()
    return count


def migrate_decisions(session):
    """Migrate decisions and evaluations from JSON files."""
    if not os.path.exists(EVALUATIONS_DIR):
        print("  No evaluations directory found")
        return 0

    count = 0
    eval_count = 0
    for filename in os.listdir(EVALUATIONS_DIR):
        if not filename.endswith('.json'):
            continue

        path = os.path.join(EVALUATIONS_DIR, filename)
        try:
            with open(path, 'r') as f:
                data = json.load(f)

            # Check if already exists
            existing = session.query(DecisionDB).filter_by(id=data["id"]).first()
            if existing:
                print(f"    Skipping {data['id']} - already exists")
                continue

            decision = DecisionDB(
                id=data["id"],
                application_id=data.get("application_id", ""),
                average_score=data.get("average_score", 0.0),
                average_confidence=data.get("average_confidence", 0.0),
                recommendation=data.get("recommendation", "needs_review"),
                auto_executed=data.get("auto_executed", False),
                requires_human_review=data.get("requires_human_review", True),
                review_reasons=data.get("review_reasons", []),
                human_decision=data.get("human_decision"),
                human_rationale=data.get("human_rationale"),
                human_reviewer=data.get("human_reviewer"),
                synthesis=data.get("synthesis", ""),
                feedback_for_applicant=data.get("feedback_for_applicant", ""),
                created_at=parse_datetime(data.get("created_at")),
                decided_at=parse_datetime(data.get("decided_at")),
            )
            session.add(decision)
            session.flush()  # Get the ID for evaluations

            # Migrate evaluations
            for eval_data in data.get("evaluations", []):
                evaluation = EvaluationDB(
                    id=eval_data.get("id"),
                    decision_id=decision.id,
                    application_id=eval_data.get("application_id", ""),
                    agent_id=eval_data.get("agent_id", ""),
                    agent_name=eval_data.get("agent_name", ""),
                    score=eval_data.get("score", 0.0),
                    recommendation=eval_data.get("recommendation", "needs_review"),
                    confidence=eval_data.get("confidence", 0.0),
                    rationale=eval_data.get("rationale", ""),
                    strengths=eval_data.get("strengths", []),
                    concerns=eval_data.get("concerns", []),
                    questions=eval_data.get("questions", []),
                    observations_used=eval_data.get("observations_used", []),
                    similar_applications=eval_data.get("similar_applications", []),
                    is_revised=eval_data.get("is_revised", False),
                    original_score=eval_data.get("original_score"),
                    revision_rationale=eval_data.get("revision_rationale"),
                    deliberation_round=eval_data.get("deliberation_round", 0),
                    created_at=parse_datetime(eval_data.get("created_at")),
                )
                session.add(evaluation)
                eval_count += 1

            count += 1
            print(f"    Migrated decision: {data['id'][:8]}... with {len(data.get('evaluations', []))} evaluations")
        except Exception as e:
            print(f"    Error migrating {filename}: {e}")

    session.commit()
    return count, eval_count


def migrate_conversations(session):
    """Migrate conversations from JSON files."""
    if not os.path.exists(CONVERSATIONS_DIR):
        print("  No conversations directory found")
        return 0

    count = 0
    for filename in os.listdir(CONVERSATIONS_DIR):
        if not filename.endswith('.json'):
            continue

        path = os.path.join(CONVERSATIONS_DIR, filename)
        try:
            with open(path, 'r') as f:
                data = json.load(f)

            # Check if already exists
            existing = session.query(ConversationDB).filter_by(id=data["id"]).first()
            if existing:
                print(f"    Skipping {data['id']} - already exists")
                continue

            conv = ConversationDB(
                id=data["id"],
                title=data.get("title", "New Evaluation"),
                application_id=data.get("application_id"),
                messages=data.get("messages", []),
                created_at=parse_datetime(data.get("created_at")),
            )
            session.add(conv)
            count += 1
            print(f"    Migrated: {data.get('title', 'Untitled')[:40]}")
        except Exception as e:
            print(f"    Error migrating {filename}: {e}")

    session.commit()
    return count


def run_migration():
    """Run the full migration."""
    print("=" * 60)
    print("Grants Council - JSON to PostgreSQL Migration")
    print("=" * 60)

    # Initialize database
    print("\n1. Initializing database...")
    init_db()

    # Get session
    session = get_or_create_session()

    try:
        # Migrate each entity type
        print("\n2. Migrating applications...")
        app_count = migrate_applications(session)
        print(f"   Total applications migrated: {app_count}")

        print("\n3. Migrating teams...")
        team_count = migrate_teams(session)
        print(f"   Total teams migrated: {team_count}")

        print("\n4. Migrating observations...")
        obs_count = migrate_observations(session)
        print(f"   Total observations migrated: {obs_count}")

        print("\n5. Migrating decisions...")
        dec_count, eval_count = migrate_decisions(session)
        print(f"   Total decisions migrated: {dec_count}")
        print(f"   Total evaluations migrated: {eval_count}")

        print("\n6. Migrating conversations...")
        conv_count = migrate_conversations(session)
        print(f"   Total conversations migrated: {conv_count}")

        print("\n" + "=" * 60)
        print("Migration Summary")
        print("=" * 60)
        print(f"  Applications: {app_count}")
        print(f"  Teams: {team_count}")
        print(f"  Observations: {obs_count}")
        print(f"  Decisions: {dec_count}")
        print(f"  Evaluations: {eval_count}")
        print(f"  Conversations: {conv_count}")
        print("\nMigration complete!")

    finally:
        session.close()


if __name__ == "__main__":
    run_migration()
