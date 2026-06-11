---
sidebar_position: 4
title: "Project: Data Pipeline Agent"
description: "Build a data analysis agent with LangChain — natural language to SQL, sandboxed Python execution, and automated visualization"
---

# Project: Data Pipeline Agent

Build an AI agent that accepts natural language questions about data, generates and executes SQL queries, performs Python-based analysis, and produces visualizations — all with safety guardrails. Uses LangChain for chain composition and custom Docker-based sandboxing for secure code execution.

:::info Framework Decision
**Why LangChain + Custom Sandboxing?**
- **LangChain for chain composition** — The SQL to Python to Visualization pipeline is inherently sequential. LangChain's chain abstraction (`RunnableSequence`, `RunnableParallel`) maps cleanly to this flow.
- **Custom sandboxing for security** — LangChain does not provide secure code execution. Generated Python code must run in isolated Docker containers with no network access, limited CPU/memory, and hard timeouts.
- **Why not LangGraph?** — The workflow is relatively linear (not a complex graph with many conditional branches). LangGraph's state machine abstraction would add overhead without benefit here.
- **Why not fully custom?** — LangChain's SQL chain utilities (`create_sql_query_chain`, `QuerySQLDataBaseTool`) handle the tricky parts of schema injection and SQL generation well. No need to reinvent these.
:::

---

## Architecture Overview

```mermaid
graph TD
    A[User Question] --> B[Schema Discovery]
    B --> C[SQL Generation]
    C --> D[SQL Validation]
    D --> E[SQL Execution]
    E --> F{Needs Analysis?}
    F -->|yes| G[Python Analysis<br/>Sandboxed]
    F -->|no| H[Response Synthesis]
    G --> I[Visualization<br/>Sandboxed]
    I --> H
    H --> J[Final Answer]
```

---

## Prerequisites

- Python 3.10+
- OpenAI API key
- A PostgreSQL or SQLite database with data to query
- Docker installed (for sandboxed Python/viz execution)

---

## Setup

```bash
pip install langchain langchain-openai langchain-community \
    sqlalchemy psycopg2-binary pandas plotly python-dotenv docker
```

`.env`:
```bash
OPENAI_API_KEY=your-key
DATABASE_URL=sqlite:///./sample_data.db
# Or: DATABASE_URL=postgresql://user:pass@localhost:5432/analytics
```

---

## Implementation

### Step 1: Database Schema Discovery

The schema discovery module connects to the database, introspects every table, samples representative values, and formats the schema into a compact string the LLM can reason over. Caching avoids redundant introspection calls on repeated questions against the same database.

```python
"""data_pipeline_agent.py -- Complete LangChain data pipeline agent."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine, inspect, text

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sample_data.db")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_ROWS = 1000
SQL_TIMEOUT_SECONDS = 30
SANDBOX_TIMEOUT_SECONDS = 30
SANDBOX_MEMORY_LIMIT = "256m"
OUTPUT_DIR = Path("output")


# ---------------------------------------------------------------------------
# Step 1: Schema Discovery
# ---------------------------------------------------------------------------


class SchemaDiscovery:
    """Introspect a database and produce a concise schema description for LLM prompts."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url)
        self._cache: Optional[str] = None
        self._cache_hash: Optional[str] = None

    def discover(self, force: bool = False) -> str:
        """Return a formatted schema string. Uses a cache unless force=True."""
        db_hash = hashlib.md5(str(self._engine.url).encode()).hexdigest()
        if not force and self._cache and self._cache_hash == db_hash:
            return self._cache

        inspector = inspect(self._engine)
        table_names = inspector.get_table_names()
        sections: list[str] = []

        for table in table_names:
            columns = inspector.get_columns(table)
            pk_cols = [
                c["name"]
                for c in inspector.get_pk_constraint(table).get("constrained_columns", [])
            ] if isinstance(inspector.get_pk_constraint(table), dict) else []

            col_lines: list[str] = []
            for col in columns:
                pk_marker = " [PK]" if col["name"] in pk_cols else ""
                nullable = "" if col.get("nullable", True) else " NOT NULL"
                samples = self._get_sample_values(table, col["name"])
                sample_str = f"  -- e.g. {', '.join(str(s) for s in samples)}" if samples else ""
                col_lines.append(
                    f"    {col['name']} {col['type']}{nullable}{pk_marker}{sample_str}"
                )

            row_count = self._get_row_count(table)
            sections.append(
                f"  {table} ({row_count} rows):\n" + "\n".join(col_lines)
            )

        schema_text = "DATABASE SCHEMA:\n" + "\n\n".join(sections)
        self._cache = schema_text
        self._cache_hash = db_hash
        return schema_text

    def _get_sample_values(self, table: str, column: str, n: int = 3) -> list[Any]:
        """Fetch up to n distinct non-null sample values for a column."""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT DISTINCT \"{column}\" FROM \"{table}\" "
                         f"WHERE \"{column}\" IS NOT NULL LIMIT :n"),
                    {"n": n},
                )
                return [row[0] for row in result]
        except Exception:
            return []

    def _get_row_count(self, table: str) -> int:
        """Return the approximate row count for a table."""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                return result.scalar() or 0
        except Exception:
            return 0

    @property
    def engine(self):
        return self._engine
```

