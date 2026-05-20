import { useState } from "react";
import { t } from "../locales";

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

  const placeholder = parentCellId
    ? t("input.placeholder.followup")
    : t("input.placeholder");

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
          {t("input.submit")}
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
        {t("input.submit")}
      </button>
    </div>
  );
}
