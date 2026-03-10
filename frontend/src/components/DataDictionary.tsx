import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { t } from "../locales";

interface SchemaColumn {
  name: string;
  data_type: string;
  role: string;
  is_primary_key?: boolean;
  comment?: string | null;
  distinct_estimate?: number | null;
  sample_values?: string[];
  suggested_agg?: string | null;
}

interface SchemaTable {
  name: string;
  row_count: number;
  comment?: string | null;
  columns: SchemaColumn[];
}

interface DataDictionaryProps {
  tables: SchemaTable[];
  tableDescriptions: Record<string, string>;
  isOpen: boolean;
  onClose: () => void;
  onAskAbout: (question: string) => void;
}

function roleBadgeClass(role: string): string {
  switch (role) {
    case "measure_candidate":
      return "dictionary-role-badge dictionary-role-badge--accent";
    case "time_dimension":
      return "dictionary-role-badge dictionary-role-badge--info";
    case "key":
    case "categorical":
      return "dictionary-role-badge dictionary-role-badge--muted";
    case "geographic_key":
      return "dictionary-role-badge dictionary-role-badge--success";
    default:
      return "dictionary-role-badge dictionary-role-badge--muted";
  }
}

function roleLabel(role: string): string {
  switch (role) {
    case "measure_candidate":
      return "measure";
    case "time_dimension":
      return "time";
    case "geographic_key":
      return "geo";
    default:
      return role;
  }
}

const MIN_WIDTH = 340;
const DEFAULT_WIDTH = 400;
const MAX_WIDTH_RATIO = 0.5;

export default function DataDictionary({
  tables,
  tableDescriptions,
  isOpen,
  onClose,
  onAskAbout,
}: DataDictionaryProps) {
  const [search, setSearch] = useState("");
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [panelWidth, setPanelWidth] = useState(DEFAULT_WIDTH);
  const isDragging = useRef(false);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return tables;

    return tables
      .map((table) => {
        const desc = tableDescriptions[table.name]?.toLowerCase() ?? "";
        const tableMatch =
          table.name.toLowerCase().includes(q) ||
          desc.includes(q) ||
          (table.comment?.toLowerCase().includes(q) ?? false);

        const matchingColumns = table.columns.filter(
          (col) =>
            col.name.toLowerCase().includes(q) ||
            (col.comment?.toLowerCase().includes(q) ?? false)
        );

        if (tableMatch) return table;
        if (matchingColumns.length > 0) return { ...table, columns: matchingColumns };
        return null;
      })
      .filter((t): t is SchemaTable => t !== null);
  }, [tables, tableDescriptions, search]);

  const toggleTable = (name: string) => {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  // Resize drag handlers
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const maxW = window.innerWidth * MAX_WIDTH_RATIO;
      const newWidth = Math.max(MIN_WIDTH, Math.min(maxW, window.innerWidth - e.clientX));
      setPanelWidth(newWidth);
    };
    const onMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  return (
    <div
      className={`dictionary-panel ${isOpen ? "open" : ""}`}
      style={{ width: panelWidth, right: isOpen ? 0 : -panelWidth }}
    >
      {/* Resize handle */}
      <div className="dictionary-resize-handle" onMouseDown={onMouseDown} />

      <div className="dictionary-header">
        <h2>{t("dictionary.title")}</h2>
        <button className="dictionary-close-btn" onClick={onClose} aria-label="Close">
          &times;
        </button>
        <input
          type="text"
          className="dictionary-search"
          placeholder={t("dictionary.search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* "Tell me about this dataset" link */}
      <div className="dictionary-overview">
        <button
          className="dictionary-overview-link"
          onClick={() => onAskAbout(t("dictionary.tellme.question"))}
        >
          {t("dictionary.tellme")} &rarr;
        </button>
      </div>

      <div className="dictionary-content">
        {filtered.map((table) => {
          const desc = tableDescriptions[table.name];
          const isExpanded = expandedTables.has(table.name);

          return (
            <div key={table.name} className="dictionary-table">
              <div
                className="dictionary-table-header"
                onClick={() => toggleTable(table.name)}
              >
                <span className={`arrow ${isExpanded ? "open" : ""}`}>
                  &#9656;
                </span>
                <div className="dictionary-table-labels">
                  {desc ? (
                    <>
                      <span className="dictionary-table-desc-label">{desc}</span>
                      <span className="dictionary-table-name-sub">{table.name}</span>
                    </>
                  ) : (
                    <span className="dictionary-table-name">{table.name}</span>
                  )}
                </div>
                <span className="dictionary-table-meta">
                  {table.row_count.toLocaleString()}
                </span>
              </div>

              {table.comment && !desc && (
                <div className="dictionary-table-desc">{table.comment}</div>
              )}

              {isExpanded && (
                <>
                  <div className="dictionary-columns">
                    {table.columns.map((col) => (
                      <div key={col.name} className="dictionary-column">
                        <div className="dictionary-column-header">
                          <code className="dictionary-column-name">{col.name}</code>
                          <span className="dictionary-column-type">{col.data_type}</span>
                          <span className={roleBadgeClass(col.role)}>
                            {roleLabel(col.role)}
                          </span>
                          {col.is_primary_key && (
                            <span className="dictionary-role-badge dictionary-role-badge--muted">
                              PK
                            </span>
                          )}
                        </div>
                        {col.comment && (
                          <div className="dictionary-column-desc">{col.comment}</div>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="dictionary-table-actions">
                    <button
                      className="dictionary-ask-table-btn"
                      onClick={() => onAskAbout(`${t("dictionary.askTable.question")} ${table.name}`)}
                    >
                      {t("dictionary.askTable")} &rarr;
                    </button>
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
