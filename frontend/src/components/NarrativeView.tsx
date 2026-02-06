import type { DataReference } from "../types/cell";

interface NarrativeViewProps {
  text: string;
  dataReferences: DataReference[];
}

export default function NarrativeView({
  text,
  dataReferences,
}: NarrativeViewProps) {
  if (!text) return null;

  // Build highlighted narrative by replacing data reference text with styled spans
  const parts: { text: string; ref: DataReference | null }[] = [];
  let remaining = text;

  // Sort references by their position in text (find first occurrence)
  const sortedRefs = [...dataReferences].sort((a, b) => {
    const posA = text.indexOf(a.text);
    const posB = text.indexOf(b.text);
    return posA - posB;
  });

  for (const ref of sortedRefs) {
    const idx = remaining.indexOf(ref.text);
    if (idx === -1) continue;

    if (idx > 0) {
      parts.push({ text: remaining.slice(0, idx), ref: null });
    }
    parts.push({ text: ref.text, ref });
    remaining = remaining.slice(idx + ref.text.length);
  }

  if (remaining) {
    parts.push({ text: remaining, ref: null });
  }

  return (
    <p
      style={{
        fontSize: "14px",
        lineHeight: "1.6",
        color: "#333",
        margin: "12px 0",
      }}
    >
      {parts.map((part, i) =>
        part.ref ? (
          <span
            key={i}
            title={part.ref.source}
            style={{
              backgroundColor: "#e8f0fe",
              padding: "1px 4px",
              borderRadius: "3px",
              cursor: "help",
            }}
          >
            {part.text}
          </span>
        ) : (
          <span key={i}>{part.text}</span>
        )
      )}
    </p>
  );
}
