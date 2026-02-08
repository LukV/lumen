import { useState } from "react";

interface InputBarProps {
  variant: "hero" | "compact";
  onAsk: (question: string) => void;
  disabled: boolean;
  parentCellId?: string | null;
}

export default function InputBar({
  variant,
  onAsk,
  disabled,
  parentCellId,
}: InputBarProps) {
  const [question, setQuestion] = useState("");

  const placeholder =
    parentCellId
      ? "Ask a follow-up question..."
      : "Ask any question about your data...";

  const handleSubmit = () => {
    const trimmed = question.trim();
    if (!trimmed || disabled) return;
    onAsk(trimmed);
    setQuestion("");
  };

  if (variant === "hero") {
    return (
      <div className="hero-input-wrapper">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
          }}
          placeholder={placeholder}
          disabled={disabled}
          className="hero-input"
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !question.trim()}
          className="btn-ask"
        >
          Ask
        </button>
      </div>
    );
  }

  return (
    <div className="bottom-input-wrapper">
      <input
        type="text"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleSubmit();
        }}
        placeholder={placeholder}
        disabled={disabled}
        className="bottom-input"
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !question.trim()}
        className="btn-ask-sm"
      >
        Ask
      </button>
    </div>
  );
}
