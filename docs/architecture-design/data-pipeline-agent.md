---
sidebar_position: 4
title: "Data Pipeline Agent"
description: "Architecture design for an AI agent that builds, manages, and monitors data pipelines"
---

# Data Pipeline Agent

Design an AI agent that helps data engineers build and manage data pipelines by automating schema discovery, transformation generation, data quality checks, pipeline monitoring, and self-healing. This is a strong system design interview topic because it combines agentic reasoning with infrastructure automation and demands both correctness and efficiency at scale.

---

## Problem Statement

> "Design an AI-powered agent that can connect to heterogeneous data sources, discover schemas, generate SQL and Python transformations from natural language descriptions, assemble those transformations into runnable pipeline DAGs, enforce data quality, monitor pipeline health in production, and automatically heal common failures such as schema drift. Walk me through the architecture, key components, data flow, and how you would keep the system safe and cost-effective."

---

## Clarifying Questions to Ask

1. **What data sources are in scope?** Relational databases only, or also data lakes (S3/GCS), streaming systems (Kafka), and external APIs?
2. **Which orchestration framework is the target?** Airflow, Dagster, Prefect, dbt, or a custom runner? This changes the DAG generation strategy.
3. **What is the expected pipeline scale?** Number of pipelines, tables per pipeline, and volume of data flowing through -- this drives execution-layer sizing.
4. **Who approves generated pipelines?** Should the agent deploy directly, or must a data engineer review and merge generated code through a CI/CD workflow?
5. **What security posture is required?** Are we dealing with PII/PHI data? This determines credential management, row-level access policies, and audit requirements.
6. **What is the acceptable blast radius for self-healing?** Should the agent auto-fix minor schema drift without approval, or must every fix be human-approved?

---

## Requirements

### Functional Requirements

1. **Schema discovery** -- connect to data sources (databases, APIs, files) and automatically discover schemas with semantic enrichment
2. **Transformation generation** -- generate SQL/Python transformations from natural language descriptions
3. **Pipeline construction** -- assemble discovered sources and transformations into a runnable DAG (Airflow, dbt, etc.)
4. **Data quality checks** -- automatically generate and run quality checks (null rates, uniqueness, distributions, business rules)
5. **Monitoring and alerting** -- detect anomalies in pipeline runs (row count swings, duration spikes, quality failures) and alert engineers
6. **Self-healing** -- diagnose and attempt to fix common pipeline failures automatically (schema drift, null constraint violations, type mismatches)

### Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Latency (schema discovery) | < 30 seconds per source |
| Latency (transformation generation) | < 20 seconds |
| Pipeline correctness | 100% of generated SQL must be syntactically valid |
| Data quality | Detect 95% of schema drift within one pipeline run |
| Cost per pipeline task | < $0.25 |
| Security | Never expose raw credentials; use IAM roles and secret managers |

### Out of Scope

- Real-time / streaming pipeline construction (focus is on batch and micro-batch)
- Building a full-featured data catalog UI (we store catalog metadata but do not build an exploration frontend)
- Fine-tuning LLMs on proprietary SQL -- we rely on prompt engineering, few-shot examples, and sandbox validation

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface"
        Chat[Chat Interface]
        Notebook[Notebook Plugin<br/>Jupyter / Databricks]
        CICD[CI/CD Trigger<br/>dbt / Airflow]
    end

    subgraph "Agent Orchestrator"
        Planner[Pipeline Planner<br/>Decomposes requests]
        Schema[Schema Agent<br/>Discovers sources]
        Transform[Transform Agent<br/>Generates SQL/Python]
        Quality[Quality Agent<br/>Generates checks]
        Monitor[Monitor Agent<br/>Analyzes runs]
        Healer[Self-Heal Agent<br/>Fixes failures]
    end

    subgraph "Code Generation"
        SQLGen[SQL Generator]
        PyGen[Python Generator]
        DAGGen[DAG Generator<br/>Airflow / dbt]
        TestGen[Test Generator<br/>Great Expectations / dbt tests]
    end

    subgraph "Execution Layer"
        Sandbox[SQL Sandbox<br/>DuckDB / Test DB]
        Runner[Pipeline Runner<br/>Airflow / Dagster / Prefect]
        Validator[Data Validator<br/>Great Expectations]
    end

    subgraph "Data Sources"
        PG[(PostgreSQL)]
        BQ[(BigQuery)]
        S3[(S3 / Data Lake)]
        API[External APIs]
    end

    subgraph "Metadata"
        Catalog[Data Catalog<br/>Schema + Lineage]
        VectorDB[Vector Store<br/>Schema Embeddings]
        RunHistory[Run History<br/>Execution Logs]
    end

    Chat --> Planner
    Notebook --> Planner
    CICD --> Monitor

    Planner --> Schema
    Planner --> Transform
    Planner --> Quality
    Monitor --> Healer
    Healer --> Transform

    Schema --> PG
    Schema --> BQ
    Schema --> S3
    Schema --> API
    Schema --> Catalog
    Schema --> VectorDB

    Transform --> SQLGen
    Transform --> PyGen
    Quality --> TestGen
    Planner --> DAGGen

    SQLGen --> Sandbox
    DAGGen --> Runner
    TestGen --> Validator
    Runner --> RunHistory
    Validator --> RunHistory
    RunHistory --> Monitor
