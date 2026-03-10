import { t } from "../locales";

interface StageIndicatorProps {
  stage: string;
}

export default function StageIndicator({ stage }: StageIndicatorProps) {
  const label = t(`stage.${stage}`) ?? stage;

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
