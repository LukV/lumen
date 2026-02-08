import { useState } from "react";
import type { Cell } from "../types/cell";
import { API_BASE } from "../config";
import { consumeSSE } from "../utils/sse";
import StageIndicator from "./StageIndicator";

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

      await consumeSSE(response, {
        onStage: (stage) => setRunStage(stage),
        onCell: (data) => {
          onCellUpdate(data as Cell);
          setRunStage(null);
        },
        onError: (message) => {
          setRunError(message);
          setRunStage(null);
        },
      });
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
    <div className="code-view">
      {/* Tab bar */}
      <div className="code-view__tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`code-view__tab ${activeTab === tab.key ? "code-view__tab--active" : ""}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="code-view__content">
        {activeTab === "sql" && (
          <div>
            <textarea
              value={editedSql}
              onChange={(e) => setEditedSql(e.target.value)}
              disabled={isRunning}
              className="code-view__textarea"
            />
            <div className="code-view__actions">
              <button
                onClick={handleRun}
                disabled={!sqlChanged || isRunning}
                className="btn-run"
              >
                Run
              </button>
              {runStage && <StageIndicator stage={runStage} />}
              {runError && (
                <span className="code-view__run-error">{runError}</span>
              )}
            </div>
          </div>
        )}

        {activeTab === "chart" && (
          <pre className="code-view__pre">
            {cell.chart ? JSON.stringify(cell.chart.spec, null, 2) : "No chart spec"}
          </pre>
        )}

        {activeTab === "reasoning" && (
          <p className="code-view__reasoning">
            {cell.metadata.reasoning || "No reasoning available"}
          </p>
        )}
      </div>
    </div>
  );
}
