// api_client.js — thin wrapper around the backend's REST endpoints.
// Used by dashboard.js (analyze.js uses sse_client.js directly since
// that endpoint streams rather than returning JSON).

const API = ""; // same origin — the backend serves this web app itself

const ApiClient = {
  async getScans({ channel, limit = 20, offset = 0 } = {}) {
    const params = new URLSearchParams({ limit, offset });
    if (channel) params.set("channel", channel);
    return fetch(`${API}/api/scans?${params}`).then(r => r.json());
  },

  async getSummary() {
    return fetch(`${API}/api/scans/stats/summary`).then(r => r.json());
  },

  async getTrends(days = 30) {
    return fetch(`${API}/api/scans/stats/trends?days=${days}`).then(r => r.json());
  },

  async getReferenceDocuments(category) {
    const params = category ? `?category=${encodeURIComponent(category)}` : "";
    return fetch(`${API}/api/reference-documents${params}`).then(r => r.json());
  },

  async uploadReferenceDocument(formData) {
    return fetch(`${API}/api/reference-documents`, { method: "POST", body: formData }).then(async r => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to upload reference document.");
      }
      return r.json();
    });
  },

  async deleteReferenceDocument(id) {
    return fetch(`${API}/api/reference-documents/${id}`, { method: "DELETE" }).then(r => r.json());
  },

  // ---------- error log ----------
  async getErrors(limit = 50, offset = 0) {
    return fetch(`${API}/api/errors?limit=${limit}&offset=${offset}`).then(r => r.json());
  },

  async getSettings() {
    return fetch(`${API}/api/settings`).then(r => r.json());
  },

  async clearErrors() {
    return fetch(`${API}/api/errors`, { method: "DELETE" }).then(r => r.json());
  },

  async clearScans() {
    return fetch(`${API}/api/scans`, { method: "DELETE" }).then(r => r.json());
  },

  // ---------- ollama models ----------
  async getOllamaModels() {
    return fetch(`${API}/api/ollama/models`).then(r => r.json());
  },

  async switchOllamaModel(modelName) {
    return fetch(`${API}/api/ollama/switch-model`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelName }),
    }).then(r => r.json());
  },

  async switchProvider(providerName) {
    return fetch(`${API}/api/settings/switch-provider`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: providerName }),
    }).then(r => r.json());
  },

  async switchGeminiModel(modelName) {
    return fetch(`${API}/api/settings/switch-gemini-model`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelName }),
    }).then(r => r.json());
  },
};