:::info Why Sample Values?
Including 2-3 sample values per column dramatically improves SQL generation accuracy. The LLM can see that `status` contains `'shipped'`, `'delivered'`, `'pending'` rather than guessing. This is especially important for string columns used in WHERE clauses.
:::

---

### Step 2: SQL Generation and Validation Chain

The SQL chain injects the discovered schema into a system prompt, asks the LLM to produce a SELECT query, then validates the output before executing it. The validator rejects any mutation statements and enforces a row limit to prevent full-table-scan disasters.

```python
# ---------------------------------------------------------------------------
# Step 2: SQL Generation & Validation
# ---------------------------------------------------------------------------


class SQLValidator:
    """Validate generated SQL to ensure safety."""

    FORBIDDEN_KEYWORDS = [
        "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE",
        "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
        "MERGE", "REPLACE INTO",
    ]

    @classmethod
    def validate(cls, sql: str) -> tuple[bool, str]:
        """Return (is_valid, reason). Only SELECT queries pass."""
        sql_upper = sql.strip().upper()

        # Must start with SELECT or WITH (for CTEs)
        if not sql_upper.startswith(("SELECT", "WITH")):
            return False, "Query must start with SELECT or WITH (CTE)."

        # Check for forbidden mutation keywords
        for keyword in cls.FORBIDDEN_KEYWORDS:
            # Word boundary check to avoid false positives like "UPDATED_AT"
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, sql_upper):
                return False, f"Forbidden keyword detected: {keyword}"

        # Reject multiple statements (semicolon followed by more SQL)
        stripped = sql.strip().rstrip(";")
        if ";" in stripped:
            return False, "Multiple statements are not allowed."

        return True, "OK"

    @classmethod
    def enforce_limit(cls, sql: str, max_rows: int = MAX_ROWS) -> str:
        """Append a LIMIT clause if none is present."""
        sql_upper = sql.strip().upper()
        if "LIMIT" not in sql_upper:
            sql = sql.rstrip().rstrip(";") + f" LIMIT {max_rows}"
        return sql


def build_sql_chain(llm: ChatOpenAI, schema: str) -> Any:
    """Build a LangChain runnable that generates SQL from a natural language question."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", textwrap.dedent("""\
            You are a SQL expert. Given the database schema below and a user question,
            generate a single SQL SELECT query that answers the question.

            Rules:
            - Output ONLY the SQL query, no explanation, no markdown fences.
            - Use only tables and columns from the schema.
            - Always alias aggregated columns for clarity.
            - Use JOIN instead of sub-selects when practical.
            - Never generate DML (INSERT, UPDATE, DELETE) or DDL.

            {schema}
        """)),
        ("human", "{question}"),
    ])

    chain = prompt | llm | StrOutputParser()
    return chain


def execute_sql(engine, sql: str) -> tuple[list[str], list[tuple]]:
    """Execute a validated SQL query and return (columns, rows)."""
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = result.fetchall()
    return columns, rows


def sql_results_to_csv(columns: list[str], rows: list[tuple]) -> str:
    """Convert SQL results to a CSV string for downstream analysis."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()
```

