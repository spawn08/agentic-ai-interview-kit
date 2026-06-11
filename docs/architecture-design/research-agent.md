---
sidebar_position: 3
title: "Research Agent"
description: "Architecture design for a deep research agent with multi-source search, synthesis, and citation tracking"
---

# Research Agent

An autonomous research agent takes a research question, searches multiple sources, synthesizes findings, tracks citations, and produces a structured report. This is one of the most compelling agentic system design problems because it demands planning under uncertainty, iterative deepening, cost control, and rigorous information quality assessment.

---

## Problem Statement

> **Interviewer:** Design an autonomous research agent that accepts a natural language research question, searches across the web, academic databases, and internal knowledge bases, reads and synthesizes content from multiple sources, tracks citations for every claim, and produces a structured research report. The system should handle tasks that range from quick lookups (under 2 minutes) to deep investigations (up to 15 minutes), and must remain cost-efficient while maintaining high factual accuracy.

---

## Clarifying Questions to Ask

1. **Scope of sources** -- Are we limited to public web and academic papers, or must the agent also search internal knowledge bases, structured databases, or proprietary APIs?
2. **Depth levels** -- Should the system support multiple depth modes (quick lookup vs. deep research), and how should it decide when to stop deepening?
3. **Latency tolerance** -- What are the acceptable response times? Is the user waiting synchronously, or can this be a background job with progress updates?
4. **Output format** -- Should the report be markdown, PDF, or structured JSON? Does the consumer want an executive summary, full analysis, or both?
5. **Cost constraints** -- Is there a per-task token budget? How should the agent behave when approaching the spending limit?
6. **Quality bar** -- What citation accuracy and factual correctness rates are expected? Must every claim be backed by a verifiable source, or are some unsupported observations acceptable?

---

## Requirements

### Functional Requirements

1. **Multi-source search** -- query web search, academic papers, internal knowledge bases, and structured databases
2. **Information synthesis** -- combine findings from multiple sources into a coherent analysis
3. **Citation tracking** -- every claim must be linked to its source with a verifiable citation
4. **Iterative deepening** -- identify knowledge gaps and perform additional research to fill them
5. **Report generation** -- produce a structured report with executive summary, findings, analysis, and references
6. **Quality control** -- verify claims against sources, detect contradictions, and flag low-confidence findings

### Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Latency (quick research) | < 2 minutes |
| Latency (deep research) | < 15 minutes |
| Citation accuracy | > 95% of citations correctly link to source material |
| Source diversity | At least 3 independent sources per major finding |
| Factual accuracy | > 90% of claims verifiable against cited sources |
| Cost per research task | < $2.00 for deep research |

### Out of Scope

- Real-time data (stock prices, live events)
- Primary research (conducting surveys, experiments)
- Languages other than English (V1)

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface"
        Chat[Chat Interface]
        API[Research API]
        Scheduled[Scheduled Reports]
    end

    subgraph "Research Orchestrator"
        Planner[Research Planner<br/>Decomposes questions]
        Searcher[Search Agent<br/>Multi-source search]
        Analyst[Analysis Agent<br/>Synthesizes findings]
        Verifier[Verification Agent<br/>Fact-checks claims]
        Writer[Report Writer<br/>Generates output]
        Deepener[Deepening Agent<br/>Identifies gaps]
    end

    subgraph "Search Sources"
        Web[Web Search<br/>Tavily / Bing / Google]
        Academic[Academic Search<br/>Semantic Scholar / arXiv]
        Internal[Internal KB<br/>Company documents]
        Structured[Structured Data<br/>APIs / Databases]
    end

    subgraph "Processing"
        Extract[Content Extractor<br/>HTML to text, PDF parser]
        Chunk[Document Chunker<br/>Semantic chunking]
        Embed[Embedding Service]
    end

    subgraph "Storage"
        Sources[Source Store<br/>Raw content + metadata]
        Citations[Citation Graph<br/>Claims linked to sources]
        Research[Research Sessions<br/>State + findings]
        VectorDB[Vector Store<br/>Source embeddings]
    end

    subgraph "Quality"
        FactCheck[Fact Checker<br/>Cross-reference claims]
        Bias[Bias Detector<br/>Source diversity check]
        Contradiction[Contradiction Detector<br/>Conflicting claims]
    end

    Chat --> Planner
    API --> Planner
    Scheduled --> Planner

    Planner --> Searcher
    Searcher --> Web
    Searcher --> Academic
    Searcher --> Internal
    Searcher --> Structured
    Searcher --> Extract
    Extract --> Chunk
    Chunk --> Embed
    Embed --> VectorDB

    Searcher --> Sources
    Planner --> Analyst
    Analyst --> Citations
    Planner --> Verifier
    Verifier --> FactCheck
    Verifier --> Bias
    Verifier --> Contradiction
    Planner --> Deepener
    Deepener --> Searcher
    Planner --> Writer
    Writer --> Research
