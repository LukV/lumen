import { useEffect, useRef, useState } from "react";
import { t } from "../locales";

interface ReasoningStreamProps {
  text: string;
  isStreaming: boolean;
}

export default function ReasoningStream({ text, isStreaming }: ReasoningStreamProps) {
  const [expanded, setExpanded] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [text, expanded]);

  if (!text) return null;

  return (
    <div className="reasoning-stream">
      <button
        className="reasoning-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        {t("reasoning.label")} {expanded ? "\u25be" : "\u25b8"}
      </button>

      {expanded && (
        <div className="reasoning-content" ref={contentRef}>
          {text}
          {isStreaming && <span className="reasoning-cursor" />}
        </div>
      )}
    </div>
  );
}
