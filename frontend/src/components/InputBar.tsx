import { useEffect, useState } from "react";

interface SchemaData {
  database: string;
  tables: {
    name: string;
    columns: { name: string; role: string }[];
  }[];
}

interface InputBarProps {
  onAsk: (question: string) => void;
  disabled: boolean;
  parentCellId?: string | null;
  schema?: SchemaData | null;
}

function buildPlaceholders(schema: SchemaData): string[] {
  const hints: string[] = [];
  for (const table of schema.tables) {
    const measures = table.columns.filter(
      (c) => c.role === "measure_candidate"
    );
    const timeCols = table.columns.filter((c) => c.role === "time_dimension");
    const cats = table.columns.filter((c) => c.role === "categorical");

    if (timeCols.length > 0 && measures.length > 0) {
      hints.push(
        `Show monthly ${measures[0].name} trend from ${table.name}...`
      );
    }
    if (cats.length > 0 && measures.length > 0) {
      hints.push(
        `Top 10 ${cats[0].name} by ${measures[0].name} in ${table.name}...`
      );
    }
    if (hints.length >= 4) break;
  }
  return hints.length > 0 ? hints : ["Ask a question about your data..."];
}

export default function InputBar({
  onAsk,
  disabled,
  parentCellId,
  schema,
}: InputBarProps) {
  const [question, setQuestion] = useState("");
  const [placeholderIndex, setPlaceholderIndex] = useState(0);

  const placeholders =
    parentCellId
      ? ["Refine this analysis..."]
      : schema
        ? buildPlaceholders(schema)
        : ["Ask a question about your data..."];

  // Rotate placeholders every 4s
  useEffect(() => {
    if (placeholders.length <= 1) return;
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % placeholders.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [placeholders.length]);

  const handleSubmit = () => {
    const trimmed = question.trim();
    if (!trimmed || disabled) return;
    onAsk(trimmed);
    setQuestion("");
  };

  return (
    <div className="input-bar">
      <div className="input-bar__inner">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
          }}
          placeholder={placeholders[placeholderIndex % placeholders.length]}
          disabled={disabled}
          className="input-bar__input"
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !question.trim()}
          className="btn-primary"
        >
          Ask
        </button>
      </div>
    </div>
  );
}