:::warning SQL Injection via LLM
The validator blocks mutation keywords, but the real defense is the database connection itself. Always connect with a **read-only database user** in production. The validator is a second layer, not the only layer.
:::

---

### Step 3: Python Execution Sandbox

Generated Python code is untrusted. The sandbox runs it inside an ephemeral Docker container with no network access, hard CPU/memory limits, and a strict timeout. If Docker is unavailable (local dev), it falls back to a subprocess with `resource` limits on Linux/macOS.

```python
# ---------------------------------------------------------------------------
# Step 3: Python Execution Sandbox
# ---------------------------------------------------------------------------


@dataclass
class SandboxResult:
    """Result from a sandboxed Python execution."""
    stdout: str = ""
    stderr: str = ""
    files: dict[str, bytes] = field(default_factory=dict)
    timed_out: bool = False
    exit_code: int = 0


class PythonSandbox:
    """Execute untrusted Python code in an isolated environment."""

    DOCKER_IMAGE = "python:3.11-slim"

    def __init__(
        self,
        timeout: int = SANDBOX_TIMEOUT_SECONDS,
        memory_limit: str = SANDBOX_MEMORY_LIMIT,
    ) -> None:
        self._timeout = timeout
        self._memory_limit = memory_limit
        self._docker_available = self._check_docker()

    @staticmethod
    def _check_docker() -> bool:
        """Return True if the Docker daemon is reachable."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def execute(self, code: str, data_csv: Optional[str] = None) -> SandboxResult:
        """Run Python code and return stdout, stderr, and generated files."""
        if self._docker_available:
            return self._execute_docker(code, data_csv)
        return self._execute_subprocess(code, data_csv)

    def _execute_docker(self, code: str, data_csv: Optional[str]) -> SandboxResult:
        """Run code in an ephemeral Docker container."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write the script
            (tmppath / "script.py").write_text(code)

            # Write data if provided
            if data_csv:
                (tmppath / "data.csv").write_text(data_csv)

            # Create output directory inside the mount
            (tmppath / "output").mkdir()

            # Install dependencies inside the container, then run the script
            setup_cmd = "pip install -q pandas numpy plotly kaleido 2>/dev/null; "
            run_cmd = f"{setup_cmd}cd /workspace && python script.py"

            cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "--memory", self._memory_limit,
                "--cpus", "1.0",
                "--pids-limit", "64",
                "--read-only",
                "--tmpfs", "/tmp:size=64m",
                "-v", f"{tmppath}:/workspace",
                "-w", "/workspace",
                self.DOCKER_IMAGE,
                "bash", "-c", run_cmd,
            ]

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout + 30,  # extra time for pip install
                )
                # Collect generated files from the output directory
                generated_files: dict[str, bytes] = {}
                output_path = tmppath / "output"
                if output_path.exists():
                    for fpath in output_path.iterdir():
                        if fpath.is_file():
                            generated_files[fpath.name] = fpath.read_bytes()

                return SandboxResult(
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    files=generated_files,
                    exit_code=proc.returncode,
                )
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    stderr="Execution timed out.",
                    timed_out=True,
                    exit_code=124,
                )

    def _execute_subprocess(self, code: str, data_csv: Optional[str]) -> SandboxResult:
        """Fallback: run code in a subprocess with basic resource limits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "script.py").write_text(code)
            if data_csv:
                (tmppath / "data.csv").write_text(data_csv)
            (tmppath / "output").mkdir()

            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            try:
                proc = subprocess.run(
                    [sys.executable, str(tmppath / "script.py")],
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                    cwd=str(tmppath),
                    env=env,
                )
                generated_files: dict[str, bytes] = {}
                output_path = tmppath / "output"
                for fpath in output_path.iterdir():
                    if fpath.is_file():
                        generated_files[fpath.name] = fpath.read_bytes()

                return SandboxResult(
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    files=generated_files,
                    exit_code=proc.returncode,
                )
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    stderr="Execution timed out.",
                    timed_out=True,
                    exit_code=124,
                )
```