```

### Architecture Walkthrough

The architecture is organized into five layers.

**User Interface Layer** -- Requests enter through a chat interface (for interactive research), a REST API (for programmatic access), or a scheduler (for recurring reports). All three entry points feed into the Research Orchestrator.

**Research Orchestrator** -- This is the brain of the system, built around the Plan-and-Execute pattern. The Research Planner decomposes the incoming question into sub-questions and creates a full research plan before any execution begins. Workers (Search Agent, Analysis Agent, Verification Agent, Deepening Agent, Report Writer) execute phases of that plan. After each phase completes, the Planner revises the remaining steps based on what has been discovered so far. This is not a reactive loop where the agent improvises; it is a structured plan that adapts as evidence accumulates.

**Search Sources** -- The Search Agent queries multiple sources in parallel: web search engines (Tavily, Bing, Google), academic databases (Semantic Scholar, arXiv), internal knowledge bases, and structured data APIs. Results from all sources are deduplicated and re-ranked by relevance.

**Processing Layer** -- Raw content from search results passes through the Content Extractor (handling HTML, PDFs, and API responses), then through a Document Chunker that produces semantically coherent segments, and finally through an Embedding Service that indexes chunks into the vector store for retrieval during synthesis.

**Storage and Quality Layers** -- The Source Store holds raw content and metadata. The Citation Graph maps every claim to its supporting sources. Research Sessions track the state of each task, including cumulative token spend. The Quality subsystem (Fact Checker, Bias Detector, Contradiction Detector) runs as a validation pass before report generation.

---

## Component Design

### Research Planner

**What it does:** The Planner decomposes a broad research question into specific, searchable sub-questions and creates a full research plan before any execution begins.

**Why it exists:** Without decomposition, the agent would attempt to answer complex questions with a single search query, producing shallow and incomplete results. The Planner enforces the Plan-and-Execute pattern: create the plan first, then execute it phase by phase, revising remaining steps based on findings from completed phases.

**Key design decisions:**

- Each sub-question is tagged with a priority level (critical, important, supplementary) and the planner orders execution by priority so the most essential information is gathered first.
- The planner specifies which source types to search for each sub-question and what type of evidence to look for (statistics, expert opinions, case studies).
- After each execution phase, the planner receives a summary of findings and revises the remaining plan. This is not full re-planning from scratch; it is incremental revision of the remaining steps.
- For quick research, the planner generates 2-3 sub-questions. For deep research, it generates 5-8.

### Search Agent

**What it does:** Executes searches across multiple source providers in parallel, deduplicates results, and re-ranks them by semantic relevance.

**Why it exists:** No single source provides comprehensive coverage. Web search captures current information, academic search provides peer-reviewed depth, internal knowledge bases contain proprietary context, and structured APIs offer precise data. Parallel execution across all relevant sources is essential for both coverage and latency.

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Parallel search across sources | Reduces latency from serial sum to parallel max. A failed source does not block others. |
| Per-source timeout (15 seconds) | Prevents a slow source from stalling the entire search phase. Timed-out sources are logged and skipped. |
| Semantic re-ranking | Initial search results are ranked by the source engine's relevance scoring, which varies by provider. Re-ranking with embedding similarity against the original query produces a consistent, quality-ordered result set. |
| Deduplication by URL and content hash | Multiple sources often return the same page. Deduplication prevents redundant extraction and analysis. |

### Content Extractor

**What it does:** Converts raw source content (HTML pages, PDFs, API responses) into clean text, then chunks it semantically for embedding and analysis.

**Why it exists:** Search results are URLs and snippets. The agent needs full content to extract evidence, verify claims, and build citations. Different content types require different parsing strategies -- HTML needs tag stripping and boilerplate removal, PDFs need layout-aware text extraction, and API responses need JSON flattening.

**Key design decisions:**

- Content type is auto-detected from the URL and HTTP headers, with specialized parsers for each type.
- Semantic chunking (target size: 1000 tokens) preserves paragraph and section boundaries rather than splitting at arbitrary character offsets. This produces chunks that are coherent units of meaning, which improves both embedding quality and citation accuracy.
- Metadata (title, word count, chunk count, extraction timestamp) is captured alongside the content for provenance tracking.

### Analysis Agent

**What it does:** Synthesizes findings from extracted content, identifies key themes and claims, and associates each claim with its supporting citations.

**Why it exists:** Raw extracted text is not a research finding. The Analysis Agent performs the intellectual work of reading across sources, identifying patterns, extracting specific claims, and assessing the strength of evidence behind each claim.

**Key design decisions:**

- Every claim produced by the Analysis Agent must be paired with at least one citation. The citation includes the source URL, the specific passage that supports the claim, and a confidence score indicating how strongly the source supports the claim.
- Claims are categorized by type (fact, opinion, statistic, case study) so the report can present them appropriately.
- The agent receives existing findings as context to avoid generating duplicate claims and to enable cross-referencing.

### Verification Agent

**What it does:** Cross-references findings against their cited sources and against each other, checking for unsupported claims, contradictions, and insufficient source diversity.

**Why it exists:** LLMs can hallucinate citations, misrepresent source content, or fail to notice when two sources contradict each other. The Verification Agent acts as an independent quality gate that catches these errors before they reach the final report.

**Key design decisions:**

- **Support checking:** For each finding-citation pair, the agent verifies that the cited text actually supports the stated claim. This catches the common failure mode where an LLM cites a source that discusses the topic but does not support the specific claim.
- **Contradiction detection:** The agent compares all findings pairwise to identify contradictions. When found, contradictions are flagged so the report can present both perspectives rather than silently favoring one.
- **Source diversity validation:** If all findings come from fewer than 3 unique domains, the agent flags the research as having insufficient source diversity and recommends broadening the search.
- **Temperature zero for verification prompts:** Verification requires deterministic, precise judgment. Using temperature 0 for verification LLM calls reduces variability in the quality gate.

### Report Writer

**What it does:** Generates a structured research report from verified findings, with inline citations, an executive summary, detailed analysis organized by theme, a section on contradictions and uncertainties, and a numbered reference list.

**Why it exists:** The final deliverable is a human-readable report, not a bag of findings. The Report Writer transforms structured data into a coherent narrative that follows academic conventions (inline citation notation, reference list, explicit uncertainty flagging).

**Key design decisions:**

- The report follows a fixed structure: Executive Summary, Key Findings, Detailed Analysis, Contradictions and Uncertainties, Recommendations for Further Research, and References.
- Every factual claim in the report must have at least one inline citation using [N] notation. The writer performs a post-processing pass to verify all citation references resolve to entries in the reference list.
- Low-confidence findings are explicitly flagged in the report text rather than silently included at the same confidence level as well-supported claims.

### Deepening Agent

**What it does:** Evaluates the current state of research, identifies knowledge gaps, and generates follow-up queries to fill them.

**Why it exists:** Initial search rarely covers a complex topic completely. The Deepening Agent enables iterative refinement by identifying what is missing (unanswered sub-questions, weak evidence, unresolved contradictions) and directing additional search passes to fill those gaps.

**Key design decisions:**

- **Iteration cap of 3:** Deepening is capped at a maximum of 3 iterations. Beyond this point, diminishing returns set in and token costs escalate without proportional quality improvement. If the research is still incomplete after 3 rounds, the report is generated with explicit notes about remaining gaps.
- **Quality threshold for early termination:** Deepening stops early if citation coverage exceeds 95% and there are zero weak findings, even if the iteration cap has not been reached.
- **Top-3 gaps per iteration:** Each deepening iteration addresses at most 3 knowledge gaps to keep the search focused and cost-controlled. Gaps are prioritized by impact on the overall research question.
- **Cost-aware deepening:** The Deepening Agent checks cumulative token spend before initiating additional search passes. When approaching the per-task budget, the agent forces synthesis of existing findings rather than searching further.

---

## Data Flow

```mermaid
graph TD
    Start[Receive Research Question] --> Plan[Plan Research<br/>Decompose into sub-questions]
    Plan --> Search[Search Multiple Sources<br/>Web, academic, internal]
    Search --> Extract[Extract and Chunk<br/>Parse content from sources]
    Extract --> Analyze[Analyze Findings<br/>Identify key themes and claims]
    Analyze --> Verify[Verify Claims<br/>Cross-reference sources]
    Verify --> Gap{Knowledge Gaps?}
    Gap -->|Yes| Deepen[Generate Follow-up Queries]
    Deepen --> Search
    Gap -->|No| Quality{Quality Sufficient?}
    Quality -->|No| Deepen
    Quality -->|Yes| Report[Generate Report<br/>With citations]
    Report --> Done[Return Report]

    style Start fill:#264653,stroke:#2a9d8f,color:#e9c46a
    style Done fill:#264653,stroke:#2a9d8f,color:#e9c46a
