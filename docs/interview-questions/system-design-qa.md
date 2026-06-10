---
sidebar_position: 4
title: "System Design Questions"
description: "10 open-ended system design problems for agentic AI interviews with detailed solutions."
---

# System Design Questions

These 10 system design problems simulate real interview scenarios. Each presents a problem statement, then a collapsible solution covering requirements, architecture, key decisions, and scaling considerations. Practice whiteboarding these -- they are the most common format for senior and staff-level AI engineering interviews.

:::warning How to Approach These
In an interview, spend 5 minutes clarifying requirements, 10-15 minutes drawing the architecture, 5 minutes discussing trade-offs, and 5 minutes on scaling. Do not dive into code -- focus on components, data flow, and design decisions.
:::

---

## Problem 1: Customer Support Agent Platform

**Design a platform that allows enterprises to deploy custom AI-powered customer support agents. Each tenant configures their own knowledge base, tools, escalation policies, and brand voice. The platform handles millions of conversations per day across thousands of tenants.**

<details>
<summary>View Answer</summary>

**Functional Requirements:**
- Multi-tenant agent configuration (knowledge base, tools, prompts, escalation rules)
- Real-time conversational interface (web chat, API)
- Tool integration framework (CRM, ticketing, billing system connectors)
- Human escalation with context handoff
- Conversation analytics and reporting

**Non-Functional Requirements:**
- Sub-2-second time-to-first-token for each response
- 99.9% uptime SLA
- Tenant data isolation (no cross-tenant data leakage)
- Horizontal scaling to millions of concurrent conversations

**Architecture (Mermaid-compatible):**
The system has three layers. The **API Gateway** (with rate limiting, auth, and tenant routing) receives requests. It routes to a **Conversation Service** (stateless, horizontally scaled) that manages session state in Redis and makes LLM calls. The Conversation Service reads tenant configuration from a **Tenant Config Store** (PostgreSQL + cache), retrieves documents from a **per-tenant Vector Store** (Qdrant or Pinecone with namespace isolation), and executes tools via a **Tool Execution Service** (sandboxed, async). A **Human Escalation Service** integrates with the tenant's helpdesk. An **Analytics Pipeline** (Kafka to ClickHouse) captures all events.

**Key Design Decisions:**
1. **Tenant isolation**: Use namespace-based isolation in the vector store (not separate instances per tenant, which does not scale). Use row-level security in PostgreSQL for tenant config.
2. **LLM provider abstraction**: Build an LLM Gateway that routes to different providers (OpenAI, Anthropic, Azure) based on tenant configuration, with fallback on provider outages.
3. **Stateless conversation service**: Store conversation state in Redis (with TTL), so any service instance can handle any request. This enables horizontal scaling.
4. **Tool sandboxing**: Execute tenant-defined tools in sandboxed containers with resource limits and network policies to prevent abuse.

**Scaling Considerations:**
- Use connection pooling for LLM API calls; batch where possible for throughput.
- Cache common queries with semantic caching (embed the query, check similarity against recent queries before making a new LLM call).
- Implement circuit breakers per LLM provider to handle outages gracefully.
- Shard the vector store by tenant for large tenants; share a multi-tenant cluster for small tenants.

</details>

---

## Problem 2: Autonomous Research Agent

**Design an autonomous research agent that takes a research question, searches the web and academic databases, reads and synthesizes papers, and produces a structured research report with citations. The system should handle research tasks that take hours to complete.**

<details>
<summary>View Answer</summary>

**Functional Requirements:**
- Accept research questions in natural language
- Search multiple sources (web, arXiv, Semantic Scholar, Google Scholar)
- Read and extract information from papers (PDFs)
- Synthesize findings into structured reports with proper citations
- Support long-running tasks (hours) with progress updates

**Non-Functional Requirements:**
- Idempotent task execution (resume on failure)
- Cost control (cap LLM spend per research task)
- Source attribution for every claim

**Architecture:**
The system uses a **Task Queue** (Celery + Redis) to manage long-running research jobs. A **Planner Agent** decomposes the research question into sub-questions and creates a research plan. **Search Workers** execute searches in parallel across multiple sources. A **Paper Processing Pipeline** downloads PDFs, extracts text (using PyMuPDF or Unstructured), chunks them, and indexes them in a per-task vector store. A **Synthesis Agent** retrieves relevant chunks across all ingested papers and writes sections of the report. A **Citation Manager** tracks source-to-claim mappings. A **Report Assembler** combines sections into the final structured output.