```

### Architecture Walkthrough

The architecture is organized into five layers. Users interact through a chat interface, a notebook plugin, or CI/CD triggers. All requests flow into an **Agent Orchestrator** layer that houses six specialized agents -- each responsible for a distinct concern (planning, schema discovery, transformation, quality, monitoring, self-healing). The orchestrator delegates to a **Code Generation** layer that produces SQL, Python, DAG definitions, and test code. All generated code is validated in a **Sandbox** before it reaches the production **Execution Layer** (Airflow, Dagster, or Prefect). A **Metadata** layer consisting of a data catalog, a vector store of schema embeddings, and run history provides the contextual backbone -- agents query it to understand what exists, what has changed, and what has happened before.

The key architectural insight is separation of concerns: the Planner never generates SQL directly; the Transform Agent never deploys a pipeline. Each agent has a narrow mandate with well-defined inputs and outputs, making the system easier to test, debug, and evolve.

---

## Component Design

### Pipeline Planner

The Planner is the entry point for all user requests. It decomposes a natural language request ("Build a pipeline that joins customers with orders and computes monthly revenue") into a structured execution plan: which sources to discover, which transformations to generate, which quality checks to apply, and how to wire them into a DAG. It coordinates the other agents, aggregates their outputs, and presents a cohesive result to the user.

**Why it exists:** Without a planner, the user would have to invoke each agent manually and stitch results together. The planner provides the "agentic loop" -- it reasons about what to do next, handles inter-agent dependencies, and re-plans when intermediate results change the approach.

**Key decisions:** The planner uses a plan-then-execute pattern rather than a purely reactive loop. It generates the full plan upfront, then executes steps, revising the plan if a step produces unexpected results (e.g., schema discovery reveals that a table does not exist).

### Schema Agent

The Schema Agent connects to heterogeneous data sources (PostgreSQL, BigQuery, S3, APIs), extracts raw schema metadata (table names, column names, types, constraints), profiles the data (sample rows, null rates, cardinality, value distributions), and enriches the schema with LLM-generated semantic descriptions (business meaning of each table and column, likely primary/foreign keys, data quality observations).

**Why it exists:** Raw schema metadata (column names like `cust_id`, `txn_amt`) is not enough for downstream agents to generate correct transformations. Semantic enrichment turns cryptic column names into business context, and profiling provides the statistical baseline needed for quality check generation.

**Key decisions:** Enriched schemas are embedded as vectors and stored in the vector store, enabling semantic search. When the Transform Agent needs to find tables relevant to a request ("monthly revenue by customer segment"), it searches the vector store rather than scanning all tables. This scales to catalogs with thousands of tables.

### Transform Agent

The Transform Agent receives a natural language transformation description along with source and (optionally) target schemas, and produces syntactically valid, well-commented SQL (or Python for complex logic). It retrieves similar existing transformations from the vector store as few-shot examples, calls the LLM with the schemas and examples in context, extracts the generated SQL, and validates it in the sandbox.

**Why it exists:** Generating correct SQL from natural language is the core value proposition of the system. Separating it into its own agent allows specialized prompt engineering, dedicated validation, and a self-correction loop.

**Key decisions:** If sandbox validation fails (syntax error, missing column), the agent re-prompts the LLM with the error message and schema context. This self-correction loop runs up to two iterations. Generated SQL is required to use standard SQL compatible with both BigQuery and PostgreSQL, use CTEs for readability, and handle NULL values explicitly.

### Quality Agent

The Quality Agent generates data quality checks for a given table. It combines rule-based checks (not-null for required columns, uniqueness for primary keys) with LLM-generated checks (value range validation, referential integrity, distribution anomaly thresholds, freshness checks for timestamp columns, business rule validation).

**Why it exists:** Data quality is the top concern for production pipelines, yet most teams under-invest in quality checks because writing them is tedious. Automating quality check generation from schema profiles and business descriptions dramatically increases coverage.

**Key decisions:** Rule-based checks are always generated -- they do not require an LLM call and are guaranteed to be correct. LLM-generated checks add business-aware coverage (e.g., "price should be positive," "order date should not be in the future") but are validated against the schema before inclusion.

### Monitor Agent

The Monitor Agent analyzes completed pipeline runs for anomalies. It compares execution duration against historical averages, checks output row counts for unexpected swings (below 50% or above 300% of the historical average), evaluates quality check results, and feeds anomalies to the LLM for root-cause analysis with severity assessment and recommended actions.

**Why it exists:** Pipeline failures are often silent -- a pipeline completes successfully but produces wrong or incomplete data. The Monitor Agent catches these "silent failures" by looking at statistical deviations rather than just exit codes.

**Key decisions:** The agent uses a hybrid approach: deterministic rules for straightforward anomalies (duration, row counts) and LLM analysis for complex pattern recognition across multiple signals. Recent run history (last 10 runs) is included in the LLM context to identify trends.

### Self-Heal Agent

When the Monitor Agent detects a failure, the Self-Heal Agent diagnoses it and attempts an automatic fix. It classifies failures using regex pattern matching against known failure types (schema drift, null constraint violations, type mismatches, timeouts, permission errors), gathers context (source schema, transformation SQL, run logs), and applies a type-specific healing strategy.

**Why it exists:** Many pipeline failures are routine and fixable (a source table added a column, a nullable column became non-nullable). Automating fixes for these common cases reduces on-call burden and mean time to recovery.

**Key decisions:** For schema drift, the agent re-discovers the source schema, computes a diff, and -- if the change is minor (column added, column renamed) -- adapts the transformation SQL automatically without human approval. For major schema changes (column removed, type changed), the agent creates a draft fix that requires human approval. This graduated autonomy balances speed with safety.

---

## Data Flow

### End-to-End Pipeline Build

```mermaid
sequenceDiagram
    participant User
    participant Planner
    participant Schema as Schema Agent
    participant Transform as Transform Agent
    participant Quality as Quality Agent
    participant Sandbox
    participant Runner as Pipeline Runner

    User->>Planner: "Build a pipeline that joins customers with orders and computes monthly revenue"
    Planner->>Planner: Decompose into steps

    Planner->>Schema: Discover 'customers' table
    Schema-->>Planner: Schema + profile

    Planner->>Schema: Discover 'orders' table
    Schema-->>Planner: Schema + profile

    Planner->>Transform: Generate join + aggregation SQL
    Transform-->>Planner: SQL transformation

    Planner->>Sandbox: Validate SQL on sample data
    Sandbox-->>Planner: Valid, 1,234 rows

    Planner->>Quality: Generate quality checks
    Quality-->>Planner: 8 quality checks

    Planner->>Planner: Assemble DAG
    Planner-->>User: Pipeline ready for review

    User->>Runner: Approve and deploy
    Runner->>Runner: Execute pipeline
    Runner-->>User: Pipeline complete (2,345,678 rows)
