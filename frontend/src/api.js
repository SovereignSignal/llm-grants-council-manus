/**
 * API client for the LLM Council backend.
 */

const API_BASE = 'http://localhost:8001';

export const api = {
  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  /**
   * Submit a human decision on a council evaluation.
   */
  async submitHumanDecision(decisionId, decision, rationale, reviewer = 'reviewer') {
    const response = await fetch(
      `${API_BASE}/api/decisions/${decisionId}/human-decision`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ decision, rationale, reviewer }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to submit human decision');
    }
    return response.json();
  },

  /**
   * List observations (agent learned patterns).
   */
  async listObservations(status = null) {
    const url = status
      ? `${API_BASE}/api/observations?status=${status}`
      : `${API_BASE}/api/observations`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error('Failed to list observations');
    }
    return response.json();
  },

  /**
   * Activate a draft observation.
   */
  async activateObservation(observationId, reviewer = 'reviewer') {
    const response = await fetch(
      `${API_BASE}/api/observations/${observationId}/activate?reviewer=${reviewer}`,
      {
        method: 'POST',
      }
    );
    if (!response.ok) {
      throw new Error('Failed to activate observation');
    }
    return response.json();
  },

  /**
   * Record the outcome of an approved application.
   * @param {string} applicationId - The application ID
   * @param {string} outcome - "success" or "failure"
   * @param {string} notes - Explanation of the outcome (min 10 chars)
   */
  async recordOutcome(applicationId, outcome, notes) {
    const response = await fetch(
      `${API_BASE}/api/applications/${applicationId}/outcome`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ outcome, notes }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to record outcome');
    }
    return response.json();
  },
};
