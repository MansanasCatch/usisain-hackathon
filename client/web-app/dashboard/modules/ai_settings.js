let aiSettingsEventsBound = false;

export async function loadAISettingsTab(options = {}) {
  const {
    apiClient,
    allOllamaModels = window.allOllamaModels || [],
    loadSettingsFn = window.loadSettings
  } = options;

  const client = apiClient || window.ApiClient || (typeof ApiClient !== "undefined" ? ApiClient : null);
  if (!client || typeof client.getAISettings !== "function") {
    setTimeout(() => loadAISettingsTab(options), 150);
    return;
  }

  try {
    const [aiData, generalData] = await Promise.all([
      client.getAISettings().catch(() => null),
      client.getSettings().catch(() => null)
    ]);

    if (!aiData) return;

    const selectDefault = document.getElementById("setting-default-provider") || document.getElementById("select-default-provider");
    const activeProv = aiData.default_provider || generalData?.default_llm_provider || window.activeProvider || "ollama";
    if (selectDefault) {
      selectDefault.value = activeProv;
    }

    if (aiData.ollama) {
      const hostInput = document.getElementById("setting-ollama-host");
      const modelSelect = document.getElementById("setting-ollama-model");
      const visionInput = document.getElementById("setting-ollama-vision-model");
      
      if (hostInput) hostInput.value = aiData.ollama.host || "http://localhost:11434";
      if (visionInput) visionInput.value = aiData.ollama.vision_model || "moondream";

      if (modelSelect) {
        const currentModel = aiData.ollama.model || "llama3.2:1b";
        if (allOllamaModels && allOllamaModels.length > 0) {
          modelSelect.innerHTML = "";
          allOllamaModels.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m.name;
            opt.textContent = m.name;
            if (m.name === currentModel) opt.selected = true;
            modelSelect.appendChild(opt);
          });
        } else {
          if (!modelSelect.querySelector(`option[value="${currentModel}"]`)) {
            const opt = document.createElement("option");
            opt.value = currentModel;
            opt.textContent = currentModel;
            opt.selected = true;
            modelSelect.appendChild(opt);
          } else {
            modelSelect.value = currentModel;
          }
        }
      }
    }

    const ollamaBadge = document.getElementById("ollama-status-badge");
    const guideBox = document.getElementById("ollama-guide-box");
    const pullActions = document.getElementById("ollama-pull-actions");

    try {
      const oStatus = await (apiClient.getOllamaStatus ? apiClient.getOllamaStatus() : apiClient.getOllamaModels());
      const isOnline = oStatus && (oStatus.online !== undefined ? oStatus.online : !oStatus.error);
      const defModel = oStatus?.default_model || aiData.ollama?.model || "llama3.2:1b";

      if (isOnline) {
        if (oStatus.is_pulling) {
          if (ollamaBadge) {
            ollamaBadge.className = "badge inconclusive";
            ollamaBadge.textContent = "PULLING MODEL...";
          }
          if (guideBox) {
            guideBox.classList.remove("hidden");
            guideBox.innerHTML = `
              <div style="background: rgba(99,102,241,0.12); border: 1px solid var(--accent); border-radius: 8px; padding: 10px; color: var(--text);">
                <div style="font-weight: 700; color: var(--accent-light); display: flex; align-items: center; gap: 8px;">
                  <span style="display:inline-block; width:12px; height:12px; border:2px solid var(--accent-light); border-top-color:transparent; border-radius:50%; animation:spin 1s linear infinite;"></span>
                  ${oStatus.pull_status || `Downloading default model (${defModel})...`}
                </div>
                <div style="color: var(--muted); font-size: 11px; margin-top: 4px;">Downloading model weights in the background...</div>
              </div>`;
          }
          if (pullActions) pullActions.classList.add("hidden");
          setTimeout(() => loadAISettingsTab({ apiClient, loadSettingsFn }), 3000);
        } else if (oStatus.has_default_model || (oStatus.models && oStatus.models.length > 0)) {
          if (ollamaBadge) {
            ollamaBadge.className = "badge likely_true";
            ollamaBadge.textContent = "ONLINE · READY";
          }
          if (guideBox) {
            guideBox.classList.remove("hidden");
            guideBox.innerHTML = `
              <div style="background: rgba(46,125,50,0.12); border: 1px solid var(--good); border-radius: 8px; padding: 8px 12px; color: var(--good); font-size: 12px; font-weight: 500;">
                ✅ Ollama is active with ${oStatus.models.length} model(s). Default model <strong>${defModel}</strong> is ready for offline analysis!
              </div>`;
          }
          if (pullActions) pullActions.classList.add("hidden");
        } else {
          if (ollamaBadge) {
            ollamaBadge.className = "badge inconclusive";
            ollamaBadge.textContent = "NO MODELS";
          }
          if (guideBox) {
            guideBox.classList.remove("hidden");
            guideBox.innerHTML = `
              <div style="background: rgba(234,179,8,0.12); border: 1px solid #eab308; border-radius: 8px; padding: 10px; color: var(--text);">
                <div style="font-weight: 700; color: #eab308; margin-bottom: 2px;">⚡ Ollama Connected - Model Needed</div>
                <div style="color: var(--muted); font-size: 11.5px;">Click below to download the recommended lightweight model (<code>${defModel}</code>).</div>
              </div>`;
          }
          if (pullActions) pullActions.classList.remove("hidden");
        }
      } else {
        if (ollamaBadge) {
          ollamaBadge.className = "badge flagged";
          ollamaBadge.textContent = "NOT INSTALLED / OFFLINE";
        }
        if (guideBox) {
          guideBox.classList.remove("hidden");
          guideBox.innerHTML = `
            <div style="background: rgba(230,88,79,0.08); border: 1px solid var(--bad); border-radius: 8px; padding: 12px; color: var(--text);">
              <div style="font-weight: 700; color: var(--bad); margin-bottom: 4px;">⚠️ Ollama Not Detected</div>
              <div style="color: var(--muted); font-size: 11.5px; margin-bottom: 8px;">To run AI 100% locally and offline without API keys:</div>
              <ol style="margin: 0; padding-left: 18px; color: var(--text); font-size: 11.5px; display: flex; flex-direction: column; gap: 4px;">
                <li>Download & install from <a href="https://ollama.com/download" target="_blank" style="color: var(--accent-light); text-decoration: underline; font-weight: 600;">ollama.com/download ↗</a> (or run <code>winget install Ollama.Ollama</code>).</li>
                <li>Launch Ollama on your computer.</li>
                <li>Once detected, UsisAIn will automatically pull the default model (<code>${defModel}</code>).</li>
              </ol>
            </div>`;
        }
        if (pullActions) pullActions.classList.add("hidden");
      }
    } catch (e) {
      if (ollamaBadge) {
        ollamaBadge.className = "badge flagged";
        ollamaBadge.textContent = "OFFLINE";
      }
    }

    if (aiData.gemini) {
      const gemBadge = document.getElementById("gemini-key-status-badge");
      if (gemBadge) {
        if (aiData.gemini.has_key) {
          gemBadge.className = "badge likely_true";
          gemBadge.textContent = "ACTIVE KEY";
        } else {
          gemBadge.className = "badge inconclusive";
          gemBadge.textContent = "NO KEY";
        }
      }

      const gemHint = document.getElementById("gemini-current-key-hint");
      if (gemHint) {
        gemHint.textContent = aiData.gemini.key_masked 
          ? `Current: ${aiData.gemini.key_masked}` 
          : "No key configured";
      }

      const gemModelSelect = document.getElementById("setting-gemini-model");
      if (gemModelSelect && aiData.gemini.model) {
        gemModelSelect.value = aiData.gemini.model;
      }
    }

    if (aiData.grok) {
      const grokBadge = document.getElementById("grok-key-status-badge");
      if (grokBadge) {
        if (aiData.grok.has_key) {
          grokBadge.className = "badge likely_true";
          grokBadge.textContent = "ACTIVE KEY";
        } else {
          grokBadge.className = "badge inconclusive";
          grokBadge.textContent = "NO KEY";
        }
      }

      const grokHint = document.getElementById("grok-current-key-hint");
      if (grokHint) {
        grokHint.textContent = aiData.grok.key_masked 
          ? `Current: ${aiData.grok.key_masked}` 
          : "No key configured";
      }

      const grokModelSelect = document.getElementById("setting-grok-model");
      if (grokModelSelect) {
        const curM = aiData.grok.model || "openai/gpt-oss-120b";
        const avail = aiData.grok.available_models || [];
        if (avail.length > 0) {
          grokModelSelect.innerHTML = "";
          avail.forEach(m => {
            const mName = typeof m === "string" ? m : m.name;
            const opt = document.createElement("option");
            opt.value = mName;
            opt.textContent = mName;
            if (mName === curM || (curM === "gpt-oss-120b" && mName.endsWith("gpt-oss-120b"))) {
              opt.selected = true;
            }
            grokModelSelect.appendChild(opt);
          });
        } else if (aiData.grok.model) {
          grokModelSelect.value = aiData.grok.model;
        }
      }
    }

    const ocrBadge = document.getElementById("ocr-availability-badge");
    const ocrSummary = document.getElementById("ocr-status-summary");
    const isOcrReady = Boolean(generalData?.ocr_available);
    if (ocrBadge) {
      ocrBadge.className = isOcrReady ? "badge likely_true" : "badge inconclusive";
      ocrBadge.textContent = isOcrReady ? "AVAILABLE" : "OPTIONAL (VISION FALLBACK)";
    }
    if (ocrSummary) {
      ocrSummary.textContent = isOcrReady
        ? "Tesseract OCR engine is detected and ready. Used for optical character recognition when applicable."
        : "Tesseract OCR is not installed. Multimodal vision models (Gemini, Grok, or Ollama Vision) handle visual verification smoothly without errors.";
    }

    if (!aiSettingsEventsBound) {
      aiSettingsEventsBound = true;
      bindAISettingsEvents({ apiClient, loadSettingsFn });
    }
  } catch (err) {
    console.error("Failed to load AI settings tab:", err);
  }
}

