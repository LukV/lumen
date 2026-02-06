export interface Diagnostic {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  hint: string | null;
}

export interface CellContext {
  parent_cell_id: string | null;
  refinement_of: string | null;
  conversation_position: number;
}

export interface CellSQL {
  query: string;
  generated_by: string;
  edited_by_user: boolean;
  user_sql_override: string | null;
}

export interface CellResult {
  columns: string[];
  column_types: string[];
  row_count: number;
  data_hash: string;
  data: Record<string, unknown>[];
  truncated: boolean;
  execution_time_ms: number;
  diagnostics: Diagnostic[];
}

export interface CellChart {
  spec: Record<string, unknown>;
  auto_detected: boolean;
  theme: string;
}

export interface DataReference {
  ref_id: string;
  text: string;
  source: string;
}

export interface CellNarrative {
  text: string;
  data_references: DataReference[];
}

export interface CellMetadata {
  model: string;
  schema_version: string;
  agent_steps: string[];
  retry_count: number;
  reasoning: string;
}

export interface Cell {
  id: string;
  created_at: string;
  question: string;
  context: CellContext;
  sql: CellSQL | null;
  result: CellResult | null;
  chart: CellChart | null;
  narrative: CellNarrative | null;
  metadata: CellMetadata;
}

export interface AskRequest {
  question: string;
  parent_cell_id?: string;
}

export interface RunSQLRequest {
  cell_id: string;
  sql: string;
}
