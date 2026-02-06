"""Schema enrichment: infer column roles from introspection data.

Adapted from DuckBook's bootstrap/generator.py. Instead of building Entity
objects, we tag columns with roles for the schema context XML.

Roles: "key", "time_dimension", "categorical", "measure_candidate", "other"
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from lumen.schema.introspector import ColumnSnapshot, SchemaSnapshot, TableSnapshot

# --- Type classification ---

_DATE_TYPES = frozenset({"date"})
_TIMESTAMP_TYPES = frozenset(
    {
        "timestamp",
        "timestamp without time zone",
        "timestamp with time zone",
        "timestamptz",
        "datetime",
    }
)
_NUMERIC_TYPES = frozenset(
    {
        "integer",
        "int",
        "int4",
        "int8",
        "bigint",
        "smallint",
        "tinyint",
        "float",
        "double",
        "real",
        "decimal",
        "numeric",
        "double precision",
        "float4",
        "float8",
    }
)
_BOOLEAN_TYPES = frozenset({"boolean", "bool"})
_STRING_TYPES = frozenset({"varchar", "character varying", "text", "char", "bpchar", "string"})

# Patterns for time column names (preferred -> fallback)
_TIME_COLUMN_PATTERNS = [
    re.compile(r"^created_at$", re.IGNORECASE),
    re.compile(r"^creation_date$", re.IGNORECASE),
    re.compile(r"^created_date$", re.IGNORECASE),
    re.compile(r"^established_date$", re.IGNORECASE),
    re.compile(r"^registration_date$", re.IGNORECASE),
    re.compile(r"^event_date$", re.IGNORECASE),
    re.compile(r"^date$", re.IGNORECASE),
    re.compile(r"^timestamp$", re.IGNORECASE),
    re.compile(r"^valid_from$", re.IGNORECASE),
]

_AUDIT_TIME_PATTERNS = [
    re.compile(r"^loaded_at$", re.IGNORECASE),
    re.compile(r"^updated_at$", re.IGNORECASE),
    re.compile(r"^modified_at$", re.IGNORECASE),
]

# Measure name patterns -> aggregation type
_MEASURE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(amount|revenue|price|cost|total|fee|salary|capital)", re.IGNORECASE), "sum"),
    (re.compile(r"(qty|quantity|count|num_|number_of)", re.IGNORECASE), "sum"),
    (re.compile(r"(score|rating|rank|percentage|pct|ratio|rate)", re.IGNORECASE), "avg"),
    (re.compile(r"(weight|duration|distance|size|length|height|width)", re.IGNORECASE), "avg"),
]

# Dimension name patterns
_DIMENSION_PATTERNS = re.compile(
    r"(_type|_status|_code|_name|_category|_class|_group|_level|_band|_zone|_region|_country"
    r"|_descr|_acronym|_text|_label|_lang|_nl|_fr|_de|_en|is_|has_)$",
    re.IGNORECASE,
)

_HIGH_CARDINALITY_RATIO = 0.9
_LOW_CARDINALITY_THRESHOLD = 200


class EnrichedColumn(BaseModel):
    name: str
    data_type: str
    is_nullable: bool = True
    comment: str | None = None
    role: str = "other"  # key, time_dimension, categorical, measure_candidate, other
    is_primary_key: bool = False
    foreign_key: str | None = None
    distinct_estimate: int | None = None
    sample_values: list[str] = Field(default_factory=list)
    min_value: str | None = None
    max_value: str | None = None
    suggested_agg: str | None = None  # sum, avg, count — for measure_candidate


class EnrichedTable(BaseModel):
    name: str
    row_count: int = 0
    comment: str | None = None
    columns: list[EnrichedColumn] = Field(default_factory=list)


class EnrichedSchema(BaseModel):
    database: str = ""
    schema_name: str = "public"
    introspected_at: str = ""
    tables: list[EnrichedTable] = Field(default_factory=list)


def enrich(snapshot: SchemaSnapshot) -> EnrichedSchema:
    """Enrich a SchemaSnapshot with inferred column roles."""
    enriched = EnrichedSchema(
        database=snapshot.database,
        schema_name=snapshot.schema_name,
        introspected_at=snapshot.introspected_at,
    )

    for table in snapshot.tables:
        enriched_table = _enrich_table(table)
        enriched.tables.append(enriched_table)

    return enriched


def _enrich_table(table: TableSnapshot) -> EnrichedTable:
    """Enrich a single table."""
    enriched = EnrichedTable(
        name=table.name,
        row_count=table.row_count,
        comment=table.comment,
    )

    for col in table.columns:
        role = _classify_role(col, table.row_count)
        suggested_agg = _infer_suggested_agg(col.name) if role == "measure_candidate" else None

        enriched.columns.append(
            EnrichedColumn(
                name=col.name,
                data_type=col.data_type,
                is_nullable=col.is_nullable,
                comment=col.comment,
                role=role,
                is_primary_key=col.is_primary_key,
                foreign_key=col.foreign_key,
                distinct_estimate=col.distinct_estimate,
                sample_values=col.sample_values,
                min_value=col.min_value,
                max_value=col.max_value,
                suggested_agg=suggested_agg,
            )
        )

    return enriched


def _normalize_type(col_type: str) -> str:
    """Normalize a Postgres type string for matching."""
    base = re.sub(r"\(.*\)", "", col_type).strip().lower()
    return base


def _classify_role(col: ColumnSnapshot, row_count: int) -> str:
    """Classify a column into a role."""
    norm = _normalize_type(col.data_type)

    # Key detection: explicit PK/FK
    if col.is_primary_key:
        return "key"
    if col.foreign_key:
        return "key"

    # Key detection: heuristic (*_id with high cardinality)
    if _is_likely_key(col, row_count):
        return "key"

    # Time dimension: date/timestamp types
    if norm in _DATE_TYPES or norm in _TIMESTAMP_TYPES:
        return "time_dimension"

    # Boolean: always categorical
    if norm in _BOOLEAN_TYPES:
        return "categorical"

    # String columns
    if norm in _STRING_TYPES or norm.startswith("character"):
        # Low cardinality or matching dimension patterns → categorical
        if _DIMENSION_PATTERNS.search(col.name):
            return "categorical"
        if col.distinct_estimate is not None and col.distinct_estimate <= _LOW_CARDINALITY_THRESHOLD:
            return "categorical"
        if col.distinct_estimate is not None and row_count > 0:
            ratio = col.distinct_estimate / row_count
            if ratio < _HIGH_CARDINALITY_RATIO:
                return "categorical"
        return "other"

    # Numeric columns (not keys) → measure candidate
    if norm in _NUMERIC_TYPES:
        # Numeric _id columns are keys
        if col.name.endswith("_id"):
            return "key"
        return "measure_candidate"

    return "other"


def _is_likely_key(col: ColumnSnapshot, row_count: int) -> bool:
    """Detect likely key columns from naming and cardinality."""
    if not col.name.endswith("_id"):
        return False
    if col.distinct_estimate is not None and row_count > 0:
        ratio = col.distinct_estimate / row_count
        return ratio > _HIGH_CARDINALITY_RATIO
    # If we can't determine cardinality, _id suffix alone is suggestive
    return True


def _infer_suggested_agg(column_name: str) -> str:
    """Infer the best aggregation type for a numeric column."""
    for pattern, agg in _MEASURE_PATTERNS:
        if pattern.search(column_name):
            return agg
    return "sum"