```

### Pipeline DAG Structure

```mermaid
graph LR
    subgraph "Generated Pipeline DAG"
        S1[Source: PostgreSQL<br/>customers table] --> T1[Transform:<br/>Clean customer data]
        S2[Source: S3<br/>transactions.parquet] --> T2[Transform:<br/>Parse transactions]
        T1 --> T3[Transform:<br/>Join customers + transactions]
        T2 --> T3
        T3 --> Q1[Quality Check:<br/>Null rates, uniqueness]
        Q1 --> T4[Transform:<br/>Aggregate monthly metrics]
        T4 --> Q2[Quality Check:<br/>Business rules]
        Q2 --> D1[Destination:<br/>BigQuery analytics table]
    end
```

The data flow follows a strict sequence. The user's natural language request enters the Planner, which decomposes it into schema discovery, transformation generation, and quality check generation steps. Schema discovery runs first because downstream agents need schema context. Once schemas are available, the Transform Agent generates SQL and the Sandbox validates it against sample data. Quality checks are generated based on the profiled schemas. Finally, the Planner assembles all components into a DAG definition (Airflow or dbt), presents it for review, and deploys on approval. In production, the Monitor Agent watches each run and triggers the Self-Heal Agent if failures occur.

---

## Variant: Natural Language Data Analysis

This variant addresses a closely related problem: instead of building reusable pipelines, the agent answers ad-hoc analytical questions from natural language by generating and executing SQL, running Python computations, and producing visualizations.

A **Planner Agent** receives the user's question and the database schema, then generates an analysis plan covering what data to fetch, what computations to run, and what visualizations to create. Specialized agents execute each step.

### Key Design Decisions

**NL-to-SQL with read-only database access.** The SQL Agent generates queries and executes them against a read-only database connection with query timeouts and row limits. This ensures the agent cannot modify production data regardless of what the LLM generates.

**Schema injection into SQL agent prompt.** The database schema (table names, columns, types, sample values) is injected directly into the SQL Agent's system prompt. For databases with hundreds of tables, RAG is used to retrieve only the tables relevant to the user's question, keeping the prompt focused and within token limits.

**SQL injection prevention via whitelist of allowed operations.** All generated SQL is validated against a whitelist that permits only SELECT statements. DDL (CREATE, DROP, ALTER) and DML (INSERT, UPDATE, DELETE) are rejected before execution. Parameterized queries are used where possible.

**Query cost estimation with EXPLAIN.** Before executing a generated query, the agent runs EXPLAIN to estimate cost. Queries predicted to scan too many rows or take too long are rejected with a suggestion to add filters or aggregations.

**Sandboxed Python execution in Docker containers.** When the analysis requires statistical computation or data transformation beyond SQL, the Python Agent generates pandas/scipy/sklearn code that runs in ephemeral Docker containers with no network access, limited CPU and memory, and a hard timeout. The container is destroyed after each execution.

**Iterative refinement.** When the user says "show me a different chart type" or "filter to just Q4," the Planner modifies the existing analysis plan rather than starting from scratch. This preserves context, avoids redundant queries, and provides a conversational analysis experience.

---

## Scaling Considerations

- **Schema caching.** Pre-compute and cache schema metadata and embeddings. Invalidate on detected schema changes rather than re-discovering on every request.
- **Transformation indexing.** Store all generated transformations in the vector store. As the library grows, the Transform Agent's few-shot examples improve, producing better SQL with fewer self-correction iterations.
- **Sandbox pooling.** Maintain a pool of warm sandbox instances (DuckDB or Docker containers) to eliminate cold-start latency for SQL validation and Python execution.
- **Horizontal orchestrator scaling.** The agent orchestrator is stateless -- conversation state lives in Redis. Any orchestrator instance can handle any request, enabling straightforward horizontal scaling.
- **Query result caching.** For the NL analysis variant, cache query results keyed on the SQL hash to avoid redundant database queries during iterative refinement.
- **Tiered monitoring.** Run deterministic anomaly checks (row counts, duration) on every pipeline run. Run LLM-based analysis only when anomalies are detected, keeping monitoring costs proportional to incident rate rather than run volume.

---

## Cost Analysis

| Operation | Tokens | Cost |
|-----------|--------|------|
| Schema discovery (per source) | 5K-15K | $0.02-$0.08 |
| Transformation generation | 10K-30K | $0.05-$0.30 |
| Quality check generation | 5K-10K | $0.02-$0.05 |
| DAG generation | 8K-20K | $0.04-$0.20 |
| Self-healing (per failure) | 10K-25K | $0.05-$0.25 |
| Monitoring analysis | 5K-15K | $0.02-$0.08 |
| **Typical full pipeline build** | **40K-100K** | **$0.20-$0.80** |

The dominant cost driver is transformation generation, especially when self-correction loops are needed. Caching similar transformations as few-shot examples reduces iteration count and therefore cost over time. Monitoring costs are kept low by reserving LLM calls for anomaly investigation rather than routine run analysis.

---

## Data Layer Deep Dive

### Database Selection Justification

| Store | Technology | Why This Choice | Alternative Considered | Why Not |
|-------|-----------|----------------|----------------------|---------|
| Pipeline metadata & query history | PostgreSQL | ACID guarantees for pipeline state, rich SQL querying for analyzing past queries, JSONB for heterogeneous query plans and results | MongoDB | Flexible schema for varied query results, but pipeline state management is inherently relational -- steps have ordering, dependencies, and foreign keys to data sources |
| Execution state & caching | Redis | Sub-ms reads for real-time pipeline status, TTL for caching query results and schema metadata, pub/sub for streaming execution progress | Memcached | Simpler, but lacks pub/sub and persistence options needed for execution state recovery |
| Data warehouses | Snowflake / BigQuery / Redshift | The agent queries these, not manages them. Requires read access to INFORMATION_SCHEMA for schema discovery; must understand each warehouse's SQL dialect differences | N/A | These are the user's existing warehouses -- the agent adapts to them |
| Large result caching | S3 (Object Storage) | Large query results (millions of rows) cannot be held in Redis. Store result snapshots with presigned URLs for retrieval | Streaming results directly | Works for small results, but large results need pagination and caching |

:::info Why PostgreSQL over MongoDB for pipeline state?
You cannot lose a half-executed pipeline state. Pipeline steps have strict ordering, dependencies between sources and transforms, and foreign key relationships to data sources and schema caches. This is inherently relational. JSONB columns give you schema flexibility where you need it (execution plans, heterogeneous results) without giving up transactional guarantees where you cannot afford to.
:::

### Schema Design

**1. pipeline_runs** -- tracks each data pipeline execution

```sql
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    natural_language_query TEXT NOT NULL,
    target_database VARCHAR(50) NOT NULL,
    target_schema VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'planning'
        CHECK (status IN ('planning', 'validating', 'executing',
                          'visualizing', 'completed', 'failed', 'cancelled')),
    generated_sql TEXT,
    sql_explanation TEXT,
    execution_plan JSONB,
    result_row_count INTEGER,
    result_s3_key TEXT,
    error_message TEXT,
    tokens_used INTEGER DEFAULT 0,
    cost_usd NUMERIC(10, 6) DEFAULT 0,
    execution_time_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- Fast lookup by user for query history display