export function bindAISettingsEvents(options = {}) {
  const {
    apiClient = window.ApiClient,
    loadSettingsFn = window.loadSettings
  } = options;

  const toastFeedback = (msg, isErr = false) => {
    const toast = document.getElementById("model-switch-toast");
    const toastMsg = document.getElementById("model-switch-toast-message");
    const toastIcon = toast?.querySelector(".toast-icon");
    if (!toast || !toastMsg) return;
    toastMsg.innerHTML = msg;
    toast.style.borderColor = isErr ? "var(--bad-border)" : "var(--good-border)";
    if (toastIcon) toastIcon.textContent = isErr ? "❌" : "✅";
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 4000);
  };

  const btnToggleGeminiVis = document.getElementById("btn-toggle-gemini-key-vis");
  const inputGeminiKey = document.getElementById("setting-gemini-key");
  if (btnToggleGeminiVis && inputGeminiKey) {
    btnToggleGeminiVis.addEventListener("click", () => {
      inputGeminiKey.type = inputGeminiKey.type === "password" ? "text" : "password";
      btnToggleGeminiVis.textContent = inputGeminiKey.type === "password" ? "👁️" : "🙈";
    });
  }

  const btnToggleGrokVis = document.getElementById("btn-toggle-grok-key-vis");
  const inputGrokKey = document.getElementById("setting-grok-key");
  if (btnToggleGrokVis && inputGrokKey) {
    btnToggleGrokVis.addEventListener("click", () => {
      inputGrokKey.type = inputGrokKey.type === "password" ? "text" : "password";
      btnToggleGrokVis.textContent = inputGrokKey.type === "password" ? "👁️" : "🙈";
    });
  }

  const btnSaveDefault = document.getElementById("btn-save-default-provider");
  const selectDefaultInput = document.getElementById("setting-default-provider") || document.getElementById("select-default-provider");

  async function handleApplyDefaultProvider() {
    const provider = selectDefaultInput?.value;
    if (!provider) return;

    if (btnSaveDefault) {
      btnSaveDefault.disabled = true;
      btnSaveDefault.textContent = "Applying...";
    }
    try {
      if (window.switchActiveProvider) {
        await window.switchActiveProvider(provider);
      } else {
        const res = await apiClient.switchProvider(provider);
        if (res?.status === "ok") {
          toastFeedback(`Default AI provider set to <strong>${provider.toUpperCase()}</strong>`);
          if (window.updateLlmSelectorUI) window.updateLlmSelectorUI();
          if (typeof loadSettingsFn === "function") await loadSettingsFn();
          if (window.fetchAndRenderModels) await window.fetchAndRenderModels();
        } else {
          toastFeedback("Failed to update default provider", true);
        }
      }
    } catch (err) {
      toastFeedback("Error updating default provider", true);
    } finally {
      if (btnSaveDefault) {
        btnSaveDefault.disabled = false;
        btnSaveDefault.textContent = "Apply";
      }
    }
  }

  if (btnSaveDefault) {
    btnSaveDefault.addEventListener("click", handleApplyDefaultProvider);
  }
  if (selectDefaultInput) {
    selectDefaultInput.addEventListener("change", handleApplyDefaultProvider);
  }

  const btnSaveOllama = document.getElementById("btn-save-ollama");
  if (btnSaveOllama) {
    btnSaveOllama.addEventListener("click", async () => {
      const model = document.getElementById("setting-ollama-model")?.value;
      const visionModel = document.getElementById("setting-ollama-vision-model")?.value;

      btnSaveOllama.disabled = true;
      btnSaveOllama.textContent = "Saving...";
      try {
        const res = await apiClient.updateAISettings({
          ollama_model: model || undefined,
          ollama_vision_model: visionModel || undefined
        });
        if (res?.status === "ok") {
          toastFeedback("Ollama configuration updated successfully");
          await loadAISettingsTab({ apiClient, loadSettingsFn });
          if (typeof loadSettingsFn === "function") await loadSettingsFn();
          if (window.updateActiveModelUI) window.updateActiveModelUI();
          if (window.fetchAndRenderModels) await window.fetchAndRenderModels();
        } else {
          toastFeedback("Failed to update Ollama settings", true);
        }
      } catch (err) {
        toastFeedback("Error saving Ollama configuration", true);
      } finally {
        btnSaveOllama.disabled = false;
        btnSaveOllama.textContent = "Save Ollama";
      }
    });
  }

  const btnRefreshOllama = document.getElementById("btn-refresh-ollama");
  if (btnRefreshOllama) {
    btnRefreshOllama.addEventListener("click", async () => {
      btnRefreshOllama.disabled = true;
      btnRefreshOllama.textContent = "Refreshing...";
      try {
        const data = await apiClient.getOllamaModels();
        if (data?.models) {
          window.allOllamaModels = data.models;
          toastFeedback(`Loaded <strong>${data.models.length}</strong> local Ollama models`);
        }
        await loadAISettingsTab({ apiClient, allOllamaModels: window.allOllamaModels, loadSettingsFn });
      } catch (err) {
        toastFeedback("Failed to reach Ollama", true);
      } finally {
        btnRefreshOllama.disabled = false;
        btnRefreshOllama.textContent = "🔄 Refresh Models";
      }
    });
  }

  const btnPullDefault = document.getElementById("btn-pull-default-ollama");
  if (btnPullDefault) {
    btnPullDefault.addEventListener("click", async () => {
      btnPullDefault.disabled = true;
      btnPullDefault.textContent = "Starting download...";
      try {
        const res = await (apiClient.pullOllamaModel ? apiClient.pullOllamaModel("llama3.2:1b") : Promise.resolve({}));
        toastFeedback(res?.message || "Pull started in background");
        await loadAISettingsTab({ apiClient, loadSettingsFn });
      } catch (err) {
        toastFeedback("Failed to trigger model pull", true);
      } finally {
        btnPullDefault.disabled = false;
        btnPullDefault.textContent = "📥 Auto-Pull Default Model (llama3.2:1b)";
      }
    });
  }

  const btnSaveGemini = document.getElementById("btn-save-gemini");
  if (btnSaveGemini) {
    btnSaveGemini.addEventListener("click", async () => {
      const key = document.getElementById("setting-gemini-key")?.value?.trim();
      const model = document.getElementById("setting-gemini-model")?.value;

      btnSaveGemini.disabled = true;
      btnSaveGemini.textContent = "Updating...";
      try {
        const payload = { gemini_model: model };
        if (key) payload.gemini_api_key = key;

        const res = await apiClient.updateAISettings(payload);
        if (res?.status === "ok") {
          toastFeedback("Gemini settings updated successfully");
          if (key) document.getElementById("setting-gemini-key").value = "";
          await loadAISettingsTab({ apiClient, loadSettingsFn });
          if (typeof loadSettingsFn === "function") await loadSettingsFn();
          if (window.updateActiveModelUI) window.updateActiveModelUI();
          if (window.fetchAndRenderModels) await window.fetchAndRenderModels();
        } else {
          toastFeedback("Failed to update Gemini settings", true);
        }
      } catch (err) {
        toastFeedback("Error saving Gemini settings", true);
      } finally {
        btnSaveGemini.disabled = false;
        btnSaveGemini.textContent = "Update Gemini";
      }
    });
  }

  const btnTestGemini = document.getElementById("btn-test-gemini");
  const gemTestBox = document.getElementById("gemini-test-result");
  if (btnTestGemini) {
    btnTestGemini.addEventListener("click", async () => {
      const key = document.getElementById("setting-gemini-key")?.value?.trim();
      btnTestGemini.disabled = true;
      btnTestGemini.textContent = "Testing...";
      if (gemTestBox) {
        gemTestBox.classList.remove("hidden");
        gemTestBox.style.background = "rgba(99,102,241,0.1)";
        gemTestBox.style.color = "var(--text)";
        gemTestBox.style.border = "1px solid var(--border)";
        gemTestBox.textContent = "Sending test ping to Gemini API...";
      }

      try {
        const res = await apiClient.testApiKey("gemini", key || "");
        if (gemTestBox) {
          if (res?.status === "ok") {
            gemTestBox.style.background = "rgba(46,125,50,0.15)";
            gemTestBox.style.color = "var(--good)";
            gemTestBox.style.border = "1px solid var(--good)";
            gemTestBox.textContent = `✅ ${res.message}`;
          } else {
            gemTestBox.style.background = "rgba(230,88,79,0.15)";
            gemTestBox.style.color = "var(--bad)";
            gemTestBox.style.border = "1px solid var(--bad)";
            gemTestBox.textContent = `❌ ${res?.message || "Verification failed"}`;
          }
        }
      } catch (err) {
        if (gemTestBox) {
          gemTestBox.style.background = "rgba(230,88,79,0.15)";
          gemTestBox.style.color = "var(--bad)";
          gemTestBox.style.border = "1px solid var(--bad)";
          gemTestBox.textContent = `❌ Network error: ${err.message}`;
        }
      } finally {
        btnTestGemini.disabled = false;
        btnTestGemini.textContent = "⚡ Test Key";
      }
    });
  }

  const btnSaveGrok = document.getElementById("btn-save-grok");
  if (btnSaveGrok) {
    btnSaveGrok.addEventListener("click", async () => {
      const key = document.getElementById("setting-grok-key")?.value?.trim();
      const model = document.getElementById("setting-grok-model")?.value;

      btnSaveGrok.disabled = true;
      btnSaveGrok.textContent = "Updating...";
      try {
        const payload = { grok_model: model };
        if (key) payload.grok_api_key = key;

        const res = await apiClient.updateAISettings(payload);
        if (res?.status === "ok") {
          toastFeedback("Grok settings updated successfully");
          if (key) document.getElementById("setting-grok-key").value = "";
          await loadAISettingsTab({ apiClient, loadSettingsFn });
          if (typeof loadSettingsFn === "function") await loadSettingsFn();
          if (window.updateActiveModelUI) window.updateActiveModelUI();
          if (window.fetchAndRenderModels) await window.fetchAndRenderModels();
        } else {
          toastFeedback("Failed to update Grok settings", true);
        }
      } catch (err) {
        toastFeedback("Error saving Grok settings", true);
      } finally {
        btnSaveGrok.disabled = false;
        btnSaveGrok.textContent = "Update Grok";
      }
    });
  }

  const btnTestGrok = document.getElementById("btn-test-grok");
  const grokTestBox = document.getElementById("grok-test-result");
  if (btnTestGrok) {
    btnTestGrok.addEventListener("click", async () => {
      const key = document.getElementById("setting-grok-key")?.value?.trim();
      btnTestGrok.disabled = true;
      btnTestGrok.textContent = "Testing...";
      if (grokTestBox) {
        grokTestBox.classList.remove("hidden");
        grokTestBox.style.background = "rgba(99,102,241,0.1)";
        grokTestBox.style.color = "var(--text)";
        grokTestBox.style.border = "1px solid var(--border)";
        grokTestBox.textContent = "Sending test ping to xAI Grok API...";
      }

      try {
        const res = await apiClient.testApiKey("grok", key || "");
        if (grokTestBox) {
          if (res?.status === "ok") {
            grokTestBox.style.background = "rgba(46,125,50,0.15)";
            grokTestBox.style.color = "var(--good)";
            grokTestBox.style.border = "1px solid var(--good)";
            grokTestBox.textContent = `✅ ${res.message}`;
          } else {
            grokTestBox.style.background = "rgba(230,88,79,0.15)";
            grokTestBox.style.color = "var(--bad)";
            grokTestBox.style.border = "1px solid var(--bad)";
            grokTestBox.textContent = `❌ ${res?.message || "Verification failed"}`;
          }
        }
      } catch (err) {
        if (grokTestBox) {
          grokTestBox.style.background = "rgba(230,88,79,0.15)";
          grokTestBox.style.color = "var(--bad)";
          grokTestBox.style.border = "1px solid var(--bad)";
          grokTestBox.textContent = `❌ Network error: ${err.message}`;
        }
      } finally {
        btnTestGrok.disabled = false;
        btnTestGrok.textContent = "⚡ Test Key";
      }
    });
  }
}
