




async function streamAnalyze(formData, onEvent, backendUrl = "") {
  const response = await fetch(`${backendUrl}/api/analyze/stream`, { method: "POST", body: formData });
  if (!response.ok || !response.body) {
    throw new Error(`Backend returned ${response.status}. Is it running?`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (!frame.startsWith("data: ")) continue;

      const payload = JSON.parse(frame.slice(6));
      if (payload.done) {
        onEvent({ done: true, scan_id: payload.scan_id });
        continue;
      }
      if (payload.error && !payload.step) {
        
        onEvent({ systemError: payload.error });
        continue;
      }
      onEvent(payload);
    }
  }
}

if (typeof window !== "undefined") {
  window.streamAnalyze = streamAnalyze;
}