:::warning Docker Fallback
The subprocess fallback provides no real isolation -- it runs code as your OS user. It exists only for local development convenience. In production, always require Docker and fail fast if the daemon is unreachable.
:::

---

### Step 4: Visualization Generator

The visualization generator asks the LLM to produce Plotly code that reads a CSV and writes a chart to the sandbox output directory. If the chart generation fails, it falls back to a plain-text table so the user always gets a usable answer.

```python
# ---------------------------------------------------------------------------
# Step 4: Visualization Generator
# ---------------------------------------------------------------------------


class VizGenerator:
    """Generate Plotly visualizations from data summaries."""

    def __init__(self, llm: ChatOpenAI, sandbox: PythonSandbox) -> None:
        self._llm = llm
        self._sandbox = sandbox

    def generate(
        self,
        data_csv: str,
        user_question: str,
        analysis_summary: str,
    ) -> tuple[Optional[bytes], str]:
        """Generate a chart. Returns (chart_html_bytes, description).

        Falls back to a text table if chart generation fails.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", textwrap.dedent("""\
                You are a data visualization expert. Generate Python code using Plotly
                that creates a chart answering the user's question.

                Rules:
                - Read the data from 'data.csv' using pandas.
                - Save the chart to 'output/chart.html' using fig.write_html().
                - Also print a one-line description of the chart to stdout.
                - Use appropriate chart type (bar, line, scatter, pie) for the data.
                - Add clear title, axis labels, and a clean layout.
                - Output ONLY Python code, no markdown fences, no explanation.
            """)),
            ("human", (
                "User question: {question}\n"
                "Analysis summary: {analysis}\n"
                "Data preview (CSV, first 10 rows):\n{data_preview}"
            )),
        ])

        # Take only the first 10 rows for the prompt preview
        lines = data_csv.strip().split("\n")
        preview = "\n".join(lines[:11])

        chain = prompt | self._llm | StrOutputParser()
        viz_code = chain.invoke({
            "question": user_question,
            "analysis": analysis_summary,
            "data_preview": preview,
        })

        # Strip markdown fences if the LLM includes them despite instructions
        viz_code = re.sub(r"^```(?:python)?\n?", "", viz_code.strip())
        viz_code = re.sub(r"\n?```$", "", viz_code.strip())

        result = self._sandbox.execute(viz_code, data_csv=data_csv)

        if result.exit_code == 0 and "chart.html" in result.files:
            description = result.stdout.strip() or "Chart generated successfully."
            return result.files["chart.html"], description

        # Fallback: return a text table
        fallback_table = self._text_table(data_csv)
        return None, f"Chart generation failed. Text summary:\n{fallback_table}"

    @staticmethod
    def _text_table(data_csv: str, max_rows: int = 15) -> str:
        """Format CSV data as a plain-text aligned table."""
        lines = data_csv.strip().split("\n")
        reader = csv.reader(lines)
        rows = list(reader)
        if not rows:
            return "(empty result set)"

        # Calculate column widths
        col_widths = [
            max(len(str(row[i])) for row in rows if i < len(row))
            for i in range(len(rows[0]))
        ]
        header = rows[0]
        divider = "-+-".join("-" * w for w in col_widths)
        header_line = " | ".join(
            str(h).ljust(w) for h, w in zip(header, col_widths)
        )
        data_lines = [
            " | ".join(str(c).ljust(w) for c, w in zip(row, col_widths))
            for row in rows[1:max_rows + 1]
        ]

        parts = [header_line, divider] + data_lines
        if len(rows) - 1 > max_rows:
            parts.append(f"... and {len(rows) - 1 - max_rows} more rows")
        return "\n".join(parts)
