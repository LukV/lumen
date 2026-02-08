/** Parse SSE events from a fetch Response and dispatch to handlers. */
export interface SSEHandlers {
  onStage?: (stage: string) => void;
  onCell?: (data: unknown) => void;
  onError?: (message: string) => void;
}

export async function consumeSSE(
  response: Response,
  handlers: SSEHandlers
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let eventType = "";
  let eventData = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

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
}