CREATE INDEX idx_pipeline_runs_user ON pipeline_runs(user_id, created_at DESC);

-- Partial index for in-progress pipelines (monitoring dashboard)
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status)
    WHERE status NOT IN ('completed', 'failed');
```

**2. schema_cache** -- cached database schema metadata

```sql
CREATE TABLE schema_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    database_name VARCHAR(100) NOT NULL,
    schema_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(200) NOT NULL,
    column_name VARCHAR(200) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    is_nullable BOOLEAN,
    is_primary_key BOOLEAN DEFAULT false,
    foreign_key_ref TEXT,
    column_description TEXT,
    sample_values JSONB,
    row_count_estimate BIGINT,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Upsert target: one row per column
CREATE UNIQUE INDEX idx_schema_cache_unique
    ON schema_cache(database_name, schema_name, table_name, column_name);

-- Fast table-level schema retrieval
CREATE INDEX idx_schema_cache_table
    ON schema_cache(database_name, schema_name, table_name);
```

:::note Why cache schema metadata?
INFORMATION_SCHEMA queries are slow on large warehouses (5-30 seconds on Snowflake with thousands of tables). The schema rarely changes, so caching with a TTL of 1 hour eliminates repeated expensive metadata queries. The `last_synced_at` column enables staleness detection and targeted invalidation.
:::

**3. query_history** -- past queries for learning and suggestion

```sql
CREATE TABLE query_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_run_id UUID REFERENCES pipeline_runs(id),
    natural_language TEXT NOT NULL,
    generated_sql TEXT NOT NULL,
    target_database VARCHAR(100) NOT NULL,
    was_executed BOOLEAN DEFAULT false,
    was_corrected BOOLEAN DEFAULT false,
    corrected_sql TEXT,
    user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 5),
    embedding vector(1536),  -- pgvector for similarity search
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- HNSW index for fast approximate nearest neighbor search
CREATE INDEX idx_query_history_embedding
    ON query_history USING hnsw (embedding vector_cosine_ops);