**Key Design Decisions:**
1. **Plan-and-Execute pattern**: The Planner creates a full research plan first, then workers execute. After each phase, the planner revises remaining steps based on findings.
2. **Per-task vector store**: Each research task gets its own ephemeral vector store, populated with papers found during search. This prevents cross-task contamination and simplifies cleanup.
3. **Iterative deepening**: After initial search and synthesis, the agent evaluates gaps in its research and performs targeted follow-up searches. Cap at 3 deepening iterations.
4. **Cost control**: Set a token budget per task. Track cumulative spend in the task state. When approaching the budget, force the agent to synthesize what it has rather than searching more.

**Scaling Considerations:**
- Use async workers for search and PDF processing (I/O-bound tasks).
- Implement rate limiting per source API to avoid bans.
- For popular research topics, cache search results and paper embeddings to avoid redundant processing.
- Use streaming for progress updates to the user (SSE or WebSocket).

</details>

---

## Problem 3: Code Review Agent

**Design an AI agent that performs automated code reviews on pull requests. It should understand the codebase context, identify bugs, suggest improvements, check for security vulnerabilities, and leave inline comments. It must integrate with GitHub/GitLab.**

<details>
<summary>View Answer</summary>

**Functional Requirements:**
- Triggered on PR creation and updates (webhook-based)
- Read and understand code diffs in context of the full repository
- Identify bugs, security issues, performance problems, and style violations
- Post inline comments on specific lines with explanations and fix suggestions
- Learn from reviewer feedback (thumbs up/down on comments)

**Non-Functional Requirements:**
- Process a PR within 2 minutes for typical diffs (under 500 lines)
- Low false-positive rate (aim for under 20% -- bad suggestions erode trust)
- Support multiple languages (Python, TypeScript, Java, Go)

**Architecture:**
A **Webhook Handler** receives PR events from GitHub/GitLab. A **Context Builder** fetches the diff, surrounding code (full files for changed files), and relevant documentation. It builds a context package with: the diff, the full files, the PR description, and recent commit history. A **Codebase Index** (vector store of the full repo, updated on each push) provides broader context -- e.g., how a function is used elsewhere. A **Review Pipeline** runs multiple specialized analysis passes: (1) a bug detection pass, (2) a security pass (using OWASP patterns), (3) a style/consistency pass, and (4) a code quality pass. A **Comment Aggregator** deduplicates, prioritizes (critical > important > suggestion), and formats comments. A **GitHub API Client** posts the inline comments.

**Key Design Decisions:**
1. **Multi-pass analysis**: Each review category uses a specialized prompt optimized for that concern. This produces better results than a single "review this code" prompt.
2. **Codebase RAG**: For each changed file, retrieve related files from the codebase index (files that import the changed module, tests for the changed code). This gives the LLM cross-file context.
3. **Confidence-gated commenting**: Each finding has a confidence score. Only post comments above a threshold (e.g., 0.8). Low-confidence findings are logged but not posted.
4. **Feedback loop**: When developers react to comments (resolve, dismiss), store these signals and use them to tune prompts and confidence thresholds over time.

**Scaling Considerations:**
- Queue PR reviews to handle bursts (many PRs at market open, for example).
- Cache the codebase index and update incrementally on each push (do not rebuild from scratch).
- Use smaller, faster models for the style pass and larger models for the bug/security pass.
- Implement rate limiting to stay within GitHub API limits.

</details>

---

## Problem 4: Multi-Agent Data Analysis Pipeline

**Design a system where a user provides a natural language question about their data and the system generates the answer using a pipeline of specialized agents: a SQL agent for data extraction, a Python agent for computation, and a visualization agent for charts.**

<details>
<summary>View Answer</summary>

**Functional Requirements:**
- Natural language to SQL generation and execution
- Python-based data transformation and statistical analysis
- Automated chart generation (bar, line, scatter, etc.)
- Multi-turn conversation for iterative analysis
- Support for multiple data sources (PostgreSQL, BigQuery, CSV uploads)

**Non-Functional Requirements:**
- SQL injection prevention (critical -- the system generates and executes SQL)
- Query result size limits (prevent full table scans that return millions of rows)
- Execution sandboxing for Python code

