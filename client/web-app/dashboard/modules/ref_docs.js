export async function loadRefDocs(apiClient) {
  const client = apiClient || window.ApiClient || (typeof ApiClient !== "undefined" ? ApiClient : null);
  if (!client || typeof client.getReferenceDocuments !== "function") {
    setTimeout(() => loadRefDocs(apiClient), 150);
    return;
  }
  const docs = await client.getReferenceDocuments();
  const grid = document.getElementById("refdoc-grid");
  if (!grid) return;
  grid.innerHTML = "";
  
  if (docs.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--muted-light); border: 1px dashed var(--border); border-radius: 12px;">No reference documents uploaded yet. Upload one above to train the local RAG database.</div>`;
    return;
  }

  for (const d of docs) {
    let imgHtml = "";
    if (d.image_path) {
      imgHtml = `<img src="/api/reference-documents/image/${d.id}" alt="${d.name}" onerror="this.src='https://placehold.co/200x120/11131e/9ca3af?text=No+Preview'">`;
    }
    grid.innerHTML += `
      <div class="ref-card">
        <span class="del" data-id="${d.id}">✕</span>
        ${imgHtml}
        <div style="font-weight:600; font-size:13px; color:var(--text);">${d.name}</div>
        <div style="font-size:11px; color:var(--accent-light); font-weight:600; text-transform:uppercase; margin-top:2px;">${d.category}</div>
        ${d.notes ? `<div style="color:var(--muted); font-size:11px; margin-top:4px; font-style:italic;">${d.notes}</div>` : ""}
        <div style="color:var(--muted-light); font-size:10px; margin-top:6px; border-t: 1px solid var(--border); padding-top:4px;">Uploaded ${new Date(d.uploaded_at + "Z").toLocaleDateString()}</div>
      </div>`;
  }
  
  grid.querySelectorAll(".del").forEach(el => {
    el.addEventListener("click", async () => {
      if (confirm(`Delete reference document?`)) {
        await apiClient.deleteReferenceDocument(el.dataset.id);
        loadRefDocs(apiClient);
      }
    });
  });
}

export function onRefDocFileSelected(input, maxMb = 10) {
  const file = input.files[0];
  const label = document.getElementById('refdoc-file-label');
  if (!file) {
    if (label) label.textContent = 'No file selected';
    return;
  }
  
  const maxBytes = maxMb * 1024 * 1024;
  if (file.size > maxBytes) {
    alert(`The selected image exceeds the maximum allowed file size of ${maxMb} MB. Please upload a smaller image.`);
    input.value = "";
    if (label) label.textContent = 'No file selected';
    return;
  }
  
  if (label) label.textContent = file.name;
}

export function bindRefDocsEvents(getMaxMb = () => 10, apiClient = window.ApiClient) {
  window.onRefDocFileSelected = (input) => onRefDocFileSelected(input, getMaxMb());

  const refdocForm = document.getElementById("refdoc-form");
  if (refdocForm) {
    refdocForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = e.target;
      const fileInput = document.getElementById("refdoc-file-input");
      const file = fileInput.files[0];
      const maxMb = getMaxMb();
      
      if (!file) {
        alert("Please select a file to upload.");
        return;
      }
      
      const maxBytes = maxMb * 1024 * 1024;
      if (file.size > maxBytes) {
        alert(`The selected image exceeds the maximum allowed file size of ${maxMb} MB. Please upload a smaller image.`);
        fileInput.value = "";
        const label = document.getElementById('refdoc-file-label');
        if (label) label.textContent = 'No file selected';
        return;
      }

      try {
        await apiClient.uploadReferenceDocument(new FormData(form));
        form.reset();
        const label = document.getElementById('refdoc-file-label');
        if (label) label.textContent = 'No file selected';
        loadRefDocs(apiClient);
      } catch (err) {
        console.error("Upload reference document failed:", err);
        alert(err.message || "Failed to upload reference document.");
      }
    });
  }
}