```

---

### Step 5: Pipeline Orchestrator

The orchestrator ties every component together. It accepts a natural language question, runs the full pipeline (schema discovery, SQL generation, validation, execution, optional analysis, optional visualization), and synthesizes a human-readable answer.

```python
# ---------------------------------------------------------------------------
# Step 5: Pipeline Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class PipelineAnswer:
    """Structured result from the data pipeline agent."""
    question: str
    sql: str
    row_count: int
    analysis: str
    chart_html: Optional[bytes]
    chart_description: str
    final_answer: str
    steps: list[str] = field(default_factory=list)


class DataPipelineAgent:
    """Orchestrate the full data analysis pipeline."""

    # Question patterns that suggest deeper analysis or visualization
    ANALYSIS_KEYWORDS = [
        "trend", "compare", "correlation", "distribution", "outlier",
        "average", "growth", "percentage", "change over", "top",
        "bottom", "rank", "forecast", "seasonal", "breakdown",
    ]

    def __init__(self) -> None:
        self._llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0.0)
        self._schema_discovery = SchemaDiscovery(DATABASE_URL)
        self._sandbox = PythonSandbox()
        self._viz = VizGenerator(self._llm, self._sandbox)

    def ask(self, question: str) -> PipelineAnswer:
        """Run the full pipeline for a user question."""
        steps: list[str] = []

        # 1. Schema discovery
        schema = self._schema_discovery.discover()
        table_count = schema.count(" rows):")
        steps.append(f"Schema: {table_count} tables discovered")

        # 2. SQL generation
        sql_chain = build_sql_chain(self._llm, schema)
        raw_sql = sql_chain.invoke({"question": question, "schema": schema})

        # Strip markdown fences if present
        raw_sql = re.sub(r"^```(?:sql)?\n?", "", raw_sql.strip())
        raw_sql = re.sub(r"\n?```$", "", raw_sql.strip())

        # 3. SQL validation
        is_valid, reason = SQLValidator.validate(raw_sql)
        if not is_valid:
            return PipelineAnswer(
                question=question,
                sql=raw_sql,
                row_count=0,
                analysis="",
                chart_html=None,
                chart_description="",
                final_answer=f"SQL validation failed: {reason}",
                steps=steps + [f"Validation FAILED: {reason}"],
            )

        safe_sql = SQLValidator.enforce_limit(raw_sql)
        steps.append(f"SQL: {safe_sql[:120]}{'...' if len(safe_sql) > 120 else ''}")

        # 4. SQL execution
        try:
            columns, rows = execute_sql(self._schema_discovery.engine, safe_sql)
        except Exception as exc:
            return PipelineAnswer(
                question=question,
                sql=safe_sql,
                row_count=0,
                analysis="",
                chart_html=None,
                chart_description="",
                final_answer=f"SQL execution error: {exc}",
                steps=steps + [f"Execution FAILED: {exc}"],
            )

        steps.append(f"Results: {len(rows)} rows returned")
        data_csv = sql_results_to_csv(columns, [tuple(r) for r in rows])

        # 5. Decide if deeper analysis or visualization is warranted
        needs_analysis = self._needs_analysis(question, len(rows))

        analysis_text = ""
        chart_html: Optional[bytes] = None
        chart_desc = ""

        if needs_analysis and len(rows) > 0:
            # Generate and run analysis code in the sandbox
            analysis_text = self._run_analysis(question, data_csv)
            steps.append("Analysis: completed in sandbox")

            # Generate visualization
            chart_html, chart_desc = self._viz.generate(
                data_csv, question, analysis_text,
            )
            if chart_html:
                steps.append("Visualization: chart generated")
            else:
                steps.append("Visualization: fell back to text table")

        # 6. Synthesize final answer
        final_answer = self._synthesize(question, data_csv, analysis_text, chart_desc)
        steps.append("Answer: synthesized")

        return PipelineAnswer(
            question=question,
            sql=safe_sql,
            row_count=len(rows),
            analysis=analysis_text,
            chart_html=chart_html,
            chart_description=chart_desc,
            final_answer=final_answer,
            steps=steps,
        )

    def _needs_analysis(self, question: str, row_count: int) -> bool:
        """Decide whether the question warrants Python analysis and visualization."""
        if row_count == 0:
            return False
        question_lower = question.lower()
        return any(kw in question_lower for kw in self.ANALYSIS_KEYWORDS)

    def _run_analysis(self, question: str, data_csv: str) -> str:
        """Generate and execute Python analysis code in the sandbox."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", textwrap.dedent("""\
                You are a data analyst. Generate Python code that reads 'data.csv'
                with pandas and performs a brief statistical analysis relevant to
                the user's question.

                Rules:
                - Read from 'data.csv' using pandas.
                - Print a concise summary (5-10 lines) to stdout.
                - Include key statistics: counts, averages, percentages, trends.
                - Do NOT generate charts -- that happens in a separate step.
                - Output ONLY Python code, no markdown fences, no explanation.
            """)),
            ("human", "User question: {question}\nData columns: {columns}"),
        ])

        columns_line = data_csv.split("\n")[0] if data_csv else ""
        chain = prompt | self._llm | StrOutputParser()
        analysis_code = chain.invoke({
            "question": question,
            "columns": columns_line,
        })

        analysis_code = re.sub(r"^```(?:python)?\n?", "", analysis_code.strip())
        analysis_code = re.sub(r"\n?```$", "", analysis_code.strip())

        result = self._sandbox.execute(analysis_code, data_csv=data_csv)
        if result.exit_code == 0:
            return result.stdout.strip()
        return f"Analysis execution failed: {result.stderr[:300]}"

    def _synthesize(
        self,
        question: str,
        data_csv: str,
        analysis: str,
        chart_description: str,
    ) -> str:
        """Combine all outputs into a natural language answer."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", textwrap.dedent("""\
                You are a data analyst presenting findings to a non-technical user.
                Combine the SQL results, analysis, and chart description into a clear,
                concise answer. Use specific numbers from the data. Keep it under
                200 words.
            """)),
            ("human", (
                "Question: {question}\n\n"
                "Data (CSV):\n{data_preview}\n\n"
                "Analysis:\n{analysis}\n\n"
                "Chart: {chart_description}"
            )),
        ])

        lines = data_csv.strip().split("\n")
        preview = "\n".join(lines[:16])

        chain = prompt | self._llm | StrOutputParser()
        return chain.invoke({
            "question": question,
            "data_preview": preview,
            "analysis": analysis or "(no additional analysis performed)",
            "chart_description": chart_description or "(no chart generated)",
        })
