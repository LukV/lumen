import { useState } from "react";
import type { Cell } from "../types/cell";
import ChartRenderer from "./ChartRenderer";
import CodeView from "./CodeView";
import NarrativeView from "./NarrativeView";

interface CellViewProps {
  cell: Cell;
  onCellUpdate: (updated: Cell) => void;
}

export default function CellView({ cell, onCellUpdate }: CellViewProps) {
  const [showCode, setShowCode] = useState(false);

  const hasErrors = cell.result?.diagnostics?.some(
    (d) => d.severity === "error"
  );

  return (
    <div
      style={{
        border: "1px solid #e0e0e0",
        borderRadius: "8px",
        padding: "20px",
        marginBottom: "16px",
        backgroundColor: "#fff",
      }}
    >
      {/* Question header */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
        <h3
          style={{
            fontSize: "15px",
            fontWeight: 600,
            color: "#1a1a1a",
            margin: 0,
            flex: 1,
          }}
        >
          {cell.question}
        </h3>
        {cell.sql?.edited_by_user && (
          <span
            style={{
              fontSize: "10px",
              fontWeight: 600,
              color: "#3b5998",
              backgroundColor: "#e8f0fe",
              padding: "2px 8px",
              borderRadius: "10px",
              whiteSpace: "nowrap",
            }}
          >
            edited
          </span>
        )}
      </div>

      {/* Error banner */}
      {hasErrors && (
        <div
          style={{
            padding: "10px 14px",
            backgroundColor: "#fff5f5",
            border: "1px solid #fcc",
            borderRadius: "6px",
            color: "#c33",
            fontSize: "13px",
            marginBottom: "16px",
          }}
        >
          {cell.result?.diagnostics
            ?.filter((d) => d.severity === "error")
            .map((d, i) => (
              <div key={i}>
                {d.message}
                {d.hint && (
                  <span style={{ color: "#999", marginLeft: "8px" }}>
                    Hint: {d.hint}
                  </span>
                )}
              </div>
            ))}
        </div>
      )}

      {/* Chart */}
      {cell.chart && cell.result && cell.result.data.length > 0 && (
        <div style={{ marginBottom: "16px" }}>
          <ChartRenderer spec={cell.chart.spec} data={cell.result.data} />
        </div>
      )}

      {/* Narrative */}
      {cell.narrative && (
        <NarrativeView
          text={cell.narrative.text}
          dataReferences={cell.narrative.data_references}
        />
      )}

      {/* Code toggle */}
      {cell.sql && (
        <div style={{ marginTop: "12px" }}>
          <button
            onClick={() => setShowCode(!showCode)}
            style={{
              background: "none",
              border: "none",
              color: "#666",
              fontSize: "12px",
              cursor: "pointer",
              padding: "4px 0",
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            {showCode ? "Hide code" : "Show code"}
          </button>
          {showCode && <CodeView cell={cell} onCellUpdate={onCellUpdate} />}
        </div>
      )}

      {/* Footer */}
      <div
        style={{
          display: "flex",
          gap: "16px",
          marginTop: "12px",
          fontSize: "11px",
          color: "#999",
        }}
      >
        {cell.result && (
          <>
            <span>{cell.result.row_count} rows</span>
            <span>{cell.result.execution_time_ms}ms</span>
          </>
        )}
        {cell.metadata.model && <span>{cell.metadata.model}</span>}
        {cell.chart?.auto_detected && <span>auto-detected chart</span>}
      </div>
    </div>
  );
}