-- Filter by database before similarity search
CREATE INDEX idx_query_history_database
    ON query_history(target_database, created_at DESC);
```

:::note Why store embeddings of past queries?
When a user asks a similar question to one that has been successfully answered before, the system retrieves previously successful SQL as few-shot examples for the LLM. This dramatically improves SQL generation accuracy for recurring query patterns and reduces the need for self-correction iterations.
:::

### Key Queries

**1. Schema discovery** -- load all columns for a target table with relationships

```sql
SELECT
    sc.column_name,
    sc.data_type,
    sc.is_nullable,
    sc.is_primary_key,
    sc.foreign_key_ref,
    sc.column_description,
    sc.sample_values
FROM schema_cache sc
WHERE sc.database_name = :database
  AND sc.schema_name = :schema
  AND sc.table_name = :table
ORDER BY sc.is_primary_key DESC, sc.column_name;
```

**2. Similar past query lookup** -- pgvector similarity search for finding relevant query examples

```sql
SELECT
    qh.natural_language,
    qh.generated_sql,
    qh.was_corrected,
    COALESCE(qh.corrected_sql, qh.generated_sql) AS best_sql,
    1 - (qh.embedding <=> :query_embedding) AS similarity
FROM query_history qh
WHERE qh.target_database = :database
  AND qh.was_executed = true
  AND qh.user_rating >= 3