```

---

### Step 6: Sample Database Setup

The sample database includes three tables -- `customers`, `products`, and `orders` -- with realistic data spanning six months. This lets you test the agent immediately without configuring an external database.

```python
# ---------------------------------------------------------------------------
# Step 6: Sample Database Setup
# ---------------------------------------------------------------------------


def create_sample_db(db_url: str = "sqlite:///./sample_data.db") -> None:
    """Create a sample SQLite database with sales data for testing."""
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS orders"))
        conn.execute(text("DROP TABLE IF EXISTS products"))
        conn.execute(text("DROP TABLE IF EXISTS customers"))

        conn.execute(text("""
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                region TEXT NOT NULL,
                signup_date TEXT NOT NULL
            )
        """))

        conn.execute(text("""
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL
            )
        """))

        conn.execute(text("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """))

        # Insert customers
        regions = ["North", "South", "East", "West"]
        first_names = [
            "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace",
            "Hank", "Iris", "Jack", "Karen", "Leo", "Mona", "Nate",
            "Olivia", "Paul", "Quinn", "Rosa", "Sam", "Tina",
        ]
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
            "Miller", "Davis", "Rodriguez", "Martinez",
        ]

        random.seed(42)
        customers: list[dict] = []
        for i in range(1, 51):
            first = random.choice(first_names)
            last = random.choice(last_names)
            name = f"{first} {last}"
            email = f"{first.lower()}.{last.lower()}{i}@example.com"
            region = random.choice(regions)
            days_ago = random.randint(30, 365)
            signup = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            customers.append({
                "customer_id": i, "name": name, "email": email,
                "region": region, "signup_date": signup,
            })

        for c in customers:
            conn.execute(text(
                "INSERT INTO customers VALUES (:customer_id, :name, :email, :region, :signup_date)"
            ), c)

        # Insert products
        products = [
            (1, "Wireless Headphones", "Electronics", 79.99),
            (2, "USB-C Hub", "Electronics", 34.99),
            (3, "Mechanical Keyboard", "Electronics", 129.99),
            (4, "Laptop Stand", "Accessories", 49.99),
            (5, "Webcam HD", "Electronics", 59.99),
            (6, "Desk Mat XL", "Accessories", 24.99),
            (7, "Monitor Light Bar", "Accessories", 44.99),
            (8, "Portable SSD 1TB", "Storage", 89.99),
            (9, "Wireless Mouse", "Electronics", 39.99),
            (10, "Noise Cancelling Earbuds", "Electronics", 149.99),
            (11, "Phone Stand", "Accessories", 14.99),
            (12, "Cable Management Kit", "Accessories", 19.99),
        ]
        for p in products:
            conn.execute(text(
                "INSERT INTO products VALUES (:id, :name, :cat, :price)"
            ), {"id": p[0], "name": p[1], "cat": p[2], "price": p[3]})

        # Insert orders
        statuses = ["completed", "completed", "completed", "shipped", "pending", "cancelled"]
        base_date = datetime.now(timezone.utc) - timedelta(days=180)

        for i in range(1, 1001):
            customer_id = random.randint(1, 50)
            product_id = random.randint(1, 12)
            quantity = random.choices([1, 2, 3, 4, 5], weights=[50, 25, 15, 7, 3])[0]
            days_offset = random.randint(0, 180)
            order_date = (base_date + timedelta(days=days_offset)).strftime("%Y-%m-%d")
            status = random.choice(statuses)
            conn.execute(text(
                "INSERT INTO orders VALUES (:oid, :cid, :pid, :qty, :odate, :status)"
            ), {
                "oid": i, "cid": customer_id, "pid": product_id,
                "qty": quantity, "odate": order_date, "status": status,
            })

        conn.commit()

    print(f"Sample database created: {db_url}")
    print("  - 50 customers across 4 regions")
    print("  - 12 products in 3 categories")
    print("  - 1,000 orders spanning 6 months")