**Architecture:**
A **Planner Agent** receives the user's question and the database schema, then generates an analysis plan: which data to fetch, what computations to run, what visualizations to create. A **SQL Agent** generates SQL queries, validates them against security rules, executes them (read-only connection, query timeout, row limit), and returns results as DataFrames. A **Python Agent** receives DataFrames and the analysis goal, generates Python code (pandas, scipy, sklearn), executes it in a sandboxed environment (Docker container with resource limits), and returns computed results. A **Visualization Agent** generates chart specifications (Plotly or matplotlib code), renders them, and returns images or interactive HTML. A **Synthesizer** combines all outputs into a narrative answer with embedded charts.

**Key Design Decisions:**
1. **Read-only database access**: The SQL agent connects with a read-only user. All generated SQL is validated against a whitelist of allowed operations (SELECT only, no DDL, no DML).
2. **Sandboxed execution**: Python code runs in ephemeral Docker containers with no network access, limited CPU/memory, and a timeout. The container is destroyed after each execution.
3. **Schema injection**: The database schema (table names, columns, types, sample values) is injected into the SQL agent's prompt. For large schemas, use RAG to retrieve only relevant tables.
4. **Iterative refinement**: If the user says "show me a different chart type" or "filter to just Q4," the planner modifies the existing plan rather than starting from scratch.

**Scaling Considerations:**
- Pre-compute and cache schema metadata to avoid querying it on every request.
- Use query result caching keyed on the generated SQL hash to avoid redundant database queries.
- Pool sandboxed containers to reduce cold-start latency for Python execution.
- Implement query cost estimation (EXPLAIN) and reject queries predicted to be too expensive.

</details>

---

## Problem 5: AI-Powered Content Moderation System

**Design a content moderation system that uses AI agents to review user-generated content (text, images, video) across a social media platform. It must handle 10 million posts per day with sub-second moderation latency for most content.**

<details>
<summary>View Answer</summary>

**Functional Requirements:**
- Classify content as safe, needs-review, or violating (with violation category)
- Support text, image, and video moderation
- Configurable policies per community/region
- Human review queue for edge cases
- Appeal workflow for moderation decisions

**Non-Functional Requirements:**
- Sub-second latency for 95% of content (p95 < 1 second)
- False positive rate below 2% (blocking good content is costly)
- False negative rate below 0.5% (allowing bad content is worse)
- 10 million posts/day throughput

**Architecture:**
A **Fast-Path Classifier** (lightweight ML model, not LLM) handles the first pass -- it runs in under 50ms and catches obvious violations (known hate speech patterns, NSFW images, spam). Clear-pass content (85% of traffic) is published immediately. Borderline content goes to the **Agent Review Pipeline**: a multimodal LLM agent evaluates the content in context (user history, community norms, conversation thread), applies the relevant policy, and produces a decision with confidence score and reasoning. Low-confidence decisions route to a **Human Review Queue** (priority-ordered). A **Policy Engine** stores per-community moderation rules in a configuration database. An **Appeals Service** allows users to request re-review, which goes to a different (senior) human reviewer or an independent LLM evaluation.

**Key Design Decisions:**
1. **Tiered architecture**: Use cheap, fast classifiers for the easy 85%, and expensive LLM agents for the hard 15%. This balances cost and quality.
2. **Context-aware moderation**: The LLM agent sees not just the post but the conversation thread, the poster's history, and the community's specific rules. This handles sarcasm, inside jokes, and context-dependent content.
3. **Confidence-based routing**: High-confidence agent decisions (&gt;0.95) are auto-applied. Medium-confidence (0.7-0.95) are applied but flagged for audit. Low-confidence (&lt;0.7) route to humans.
4. **Feedback loop**: Human decisions are used to retrain the fast-path classifier and to evaluate the LLM agent's accuracy over time.

**Scaling Considerations:**
- The fast-path classifier runs on GPU inference servers with batching for throughput.
- The LLM agent pipeline is the bottleneck; use caching for repeat/similar content.
- Shard the human review queue by content category and region.
- Implement backpressure: if the review pipeline is overwhelmed, temporarily tighten the fast-path threshold (more content gets auto-passed).

</details>

---

## Problem 6: Intelligent Document Processing Pipeline