ORDER BY qh.embedding <=> :query_embedding
LIMIT 3;
```

**3. Query success rate by database** -- analytics on which databases have highest correction rates

```sql
SELECT
    qh.target_database,
    COUNT(*) AS total_queries,
    SUM(CASE WHEN qh.was_corrected THEN 1 ELSE 0 END) AS corrected_count,
    ROUND(100.0 * SUM(CASE WHEN qh.was_corrected THEN 1 ELSE 0 END) / COUNT(*), 2)
        AS correction_rate_pct,
    AVG(qh.user_rating) FILTER (WHERE qh.user_rating IS NOT NULL) AS avg_rating
FROM query_history qh
WHERE qh.was_executed = true
GROUP BY qh.target_database
ORDER BY correction_rate_pct DESC;
```

**4. Stale schema detection** -- find tables not re-synced in over 1 hour

```sql
SELECT DISTINCT
    sc.database_name,
    sc.schema_name,
    sc.table_name,
    MAX(sc.last_synced_at) AS last_synced,
    now() - MAX(sc.last_synced_at) AS staleness
FROM schema_cache sc
GROUP BY sc.database_name, sc.schema_name, sc.table_name
HAVING MAX(sc.last_synced_at) < now() - INTERVAL '1 hour'
ORDER BY staleness DESC;
```

---

## Agent Memory Architecture

The agent's primary memory challenge is fitting database schema information into the context window. A warehouse with 500 tables and 5,000 columns cannot fit in a single prompt. The memory architecture is designed around **session-scoped context with schema-aware packing**.

### Schema-Aware Context Packing

Rather than loading the entire database schema into every prompt, the agent selectively loads only the tables relevant to the current query.

1. **User query arrives** -- "Show me monthly revenue by region"
2. **Table identification** -- A lightweight classifier (embedding similarity against table descriptions) identifies relevant tables: `orders`, `customers`, `regions`
3. **Selective schema loading** -- Only relevant table schemas are loaded into context (~500 tokens per table vs 50,000 for the full schema)
4. **Dynamic expansion** -- If the agent needs additional tables mid-execution, it issues a tool call to load more schema context

```mermaid
graph LR
    subgraph "Data Warehouse"
        WH[INFORMATION_SCHEMA<br/>500 tables, 5000 columns]
    end

    subgraph "Schema Cache (PostgreSQL)"
        SC[schema_cache table<br/>All columns cached<br/>TTL: 1 hour]
    end

    subgraph "Context Assembly"
        CLS[Table Classifier<br/>Embedding similarity]
        SEL[Selected Tables<br/>3-5 tables, ~1500 tokens]
    end

    subgraph "LLM Context Window"
        SYS[System Prompt<br/>+ SQL dialect rules]
        SCH[Relevant Schema<br/>3-5 table definitions]
        FEW[Few-Shot Examples<br/>3 similar past queries]
        USR[User Query]
    end

    WH -->|Sync every 1h| SC
    SC -->|All table descriptions| CLS
    CLS -->|Top matching tables| SEL
    SEL --> SCH
    SC -->|"pgvector search"| FEW
    SYS --> SCH --> FEW --> USR
```

### Query Memory

Past successful queries for the same database are embedded and stored in the `query_history` table. When a new query arrives, the top 3 most similar past queries are retrieved via pgvector similarity search and included as few-shot examples in the LLM prompt. This dramatically improves SQL generation accuracy for recurring query patterns -- the LLM sees concrete examples of what worked before on this specific database schema.

### Execution Context

During multi-step pipelines (query, validate, execute, visualize), intermediate results are stored in Redis with the `pipeline_run_id` as the key. Each step can access results from previous steps without re-querying the data warehouse.

```
Redis key pattern:
  pipeline:{run_id}:plan      → JSON execution plan
  pipeline:{run_id}:sql       → Generated SQL
  pipeline:{run_id}:explain   → EXPLAIN output
  pipeline:{run_id}:result    → Result metadata (row count, S3 key)
  pipeline:{run_id}:progress  → Current step + status (pub/sub channel)
