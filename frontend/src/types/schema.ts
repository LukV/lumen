export interface EnrichedColumn {
  name: string;
  data_type: string;
  is_nullable: boolean;
  comment: string | null;
  role: "key" | "time_dimension" | "categorical" | "measure_candidate" | "other";
  is_primary_key: boolean;
  foreign_key: string | null;
  distinct_estimate: number | null;
  sample_values: string[];
  min_value: string | null;
  max_value: string | null;
  suggested_agg: string | null;
}

export interface EnrichedTable {
  name: string;
  row_count: number;
  comment: string | null;
  columns: EnrichedColumn[];
}

export interface EnrichedSchema {
  database: string;
  schema_name: string;
  introspected_at: string;
  tables: EnrichedTable[];
}

export interface SchemaContext {
  schema: EnrichedSchema;
  augmented_docs: string | null;
  hash: string;
}