```

### Research Lifecycle Walkthrough

1. **Question intake** -- The user submits a natural language research question. The system classifies it by depth (quick or deep) based on complexity or explicit user preference.

2. **Planning** -- The Research Planner decomposes the question into 2-8 sub-questions, each tagged with priority, target source types, and expected evidence types. This is the full plan created upfront.

3. **Parallel search** -- The Search Agent executes queries across all specified sources concurrently. Each source has a 15-second timeout. Failed sources are logged and skipped without blocking the pipeline.

4. **Content extraction** -- Search results are fetched, parsed (HTML, PDF, or API), and chunked into semantically coherent segments. Chunks are embedded and stored in the per-task ephemeral vector store.

5. **Analysis and synthesis** -- The Analysis Agent reads across all extracted content, identifies key themes and claims, and pairs each claim with supporting citations. Claims are categorized and scored by confidence.

6. **Verification** -- The Verification Agent cross-references every claim against its cited source text, detects contradictions between findings, and checks source diversity. Issues are flagged in a verification report.

7. **Gap assessment and deepening** -- The Deepening Agent evaluates whether the research is complete. If knowledge gaps exist and the iteration cap (3 rounds) and token budget have not been exhausted, it generates follow-up queries and the process loops back to search. Otherwise, it forces synthesis.

8. **Report generation** -- The Report Writer produces the final structured report with inline citations, an executive summary, and explicit flagging of contradictions and low-confidence findings. A post-processing step validates that all citation references resolve correctly.

---

## Scaling Considerations

### Concurrency Model

```mermaid
graph LR
    subgraph "Parallel Search"
        Q1[Web Search] --> |concurrent| Results
        Q2[Academic Search] --> |concurrent| Results
        Q3[Internal KB] --> |concurrent| Results
    end

    subgraph "Sequential Analysis"
        Results --> Analyze[Analyze] --> Verify[Verify] --> Gaps{Gaps?}
        Gaps -->|Yes| Q1
        Gaps -->|No| Report[Report]
    end
