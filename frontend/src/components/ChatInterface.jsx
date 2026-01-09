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

// Individual evaluation card
function EvaluationCard({ evaluation }) {
  return (
    <div className="evaluation-card">
      <div className="evaluation-header">
        <span className="agent-name">{evaluation.agent}</span>
        <div className="evaluation-metrics">
          <span className="score">{formatScore(evaluation.score)}</span>
          <span
            className="recommendation-badge"
            style={{ backgroundColor: getRecommendationColor(evaluation.recommendation) }}
          >
            {evaluation.recommendation.replace('_', ' ')}
          </span>
        </div>
      </div>
    </div>
  );
}

// Final decision component
function DecisionCard({ recommendation, averageScore, synthesis, feedback }) {
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
    </div>
  );
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
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

      {conversation.messages.length === 0 && (
        <form className="input-form" onSubmit={handleSubmit}>
          <textarea
            className="message-input"
            placeholder="Paste a grant application URL or describe the project... (Shift+Enter for new line, Enter to send)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={3}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!input.trim() || isLoading}
          >
            Evaluate
          </button>
        </form>
      )}
    </div>
  );
}