**Design a system that processes unstructured business documents (invoices, contracts, forms) and extracts structured data. The system should handle diverse formats, learn from corrections, and integrate with downstream business systems.**

<details>
<summary>View Answer</summary>

**Functional Requirements:**
- Ingest documents in multiple formats (PDF, image, scanned documents)
- Extract key fields (dates, amounts, names, clauses) into structured schemas
- Classify documents by type
- Validate extracted data against business rules
- Learn from human corrections to improve over time

**Non-Functional Requirements:**
- 95%+ extraction accuracy for key fields
- Process documents within 30 seconds
- Handle 100,000 documents per day

**Architecture:**
An **Ingestion Service** receives documents via API or email. An **OCR/Preprocessing Pipeline** (Tesseract or AWS Textract for scanned documents, PyMuPDF for digital PDFs) converts documents to text. A **Classification Agent** identifies the document type and selects the appropriate extraction schema. An **Extraction Agent** uses the schema as a guide, processes the document with a multimodal LLM (feeding both the text and document images for layout-aware extraction), and outputs structured JSON. A **Validation Service** applies business rules (e.g., invoice total must equal sum of line items, dates must be valid). Failed validations route to a **Human Correction Queue**. An **Integration Service** pushes validated data to downstream systems (ERP, CRM) via APIs or message queue. A **Learning Pipeline** aggregates human corrections, identifies recurring extraction errors, and fine-tunes the extraction prompts or model.

**Key Design Decisions:**
1. **Multimodal extraction**: Use vision capabilities to process the document image alongside extracted text. This captures layout information (tables, headers, signatures) that text extraction misses.
2. **Schema-driven extraction**: Each document type has a schema defining expected fields, types, and validation rules. The LLM's prompt includes the schema as a structured template.
3. **Confidence scoring**: Each extracted field has a confidence score. Low-confidence fields are highlighted for human review rather than silently accepted.
4. **Active learning**: Track which fields are most frequently corrected by humans and prioritize prompt improvements for those fields.

**Scaling Considerations:**
- Use GPU-accelerated OCR for high-throughput scanned document processing.
- Batch similar documents (same type, same layout) for more efficient LLM processing.
- Cache extraction templates for common document layouts.
- Implement priority queues: urgent documents (invoices near due date) jump ahead of routine processing.

</details>

---

## Problem 7: Real-Time Trading Agent with Risk Management

**Design an AI agent that monitors financial markets, identifies trading opportunities based on configurable strategies, and executes trades -- with real-time risk management guardrails. Safety is paramount: a bug must not cause unbounded financial loss.**

<details>
<summary>View Answer</summary>

**Functional Requirements:**
- Ingest real-time market data (price feeds, news, social sentiment)
- Analyze data against configurable trading strategies
- Generate and execute trade orders
- Real-time portfolio risk monitoring
- Configurable risk limits (position size, daily loss, sector exposure)

**Non-Functional Requirements:**
- Sub-100ms decision latency for market data analysis
- Zero tolerance for unauthorized trades
- Complete audit trail for every decision
- Graceful degradation (halt trading on system issues)

**Architecture:**
A **Market Data Ingestion Layer** (Kafka streams) receives and normalizes price feeds, news, and sentiment data. A **Signal Generation Agent** (this is the LLM-powered component) analyzes data against configured strategies and produces trade signals with confidence scores and reasoning. A **Risk Engine** (deterministic, rule-based, NOT LLM-powered) validates every signal against: position limits, daily P&L limits, sector exposure limits, and circuit breakers. Only signals that pass all risk checks reach the **Order Execution Service**, which interfaces with the exchange API. A **Portfolio Monitor** continuously tracks real-time positions and P&L, triggering automated stop-losses and alerts. An **Audit Logger** records every data point, signal, risk decision, and trade with timestamps for regulatory compliance.

**Key Design Decisions:**
1. **LLM for signal generation only**: The LLM provides analysis and suggestions, but NEVER directly executes trades. All execution passes through a deterministic risk engine with hard-coded limits.
2. **Kill switch**: A manual override can halt all trading instantly. An automated circuit breaker halts trading if daily loss exceeds the limit.
3. **Paper trading mode**: Every strategy must run in paper trading (simulated) mode before being approved for live trading. Evaluation metrics include Sharpe ratio, max drawdown, and win rate.
4. **No LLM in the critical path for execution**: The risk engine and order execution are deterministic code, not LLM calls. LLM latency variability must not affect trade execution timing.

