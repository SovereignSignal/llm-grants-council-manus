import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);
  const [isRecordingOutcome, setIsRecordingOutcome] = useState(false);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId]);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, title: newConv.title, message_count: 0 },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        status: null,
        application: null,
        evaluations: null,
        deliberation: [],
        recommendation: null,
        synthesis: null,
        feedback: null,
        loading: {
          parsing: false,
          evaluation: false,
          deliberation: false,
          synthesis: false,
        },
        error: null,
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Send message with streaming
      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'message_received':
            // Message received by server
            break;

          case 'status':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = { ...messages[messages.length - 1] };
              lastMsg.status = event.message;
              messages[messages.length - 1] = lastMsg;
              return { ...prev, messages };
            });
            break;

          case 'stage':
            handleStageEvent(event);
            break;

          case 'complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = { ...messages[messages.length - 1] };
              lastMsg.recommendation = event.recommendation;
              lastMsg.synthesis = event.synthesis;
              lastMsg.feedback = event.feedback;
              lastMsg.averageScore = event.average_score;
              lastMsg.decisionId = event.decision_id;
              lastMsg.applicationId = event.application_id;
              lastMsg.loading = {
                parsing: false,
                evaluation: false,
                deliberation: false,
                synthesis: false,
              };
              messages[messages.length - 1] = lastMsg;
              return { ...prev, messages };
            });
            loadConversations();
            setIsLoading(false);
            break;

          case 'error':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = { ...messages[messages.length - 1] };
              lastMsg.error = event.message;
              lastMsg.loading = {
                parsing: false,
                evaluation: false,
                deliberation: false,
                synthesis: false,
              };
              messages[messages.length - 1] = lastMsg;
              return { ...prev, messages };
            });
            setIsLoading(false);
            break;

          default:
            console.log('Unknown event type:', eventType, event);
        }
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
    }
  };

  const handleSubmitDecision = async (decisionId, decision, rationale) => {
    setIsSubmittingDecision(true);
    try {
      await api.submitHumanDecision(decisionId, decision, rationale);

      // Update the message with the human decision
      setCurrentConversation((prev) => {
        const messages = [...prev.messages];
        const lastMsg = { ...messages[messages.length - 1] };
        lastMsg.humanDecision = { decision, rationale };
        messages[messages.length - 1] = lastMsg;
        return { ...prev, messages };
      });

      // Reload conversations to update sidebar
      loadConversations();
    } catch (error) {
      console.error('Failed to submit human decision:', error);
      alert('Failed to submit decision. Please try again.');
    } finally {
      setIsSubmittingDecision(false);
    }
  };

  const handleRecordOutcome = async (applicationId, outcome, notes) => {
    setIsRecordingOutcome(true);
    try {
      await api.recordOutcome(applicationId, outcome, notes);

      // Update the message with the outcome
      setCurrentConversation((prev) => {
        const messages = [...prev.messages];
        // Find the message with this applicationId
        const msgIndex = messages.findIndex(m => m.applicationId === applicationId);
        if (msgIndex >= 0) {
          const updatedMsg = { ...messages[msgIndex] };
          updatedMsg.outcome = { outcome, notes };
          messages[msgIndex] = updatedMsg;
        }
        return { ...prev, messages };
      });

      // Reload conversations to update sidebar
      loadConversations();
    } catch (error) {
      console.error('Failed to record outcome:', error);
      alert('Failed to record outcome. Please try again.');
    } finally {
      setIsRecordingOutcome(false);
    }
  };

  const handleStageEvent = (event) => {
    const { stage, status } = event;

    setCurrentConversation((prev) => {
      const messages = [...prev.messages];
      const lastMsg = { ...messages[messages.length - 1] };

      if (stage === 'parsing') {
        if (status === 'started') {
          lastMsg.loading = { ...lastMsg.loading, parsing: true };
          lastMsg.status = 'Parsing application...';
        } else if (status === 'complete') {
          lastMsg.loading = { ...lastMsg.loading, parsing: false };
          lastMsg.application = event.application;
          lastMsg.status = null;
        }
      } else if (stage === 'initial_evaluation') {
        if (status === 'started') {
          lastMsg.loading = { ...lastMsg.loading, evaluation: true };
          lastMsg.status = 'Council agents evaluating...';
        } else if (status === 'complete') {
          lastMsg.loading = { ...lastMsg.loading, evaluation: false };
          lastMsg.evaluations = event.evaluations;
          // Debug: log the evaluation data
          console.log('[DEBUG] Received evaluations:', event.evaluations);
          if (event.evaluations && event.evaluations[0]) {
            console.log('[DEBUG] First evaluation details:', {
              rationale: event.evaluations[0].rationale,
              strengths: event.evaluations[0].strengths,
              concerns: event.evaluations[0].concerns
            });
          }
          lastMsg.status = null;
        }
      } else if (stage.startsWith('deliberation_round_')) {
        const round = stage.replace('deliberation_round_', '');
        if (status === 'started') {
          lastMsg.loading = { ...lastMsg.loading, deliberation: true };
          lastMsg.status = `Deliberation round ${round}...`;
        } else if (status === 'complete') {
          lastMsg.loading = { ...lastMsg.loading, deliberation: false };
          lastMsg.deliberation = [...(lastMsg.deliberation || []), { round, revisions: event.revisions }];
          lastMsg.status = null;
        }
      } else if (stage === 'aggregation') {
        if (status === 'started') {
          lastMsg.status = 'Aggregating votes...';
        } else if (status === 'complete') {
          lastMsg.recommendation = event.recommendation;
          lastMsg.autoExecute = event.auto_execute;
          lastMsg.status = null;
        }
      } else if (stage === 'synthesis') {
        if (status === 'started') {
          lastMsg.loading = { ...lastMsg.loading, synthesis: true };
          lastMsg.status = 'Synthesizing final decision...';
        } else if (status === 'complete') {
          lastMsg.loading = { ...lastMsg.loading, synthesis: false };
          lastMsg.status = null;
        }
      }

      messages[messages.length - 1] = lastMsg;
      return { ...prev, messages };
    });
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        onSubmitDecision={handleSubmitDecision}
        onRecordOutcome={handleRecordOutcome}
        isLoading={isLoading}
        isSubmittingDecision={isSubmittingDecision}
        isRecordingOutcome={isRecordingOutcome}
      />
    </div>
  );
}

export default App;
