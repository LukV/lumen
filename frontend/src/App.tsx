import { useEffect, useState } from "react";
import type { SchemaContext, EnrichedTable, EnrichedColumn } from "./types/schema";

const ROLE_COLORS: Record<string, string> = {
  key: "#8b6caf",
  time_dimension: "#4a9cc2",
  categorical: "#5a9e6f",
  measure_candidate: "#c67a3c",
  other: "#7d7d7d",
};

function RoleBadge({ role }: { role: string }) {
  const label = role === "measure_candidate" ? "measure" : role.replace("_", " ");
  return (
    <span
      style={{
        display: "inline-block",
        padding: "1px 8px",
        borderRadius: "10px",
        fontSize: "11px",
        fontWeight: 500,
        color: "#fff",
        backgroundColor: ROLE_COLORS[role] ?? "#7d7d7d",
      }}
    >
      {label}
    </span>
  );
}

function ColumnRow({ col }: { col: EnrichedColumn }) {
  const details: string[] = [];
  if (col.is_primary_key) details.push("PK");
  if (col.foreign_key) details.push(`FK → ${col.foreign_key}`);
  if (col.suggested_agg) details.push(`agg: ${col.suggested_agg}`);
  if (col.sample_values.length > 0)
    details.push(col.sample_values.slice(0, 3).join(", "));
  if (col.min_value && col.max_value)
    details.push(`${col.min_value} → ${col.max_value}`);

  return (
    <tr>
      <td style={{ fontWeight: 500 }}>{col.name}</td>
      <td style={{ color: "#666", fontFamily: "monospace", fontSize: "12px" }}>
        {col.data_type}
      </td>
      <td>
        <RoleBadge role={col.role} />
      </td>
      <td style={{ color: "#888", fontSize: "12px" }}>{details.join(" · ")}</td>
    </tr>
  );
}

function TableCard({ table }: { table: EnrichedTable }) {
  return (
    <div
      style={{
        border: "1px solid #e0e0e0",
        borderRadius: "8px",
        padding: "16px",
        marginBottom: "16px",
        backgroundColor: "#fff",
      }}
    >
      <div style={{ marginBottom: "12px" }}>
        <span style={{ fontSize: "16px", fontWeight: 600 }}>{table.name}</span>
        <span style={{ color: "#888", marginLeft: "8px", fontSize: "13px" }}>
          ~{table.row_count.toLocaleString()} rows
        </span>
        {table.comment && (
          <div style={{ color: "#666", fontSize: "13px", marginTop: "4px" }}>
            {table.comment}
          </div>
        )}
      </div>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: "13px",
        }}
      >
        <thead>
          <tr
            style={{
              borderBottom: "1px solid #eee",
              textAlign: "left",
              color: "#999",
              fontSize: "11px",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            <th style={{ padding: "4px 8px 4px 0" }}>Column</th>
            <th style={{ padding: "4px 8px" }}>Type</th>
            <th style={{ padding: "4px 8px" }}>Role</th>
            <th style={{ padding: "4px 8px" }}>Details</th>
          </tr>
        </thead>
        <tbody>
          {table.columns.map((col) => (
            <ColumnRow key={col.name} col={col} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [ctx, setCtx] = useState<SchemaContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/schema")
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
        return res.json();
      })
      .then((data: SchemaContext) => {
        setCtx(data);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div
      style={{
        maxWidth: "900px",
        margin: "0 auto",
        padding: "32px 16px",
        fontFamily: "Inter, system-ui, sans-serif",
        color: "#1a1a1a",
      }}
    >
      <header style={{ marginBottom: "32px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: 700, margin: 0 }}>Lumen</h1>
        <p style={{ color: "#666", fontSize: "14px", margin: "4px 0 0 0" }}>
          Schema Explorer
        </p>
      </header>

      {loading && <p style={{ color: "#888" }}>Loading schema...</p>}

      {error && (
        <div
          style={{
            padding: "12px 16px",
            backgroundColor: "#fff5f5",
            border: "1px solid #fcc",
            borderRadius: "6px",
            color: "#c33",
          }}
        >
          {error}
        </div>
      )}

      {ctx && (
        <>
          <div
            style={{
              marginBottom: "24px",
              padding: "12px 16px",
              backgroundColor: "#f8f9fa",
              borderRadius: "6px",
              fontSize: "13px",
              color: "#555",
            }}
          >
            Database: <strong>{ctx.schema.database}</strong> · Schema:{" "}
            <strong>{ctx.schema.schema_name}</strong> ·{" "}
            {ctx.schema.tables.length} tables · Hash: {ctx.hash.slice(0, 16)}...
          </div>

          {ctx.schema.tables.map((table) => (
            <TableCard key={table.name} table={table} />
          ))}
        </>
      )}
    </div>
  );
}