**Scaling Considerations:**
- Separate the fast path (market data to risk engine to execution) from the slow path (LLM analysis).
- Use in-memory data structures for risk calculations (no database in the hot path).
- Implement redundancy: dual risk engines with consensus required for large orders.
- Geographically co-locate with exchange data centers for minimum latency.

</details>

---

## Problem 8: Agent Observability and Debugging Platform

**Design a platform that provides observability, debugging, and optimization tools for AI agent deployments. Think of it as "Datadog for AI agents" -- engineering teams use it to understand, debug, and improve their agent systems.**

<details>
<summary>View Answer</summary>

**Functional Requirements:**
- Capture and visualize agent execution traces (each step: LLM call, tool call, decision)
- Real-time dashboards for key metrics (latency, cost, success rate, error rate)
- Replay any agent interaction step-by-step for debugging
- Compare agent performance across model versions and prompt changes
- Cost attribution per agent, per user, per feature

**Non-Functional Requirements:**
- Sub-10ms overhead per trace span (must not slow down agents)
- Store traces for 90 days minimum
- Handle 1 billion trace spans per day

**Architecture:**
An **SDK** (lightweight, async) instruments agent code with minimal overhead. It emits structured trace spans for each LLM call (model, tokens, latency, cost), tool call (name, args, result, latency), and decision point. Spans are batched and sent asynchronously to a **Trace Collector** (OpenTelemetry-compatible). The Collector writes to a **Time-Series Database** (ClickHouse for analytics queries) and an **Object Store** (S3 for full trace payloads). A **Query Engine** supports filtering traces by agent, user, time range, error type, cost range, and latency percentile. A **Dashboard Service** provides real-time views and alerting. A **Replay Service** reconstructs an agent interaction from its trace spans, showing each step with timing, inputs, outputs, and decisions. A **Comparison Engine** supports A/B testing: run two prompt versions against the same test suite and compare metrics.

**Key Design Decisions:**
1. **OpenTelemetry compatibility**: Use OTEL as the trace format standard so teams can integrate with existing observability stacks (Grafana, Jaeger).
2. **Sampling for high-volume tenants**: At 1B spans/day, store 100% of error traces and 10% of success traces. Use head-based sampling (decide at trace start) to keep complete traces.
3. **Cost attribution**: Each trace span carries cost metadata (tokens * price per token). Aggregate up to get cost per conversation, per agent, per user, per day.
4. **Prompt diffing**: When a prompt changes, automatically trigger evaluation suite runs and surface the before/after comparison in the dashboard.

**Scaling Considerations:**
- Use columnar storage (ClickHouse) for fast analytical queries over billions of spans.
- Implement tiered storage: hot (last 7 days, SSD), warm (7-30 days, HDD), cold (30-90 days, S3).
- Shard by tenant for data isolation and query performance.
- Use async span export with local buffering to eliminate performance impact on agents.

</details>

---

## Problem 9: Multi-Modal AI Assistant for Healthcare

**Design an AI assistant that helps doctors by analyzing patient data (lab results, imaging, clinical notes), suggesting diagnoses, and recommending treatment plans. The system must be accurate, explainable, and compliant with healthcare regulations (HIPAA).**

<details>
<summary>View Answer</summary>

**Functional Requirements:**
- Ingest and analyze structured data (lab values, vitals) and unstructured data (clinical notes, radiology reports)
- Suggest differential diagnoses with supporting evidence
- Recommend treatment plans based on clinical guidelines
- Provide explainable reasoning (cite specific data points and guidelines)
- Support multi-turn conversation with the doctor for clarification

**Non-Functional Requirements:**
- HIPAA compliance (data encryption at rest and in transit, audit logging, access controls)
- Zero hallucinated diagnoses (must cite evidence or say "insufficient data")
- Model must be deployable on-premises (some hospitals cannot use cloud LLMs)
- Complete audit trail for regulatory compliance

