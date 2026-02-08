import { useCallback, useEffect, useRef, useState } from "react";
import type { Cell } from "./types/cell";
import type { SchemaData } from "./types/schema";
import { API_BASE } from "./config";
import { consumeSSE } from "./utils/sse";
import CellView from "./components/CellView";
import InputBar from "./components/InputBar";
import StageIndicator from "./components/StageIndicator";

interface HealthData {
  ok: boolean;
  connection_name?: string;
  database?: string;
}

function generateSuggestions(schema: SchemaData): string[] {
  const suggestions: string[] = [];
  for (const table of schema.tables) {
    const timeCols = table.columns.filter((c) => c.role === "time_dimension");
    const measures = table.columns.filter(
      (c) => c.role === "measure_candidate"
    );
    const cats = table.columns.filter((c) => c.role === "categorical");

    if (timeCols.length > 0 && measures.length > 0) {
      suggestions.push(
        `Show monthly ${measures[0].name} trend from ${table.name}`
      );
    }
    if (cats.length > 0 && measures.length > 0) {
      suggestions.push(
        `Top 10 ${cats[0].name} by ${measures[0].name} in ${table.name}`
      );
    }
    if (measures.length >= 2) {
      suggestions.push(
        `Compare ${measures[0].name} vs ${measures[1].name} in ${table.name}`
      );
    }
    if (suggestions.length >= 4) break;
  }
  return suggestions.slice(0, 4);
}

export default function App() {
  const [cells, setCells] = useState<Cell[]>([]);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [schema, setSchema] = useState<SchemaData | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const lastCellId = cells.length > 0 ? cells[cells.length - 1].id : null;

  // Load notebook, schema, and health on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/notebook`)
      .then((res) => res.json())
      .then((data: Cell[]) => setCells(data))
      .catch(() => {});

    fetch(`${API_BASE}/api/schema`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { schema: SchemaData } | null) => {
        if (data?.schema) setSchema(data.schema);
      })
      .catch(() => {});

    fetch(`${API_BASE}/api/health`)
      .then((res) => res.json())
      .then((data: HealthData) => setHealth(data))
      .catch(() => setHealth(null));
  }, []);

  // Health polling every 30s
  useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${API_BASE}/api/health`)
        .then((res) => res.json())
        .then((data: HealthData) => setHealth(data))
        .catch(() => setHealth(null));
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (isProcessing) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [cells, currentStage, isProcessing]);

  const handleCellUpdate = (updated: Cell) => {
    setCells((prev) =>
      prev.map((c) => (c.id === updated.id ? updated : c))
    );
  };

  const handleCellDelete = async (cellId: string) => {
    try {
      await fetch(`${API_BASE}/api/cells/${cellId}`, { method: "DELETE" });
      setCells((prev) => prev.filter((c) => c.id !== cellId));
    } catch { /* ignore */ }
  };

  const handleAsk = useCallback(
    async (question: string) => {
      setIsProcessing(true);
      setError(null);
      setCurrentStage("thinking");

      try {
        const body: { question: string; parent_cell_id?: string } = {
          question,
        };
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

        await consumeSSE(response, {
          onStage: (stage) => setCurrentStage(stage),
          onCell: (data) => {
            setCells((prev) => [...prev, data as Cell]);
            setCurrentStage(null);
          },
          onError: (message) => {
            setError(message);
            setCurrentStage(null);
          },
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
        setCurrentStage(null);
      } finally {
        setIsProcessing(false);
      }
    },
    [lastCellId]
  );

  const suggestions = schema ? generateSuggestions(schema) : [];
  const isConnected = health?.ok === true;
  const connectionLabel = health?.database || health?.connection_name;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <h1>Lumen</h1>
          <p>Conversational Analytics</p>
        </div>
        {health !== null && (
          <div className="connection-status">
            <span
              className={`status-dot ${isConnected ? "status-dot--connected" : "status-dot--disconnected"}`}
            />
            {isConnected
              ? connectionLabel
                ? `Connected to ${connectionLabel}`
                : "Connected"
              : "Not connected"}
          </div>
        )}
      </header>

      {/* Empty state */}
      {cells.length === 0 && !isProcessing && !error && (
        <div className="empty-state">
          <div className="empty-state__icon">&#9672;</div>
          <h2 className="empty-state__title">Ask a question about your data</h2>
          <p className="empty-state__subtitle">
            Lumen turns natural language into SQL, charts, and insights.
          </p>
          {schema && (
            <p className="empty-state__schema-summary">
              {schema.tables.length} table{schema.tables.length !== 1 ? "s" : ""} available
              {schema.tables.length <= 6 && (
                <>
                  {": "}
                  {schema.tables.map((t) => t.name).join(", ")}
                </>
              )}
            </p>
          )}
          {suggestions.length > 0 && (
            <div className="empty-state__suggestions">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  className="suggestion-chip"
                  onClick={() => handleAsk(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Cells */}
      {cells.map((cell) => (
        <CellView key={cell.id} cell={cell} onCellUpdate={handleCellUpdate} onCellDelete={handleCellDelete} />
      ))}

      {/* Stage indicator */}
      {currentStage && <StageIndicator stage={currentStage} />}

      {/* Error */}
      {error && (
        <div className="app-error">
          <span className="app-error__text">{error}</span>
          <button
            className="app-error__dismiss"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            &times;
          </button>
        </div>
      )}

      <div ref={bottomRef} />

      {/* Input */}
      <InputBar
        onAsk={handleAsk}
        disabled={isProcessing}
        parentCellId={lastCellId}
        schema={schema}
      />
    </div>
  );
}