```

:::tip Memory budget per request
A typical request consumes approximately 3,000--5,000 tokens of schema context (3-5 tables), 1,500 tokens of few-shot examples (3 past queries), and 500 tokens for the system prompt and user query -- well within the context window while preserving room for the LLM's reasoning and SQL generation.
:::

---

## Hallucination Mitigation

Hallucination mitigation is critical for data pipeline agents because hallucinated SQL can return wrong data that **looks correct**. A user trusting a fabricated number in a revenue report is far more dangerous than a query that simply fails.

### Validation Pipeline

Every generated SQL statement passes through a multi-stage validation pipeline before execution.

```mermaid
graph LR
    NL[NL Query] --> GEN[SQL Generation<br/>LLM]
    GEN --> AST[AST Parse<br/>sqlglot]
    AST --> SV[Schema Validation<br/>Check tables/columns]
    SV --> EXP[EXPLAIN<br/>Cost estimation]
    EXP --> EXEC[Execute<br/>Read-only connection]
    EXEC --> RV[Result Validation<br/>Cross-check response]
    RV --> RESP[Response to User]

    AST -- "DDL/DML detected" --> REJ1[Reject]
    SV -- "Unknown column" --> REGEN[Re-generate<br/>with corrections]
    EXP -- "Cost too high" --> WARN[Warn user<br/>suggest filters]
    RV -- "Numbers mismatch" --> FLAG[Flag discrepancy]
    REGEN --> GEN
