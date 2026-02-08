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
  const [showCaveats, setShowCaveats] = useState(false);
  const [hoveredDatum, setHoveredDatum] = useState<Record<
    string,
    unknown
  > | null>(null);

  const hasErrors = cell.result?.diagnostics?.some(
    (d) => d.severity === "error"
  );
  const hasData = cell.result && cell.result.data.length > 0;
  const emptyResult =
    cell.result && cell.result.row_count === 0 && !hasErrors;

  return (
    <div className="cell">
      {/* Question header */}
      <div className="cell__header">
        <h3 className="cell__question">{cell.question}</h3>
        {cell.metadata.whatif && (
          <span className="cell__badge cell__badge--projection">projection</span>
        )}
        {cell.sql?.edited_by_user && (
          <span className="cell__badge">edited</span>
        )}
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