**Architecture:**
A **Data Ingestion Layer** normalizes patient data from EMR systems (using HL7/FHIR standards) into a structured patient context. A **Clinical RAG System** indexes clinical guidelines, drug databases, and medical literature in a vector store. A **Diagnostic Agent** analyzes the patient context, retrieves relevant guidelines, generates a differential diagnosis with supporting evidence and confidence levels. A **Treatment Planner Agent** takes the diagnosis and the patient's specific factors (allergies, comorbidities, current medications) and recommends a treatment plan, checking for drug interactions. An **Explainability Layer** maps each claim in the output to specific data points and guideline citations. A **Physician Review Interface** presents suggestions with evidence, requires physician approval before any suggestion enters the medical record.

**Key Design Decisions:**
1. **On-premises deployment**: Use open-source models (Llama 3, Mistral) fine-tuned on medical data. Deploy on the hospital's infrastructure to keep PHI within their network boundary.
2. **Evidence-required architecture**: The system CANNOT make a claim without citing either a specific patient data point or a clinical guideline. Ungrounded statements are blocked by the output validation layer.
3. **Doctor-in-the-loop always**: The system is a suggestion engine, not a decision-maker. Every suggestion requires physician approval. The UI makes it easy to accept, modify, or reject suggestions.
4. **Differential, not definitive**: The system produces a ranked list of possible diagnoses with probabilities and supporting evidence, not a single diagnosis. This matches clinical decision-making practice.

**Scaling Considerations:**
- Patient data stays on-premises; only de-identified data (if any) goes to cloud for analytics.
- Model inference runs on local GPU servers with load balancing.
- Cache guideline retrieval results (guidelines change infrequently).
- Implement priority queuing: ICU patients get faster analysis than routine consultations.

</details>

---

## Problem 10: Autonomous DevOps Agent

**Design an AI agent that monitors production infrastructure, diagnoses incidents, and takes remediation actions. It should handle alerts from monitoring systems, investigate root causes, and either auto-remediate or escalate to on-call engineers with a detailed analysis.**

<details>
<summary>View Answer</summary>

**Functional Requirements:**
- Ingest alerts from monitoring systems (Prometheus, PagerDuty, CloudWatch)
- Investigate root causes by querying logs, metrics, and traces
- Correlate alerts across services to identify cascading failures
- Execute remediation runbooks (restart service, scale up, roll back deployment)
- Escalate to humans with a structured incident analysis when auto-remediation is not possible

**Non-Functional Requirements:**
- Response time under 60 seconds from alert to first investigation step
- Auto-remediation actions must be safe (reversible, bounded, audited)
- Must not make the situation worse (a misconfigured remediation action can cause outages)
- Complete audit trail of every action taken

**Architecture:**
An **Alert Ingestion Service** receives and deduplicates alerts from monitoring systems. An **Alert Correlation Engine** (rule-based + ML) groups related alerts into incidents. A **Diagnosis Agent** investigates each incident by: querying log aggregation (Elasticsearch/Loki), checking metrics (Prometheus), reading recent deployment history, and searching a knowledge base of past incidents with similar signatures. A **Runbook Engine** stores approved remediation procedures as executable workflows with pre-conditions and safety checks. The Diagnosis Agent selects and parameterizes the appropriate runbook. A **Safety Gate** (deterministic, not LLM) validates the proposed action: is it reversible? Has it been approved for this service? Is the blast radius acceptable? Only approved actions execute. An **Escalation Service** formats the agent's analysis into a structured incident report and pages the on-call engineer.

**Key Design Decisions:**
1. **LLM for diagnosis, deterministic code for remediation**: The LLM reasons about what is wrong and selects a runbook, but the actual execution is a pre-approved, parameterized script -- not LLM-generated code.
2. **Blast radius limits**: Each remediation action has a defined blast radius. Restarting a single pod is low-blast-radius (auto-approved). Rolling back a production deployment is high-blast-radius (requires human approval).
3. **Similar incident retrieval**: Every resolved incident is indexed in a vector store. When a new incident occurs, the agent retrieves similar past incidents to learn from previous diagnoses and solutions.
4. **Dry-run mode**: All auto-remediation actions can be run in dry-run mode first, where the agent describes what it WOULD do without actually doing it. This allows validation before activation.

**Scaling Considerations:**
- Implement alert deduplication and suppression to prevent the agent from being overwhelmed during major outages.
- Use caching for frequently queried metrics and log patterns.
- Run diagnosis agents in parallel for concurrent incidents.
- Implement a cooldown period after remediation to assess effectiveness before taking further actions.

</details>
