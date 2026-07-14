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
    return fetch(`${API}/api/reference-documents`, { method: "POST", body: formData }).then(r => r.json());
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
};
