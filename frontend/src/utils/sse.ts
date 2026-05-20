/** Parse SSE events from a fetch Response and dispatch to handlers. */
export interface SSEHandlers {
  onStage?: (stage: string) => void;
  onCell?: (data: unknown) => void;
  onError?: (message: string) => void;
  onReasoning?: (text: string) => void;
}

const INACTIVITY_TIMEOUT_MS = 60_000;

export async function consumeSSE(
  response: Response,
  handlers: SSEHandlers,
  signal?: AbortSignal
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let eventType = "";
  let eventData = "";

  let inactivityTimer: ReturnType<typeof setTimeout> | null = null;

  const clearInactivityTimer = () => {
    if (inactivityTimer !== null) {
      clearTimeout(inactivityTimer);
      inactivityTimer = null;
    }
  };

  const resetInactivityTimer = () => {
    clearInactivityTimer();
    inactivityTimer = setTimeout(() => {
      handlers.onError?.("Connection timed out — please retry");
      reader.cancel().catch(() => {});
    }, INACTIVITY_TIMEOUT_MS);
  };

  try {
    resetInactivityTimer();

    while (true) {
      if (signal?.aborted) break;

      const { done, value } = await reader.read();
      if (done) break;

      resetInactivityTimer();

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const rawLine of lines) {
        const line = rawLine.replace(/\r$/, "");

        if (line.startsWith("event:")) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          eventData = line.slice(5).trim();
        } else if (line === "") {
          if (eventType && eventData) {
            try {
              const data = JSON.parse(eventData);
              if (eventType === "stage") {
                handlers.onStage?.(data.stage);
              } else if (eventType === "cell") {
                handlers.onCell?.(data);
              } else if (eventType === "error") {
                handlers.onError?.(data.message);
              } else if (eventType === "reasoning") {
                handlers.onReasoning?.(data.text);
              }
            } catch (e) {
              console.error("[SSE] parse error:", e, eventData);
            }
          }
          eventType = "";
          eventData = "";
        }
      }
    }
  } catch (err) {
    // AbortError is expected when the signal is aborted
    if (err instanceof DOMException && err.name === "AbortError") return;
    throw err;
  } finally {
    clearInactivityTimer();
    reader.releaseLock();
  }
}