```

### SQL Injection Prevention

The agent generates SQL, but it **must** be read-only. The system parses the generated SQL's abstract syntax tree using [sqlglot](https://github.com/tobymao/sqlglot) before execution. Any query containing INSERT, UPDATE, DELETE, DROP, ALTER, GRANT, or TRUNCATE is rejected immediately.

:::warning Why use a SQL parser, not regex?
Regex-based validation can be bypassed with creative formatting, comments, or CTEs that obscure the true operation. AST-level parsing is immune to syntactic tricks because it understands the query's structure, not just its text.
:::

### Table and Column Hallucination

The LLM may reference tables or columns that do not exist in the target database. Every table and column referenced in the generated SQL is validated against the `schema_cache`. If a referenced column does not exist, the system returns the error to the LLM along with the actual column list for that table and asks it to regenerate. This targeted feedback produces a correct query in a single retry in most cases.

### Join Hallucination

The agent may invent join conditions between tables that have no relationship. All join conditions in generated SQL are validated against foreign key metadata in `schema_cache`. Any join on columns without a documented foreign key relationship is flagged -- it may be valid (composite business keys are common in warehouses) but requires explicit user confirmation before execution.

### Aggregation Errors

The LLM may generate SQL with incorrect GROUP BY clauses, such as selecting non-aggregated columns not present in the GROUP BY. The system performs SQL syntax validation using the target database's dialect rules (via sqlglot dialect support) and runs EXPLAIN on the query before execution to catch semantic errors that syntax validation misses.

### Result Fabrication

If the query returns no results, the agent must report "no results found" rather than inventing data. The system compares the LLM's natural language response against the actual query result set. If the response mentions specific numbers, each number is verified to exist in the returned data. Any discrepancy is flagged to the user with both the LLM's claim and the actual data.

### Schema Drift Handling

The cached schema may become outdated after DDL changes in the warehouse. If a query fails with "column not found" or "table not found" errors, the system automatically invalidates the cache for the affected table, re-syncs from INFORMATION_SCHEMA, and retries the query with the updated schema -- without requiring user intervention.

---

## Production Issues and Fixes

| Issue | Symptoms | Root Cause | Fix |
|-------|----------|-----------|-----|
| Agent generates valid but wrong SQL | Query executes successfully but returns incorrect data | Ambiguous natural language; wrong table or column interpretation | Add an "explain before execute" step: the agent explains what the SQL does in plain English, and the user confirms before execution proceeds |
| Schema cache stale after DDL changes | Agent references dropped or renamed columns | Schema cache TTL too long; no invalidation on DDL events | Add a DDL webhook from the warehouse; invalidate affected tables immediately; reduce TTL to 15 minutes for frequently changing schemas |
| Query timeout on large tables | Agent generates a full table scan on a billion-row table | No WHERE clause or missing partition filter | Add query cost estimation: run EXPLAIN first, warn the user if the estimated scan exceeds 1M rows, and suggest adding filters |
| SQL dialect mismatch | Query fails with syntax error on Snowflake but works on PostgreSQL | LLM defaulting to PostgreSQL syntax | Include the target database dialect in the system prompt; use sqlglot to transpile between dialects; include dialect-specific examples in few-shot context |
| Sensitive data exposure | Agent returns PII columns (email, SSN) in query results | No column-level access control in the agent | Maintain a column sensitivity registry; redact or mask sensitive columns in results; require explicit user confirmation to display PII |
| Cost runaway on warehouse queries | $500 Snowflake bill from a single agent session | Agent running expensive queries without cost awareness | Set per-query cost limits in the warehouse (Snowflake resource monitors); estimate cost before execution; require approval for queries estimated above $1 |
| Agent loops on ambiguous queries | Multiple failed SQL generations for vague requests like "show me the data" | No specific tables or metrics mentioned in the request | After 2 failed attempts, ask clarifying questions instead of retrying; present available tables and suggest specific queries the user might mean |

:::caution The "valid but wrong SQL" problem
This is the most dangerous production issue because there is no error signal -- the query runs, returns data, and the user trusts it. The only defense is an "explain before execute" step where the agent describes its interpretation in plain English ("This query joins the `orders` table with `customers` on `customer_id` and sums `order_total` grouped by month and region"). If the explanation does not match the user's intent, the user catches the error before execution.
:::

---

## Trade-offs & Alternatives

| Decision | Rationale | Alternative | Why Not |
|----------|-----------|-------------|---------|
| Separate agents per concern (schema, transform, quality, etc.) | Clear ownership, testable in isolation, specialized prompts per task | Single monolithic agent that handles everything | Monolithic prompts are harder to tune, debug, and evaluate; a quality regression in one capability affects all capabilities |
| Sandbox validation of all generated SQL | Catches syntax errors before deployment; enables self-correction loop | Static analysis / linting only | Static analysis misses semantic errors (wrong joins, missing columns); sandbox validation with sample data catches both syntax and logic issues |
| Vector store for schema and transformation retrieval | Scales to thousands of tables; enables semantic search ("revenue" finds `txn_amount`) | Full schema in every prompt | Full schema exceeds token limits for large catalogs; irrelevant context reduces generation quality |
| Graduated self-healing autonomy (auto-fix minor, draft-fix major) | Balances speed (common fixes applied immediately) with safety (major changes reviewed) | Fully autonomous self-healing | Unbounded auto-fix risks propagating errors; a renamed column might indicate a business logic change that requires transformation redesign |
| DuckDB as SQL sandbox | Fast, in-process, supports standard SQL, no infrastructure required | Dedicated test database instance | Test databases require provisioning, credential management, and data seeding; DuckDB runs locally with sample data |
| Read-only DB connection for NL analysis variant | Prevents data modification regardless of LLM output | Row-level security with write permissions | Defense in depth -- read-only connection is simpler, harder to misconfigure, and provides a stronger guarantee |

---

## Interview Tips

:::tip How to Present This (35 minutes)
**Minutes 0-5 -- Clarify and scope.** Ask about data sources, orchestration framework, team size, and approval workflow. State your assumptions and what you are putting out of scope (streaming, catalog UI).

**Minutes 5-10 -- Draw the architecture.** Sketch the five layers (user interface, agent orchestrator, code generation, execution, metadata) and the six agents. Emphasize the separation of concerns: each agent has a narrow mandate.

**Minutes 10-18 -- Deep dive on two components.** Pick the Transform Agent and the Self-Heal Agent. For the Transform Agent, explain the schema context injection, few-shot example retrieval, sandbox validation, and self-correction loop. For the Self-Heal Agent, explain failure classification, graduated autonomy (auto-fix minor vs. draft-fix major), and schema diff.

**Minutes 18-23 -- Walk through the data flow.** Use the sequence diagram to trace a request from "Build a pipeline that joins customers with orders" through schema discovery, transformation generation, sandbox validation, quality check generation, DAG assembly, and deployment.

**Minutes 23-28 -- Security and safety.** Cover credential management (IAM roles, secret managers, never in prompts), sandbox isolation for all generated code, read-only connections for the NL analysis variant, SQL whitelist validation, and the blast-radius model for self-healing.

**Minutes 28-32 -- Scaling and cost.** Discuss schema caching, transformation indexing for improving few-shot quality over time, sandbox pooling, and the tiered monitoring approach. Walk through the cost table and explain why the typical pipeline build stays under $1.

**Minutes 32-35 -- Trade-offs.** Highlight one or two rows from the trade-offs table. The strongest move is to explain what you chose, what you considered, and why you rejected the alternative -- this demonstrates design maturity.
:::
