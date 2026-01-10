import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import './ChatInterface.css';

// Helper to get recommendation badge color
function getRecommendationColor(recommendation) {
  switch (recommendation) {
    case 'approve':
      return '#22c55e';
    case 'reject':
      return '#ef4444';
    case 'needs_review':
      return '#f59e0b';
    default:
      return '#6b7280';
  }
}

// Helper to format score as percentage
function formatScore(score) {
  return `${Math.round(score * 100)}%`;
}

// Application info component
function ApplicationCard({ application }) {
  if (!application) return null;

  return (
    <div className="application-card">
      <h3>{application.title}</h3>
      <div className="application-meta">
        <span className="meta-item">
          <strong>Team:</strong> {application.team}
        </span>
        <span className="meta-item">
          <strong>Funding:</strong> ${application.funding?.toLocaleString()}
        </span>
      </div>
    </div>
  );
}

// Individual evaluation card with full reasoning
function EvaluationCard({ evaluation }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="evaluation-card expanded">
      <div className="evaluation-header clickable" onClick={() => setExpanded(!expanded)}>
        <span className="agent-name">{evaluation.agent}</span>
        <div className="evaluation-metrics">
          <span className="score">{formatScore(evaluation.score)}</span>
          {evaluation.confidence !== undefined && (
            <span className="confidence">({formatScore(evaluation.confidence)} conf)</span>
          )}
          <span
            className="recommendation-badge"
            style={{ backgroundColor: getRecommendationColor(evaluation.recommendation) }}
          >
            {evaluation.recommendation.replace('_', ' ')}
          </span>
          <span className="expand-toggle">{expanded ? '−' : '+'}</span>
        </div>
      </div>

      {expanded && (
        <div className="evaluation-details">
          {evaluation.rationale && (
            <div className="evaluation-rationale">
              <p>{evaluation.rationale}</p>
            </div>
          )}

          {evaluation.strengths && evaluation.strengths.length > 0 && (
            <div className="evaluation-list strengths">
              <h5>Strengths</h5>
              <ul>
                {evaluation.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          {evaluation.concerns && evaluation.concerns.length > 0 && (
            <div className="evaluation-list concerns">
              <h5>Concerns</h5>
              <ul>
                {evaluation.concerns.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}

          {evaluation.questions && evaluation.questions.length > 0 && (
            <div className="evaluation-list questions">
              <h5>Questions</h5>
              <ul>
                {evaluation.questions.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Human decision component
function HumanDecisionPanel({ decisionId, humanDecision, onSubmitDecision, isSubmitting }) {
  const [rationale, setRationale] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [selectedDecision, setSelectedDecision] = useState(null);

  if (humanDecision) {
    return (
      <div className="human-decision-result">
        <div className="human-decision-header">
          <span className="human-decision-label">Human Decision:</span>
          <span
            className="recommendation-badge large"
            style={{ backgroundColor: getRecommendationColor(humanDecision.decision) }}
          >
            {humanDecision.decision.toUpperCase()}
          </span>
        </div>
        {humanDecision.rationale && (
          <p className="human-rationale">{humanDecision.rationale}</p>
        )}
      </div>
    );
  }

  if (!showForm) {
    return (
      <div className="human-decision-buttons">
        <span className="decision-prompt">Make your decision:</span>
        <button
          className="decision-btn approve"
          onClick={() => { setSelectedDecision('approve'); setShowForm(true); }}
          disabled={isSubmitting}
        >
          Approve
        </button>
        <button
          className="decision-btn reject"
          onClick={() => { setSelectedDecision('reject'); setShowForm(true); }}
          disabled={isSubmitting}
        >
          Reject
        </button>
      </div>
    );
  }

  return (
    <div className="human-decision-form">
      <div className="form-header">
        <span>
          {selectedDecision === 'approve' ? 'Approving' : 'Rejecting'} this application
        </span>
        <button className="cancel-btn" onClick={() => setShowForm(false)}>Cancel</button>
      </div>
      <textarea
        className="rationale-input"
        placeholder="Enter your rationale for this decision..."
        value={rationale}
        onChange={(e) => setRationale(e.target.value)}
        rows={3}
      />
      <button
        className={`submit-decision-btn ${selectedDecision}`}
        onClick={() => onSubmitDecision(decisionId, selectedDecision, rationale)}
        disabled={!rationale.trim() || isSubmitting}
      >
        {isSubmitting ? 'Submitting...' : `Confirm ${selectedDecision === 'approve' ? 'Approval' : 'Rejection'}`}
      </button>
    </div>
  );
}

// Outcome recording component (for approved grants)
function OutcomeRecordingPanel({ applicationId, outcome, onRecordOutcome, isRecording }) {
  const [notes, setNotes] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [selectedOutcome, setSelectedOutcome] = useState(null);

  if (outcome) {
    return (
      <div className={`outcome-result ${outcome.outcome}`}>
        <div className="outcome-header">
          <span className="outcome-label">Grant Outcome:</span>
          <span className={`outcome-badge ${outcome.outcome}`}>
            {outcome.outcome.toUpperCase()}
          </span>
        </div>
        {outcome.notes && (
          <p className="outcome-notes">{outcome.notes}</p>
        )}
      </div>
    );
  }

  if (!showForm) {
    return (
      <div className="outcome-buttons">
        <span className="outcome-prompt">Record grant outcome:</span>
        <button
          className="outcome-btn success"
          onClick={() => { setSelectedOutcome('success'); setShowForm(true); }}
          disabled={isRecording}
        >
          Success
        </button>
        <button
          className="outcome-btn failure"
          onClick={() => { setSelectedOutcome('failure'); setShowForm(true); }}
          disabled={isRecording}
        >
          Failure
        </button>
      </div>
    );
  }

  return (
    <div className="outcome-form">
      <div className="form-header">
        <span>
          Recording as {selectedOutcome === 'success' ? 'Successful' : 'Failed'}
        </span>
        <button className="cancel-btn" onClick={() => setShowForm(false)}>Cancel</button>
      </div>
      <textarea
        className="outcome-notes-input"
        placeholder={selectedOutcome === 'success'
          ? "Describe what made this grant successful (deliverables, impact, etc.)..."
          : "Explain why this grant failed (missed milestones, team issues, etc.)..."}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        rows={3}
      />
      <button
        className={`submit-outcome-btn ${selectedOutcome}`}
        onClick={() => onRecordOutcome(applicationId, selectedOutcome, notes)}
        disabled={notes.trim().length < 10 || isRecording}
      >
        {isRecording ? 'Recording...' : `Confirm ${selectedOutcome === 'success' ? 'Success' : 'Failure'}`}
      </button>
      {notes.trim().length > 0 && notes.trim().length < 10 && (
        <span className="char-hint">Please enter at least 10 characters</span>
      )}
    </div>
  );
}

// Final decision component
function DecisionCard({ recommendation, averageScore, synthesis, feedback, decisionId, applicationId, humanDecision, outcome, onSubmitDecision, onRecordOutcome, isSubmitting, isRecording }) {
  return (
    <div className="decision-card">
      <div className="decision-header">
        <h3>Council Decision</h3>
        <div className="decision-metrics">
          <span className="average-score">Score: {formatScore(averageScore)}</span>
          <span
            className="recommendation-badge large"
            style={{ backgroundColor: getRecommendationColor(recommendation) }}
          >
            {recommendation?.replace('_', ' ').toUpperCase()}
          </span>
        </div>
      </div>

      {synthesis && (
        <div className="decision-section">
          <h4>Summary</h4>
          <div className="markdown-content">
            <ReactMarkdown>{synthesis}</ReactMarkdown>
          </div>
        </div>
      )}

      {feedback && (
        <div className="decision-section">
          <h4>Feedback for Applicant</h4>
          <div className="markdown-content">
            <ReactMarkdown>{feedback}</ReactMarkdown>
          </div>
        </div>
      )}

      {decisionId && (
        <div className="decision-section">
          <h4>Your Decision</h4>
          <HumanDecisionPanel
            decisionId={decisionId}
            humanDecision={humanDecision}
            onSubmitDecision={onSubmitDecision}
            isSubmitting={isSubmitting}
          />
        </div>
      )}

      {/* Show outcome recording only if human approved the grant */}
      {humanDecision?.decision === 'approve' && applicationId && (
        <div className="decision-section">
          <h4>Grant Outcome</h4>
          <p className="outcome-description">
            Once this grant has completed, record the outcome to help the council learn from results.
          </p>
          <OutcomeRecordingPanel
            applicationId={applicationId}
            outcome={outcome}
            onRecordOutcome={onRecordOutcome}
            isRecording={isRecording}
          />
        </div>
      )}
    </div>
  );
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  onSubmitDecision,
  onRecordOutcome,
  isLoading,
  isSubmittingDecision,
  isRecordingOutcome,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to Grants Council</h2>
          <p>Create a new conversation to evaluate a grant application</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Evaluate a Grant Application</h2>
            <p>Paste a URL to a grant application or describe the project to evaluate</p>
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">Grants Council</div>

                  {/* Status message */}
                  {msg.status && (
                    <div className="status-message">
                      <div className="spinner"></div>
                      <span>{msg.status}</span>
                    </div>
                  )}

                  {/* Error message */}
                  {msg.error && (
                    <div className="error-message">
                      <span>Error: {msg.error}</span>
                    </div>
                  )}

                  {/* Application info */}
                  {msg.application && (
                    <ApplicationCard application={msg.application} />
                  )}

                  {/* Loading: Parsing */}
                  {msg.loading?.parsing && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Parsing application...</span>
                    </div>
                  )}

                  {/* Loading: Evaluation */}
                  {msg.loading?.evaluation && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Council agents evaluating...</span>
                    </div>
                  )}

                  {/* Evaluations */}
                  {msg.evaluations && msg.evaluations.length > 0 && (
                    <div className="evaluations-section">
                      <h4>Agent Evaluations</h4>
                      <div className="evaluations-grid">
                        {msg.evaluations.map((evaluation, idx) => (
                          <EvaluationCard key={idx} evaluation={evaluation} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Loading: Deliberation */}
                  {msg.loading?.deliberation && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Agents deliberating...</span>
                    </div>
                  )}

                  {/* Loading: Synthesis */}
                  {msg.loading?.synthesis && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Synthesizing decision...</span>
                    </div>
                  )}

                  {/* Final Decision */}
                  {msg.synthesis && (
                    <DecisionCard
                      recommendation={msg.recommendation}
                      averageScore={msg.averageScore}
                      synthesis={msg.synthesis}
                      feedback={msg.feedback}
                      decisionId={msg.decisionId}
                      applicationId={msg.applicationId}
                      humanDecision={msg.humanDecision}
                      outcome={msg.outcome}
                      onSubmitDecision={onSubmitDecision}
                      onRecordOutcome={onRecordOutcome}
                      isSubmitting={isSubmittingDecision}
                      isRecording={isRecordingOutcome}
                    />
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && conversation.messages.length === 0 && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="input-form" onSubmit={handleSubmit}>
        <textarea
          className="message-input"
          placeholder={
            conversation.messages.length === 0
              ? "Paste a grant application or describe the project to evaluate..."
              : "Submit another application to evaluate..."
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={conversation.messages.length === 0 ? 4 : 2}
        />
        <button
          type="submit"
          className="send-button"
          disabled={!input.trim() || isLoading}
        >
          {isLoading ? 'Evaluating...' : 'Evaluate'}
        </button>
      </form>
    </div>
  );
}
