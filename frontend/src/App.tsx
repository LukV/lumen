import { useCallback, useEffect, useRef, useState } from "react";
import type { Cell } from "./types/cell";
import { API_BASE } from "./config";
import { consumeSSE } from "./utils/sse";
import CellView from "./components/CellView";
import InputBar from "./components/InputBar";
import StageIndicator from "./components/StageIndicator";

interface HealthData {
  ok: boolean;
  connection_name?: string;
  database?: string;
}

function pickRandom<T>(arr: T[], n: number): T[] {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  const stored = localStorage.getItem("lumen-theme");
  if (stored === "light" || stored === "dark") return stored;
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
  return "light";
}

export default function App() {
  const [cells, setCells] = useState<Cell[]>([]);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const resultsScrollRef = useRef<HTMLDivElement>(null);

  const lastCellId = cells.length > 0 ? cells[cells.length - 1].id : null;
  const showResults = cells.length > 0 || isProcessing;

  // Apply theme to document
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("lumen-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  // Load notebook, suggestions, and health on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/notebook`)
      .then((res) => res.json())
      .then((data: Cell[]) => setCells(data))
      .catch(() => {});

    const fetchSuggestions = () => {
      fetch(`${API_BASE}/api/suggestions`)
        .then((res) => res.json())
        .then((data: { suggestions: string[]; generating: boolean }) => {
          if (data.suggestions.length > 0) {
            setSuggestions(pickRandom(data.suggestions, 5));
          } else if (data.generating) {
            // Retry once after 3s if still generating
            setTimeout(() => {
              fetch(`${API_BASE}/api/suggestions`)
                .then((res) => res.json())
                .then((retry: { suggestions: string[] }) => {
                  if (retry.suggestions.length > 0) {
                    setSuggestions(pickRandom(retry.suggestions, 5));
                  }
                })
                .catch(() => {});
            }, 3000);
          }
        })
        .catch(() => {});
    };
    fetchSuggestions();

    fetch(`${API_BASE}/api/health`)
      .then((res) => res.json())
      .then((data: HealthData) => setHealth(data))
      .catch(() => setHealth(null));
  }, []);

  // Health polling every 30s
  useEffect(() => {
    const interval = setInterval(() => {
      fetch(`${API_BASE}/api/health`)
        .then((res) => res.json())
        .then((data: HealthData) => setHealth(data))
        .catch(() => setHealth(null));
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  // Scroll to bottom when processing
  useEffect(() => {
    if (isProcessing && resultsScrollRef.current) {
      resultsScrollRef.current.scrollTop = resultsScrollRef.current.scrollHeight;
    }
  }, [cells, currentStage, isProcessing]);

  const handleCellUpdate = (updated: Cell) => {
    setCells((prev) =>
      prev.map((c) => (c.id === updated.id ? updated : c))
    );
  };

  const handleCellDelete = async (cellId: string) => {
    try {
      await fetch(`${API_BASE}/api/cells/${cellId}`, { method: "DELETE" });
      setCells((prev) => prev.filter((c) => c.id !== cellId));
    } catch { /* ignore */ }
  };

  const handleAsk = useCallback(
    async (question: string) => {
      setIsProcessing(true);
      setError(null);
      setCurrentStage("thinking");

      try {
        const body: { question: string; parent_cell_id?: string } = {
          question,
        };
        if (lastCellId) {
          body.parent_cell_id = lastCellId;
        }

        const response = await fetch(`${API_BASE}/api/ask`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        await consumeSSE(response, {
          onStage: (stage) => setCurrentStage(stage),
          onCell: (data) => {
            setCells((prev) => [...prev, data as Cell]);
            setCurrentStage(null);
          },
          onError: (message) => {
            setError(message);
            setCurrentStage(null);
          },
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
        setCurrentStage(null);
      } finally {
        setIsProcessing(false);
      }
    },
    [lastCellId]
  );

  const isConnected = health?.ok === true;
  const connectionLabel = health?.database || health?.connection_name;

  return (
    <div className="app">
      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-left">
          <svg width="26" height="26" viewBox="0 0 40 40" fill="none">
            <rect x="4" y="8" width="3" height="24" rx="1.5" fill="var(--logo-fill)" />
            <rect x="12" y="14" width="3" height="18" rx="1.5" fill="var(--logo-fill)" opacity="0.7" />
            <rect x="20" y="6" width="3" height="26" rx="1.5" fill="var(--logo-fill)" opacity="0.85" />
            <rect x="28" y="11" width="3" height="21" rx="1.5" fill="var(--logo-fill)" opacity="0.55" />
            <rect x="36" y="18" width="3" height="14" rx="1.5" fill="var(--logo-fill)" opacity="0.35" />
            <line x1="2" y1="33.5" x2="40" y2="33.5" stroke="var(--logo-fill)" strokeWidth="1" opacity="0.3" />
          </svg>
          <span className="topbar-wordmark">Lumen</span>
        </div>
        <div className="topbar-right">
          {health !== null && (
            <div className="conn-indicator">
              <span
                className={`conn-dot ${isConnected ? "conn-dot--connected" : "conn-dot--disconnected"}`}
              />
              {isConnected
                ? connectionLabel
                  ? connectionLabel
                  : "Connected"
                : "Not connected"}
            </div>
          )}
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title="Toggle theme"
            aria-label="Toggle theme"
          >
            {theme === "light" ? (
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
                <path
                  d="M13.5 9.2A5.5 5.5 0 016.8 2.5 6 6 0 1013.5 9.2z"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.3" />
                <path
                  d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1"
                  stroke="currentColor"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                />
              </svg>
            )}
          </button>
        </div>
      </header>

      {/* Empty state (hero view) */}
      {!showResults && (
        <div className="view-empty">
          <h1 className="hero-title">
            From question to insight
            <br />
            in one conversation.
          </h1>
          <p className="hero-sub">
            Your thinking partner for reproducible data exploration.
          </p>
          <InputBar
            variant="hero"
            onAsk={handleAsk}
            disabled={isProcessing}
            parentCellId={lastCellId}
          />
          {suggestions.length > 0 && (
            <div className="sample-prompts">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  className="sample-chip"
                  onClick={() => handleAsk(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Results state */}
      {showResults && (
        <div className="view-results">
          <div className="results-scroll" ref={resultsScrollRef}>
            <div className="results-inner">
              {cells.map((cell) => (
                <CellView
                  key={cell.id}
                  cell={cell}
                  theme={theme}
                  onCellUpdate={handleCellUpdate}
                  onCellDelete={handleCellDelete}
                />
              ))}

              {/* Stage indicator */}
              {currentStage && <StageIndicator stage={currentStage} />}

              {/* Error */}
              {error && (
                <div className="app-error">
                  <span className="app-error__text">{error}</span>
                  <button
                    className="app-error__dismiss"
                    onClick={() => setError(null)}
                    aria-label="Dismiss error"
                  >
                    &times;
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Bottom input bar */}
          <div className="bottom-input-bar">
            <div className="bottom-input-inner">
              <InputBar
                variant="compact"
                onAsk={handleAsk}
                disabled={isProcessing}
                parentCellId={lastCellId}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
