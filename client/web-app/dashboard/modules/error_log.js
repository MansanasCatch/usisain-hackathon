export async function loadErrors(openModalFn = window.openModal, apiClient) {
  const client = apiClient || window.ApiClient || (typeof ApiClient !== "undefined" ? ApiClient : null);
  if (!client || typeof client.getErrors !== "function") {
    setTimeout(() => loadErrors(openModalFn, apiClient), 150);
    return;
  }
  const errors = await client.getErrors(100);
  const tbody = document.querySelector("#errors-table tbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  
  const countEl = document.getElementById("error-count");
  if (countEl) countEl.textContent = `${errors.length} error(s) logged`;

  if (errors.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding: 40px; color: var(--muted-light);">No pipeline errors logged.</td></tr>`;
    return;
  }

  for (const err of errors) {
    const tr = document.createElement("tr");
    const stepLabel = err.step_name
      ? `Step ${err.step} — ${err.step_name}`
      : (err.error_type === "system" ? "System" : "General");
    const shortMsg = err.error_msg.length > 120 ? err.error_msg.slice(0, 120) + "…" : err.error_msg;
    
    tr.innerHTML = `
      <td>${new Date(err.created_at + "Z").toLocaleString()}</td>
      <td><span style="font-weight: 500;">${stepLabel}</span></td>
      <td><span class="badge ${err.error_type === "system" ? "flagged" : "inconclusive"}">${err.error_type}</span></td>
      <td style="font-family:monospace; font-size:12px; color: var(--bad);">${shortMsg}</td>`;
    
    tr.addEventListener("click", () => {
      if (typeof openModalFn === "function") {
        openModalFn(JSON.stringify(err));
      }
    });
    tbody.appendChild(tr);
  }
}

export function bindErrorLogEvents(openModalFn = window.openModal, apiClient = window.ApiClient) {
  const refreshBtn = document.getElementById("refresh-errors");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => loadErrors(openModalFn, apiClient));
  }
  
  const clearBtn = document.getElementById("clear-errors");
  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      if (confirm("Clear all error logs?")) {
        await apiClient.clearErrors();
        loadErrors(openModalFn, apiClient);
      }
    });
  }
}
