import { Component, type ReactNode, useCallback, useMemo } from "react";
import { VegaLite } from "react-vega";

interface ChartRendererProps {
  spec: Record<string, unknown>;
  data: Record<string, unknown>[];
  onHoverData?: (datum: Record<string, unknown> | null) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: string;
}

class ChartErrorBoundary extends Component<
  { children: ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: "" };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="chart-error">
          Chart rendering error: {this.state.error}
        </div>
      );
    }
    return this.props.children;
  }
}

export default function ChartRenderer({
  spec,
  data,
  onHoverData,
}: ChartRendererProps) {
  // Inject data and hover selection into spec
  const fullSpec = useMemo(() => {
    const s: Record<string, unknown> = {
      ...spec,
      data: { values: data },
    };
    // Add selection param for hover if callback provided
    if (onHoverData) {
      const existingParams = (s.params as unknown[]) ?? [];
      s.params = [
        ...existingParams,
        {
          name: "hover",
          select: { type: "point", on: "pointerover", clear: "pointerout" },
        },
      ];
    }
    return s;
  }, [spec, data, onHoverData]);

  const handleHoverSignal = useCallback(
    (_name: string, value: unknown) => {
      if (!onHoverData) return;
      // Vega selection signal value is an object with the selected datum fields
      if (value && typeof value === "object" && !Array.isArray(value)) {
        const obj = value as Record<string, unknown>;
        // Empty object means no selection (pointerout)
        if (Object.keys(obj).length === 0) {
          onHoverData(null);
        } else {
          onHoverData(obj);
        }
      } else {
        onHoverData(null);
      }
    },
    [onHoverData]
  );

  const signalListeners = useMemo(() => {
    if (!onHoverData) return undefined;
    return { hover: handleHoverSignal };
  }, [onHoverData, handleHoverSignal]);

  return (
    <ChartErrorBoundary>
      <div className="chart-container">
        <VegaLite
          spec={fullSpec as never}
          actions={false}
          style={{ width: "100%" }}
          signalListeners={signalListeners}
        />
      </div>
    </ChartErrorBoundary>
  );
}
