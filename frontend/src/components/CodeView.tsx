import { useState } from "react";
import type { Cell } from "../types/cell";
import StageIndicator from "./StageIndicator";

const API_BASE = "http://localhost:8000";

type Tab = "sql" | "chart" | "reasoning";

interface CodeViewProps {
  cell: Cell;
  onCellUpdate: (updated: Cell) => void;
}

export default function CodeView({ cell, onCellUpdate }: CodeViewProps) {
  const [activeTab, setActiveTab] = useState<Tab>("sql");
  const [editedSql, setEditedSql] = useState(cell.sql?.query ?? "");
  const [isRunning, setIsRunning] = useState(false);
  const [runStage, setRunStage] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const sqlChanged = editedSql.trim() !== (cell.sql?.query ?? "").trim();

  const handleRun = async () => {
    if (!sqlChanged || isRunning) return;
    setIsRunning(true);
    setRunError(null);
    setRunStage("thinking");

    try {
      const response = await fetch(`${API_BASE}/api/run-sql`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cell_id: cell.id, sql: editedSql }),
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);

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
                  setRunStage(data.stage);
                } else if (eventType === "cell") {
                  onCellUpdate(data as Cell);
                  setRunStage(null);
                } else if (eventType === "error") {
                  setRunError(data.message);
                  setRunStage(null);
                }
              } catch {
                console.error("[run-sql] parse error:", eventData);
              }
            }
            eventType = "";
            eventData = "";
          }
        }
      }
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "Unknown error");
      setRunStage(null);
    } finally {
      setIsRunning(false);
    }
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "sql", label: "SQL" },
    { key: "chart", label: "Chart Spec" },
    { key: "reasoning", label: "Reasoning" },
  ];

  return (
    <div style={{ marginTop: "8px" }}>
      {/* Tab bar */}
      <div style={{ display: "flex", gap: "0", borderBottom: "1px solid #e0e0e0" }}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "6px 16px",
              fontSize: "12px",
              fontWeight: activeTab === tab.key ? 600 : 400,
              color: activeTab === tab.key ? "#3b5998" : "#666",
              background: "none",
              border: "none",
              borderBottom: activeTab === tab.key ? "2px solid #3b5998" : "2px solid transparent",
              cursor: "pointer",
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ marginTop: "8px" }}>
        {activeTab === "sql" && (
          <div>
            <textarea
              value={editedSql}
              onChange={(e) => setEditedSql(e.target.value)}
              disabled={isRunning}
              style={{
                width: "100%",
                minHeight: "120px",
                padding: "12px",
                fontSize: "12px",
                fontFamily: "'SF Mono', 'Fira Code', monospace",
                lineHeight: "1.5",
                border: "1px solid #d0d0d0",
                borderRadius: "6px",
                backgroundColor: "#f8f8f8",
                resize: "vertical",
                boxSizing: "border-box",
              }}
            />
            <div style={{ display: "flex", gap: "8px", marginTop: "8px", alignItems: "center" }}>
              <button
                onClick={handleRun}
                disabled={!sqlChanged || isRunning}
                style={{
                  padding: "6px 16px",
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "#fff",
                  backgroundColor: !sqlChanged || isRunning ? "#a0a0a0" : "#3b5998",
                  border: "none",
                  borderRadius: "6px",
                  cursor: !sqlChanged || isRunning ? "not-allowed" : "pointer",
                  fontFamily: "Inter, system-ui, sans-serif",
                }}
              >
                Run
              </button>
              {runStage && <StageIndicator stage={runStage} />}
              {runError && (
                <span style={{ fontSize: "12px", color: "#c33" }}>{runError}</span>
              )}
            </div>
          </div>
        )}

        {activeTab === "chart" && (
          <pre
            style={{
              backgroundColor: "#f5f5f5",
              padding: "12px",
              borderRadius: "6px",
              fontSize: "11px",
              overflow: "auto",
              maxHeight: "300px",
              fontFamily: "'SF Mono', 'Fira Code', monospace",
              lineHeight: "1.5",
            }}
          >
            {cell.chart ? JSON.stringify(cell.chart.spec, null, 2) : "No chart spec"}
          </pre>
        )}

        {activeTab === "reasoning" && (
          <p
            style={{
              fontSize: "13px",
              lineHeight: "1.6",
              color: "#555",
              padding: "8px 0",
              margin: 0,
            }}
          >
            {cell.metadata.reasoning || "No reasoning available"}
          </p>
        )}
      </div>
    </div>
  );
}