```

| Optimization | Impact |
|-------------|--------|
| Parallel source search | 3-5x faster search phase |
| Embedding cache | Avoid re-embedding known content |
| Source content cache | Avoid re-fetching recently accessed pages |
| Early termination | Stop deepening when quality threshold met |
| Streaming report | Return sections as they are generated |

### Infrastructure Decisions

- **Task queue (Celery + Redis)** manages long-running research jobs, enabling idempotent task execution and resume-on-failure for tasks that take hours.
- **Async workers** for search and PDF processing, which are I/O-bound and benefit from non-blocking execution.
- **Rate limiting per source API** to avoid bans from web search providers and academic databases.
- **Cached search results and paper embeddings** for popular research topics to avoid redundant processing.
- **Server-sent events (SSE) or WebSocket** for streaming progress updates to users during long-running tasks.

---

## Cost Analysis

### Token Budget Per Task

Each research task is assigned a token budget tracked in the task state. The cumulative spend is updated after every LLM call. When spend approaches the budget ceiling, the system forces the agent to stop searching and synthesize whatever it has gathered so far.

| Phase | Tokens (Typical) | Cost |
|-------|-----------------|------|
| Planning | 5K | $0.02 |
| Search + extraction (5 sources) | 30K | $0.10 |
| Analysis | 25K | $0.15 |
| Verification | 15K | $0.08 |
| Deepening (1 iteration) | 30K | $0.15 |
| Report generation | 20K | $0.12 |
| **Total (deep research)** | **125K** | **$0.62** |

### Cost Control Mechanisms

- **Per-task budget cap:** Each task has a hard ceiling (default $2.00 for deep research). The orchestrator tracks cumulative spend in the task state and halts further search when approaching the limit.
- **Phase-level spend tracking:** Each phase (planning, search, analysis, verification, deepening, report) logs its token consumption independently, enabling fine-grained cost attribution and identification of cost outliers.
- **Forced synthesis on budget approach:** When cumulative spend reaches 80% of the task budget, the Deepening Agent is instructed to skip further searches and proceed directly to report generation with available findings.
- **Depth-based budget allocation:** Quick research tasks receive a lower budget (approximately $0.30) with fewer sub-questions and no deepening iterations. Deep research tasks receive the full budget.

---

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Search source down | Incomplete results | Degrade gracefully; note limited sources in report |
| Paywalled content | Cannot access full text | Use snippet/abstract; note access limitation |
| Contradictory sources | Confusing findings | Verification agent flags contradictions; present both perspectives |
| Hallucinated citations | Fake references | Verify URLs are valid and content matches |
| Circular reasoning | Agent cites its own prior output | Track source provenance; exclude agent-generated content |
| Token budget exceeded | Incomplete analysis | Prioritize critical sub-questions; generate partial report |

:::warning
The most insidious failure mode is **hallucinated citations** -- where the agent invents a reference that looks plausible but does not exist. The verification agent must check that every cited URL returns a page, and that the cited text actually appears on that page. Never trust the LLM to accurately recall source content from its training data.
:::

---

## Quality Metrics

| Metric | Measurement | Target |
|--------|-------------|--------|
| Citation accuracy | % of citations that link to actual content supporting the claim | > 95% |
| Source diversity | Number of unique domains cited | > 3 per major finding |
| Factual accuracy | Human evaluation of claims against sources | > 90% |
| Completeness | % of sub-questions adequately addressed | > 85% |
| Contradiction detection | % of contradictions flagged | > 80% |
| Report coherence | Human evaluation of structure and readability | > 4/5 |

---

## Trade-offs & Alternatives

| Decision | Rationale | Alternative | Why Not |
|----------|-----------|-------------|---------|
| Plan-and-Execute pattern | Full plan created upfront allows structured execution and incremental revision based on findings. Prevents aimless searching. | Reactive loop (search, observe, decide next step) | Reactive agents waste tokens exploring tangents and lack a coherent strategy. Planning provides structure while still allowing adaptation. |
| Per-task ephemeral vector store | Each research task gets its own vector store, populated only with sources found during that task. Prevents cross-task contamination and simplifies cleanup. | Shared persistent vector store across tasks | Cross-task contamination risks irrelevant or stale sources influencing current research. Shared stores also create cleanup and retention headaches. |
| Iterative deepening capped at 3 iterations | Diminishing returns set in rapidly. Most gaps are filled in 1-2 rounds; 3 rounds covers edge cases while keeping costs predictable. | Unlimited deepening until quality threshold met | Unbounded loops risk runaway costs and latency. An agent could cycle indefinitely on an unanswerable sub-question. |
| Forced synthesis on budget approach | When cumulative spend reaches 80% of budget, stop searching and generate the report with available findings. | Hard cut-off at budget limit | A hard cut-off might kill the process mid-generation, losing all work. Forced synthesis produces a useful (if incomplete) deliverable. |
| Semantic re-ranking of search results | Produces consistent quality ordering across heterogeneous source providers. | Trust each source engine's native ranking | Native rankings are not comparable across providers. A Bing result ranked 3rd and an arXiv result ranked 1st are not on the same scale. |
| Parallel source search | Reduces search phase latency from serial sum to parallel max. | Sequential search with early stopping | Sequential search is simpler but 3-5x slower. For a 2-minute quick-research target, parallel execution is necessary. |
| Temperature 0 for verification prompts | Verification requires deterministic, precise judgment. Low temperature reduces variability in quality gate decisions. | Default temperature (0.7) | Higher temperature introduces randomness into pass/fail decisions, making the quality gate unreliable. |
| Separate Verification Agent | Independent quality gate catches hallucinated citations, misrepresented sources, and contradictions. | Inline verification within Analysis Agent | Self-verification is unreliable. The same model that generated a hallucinated claim is unlikely to catch it on review. Separation of concerns improves accuracy. |

---

## Interview Tips

:::tip How to Present This (35 minutes)
1. **Clarify requirements** (3 min) -- Ask about source types, depth levels, latency expectations, output format, cost constraints, and quality bar. This shows you do not jump to solutions.
2. **Draw the architecture** (5 min) -- Sketch the five layers (UI, Orchestrator, Sources, Processing, Storage/Quality) and the iterative research loop. Highlight the Plan-and-Execute pattern.
3. **Deep dive: Research Planner and iterative deepening** (7 min) -- Explain how the planner decomposes questions, how the deepening loop works, why it is capped at 3 iterations, and how cost budgets gate further exploration.
4. **Deep dive: Citation tracking and verification** (7 min) -- Walk through how every claim links to a source passage, how the Verification Agent independently checks support, and how hallucinated citations are caught.
5. **Data flow walkthrough** (5 min) -- Trace the full lifecycle: question to plan to parallel search to extraction to synthesis to verification to deepening to report.
6. **Cost control and scaling** (4 min) -- Cover token budgets, per-phase spend tracking, forced synthesis on budget approach, parallel search, caching, and early termination.
7. **Failure modes** (2 min) -- Hit the top three: hallucinated citations, contradictory sources, and budget exhaustion. For each, state the impact and mitigation.
8. **Trade-offs** (2 min) -- Discuss one or two key decisions (per-task vector store vs. shared, plan-and-execute vs. reactive) with clear rationale and why you rejected the alternative.
:::

:::info
The research agent is an excellent system design interview topic because it tests your ability to design for uncertainty. Unlike a CRUD system where the data flow is deterministic, a research agent must adapt its strategy based on what it finds. Interviewers want to see that you can handle this non-determinism with structured iteration (Plan-and-Execute pattern), quality thresholds (verification agent, citation accuracy gates), cost controls (token budgets, forced synthesis), and graceful degradation (partial reports when budget is exhausted or sources are unavailable).
:::
