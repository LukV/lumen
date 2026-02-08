const STAGE_LABELS: Record<string, string> = {
  thinking: "Analyzing...",
  executing: "Running query...",
  correcting: "Fixing query...",
  projecting: "Building trend projection...",
  narrating: "Writing insight...",
  rendering: "Building chart...",
};

interface StageIndicatorProps {
  stage: string;
}

export default function StageIndicator({ stage }: StageIndicatorProps) {
  const label = STAGE_LABELS[stage] ?? stage;

  return (
    <div className="stage-indicator">
      <div className="processing-dots">
        <span />
        <span />
        <span />
      </div>
      {label}
    </div>
  );
}
