import { useRef, useState } from "react";
import type { Cell } from "../types/cell";
import { API_BASE } from "../config";
import ChartRenderer from "./ChartRenderer";
import CodeView from "./CodeView";
import NarrativeView from "./NarrativeView";

interface CellViewProps {
  cell: Cell;
  onCellUpdate: (updated: Cell) => void;
  onCellDelete: (cellId: string) => void;
}

export default function CellView({ cell, onCellUpdate, onCellDelete }: CellViewProps) {
  const [showCode, setShowCode] = useState(false);
  const [showCaveats, setShowCaveats] = useState(false);
  const [hoveredDatum, setHoveredDatum] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const titleInputRef = useRef<HTMLInputElement>(null);

  const hasErrors = cell.result?.diagnostics?.some(
    (d) => d.severity === "error"
  );
  const hasData = cell.result && cell.result.data.length > 0;
  const emptyResult =
    cell.result && cell.result.row_count === 0 && !hasErrors;

  const displayTitle = cell.title || cell.question;

  const startEditing = () => {
    setTitleDraft(displayTitle);
    setEditingTitle(true);
    setTimeout(() => titleInputRef.current?.select(), 0);
  };

  const commitTitle = async () => {
    setEditingTitle(false);
    const newTitle = titleDraft.trim();
    if (newTitle === cell.question) {
      // Reset to default (empty title means use question)
      if (cell.title === "") return;
      try {
        await fetch(`${API_BASE}/api/cells/${cell.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: "" }),
        });
        onCellUpdate({ ...cell, title: "" });
      } catch { /* ignore */ }
      return;
    }
    if (newTitle && newTitle !== cell.title) {
      try {
        await fetch(`${API_BASE}/api/cells/${cell.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: newTitle }),
        });
        onCellUpdate({ ...cell, title: newTitle });
      } catch { /* ignore */ }
    }
  };

  const cancelEditing = () => {
    setEditingTitle(false);
  };

  const handleTitleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commitTitle();
    } else if (e.key === "Escape") {
      cancelEditing();
    }
  };

  return (
    <div className="cell">
      {/* Question header */}
      <div className="cell__header">
        {editingTitle ? (
          <input
            ref={titleInputRef}
            className="cell__title-input"
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={commitTitle}
            onKeyDown={handleTitleKeyDown}
          />
        ) : (
          <h3
            className="cell__question"
            onDoubleClick={startEditing}
            title="Double-click to edit title"
          >
            {displayTitle}
          </h3>
        )}
        {cell.metadata.whatif && (
          <span className="cell__badge cell__badge--projection">projection</span>
        )}
        {cell.sql?.edited_by_user && (
          <span className="cell__badge">edited</span>
        )}
        <button
          className="cell__delete-btn"
          onClick={() => onCellDelete(cell.id)}
          aria-label="Remove cell"
        >
          &times;
        </button>
      </div>

      {/* Error banner */}
      {hasErrors && (
        <div className="error-banner">
          <div className="error-banner__content">
            {cell.result?.diagnostics
              ?.filter((d) => d.severity === "error")
              .map((d, i) => (
                <div key={i}>
                  {d.message}
                  {d.hint && (
                    <span className="error-banner__hint">Hint: {d.hint}</span>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Empty results */}
      {emptyResult && (
        <div className="cell__empty-results">
          Query returned no results. Try broadening your filters.
        </div>
      )}

      {/* Chart */}
      {cell.chart && hasData && (
        <div className="cell__chart">
          <ChartRenderer
            spec={cell.chart.spec}
            data={cell.result!.data}
            onHoverData={setHoveredDatum}
          />
        </div>
      )}

      {/* Narrative */}
      {cell.narrative && (
        <NarrativeView
          text={cell.narrative.text}
          dataReferences={cell.narrative.data_references}
          highlightedDatum={hoveredDatum}
        />
      )}

      {/* Caveats */}
      {cell.metadata.whatif?.caveats && cell.metadata.whatif.caveats.length > 0 && (
        <div className="cell__caveats">
          <button
            onClick={() => setShowCaveats(!showCaveats)}
            className="cell__caveats-toggle"
          >
            {showCaveats ? "Hide assumptions" : "View assumptions"}
          </button>
          {showCaveats && (
            <ul className="cell__caveats-list">
              {cell.metadata.whatif.caveats.map((caveat, i) => (
                <li key={i}>{caveat}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Code toggle */}
      {cell.sql && (
        <div className="cell__code-toggle">
          <button
            onClick={() => setShowCode(!showCode)}
            className="cell__code-toggle-btn"
          >
            {showCode ? "Hide code" : "Show code"}
          </button>
          {showCode && <CodeView cell={cell} onCellUpdate={onCellUpdate} />}
        </div>
      )}

      {/* Footer */}
      <div className="cell__footer">
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
