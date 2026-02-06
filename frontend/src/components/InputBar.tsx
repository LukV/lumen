import { useState } from "react";

interface InputBarProps {
  onAsk: (question: string) => void;
  disabled: boolean;
  parentCellId?: string | null;
}

export default function InputBar({ onAsk, disabled, parentCellId }: InputBarProps) {
  const [question, setQuestion] = useState("");

  const handleSubmit = () => {
    const trimmed = question.trim();
    if (!trimmed || disabled) return;
    onAsk(trimmed);
    setQuestion("");
  };

  const placeholder = parentCellId
    ? "Refine this analysis..."
    : "Ask a question about your data...";

  return (
    <div
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        padding: "12px 16px",
        backgroundColor: "#fff",
        borderTop: "1px solid #e0e0e0",
        display: "flex",
        gap: "8px",
        justifyContent: "center",
      }}
    >
      <div style={{ display: "flex", gap: "8px", maxWidth: "868px", width: "100%" }}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
          }}
          placeholder={placeholder}
          disabled={disabled}
          style={{
            flex: 1,
            padding: "10px 14px",
            fontSize: "14px",
            border: "1px solid #d0d0d0",
            borderRadius: "8px",
            outline: "none",
            fontFamily: "Inter, system-ui, sans-serif",
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !question.trim()}
          style={{
            padding: "10px 20px",
            fontSize: "14px",
            fontWeight: 600,
            color: "#fff",
            backgroundColor: disabled || !question.trim() ? "#a0a0a0" : "#3b5998",
            border: "none",
            borderRadius: "8px",
            cursor: disabled || !question.trim() ? "not-allowed" : "pointer",
            fontFamily: "Inter, system-ui, sans-serif",
          }}
        >
          Ask
        </button>
      </div>
    </div>
  );
}
