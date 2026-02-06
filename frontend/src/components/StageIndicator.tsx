const STAGE_LABELS: Record<string, string> = {
  thinking: "Analyzing...",
  executing: "Running query...",
  correcting: "Fixing query...",
  narrating: "Writing insight...",
  rendering: "Building chart...",
};

interface StageIndicatorProps {
  stage: string;
}

export default function StageIndicator({ stage }: StageIndicatorProps) {
  const label = STAGE_LABELS[stage] ?? stage;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "16px 0",
        color: "#555",
        fontSize: "14px",
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      <span
        style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          backgroundColor: "#3b5998",
          animation: "pulse 1.5s ease-in-out infinite",
        }}
      />
      {label}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