```

---

### Step 7: CLI Entry Point

The entry point supports two modes: `--setup` to create the sample database, and `--question` to ask a natural language question. Each pipeline step is printed as it completes so you can follow the agent's reasoning.

```python
# ---------------------------------------------------------------------------
# Step 7: CLI Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Data Pipeline Agent")
    parser.add_argument("--setup", action="store_true", help="Create sample database")
    parser.add_argument("--question", "-q", type=str, help="Ask a question about the data")
    args = parser.parse_args()

    if args.setup:
        create_sample_db()
        return

    if not args.question:
        parser.print_help()
        return

    agent = DataPipelineAgent()
    print(f"\nQuestion: {args.question}\n")

    answer = agent.ask(args.question)

    # Print each pipeline step
    for step in answer.steps:
        print(f"  [{step}]")

    print(f"\nSQL:\n  {answer.sql}\n")
    print(f"Rows returned: {answer.row_count}")

    if answer.analysis:
        print(f"\nAnalysis:\n{textwrap.indent(answer.analysis, '  ')}")

    print(f"\nAnswer:\n{textwrap.indent(answer.final_answer, '  ')}")

    # Save chart if generated
    if answer.chart_html:
        OUTPUT_DIR.mkdir(exist_ok=True)
        chart_path = OUTPUT_DIR / "chart.html"
        chart_path.write_bytes(answer.chart_html)
        print(f"\nChart saved to: {chart_path}")
    elif answer.chart_description:
        print(f"\n{answer.chart_description}")


