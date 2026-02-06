import { useEffect, useRef, useState } from "react";
import type { Cell } from "./types/cell";
import CellView from "./components/CellView";
import InputBar from "./components/InputBar";
import StageIndicator from "./components/StageIndicator";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [cells, setCells] = useState<Cell[]>([]);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // The last cell ID is automatically used as parent for next question
  const lastCellId = cells.length > 0 ? cells[cells.length - 1].id : null;

  // Load existing notebook on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/notebook`)
      .then((res) => res.json())
      .then((data: Cell[]) => setCells(data))
      .catch(() => {
        /* notebook may be empty */
      });
  }, []);

  // Auto-scroll to bottom when new content appears
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [cells, currentStage]);

  const handleCellUpdate = (updated: Cell) => {
    setCells((prev) =>
      prev.map((c) => (c.id === updated.id ? updated : c))
    );
  };

  const handleAsk = async (question: string) => {
    setIsProcessing(true);
    setError(null);
    setCurrentStage("thinking");

    try {
      const body: { question: string; parent_cell_id?: string } = { question };
      if (lastCellId) {
        body.parent_cell_id = lastCellId;
      }

      const response = await fetch(`${API_BASE}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

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

        // Parse SSE events from buffer (SSE uses \r\n or \n line endings)
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const rawLine of lines) {
          const line = rawLine.replace(/\r$/, "");

          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            eventData = line.slice(5).trim();
          } else if (line === "") {
            // Empty line = end of event
            if (eventType && eventData) {
              console.log("[SSE]", eventType, eventData.slice(0, 120));
              try {
                const data = JSON.parse(eventData);

                if (eventType === "stage") {
                  setCurrentStage(data.stage);
                } else if (eventType === "cell") {
                  setCells((prev) => [...prev, data as Cell]);
                  setCurrentStage(null);
                } else if (eventType === "error") {
                  setError(data.message);
                  setCurrentStage(null);
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
      setError(err instanceof Error ? err.message : "Unknown error");
      setCurrentStage(null);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: "900px",
        margin: "0 auto",
        padding: "32px 16px 100px 16px",
        fontFamily: "Inter, system-ui, sans-serif",
        color: "#1a1a1a",
      }}
    >
      {/* Header */}
      <header style={{ marginBottom: "32px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: 700, margin: 0 }}>Lumen</h1>
        <p style={{ color: "#666", fontSize: "14px", margin: "4px 0 0 0" }}>
          Conversational Analytics
        </p>
      </header>

      {/* Empty state */}
      {cells.length === 0 && !isProcessing && !error && (
        <div
          style={{
            textAlign: "center",
            padding: "80px 0",
            color: "#999",
            fontSize: "15px",
          }}
        >
          Ask a question to get started
        </div>
      )}

      {/* Cells */}
      {cells.map((cell) => (
        <CellView key={cell.id} cell={cell} onCellUpdate={handleCellUpdate} />
      ))}

      {/* Stage indicator */}
      {currentStage && <StageIndicator stage={currentStage} />}

      {/* Error */}
      {error && (
        <div
          style={{
            padding: "12px 16px",
            backgroundColor: "#fff5f5",
            border: "1px solid #fcc",
            borderRadius: "6px",
            color: "#c33",
            marginBottom: "16px",
            fontSize: "14px",
          }}
        >
          {error}
        </div>
      )}

      <div ref={bottomRef} />

      {/* Input */}
      <InputBar
        onAsk={handleAsk}
        disabled={isProcessing}
        parentCellId={lastCellId}
      />
    </div>
  );
}
