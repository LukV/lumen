import type { DataReference } from "../types/cell";

interface NarrativeViewProps {
  text: string;
  dataReferences: DataReference[];
  highlightedDatum?: Record<string, unknown> | null;
}

function datumMatchesRef(
  datum: Record<string, unknown>,
  ref: DataReference
): boolean {
  // Check if any value in the hovered datum matches the reference text
  const refText = ref.text.toLowerCase();
  for (const val of Object.values(datum)) {
    if (val == null) continue;
    const strVal = String(val).toLowerCase();
    if (refText.includes(strVal) || strVal.includes(refText)) {
      return true;
    }
  }
  return false;
}

export default function NarrativeView({
  text,
  dataReferences,
  highlightedDatum,
}: NarrativeViewProps) {
  if (!text) return null;

  // Build highlighted narrative by replacing data reference text with styled spans
  const parts: { text: string; ref: DataReference | null }[] = [];
  let remaining = text;

  // Sort references by their position in text
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
    <p className="narrative">
      {parts.map((part, i) =>
        part.ref ? (
          <span
            key={i}
            title={part.ref.source}
            className={`narrative__ref ${highlightedDatum && datumMatchesRef(highlightedDatum, part.ref) ? "narrative__ref--highlighted" : ""}`}
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
