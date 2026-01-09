import { useState, useEffect } from 'react';
import { api } from '../api';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
}) {
  const [observations, setObservations] = useState([]);
  const [showObservations, setShowObservations] = useState(false);
  const [activatingId, setActivatingId] = useState(null);

  useEffect(() => {
    loadObservations();
  }, []);

  const loadObservations = async () => {
    try {
      const obs = await api.listObservations();
      setObservations(obs);
    } catch (error) {
      console.error('Failed to load observations:', error);
    }
  };

  const handleActivate = async (obsId) => {
    setActivatingId(obsId);
    try {
      await api.activateObservation(obsId);
      loadObservations();
    } catch (error) {
      console.error('Failed to activate observation:', error);
    } finally {
      setActivatingId(null);
    }
  };

  const draftCount = observations.filter((o) => o.status === 'draft').length;
  const activeCount = observations.filter((o) => o.status === 'active').length;

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>Grants Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
        </button>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No evaluations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-title">
                {conv.title || 'New Evaluation'}
              </div>
              <div className="conversation-meta">
                {conv.messages?.length || 0} messages
              </div>
            </div>
          ))
        )}
      </div>

      {/* Observations Section */}
      <div className="observations-section">
        <div
          className="observations-header"
          onClick={() => setShowObservations(!showObservations)}
        >
          <span>Agent Learning</span>
          {draftCount > 0 && (
            <span className="draft-badge">{draftCount} pending</span>
          )}
        </div>

        {showObservations && (
          <div className="observations-list">
            <div className="observations-summary">
              <span>{activeCount} active</span>
              <span>{draftCount} drafts</span>
              <button className="refresh-btn" onClick={loadObservations}>
                Refresh
              </button>
            </div>

            {observations.filter((o) => o.status === 'draft').length > 0 && (
              <>
                <div className="observations-subheader">Pending Review</div>
                {observations
                  .filter((o) => o.status === 'draft')
                  .map((obs) => (
                    <div key={obs.id} className="observation-item draft">
                      <div className="observation-agent">{obs.agent_id}</div>
                      <div className="observation-pattern">{obs.pattern}</div>
                      <div className="observation-tags">
                        {obs.tags?.slice(0, 3).map((tag) => (
                          <span key={tag} className="tag">
                            {tag}
                          </span>
                        ))}
                      </div>
                      <button
                        className="activate-btn"
                        onClick={() => handleActivate(obs.id)}
                        disabled={activatingId === obs.id}
                      >
                        {activatingId === obs.id ? 'Activating...' : 'Activate'}
                      </button>
                    </div>
                  ))}
              </>
            )}

            {observations.filter((o) => o.status === 'active').length > 0 && (
              <>
                <div className="observations-subheader">Active Patterns</div>
                {observations
                  .filter((o) => o.status === 'active')
                  .slice(0, 5)
                  .map((obs) => (
                    <div key={obs.id} className="observation-item active">
                      <div className="observation-agent">{obs.agent_id}</div>
                      <div className="observation-pattern">{obs.pattern}</div>
                      <div className="observation-meta">
                        Used {obs.times_used || 0} times
                      </div>
                    </div>
                  ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
