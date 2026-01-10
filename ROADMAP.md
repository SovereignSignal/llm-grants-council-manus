# Agentic Grants Council - Roadmap

This document tracks progress toward the full vision of a self-improving, agentic grants evaluation system.

## Vision Summary

An LLM-powered grants council that:
- Evaluates applications through multi-agent deliberation
- Learns from human overrides and grant outcomes
- Improves over time through observation-based memory
- Integrates with Discord for community submissions
- Provides both admin review UI and public-facing portal

---

## Phase 1: Wire the Learning Loop
**Status: COMPLETE**

The foundation for agent learning from human feedback and outcomes.

- [x] Connect human override → observation generation
- [x] Add outcome recording endpoint (success/failure)
- [x] Track observation usage in agent prompts
- [x] Add observation management endpoints (activate, deprecate, prune)
- [x] Frontend: Human decision buttons (Approve/Reject)
- [x] Frontend: Observations viewer in sidebar
- [x] Frontend: Outcome recording UI
- [x] Frontend: Full agent reasoning display (rationale, strengths, concerns, questions)

**How to test:**
1. Submit an application → Council evaluates
2. Override the council's decision → Observations generated
3. Later, record outcome (Success/Failure) → More observations generated
4. View observations in sidebar → Activate useful ones
5. Future evaluations use active observations

---

## Phase 2: Vector Search + Similar Applications
**Status: NOT STARTED**

Enable agents to reference similar past applications when evaluating.

- [ ] Set up vector database (ChromaDB or Pinecone)
- [ ] Generate embeddings for applications on submission
- [ ] Implement similarity search function
- [ ] Integrate similar applications into agent prompts
- [ ] Store outcomes with applications for reference
- [ ] Add "Similar Applications" section to evaluation UI

**Why this matters:**
Agents can say "This is similar to Project X which failed because..." - grounding decisions in historical data.

---

## Phase 3: Training Data Import Pipeline
**Status: NOT STARTED**

Bootstrap the system with historical grant data.

- [ ] Design flexible import schema for various data sources
- [ ] Build structured data importer (CSV, JSON)
- [ ] Build unstructured data parser (forum posts, documents)
- [ ] Implement batch observation generation from historical outcomes
- [ ] Add data source management UI
- [ ] Support incremental imports

**Data sources to support:**
- Existing grant program CSVs
- Forum discussions about grants
- Previous evaluation documents
- On-chain grant execution data

---

## Phase 4: Database Migration
**Status: NOT STARTED**

Move from JSON files to proper database for production use.

- [ ] Set up PostgreSQL with SQLAlchemy models
- [ ] Migrate Application, Decision, Observation models
- [ ] Migrate TeamProfile and conversation storage
- [ ] Add proper indexing for queries
- [ ] Implement data migration script from JSON
- [ ] Add database connection pooling
- [ ] Set up database backups

---

## Phase 5: Discord Integration
**Status: NOT STARTED**

Allow community members to submit applications via Discord.

### 5a: Discord Bot (Receive)
- [ ] Set up Discord bot with necessary permissions
- [ ] Create `/apply` slash command
- [ ] Build application submission flow (modal or thread)
- [ ] Parse Discord messages into Application objects
- [ ] Post evaluation results back to Discord
- [ ] Handle human review notifications

### 5b: Discord Notifications (Send)
- [ ] Notify on new applications requiring review
- [ ] Post council decisions to announcement channel
- [ ] Send DMs to applicants with feedback
- [ ] Weekly digest of pending reviews

---

## Phase 6: Admin UI + Public Frontend
**Status: NOT STARTED**

Separate interfaces for reviewers and applicants.

### 6a: Admin Dashboard
- [ ] Application queue with filters (pending, reviewed, approved, rejected)
- [ ] Batch review capabilities
- [ ] Observation management panel
- [ ] Agent performance analytics
- [ ] Override history and pattern analysis
- [ ] Team reputation management

### 6b: Public Portal
- [ ] Application submission form
- [ ] Application status tracker
- [ ] FAQ and guidelines
- [ ] Past grants showcase
- [ ] Anonymous feedback submission

---

## Future Enhancements (Post-MVP)

### Multi-Program Support
- [ ] Isolated agent memories per program
- [ ] Configurable agent weights per program
- [ ] Program-specific evaluation criteria
- [ ] Cross-program learning (shared observations)

### Advanced Learning
- [ ] Automated observation quality scoring
- [ ] Observation conflict resolution
- [ ] Agent specialization based on accuracy
- [ ] A/B testing of observation sets

### Governance Integration
- [ ] On-chain voting triggers
- [ ] Multi-sig approval workflows
- [ ] Token-gated review access
- [ ] Transparent decision audit trail

### Analytics & Reporting
- [ ] Grant success prediction model
- [ ] Budget optimization recommendations
- [ ] Team risk scoring
- [ ] Program ROI analysis

---

## Current Priority

**Next up: Phase 2 - Vector Search**

This will significantly improve evaluation quality by giving agents historical context. The agents can reference similar past applications and their outcomes when making decisions.

---

## Technical Debt / Improvements

- [ ] Add comprehensive test suite
- [ ] Set up CI/CD pipeline
- [ ] Add error handling and retry logic for LLM calls
- [ ] Implement rate limiting
- [ ] Add request logging and monitoring
- [ ] Security audit (input validation, auth)

---

*Last updated: January 2025*