if __name__ == "__main__":
    main()
```

---

## How to Run

```bash
# Create sample database
python data_pipeline_agent.py --setup

# Ask questions
python data_pipeline_agent.py --question "What are the top 5 products by revenue this quarter?"

# Example output:
# Question: What are the top 5 products by revenue this quarter?
#
#   [Schema: 3 tables discovered]
#   [SQL: SELECT p.name, SUM(o.quantity * p.unit_price) as revenue FROM orders o JOIN...]
#   [Results: 5 rows returned]
#   [Analysis: completed in sandbox]
#   [Visualization: chart generated]
#   [Answer: synthesized]
#
# SQL:
#   SELECT p.name, SUM(o.quantity * p.unit_price) as revenue
#   FROM orders o JOIN products p ON o.product_id = p.product_id
#   WHERE o.order_date >= '2026-03-01' AND o.status = 'completed'
#   GROUP BY p.name ORDER BY revenue DESC LIMIT 5
#
# Rows returned: 5
#
# Analysis:
#   Top 5 Products by Revenue (Q1 2026):
#   1. Noise Cancelling Earbuds - $4,649.69 (22.1%)
#   2. Mechanical Keyboard      - $3,899.70 (18.5%)
#   3. Portable SSD 1TB         - $2,969.67 (14.1%)
#   4. Wireless Headphones       - $2,639.67 (12.5%)
#   5. Webcam HD                 - $1,979.67 (9.4%)
#
# Answer:
#   The top 5 products by revenue this quarter are Noise Cancelling Earbuds
#   leading at $4,650, followed by the Mechanical Keyboard at $3,900...
#
# Chart saved to: output/chart.html

# More example questions:
python data_pipeline_agent.py -q "Show me the monthly revenue trend for the last 6 months"
python data_pipeline_agent.py -q "Which region has the most customers?"
python data_pipeline_agent.py -q "Compare Electronics vs Accessories category sales"
python data_pipeline_agent.py -q "What is the average order value by customer region?"
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Read-only SQL (SELECT only) | Prevents data corruption from generated queries. Combined with a read-only DB user in production, this creates two independent safety layers. |
| Docker sandbox for Python | Generated code is untrusted; full isolation with no network, limited CPU/memory, and hard timeouts prevents data exfiltration and resource abuse. |
| Schema caching | Avoids repeated introspection on every question. Schema changes rarely within a single session, so a hash-based cache is sufficient. |
| Row limit on queries | `LIMIT 1000` prevents full table scans that return millions of rows, protecting both the database and the agent's context window. |
| Fallback to text tables | Chart generation depends on Plotly and kaleido inside the sandbox. If either fails, the user still gets a readable text table rather than an error. |
| Subprocess fallback for sandbox | Enables local development without Docker. Not secure, but developers working on their own machine accept that trade-off. |
| CSV as intermediate format | Universal, human-readable, and parseable by both the LLM (in prompts) and pandas (in sandbox code). Avoids serialization complexity. |

---

## Extension Ideas

- **Multi-database support**: Add BigQuery, Snowflake, or MySQL connectors by swapping the SQLAlchemy engine URI and adjusting SQL dialect hints in the prompt
- **Conversational follow-ups**: Maintain a session with previous SQL and results so "now filter to just Q4" modifies the existing query instead of starting from scratch
- **Query cost estimation**: Run `EXPLAIN` before executing; reject queries with estimated cost above a configurable threshold
- **Caching layer**: Cache SQL results keyed on a hash of the normalized query for repeated questions within a TTL window
- **Scheduled reports**: Wrap the agent in a cron job or Airflow task to generate recurring analysis and email the results
- **Natural language to dbt**: Generate dbt model SQL and YAML schema files instead of one-off queries, enabling version-controlled analytics
- **Streaming responses**: Use LangChain's streaming callbacks to show the SQL being generated token-by-token in a web UI
- **Multi-tenant isolation**: Scope schema discovery and query execution per tenant using connection pooling and row-level security policies
