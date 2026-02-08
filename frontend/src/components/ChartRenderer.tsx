import { Component, type ReactNode, useCallback, useMemo } from "react";
import { VegaLite } from "react-vega";

type Theme = "light" | "dark";

interface ChartRendererProps {
  spec: Record<string, unknown>;
  data: Record<string, unknown>[];
  theme: Theme;
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

// Light → dark color remapping for hardcoded color values (e.g. trend chart layers)
const DARK_COLOR_MAP: Record<string, string> = {
  "#4A2D4F": "#9B7BA0",
  "#C2876E": "#D4A08A",
  "#6B8F8A": "#7FABA5",
  "#B8A44C": "#D4C46E",
  "#8C7B6B": "#A99888",
  "#A3667E": "#C08A9E",
};

const DARK_PALETTE = ["#9B7BA0", "#D4A08A", "#7FABA5", "#D4C46E", "#A99888", "#C08A9E"];

const DARK_AXIS_OVERRIDES = {
  gridColor: "rgba(232,229,223,0.08)",
  domainColor: "#4A4843",
  tickColor: "#4A4843",
  labelColor: "#9A9590",
  titleColor: "#9A9590",
};

const DARK_LEGEND_OVERRIDES = {
  labelColor: "#9A9590",
  titleColor: "#9A9590",
};

const DARK_TITLE_OVERRIDES = {
  color: "#E8E5DF",
};

/** Remap hardcoded color values in encoding objects for dark mode. */
function remapEncoding(encoding: Record<string, unknown>): Record<string, unknown> {
  const result = { ...encoding };
  for (const [key, val] of Object.entries(result)) {
    if (val && typeof val === "object" && !Array.isArray(val)) {
      const enc = val as Record<string, unknown>;
      if (typeof enc.value === "string" && enc.value in DARK_COLOR_MAP) {
        result[key] = { ...enc, value: DARK_COLOR_MAP[enc.value] };
      }
    }
  }
  return result;
}

/** Deep-merge dark-mode config overrides into a Vega-Lite spec. */
function applyDarkTheme(spec: Record<string, unknown>): Record<string, unknown> {
  const s = { ...spec };

  // Merge config overrides
  const config = { ...(s.config as Record<string, unknown> ?? {}) };
  const axis = { ...(config.axis as Record<string, unknown> ?? {}), ...DARK_AXIS_OVERRIDES };
  const legend = { ...(config.legend as Record<string, unknown> ?? {}), ...DARK_LEGEND_OVERRIDES };
  const title = { ...(config.title as Record<string, unknown> ?? {}), ...DARK_TITLE_OVERRIDES };
  const range = { ...(config.range as Record<string, unknown> ?? {}), category: DARK_PALETTE };
  config.axis = axis;
  config.legend = legend;
  config.title = title;
  config.range = range;
  s.config = config;

  // Remap hardcoded color values in top-level encoding
  if (s.encoding && typeof s.encoding === "object") {
    s.encoding = remapEncoding(s.encoding as Record<string, unknown>);
  }

  // Remap in layers
  if (Array.isArray(s.layer)) {
    s.layer = (s.layer as Record<string, unknown>[]).map((layer) => {
      if (layer.encoding && typeof layer.encoding === "object") {
        return { ...layer, encoding: remapEncoding(layer.encoding as Record<string, unknown>) };
      }
      return layer;
    });
  }

  return s;
}

export default function ChartRenderer({
  spec,
  data,
  theme,
  onHoverData,
}: ChartRendererProps) {
  // Inject data, hover selection, and theme overrides into spec
  const fullSpec = useMemo(() => {
    let s: Record<string, unknown> = {
      ...spec,
      data: { values: data },
    };

    // Apply dark theme overrides
    if (theme === "dark") {
      s = applyDarkTheme(s);
    }

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
  }, [spec, data, theme, onHoverData]);

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
