import { Component, type ReactNode } from "react";
import { VegaLite } from "react-vega";

interface ChartRendererProps {
  spec: Record<string, unknown>;
  data: Record<string, unknown>[];
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
        <div
          style={{
            padding: "12px 16px",
            backgroundColor: "#fff5f5",
            border: "1px solid #fcc",
            borderRadius: "6px",
            color: "#c33",
            fontSize: "13px",
          }}
        >
          Chart rendering error: {this.state.error}
        </div>
      );
    }
    return this.props.children;
  }
}

export default function ChartRenderer({ spec, data }: ChartRendererProps) {
  // Inject data into spec
  const fullSpec = {
    ...spec,
    data: { values: data },
  };

  return (
    <ChartErrorBoundary>
      <div style={{ width: "100%" }}>
        <VegaLite
          spec={fullSpec as never}
          actions={false}
          style={{ width: "100%" }}
        />
      </div>
    </ChartErrorBoundary>
  );
}
