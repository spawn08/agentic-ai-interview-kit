---
sidebar_position: 1
title: "Customer Support Agent"
description: "Architecture design for a production AI-powered customer support agent system"
---

# Customer Support Agent

This design covers a production-grade AI-powered customer support agent that handles customer inquiries via chat, resolves common issues autonomously, and escalates to human agents when necessary. It is a canonical interview problem that tests your ability to combine LLM orchestration, tool integration, cost optimization, and production reliability.

---

## Problem Statement

> Design an AI-powered customer support agent for an e-commerce company. The system should handle customer inquiries through chat (web and mobile), answer questions about products, orders, returns, and account details, perform actions like looking up orders or initiating refunds, and escalate to human agents when the AI cannot resolve the issue. The system must support 5,000 concurrent sessions during peak hours, resolve at least 70% of conversations without human intervention, and keep the cost per conversation under $0.15. The company is SOC 2 and GDPR compliant, and all designs must respect those constraints.

---

## Clarifying Questions to Ask

Before designing, clarify these with the interviewer:

1. **Scale and traffic** -- What are the peak concurrent sessions? Is there seasonal variance (e.g., Black Friday spikes)? What is the expected daily conversation volume?
2. **Channels** -- Is this chat-only, or do we need to support voice and email as well? Are web and mobile the only entry points, or do we also serve partner APIs?
3. **Integration surface** -- What backend systems already exist? Do we have APIs for the order management system, CRM, and ticketing system, or do we need to build connectors?
4. **Scope of autonomous actions** -- Which actions can the agent perform directly (e.g., issue refunds, cancel orders) and which require human approval? What are the dollar thresholds for autonomous actions?
5. **Compliance requirements** -- What PII handling rules apply? Do we need to mask data in logs? Are there data residency requirements (e.g., EU data stays in EU)?
6. **SLAs and latency** -- What is the acceptable time-to-first-token? What latency is tolerable for tool calls like order lookups? Is there an SLA for escalation response time?

---

## Requirements

### Functional Requirements

1. Handle customer inquiries via chat (web and mobile)
2. Answer questions about products, orders, returns, and account details
3. Perform actions: look up orders, initiate returns, create support tickets, issue refunds
4. Escalate to human agents when the AI cannot resolve the issue
5. Support multi-turn conversations with context retention
6. Provide consistent responses aligned with company policies

### Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Latency (first response) | < 3 seconds |
| Latency (subsequent turns) | < 2 seconds |
| Availability | 99.9% uptime |
| Concurrent sessions | 5,000 |
| Resolution rate (no human) | > 70% |
| Cost per conversation | < $0.15 |
| Security | PII masking, SOC 2, GDPR compliance |

### Out of Scope

- Voice support (chat only for this design)
- Proactive outreach (reactive only)
- Multi-language (English only for V1)

---

## High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        Web[Web Chat Widget]
        Mobile[Mobile App Chat]
        API_EXT[Partner API]
    end

    subgraph "API Layer"
        GW[API Gateway<br/>Rate Limiting, Auth]
        WS[WebSocket Server<br/>Real-time Streaming]
    end

    subgraph "Agent Layer"
        Router[Intent Router]
        FAQ[FAQ Agent<br/>GPT-4o-mini]
        Order[Order Agent<br/>GPT-4o]
        Return[Return Agent<br/>GPT-4o]
        Escalation[Escalation Agent]
    end

    subgraph "Tool Layer"
        CRM[CRM Lookup]
        OMS[Order Management]
        KB[Knowledge Base<br/>RAG]
        Ticket[Ticketing System]
        Refund[Refund Service]
    end

    subgraph "Data Layer"
        Session[Session Store<br/>Redis]
        History[Conversation History<br/>PostgreSQL]
        Vector[Vector Store<br/>pgvector]
        Analytics[Analytics<br/>ClickHouse]
    end

    subgraph "Observability"
        OTel[OpenTelemetry]
        LF[Langfuse]
        Grafana[Grafana Dashboards]
    end

    Web --> GW
    Mobile --> GW
    API_EXT --> GW
    GW --> WS
    WS --> Router
    Router --> FAQ
    Router --> Order
    Router --> Return
    Router --> Escalation
    FAQ --> KB
    Order --> CRM
    Order --> OMS
    Return --> OMS
    Return --> Refund
    Escalation --> Ticket
    FAQ --> Session
    Order --> Session
    Return --> Session
    Session --> History
    KB --> Vector
    Router --> OTel
    FAQ --> LF
    OTel --> Grafana
```

### Architecture Walkthrough

The architecture follows a layered design that separates concerns and enables independent scaling of each tier.

The **Client Layer** accepts requests from web chat widgets, mobile app chat, and partner APIs. All traffic funnels through the **API Layer**, where an API Gateway handles authentication, rate limiting, and tenant identification, and a WebSocket server provides real-time streaming for token-by-token response delivery.

The **Agent Layer** is the core of the system. An Intent Router classifies each incoming message and dispatches it to the appropriate specialist agent -- FAQ, Order, Return, or Escalation. Each agent is purpose-built for its domain: the FAQ Agent uses RAG over a knowledge base for informational queries, the Order and Return Agents have tool access to the CRM and order management system for transactional queries, and the Escalation Agent handles handoffs to human support. This specialization allows each agent to use the optimal model for its task (cheap models for FAQ, more capable models for order actions), which is the primary cost optimization lever.

The **Tool Layer** exposes backend systems as callable tools -- CRM lookups, order management, knowledge base retrieval, ticketing, and refund processing. The **Data Layer** stores session state in Redis for fast access, persists conversation history in PostgreSQL, indexes knowledge base articles in pgvector, and streams analytics events to ClickHouse. The **Observability** stack (OpenTelemetry, Langfuse, Grafana) provides end-to-end tracing, LLM-specific metrics, and operational dashboards.

---

## Component Design

### 1. Intent Router

The Intent Router is the entry point for every customer message. Its job is to classify the user's intent and dispatch to the correct specialist agent. It exists as a separate component for one critical reason: **cost optimization**. Without a router, every message would go to the most capable (and most expensive) model. With routing, simple FAQ questions (60% of traffic) go to GPT-4o-mini at $0.15/1M input tokens, while only complex order and return issues go to GPT-4o at $2.50/1M input tokens.

The router uses GPT-4o-mini for classification itself -- it is a lightweight, fast classification task that does not need a large model. It maintains a mapping of intents to agent configurations:

| Intent | Agent | Model | Priority |
|--------|-------|-------|----------|
| FAQ / general question | FAQ Agent | GPT-4o-mini | Low |
| Order status | Order Agent | GPT-4o | Normal |
| Return request | Return Agent | GPT-4o | Normal |
| Billing issue | Order Agent | GPT-4o | High |
| Complaint / request for human | Escalation Agent | GPT-4o | High |
| Unknown | FAQ Agent | GPT-4o-mini | Normal |

The router also includes a hard-coded override: if the user explicitly asks for a human agent (detected via keyword matching, not LLM), the message is routed directly to the Escalation Agent regardless of classified intent. This ensures customers are never trapped in an AI loop when they want human help.

The classification uses the last 4 messages of conversation history (not just the current message) to handle context-dependent intents. For example, if a customer has been asking about an order and then says "this is unacceptable," the router sees the order context and routes to Escalation rather than FAQ.

### 2. FAQ Agent (RAG-Based)

The FAQ Agent handles product questions, policy inquiries, and general information -- roughly 60% of all conversations. It uses Retrieval-Augmented Generation (RAG) over the company knowledge base.

**Retrieval strategy**: When a message arrives, the agent embeds the query and retrieves the top 5 relevant articles from the pgvector store, filtering to only published articles. The retrieved documents are injected into the system prompt as context, and the LLM generates a response grounded in those documents.

**Model and temperature**: The agent uses GPT-4o-mini with a temperature of 0.1. The low temperature ensures consistent, factual responses -- customer support answers should not vary creatively between sessions. GPT-4o-mini is sufficient because FAQ responses are largely extractive (pulling answers from retrieved documents rather than reasoning over complex scenarios).

**Confidence thresholds and escalation**: The agent evaluates confidence in its response. If confidence falls below 0.6, the agent does not attempt an answer. Instead, it returns an escalation signal with the reason "low_confidence" and the confidence score. This prevents the agent from confidently delivering wrong answers, which erodes customer trust faster than admitting it cannot help. The threshold of 0.6 is tuned based on production data -- too high and you escalate too many routine questions; too low and you deliver unreliable answers.

### 3. Order Agent

The Order Agent handles order lookups, status checks, and modifications. Unlike the FAQ Agent, it needs to take actions -- looking up real data and creating real tickets -- which makes it more complex and requires a more capable model (GPT-4o).

**Tool access**: The agent has access to three tools:

| Tool | Purpose | Required Parameters |
|------|---------|-------------------|
| `lookup_order` | Find an order by order ID or customer email | `order_id` (optional), `email` (optional) |
| `get_order_status` | Get current status and tracking info | `order_id` (required) |
| `create_support_ticket` | Create a ticket for issues needing manual review | `subject`, `description`, `priority` |

**CRM integration**: The agent first loads session state from Redis to understand the customer context (authenticated user, previous messages). It then sends the message and conversation history to the LLM, which generates a plan -- typically a tool call sequence. For example, for "Where is my order #12345?", the LLM plans to call `get_order_status`, receives the order data (status, tracking number, carrier), and synthesizes a natural-language response.

**Why GPT-4o instead of GPT-4o-mini**: The Order Agent needs to reason about when to call which tool, interpret structured API responses, and compose responses that combine data from multiple sources. GPT-4o-mini's smaller capacity leads to more frequent tool-calling errors and hallucinated order data in testing. The cost difference is justified by the higher accuracy requirement for transactional queries.

### 4. Escalation Agent

The Escalation Agent manages the handoff from AI to human support. Its design goal is to make the handoff as smooth as possible -- the human agent should have full context without needing to ask the customer to repeat themselves.

**Conversation summarization**: When escalation is triggered, the agent uses GPT-4o-mini to generate a structured summary of the conversation. The summary includes: the customer's core issue, what steps the AI already took (tool calls, information retrieved), relevant order or account information discovered during the conversation, and the reason for escalation (low confidence, customer request, policy constraint).

**Handoff protocol**: The agent creates a handoff ticket in the ticketing system with the session ID, customer ID, conversation summary, full conversation history, priority level, and escalation reason. Priority is determined by signals in the conversation -- mentions of legal action, repeated frustration, high-value orders, or billing disputes increase priority.

**Ticket creation and customer communication**: The agent gives the customer a reference number and a message acknowledging the handoff. This is important for customer experience -- the customer knows their issue is not being dropped.

| Escalation Trigger | Priority Assignment |
|--------------------|-------------------|
| Customer explicitly requests human | Normal |
| Low confidence on FAQ response | Normal |
| Billing dispute over threshold | High |
| Repeated failed resolution attempts | High |
| Mention of legal action or regulatory complaint | Critical |

---

## Data Flow

### Happy Path: Order Status Inquiry

```mermaid
sequenceDiagram
    participant User
    participant GW as API Gateway
    participant Router as Intent Router
    participant OA as Order Agent
    participant LLM as GPT-4o
    participant OMS as Order System
    participant Redis as Session Store

    User->>GW: "Where is my order #12345?"
    GW->>Router: Route message
    Router->>Router: Classify intent: order_status
    Router->>OA: Dispatch to Order Agent

    OA->>Redis: Load session state
    OA->>LLM: Generate plan
    LLM-->>OA: Plan: call get_order_status

    OA->>OMS: get_order_status(order_id="12345")
    OMS-->>OA: {status: "shipped", tracking: "1Z999..."}

    OA->>LLM: Synthesize response with order data
    LLM-->>OA: "Your order #12345 was shipped on June 8..."

    OA->>Redis: Save session state
    OA-->>GW: Response
    GW-->>User: "Your order #12345 was shipped on June 8..."
```

### Happy Path Walkthrough

The user sends "Where is my order #12345?" through the web chat widget. The API Gateway authenticates the request and forwards it to the Intent Router. The router classifies the intent as `order_status` using GPT-4o-mini (a lightweight classification call costing fractions of a cent) and dispatches to the Order Agent.

The Order Agent loads the session state from Redis to check for any prior context (is this a returning customer? have they already asked about this order?). It sends the message and conversation history to GPT-4o, which generates a plan: call the `get_order_status` tool with `order_id="12345"`.

The agent executes the tool call against the Order Management System, which returns structured data: the order is shipped, the tracking number is "1Z999...", and the carrier is UPS. The agent sends this data back to GPT-4o to synthesize a natural-language response: "Your order #12345 was shipped on June 8 and is currently in transit. Your tracking number is 1Z999..."

The agent saves the updated session state (including this turn) to Redis and returns the response through the API Gateway to the user. Total latency: under 3 seconds. Total cost: approximately $0.015.

### Escalation Path

```mermaid
sequenceDiagram
    participant User
    participant Router
    participant FAQ as FAQ Agent
    participant Esc as Escalation Agent
    participant Human as Human Agent

    User->>Router: "I've been waiting 3 weeks for my refund!"
    Router->>FAQ: First attempt (classified as FAQ)
    FAQ->>FAQ: Low confidence on refund policy
    FAQ-->>Router: Escalate (confidence < 0.6)

    Router->>Esc: Handoff to escalation
    Esc->>Esc: Summarize conversation
    Esc->>Human: Create handoff ticket
    Esc-->>User: "Connecting you with a specialist. Ref: #T-9876"
    Human->>User: "Hi, I can see your refund request..."
```

### Escalation Path Walkthrough

The user sends "I've been waiting 3 weeks for my refund!" The Intent Router classifies this as an FAQ-type query (refund policy) and dispatches to the FAQ Agent. The FAQ Agent retrieves relevant knowledge base articles about refund timelines, but the retrieved documents cover standard refund policy (5-7 business days) -- they do not address a 3-week delay, which is an exception case.

The agent's confidence score drops below 0.6 because the retrieved documents do not directly address the user's specific complaint. Rather than generating a generic refund policy response (which would frustrate an already upset customer), the FAQ Agent returns an escalation signal.

The Router receives the escalation signal and hands off to the Escalation Agent. The Escalation Agent summarizes the conversation (customer issue: refund delayed beyond normal timeline, no resolution found in knowledge base), creates a handoff ticket in the ticketing system with high priority (billing-related, customer frustration signals), and responds to the user with a reference number. The human agent picks up the ticket and sees the full context -- they know the customer has been waiting 3 weeks and that the AI could not resolve it, so they can skip the initial diagnostic questions and go straight to investigating the delayed refund.

---

## Scaling Considerations

### Traffic Patterns

| Time | Traffic Level | Strategy |
|------|--------------|----------|
| Business hours (9 AM - 6 PM) | Peak: 5,000 concurrent | Full scaling |
| Evening (6 PM - 11 PM) | Moderate: 2,000 concurrent | Moderate scaling |
| Night (11 PM - 9 AM) | Low: 500 concurrent | Minimum scaling |
| Sale events (Black Friday) | Spike: 20,000 concurrent | Pre-scaled + auto-scale |

### Auto-Scaling Strategy

The agent workers scale horizontally based on queue depth, targeting 10 concurrent sessions per worker. Minimum replicas are set to 5 (to handle low overnight traffic without cold starts), maximum at 100 (for Black Friday spikes). Scale-up cooldown is 30 seconds (react fast to spikes) while scale-down cooldown is 300 seconds (avoid flapping).

The Redis session store runs in cluster mode with 3 shards and 2 replicas per shard, providing both read throughput and fault tolerance. Sessions have a TTL to prevent unbounded memory growth.

LLM API calls are distributed across multiple providers (OpenAI primary, Azure OpenAI fallback) with a combined rate limit of 10,000+ requests per minute and automatic failover.

### Bottleneck Analysis

| Component | Bottleneck | Mitigation |
|-----------|-----------|------------|
| LLM API | Rate limits (TPM/RPM) | Multiple API keys, multiple providers, request queuing |
| WebSocket server | Connection count | Horizontal scaling, connection pooling |
| Redis | Memory for sessions | Cluster mode, TTL on sessions, tiered storage |
| Knowledge base (vector search) | Query latency under load | Read replicas, result caching |
| Order management API | Rate limits from upstream | Cache recent orders, batch queries |

### Semantic Caching

For high-traffic deployments, semantic caching can dramatically reduce LLM costs. Before making a new LLM call, the system embeds the incoming query and checks similarity against recent queries in a cache. If a cached query has a cosine similarity above 0.95, the cached response is returned directly without an LLM call. This is particularly effective for the FAQ Agent, where many customers ask semantically identical questions ("where is my order" vs. "order status" vs. "track my package"). At 50,000 daily conversations with 60% FAQ traffic, even a 30% cache hit rate saves roughly 9,000 LLM calls per day.

### LLM Provider Abstraction and Circuit Breakers

Rather than coupling directly to a single LLM provider, the system uses an **LLM Gateway** -- an internal abstraction layer that routes requests to different providers (OpenAI, Azure OpenAI, Anthropic) based on configuration, cost, and availability.

Each provider connection has its own **circuit breaker**. When a provider's error rate exceeds a threshold (e.g., 5 errors in 30 seconds), the circuit breaker trips and routes all traffic to the fallback provider. The circuit breaker enters a half-open state after a cooldown period, allowing a small percentage of test requests through to detect recovery. This prevents cascading failures during provider outages -- without circuit breakers, retries against a down provider would exhaust rate limits and increase latency for all customers.

The LLM Gateway also enables transparent model upgrades, A/B testing between providers, and per-model cost tracking.

### Multi-Tenant Considerations

If this system evolves into a platform serving multiple enterprise tenants (each with their own knowledge base, tools, and brand voice), two isolation strategies become critical:

- **Vector store isolation**: Use namespace-based isolation within the vector store rather than separate instances per tenant. Each tenant's knowledge base documents are indexed under a tenant-specific namespace. Queries are scoped to the tenant's namespace, preventing cross-tenant data leakage. Separate instances per tenant do not scale past a few hundred tenants.
- **Database isolation**: Use row-level security in PostgreSQL for tenant configuration and conversation history. Every row carries a `tenant_id`, and database policies enforce that queries can only access rows matching the authenticated tenant. This provides strong isolation without the operational overhead of separate databases per tenant.

---

## Cost Analysis

### Per-Conversation Cost Breakdown

| Component | Tokens/Calls | Unit Cost | Cost per Conversation |
|-----------|-------------|-----------|----------------------|
| Intent classification | 200 tokens (mini) | $0.15/1M | $0.00003 |
| FAQ response (3 turns) | 3,000 tokens (mini) | $0.15/1M in, $0.60/1M out | $0.0008 |
| Order lookup (3 turns) | 4,500 tokens (4o) | $2.50/1M in, $10/1M out | $0.015 |
| RAG retrieval | 3 queries | $0.001/query | $0.003 |
| Redis session | 1 session | ~$0 | negligible |
| **Total (FAQ path)** | | | **$0.004** |
| **Total (order path)** | | | **$0.018** |
| **Blended average** | 60% FAQ, 40% order | | **$0.010** |

:::tip
The blended cost per conversation ($0.01) is well under the $0.15 budget. This headroom allows for longer conversations, retries, and the occasional expensive escalation path without exceeding budget.
:::

### Monthly Cost at Scale

| Metric | Value |
|--------|-------|
| Daily conversations | 50,000 |
| Monthly conversations | 1,500,000 |
| Blended cost per conversation | $0.010 |
| **Monthly LLM cost** | **$15,000** |
| Infrastructure (Redis, compute, networking) | $3,000 |
| Observability (Langfuse, Grafana) | $500 |
| **Total monthly cost** | **$18,500** |

---

## Failure Modes and Mitigations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Primary LLM down | No AI responses | Fallback to Azure OpenAI; circuit breaker |
| Redis down | Session loss | Redis Cluster with replicas; fall back to stateless mode |
| Order API down | Cannot look up orders | Return cached data if available; apologize and create ticket |
| Vector store slow | Slow FAQ responses | Cache top-100 FAQ answers; serve from cache on timeout |
| Prompt injection | Unauthorized actions | Input filtering, tool sandboxing, least privilege |

---

## Data Layer Deep Dive

### Database Selection Justification

Each data store in the architecture was chosen for a specific reason tied to the workload it serves. The table below summarizes the selection rationale and the alternatives that were evaluated and rejected.

| Store | Technology | Why This Choice | Alternative Considered | Why Not |
|-------|-----------|----------------|----------------------|---------|
| Session state | Redis | Sub-millisecond reads for real-time chat; built-in TTL handles session expiration without manual cleanup; pub/sub channel supports WebSocket event broadcasting across horizontally scaled workers | DynamoDB | Higher read latency (single-digit ms vs. sub-ms); provisioned capacity pricing is overkill for ephemeral session data that lives for minutes to hours |
| Conversation history | PostgreSQL | ACID transactions required for SOC 2 and GDPR audit compliance; rich querying for analytics and reporting; JSONB columns for flexible tool result storage; row-level security (RLS) for multi-tenant isolation without separate databases | MongoDB | Weaker consistency guarantees make audit trails harder to defend during compliance audits; RLS enforcement is more complex, requiring application-level tenant filtering rather than database-enforced policies |
| Knowledge base (vectors) | pgvector | Runs inside the existing PostgreSQL instance -- no separate managed service to operate; sufficient performance for knowledge bases under 1M documents; leverages existing PostgreSQL backup, monitoring, and access control infrastructure | Pinecone | Adds a separate managed service with its own authentication, networking, and billing; operational complexity is not justified at this scale; pgvector handles sub-100ms similarity search for the expected corpus size |
| Analytics | ClickHouse | Columnar storage optimized for aggregation queries (cost rollups, usage pattern analysis, resolution rate calculations); handles high write throughput from streaming conversation events without impacting transactional workloads | PostgreSQL with materialized views | Works for initial scale, but analytics queries (scanning millions of rows for monthly rollups) compete with OLTP workload (conversation reads/writes) as volume grows; ClickHouse isolates analytical load entirely |

### Schema Design

The following schemas define the core data model. Each table includes its indexes with justification for why each index exists.

#### conversations

Tracks each customer support session from creation through resolution.

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('web', 'mobile', 'api')),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'escalated', 'resolved', 'abandoned')),
    assigned_agent VARCHAR(20),
    resolution_type VARCHAR(20),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

-- Fast lookup when loading a returning customer's recent conversations
CREATE INDEX idx_conversations_user ON conversations(user_id, created_at DESC);

-- Dashboard queries: "show all active conversations for tenant X"
CREATE INDEX idx_conversations_tenant_status ON conversations(tenant_id, status);

-- Global conversation feed sorted by recency (admin dashboards, cleanup jobs)
CREATE INDEX idx_conversations_created ON conversations(created_at DESC);
```

**Index rationale**:
- `idx_conversations_user` -- The cross-session memory feature (described below) loads the last 3 conversations for a returning customer. This composite index on `(user_id, created_at DESC)` serves that query without a sort operation.
- `idx_conversations_tenant_status` -- Multi-tenant dashboards filter by tenant and status constantly. Without this index, every dashboard load scans the full table.
- `idx_conversations_created` -- The TTL cleanup job (see Key Queries below) scans for old abandoned conversations. A descending time index makes this scan efficient.

#### messages

Stores every turn of every conversation, including tool calls, token counts, and cost tracking.

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    tool_calls JSONB,
    tool_results JSONB,
    model VARCHAR(50),
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd NUMERIC(10, 6),
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Primary access pattern: load all messages for a conversation in chronological order
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);
```

**Index rationale**:
- `idx_messages_conversation` -- Every agent turn starts by loading recent messages for the active conversation. This composite index serves the query `WHERE conversation_id = ? ORDER BY created_at` as an index-only scan, avoiding a heap lookup for ordering.

#### knowledge_articles

Stores the knowledge base articles with their vector embeddings for RAG retrieval.

```sql
CREATE TABLE knowledge_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(64) NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50),
    embedding vector(1536),
    chunk_index INTEGER DEFAULT 0,
    source_url TEXT,
    is_published BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- HNSW index for approximate nearest neighbor search over embeddings
CREATE INDEX idx_articles_embedding ON knowledge_articles
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- Partial index: only published articles for a tenant (filters unpublished at index level)
CREATE INDEX idx_articles_tenant_published ON knowledge_articles(tenant_id)
    WHERE is_published = true;
```

**Index rationale**:
- `idx_articles_embedding` -- The HNSW index enables sub-100ms approximate nearest neighbor search. Parameters `m = 16` and `ef_construction = 200` balance recall accuracy against index build time. At fewer than 1M documents, HNSW provides better query latency than IVFFlat while maintaining recall above 0.95.
- `idx_articles_tenant_published` -- A partial index that only includes published articles. This means unpublished (draft or archived) articles are excluded at the index level, reducing index size and ensuring they never appear in retrieval results even without a WHERE clause in the query.

### Key Queries

These are the actual queries the system executes in production, not simplified examples.

**1. Retrieve conversation history (cursor-based pagination)**

Used by the agent to load recent messages and by the dashboard to display conversation history.

```sql
SELECT id, role, content, tool_calls, tool_results, model, created_at
FROM messages
WHERE conversation_id = $1
  AND created_at < $2          -- cursor: created_at of last seen message
ORDER BY created_at DESC
LIMIT 20;
```

Cursor-based pagination (using `created_at < $2` rather than `OFFSET`) avoids the performance degradation of large offsets and handles concurrent inserts correctly -- new messages arriving during pagination do not cause duplicates or skipped rows.

**2. Semantic search over knowledge base (pgvector similarity with tenant filtering)**

Used by the FAQ Agent to retrieve relevant articles for RAG.

```sql
SELECT id, title, content, category,
       1 - (embedding <=> $1) AS similarity
FROM knowledge_articles
WHERE tenant_id = $2
  AND is_published = true
ORDER BY embedding <=> $1
LIMIT 5;
```

The `<=>` operator computes cosine distance. The query filters to the tenant's published articles first (using the partial index), then performs approximate nearest neighbor search over the remaining set. The `1 - distance` conversion returns cosine similarity (higher is better) for use in confidence scoring downstream.

**3. Cost rollup per tenant per day (analytics)**

Used for billing dashboards and cost monitoring. Runs against ClickHouse in production, shown here in SQL for clarity.

```sql
SELECT tenant_id,
       DATE_TRUNC('day', m.created_at) AS day,
       COUNT(DISTINCT c.id) AS conversations,
       SUM(m.tokens_in) AS total_tokens_in,
       SUM(m.tokens_out) AS total_tokens_out,
       SUM(m.cost_usd) AS total_cost
FROM messages m
JOIN conversations c ON m.conversation_id = c.id
WHERE m.created_at >= $1 AND m.created_at < $2
GROUP BY tenant_id, DATE_TRUNC('day', m.created_at)
ORDER BY day DESC, total_cost DESC;
```

**4. Find conversations needing cleanup (TTL-based)**

Used by a scheduled cleanup job that runs every hour to close abandoned conversations and free Redis session memory.

```sql
UPDATE conversations
SET status = 'abandoned',
    updated_at = now()
WHERE status = 'active'
  AND updated_at < now() - INTERVAL '2 hours'
RETURNING id, session_id;
```

The `RETURNING` clause gives the cleanup job the session IDs it needs to delete from Redis in the same operation, avoiding a separate SELECT query.

---

## Agent Memory Architecture

Memory management is one of the most critical design decisions in a multi-turn conversational agent. The customer support agent uses a hybrid memory model: short-term memory in Redis for the active session, long-term memory in PostgreSQL for persistence and cross-session context.

### Memory Tiers

```mermaid
graph LR
    subgraph "Short-Term Memory (Redis)"
        SS[Session State<br/>Current intent, active plan]
        RM[Recent Messages<br/>Last 10 turns]
        TC[Tool Cache<br/>Recent API responses]
    end

    subgraph "Long-Term Memory (PostgreSQL)"
        CH[Conversation History<br/>Full message log]
        CS[Conversation Summaries<br/>Compressed context]
        UP[User Patterns<br/>Past interaction history]
    end

    subgraph "Context Assembly"
        CA[Context Window Builder<br/>Budget-based packing]
    end

    SS --> CA
    RM --> CA
    TC --> CA
    CS --> CA
    UP --> CA
    CA --> LLM[LLM Call]
```

**Short-term memory (Redis)** holds the active session state -- the current intent classification, the agent's active plan (e.g., "looking up order, waiting for tool response"), and the last 10 messages in the conversation. This data is accessed on every turn (sub-millisecond reads are essential) and expires automatically via Redis TTL when the session ends.

**Long-term memory (PostgreSQL)** holds the full conversation history, compressed summaries of completed conversations, and user interaction patterns. This data is accessed less frequently -- primarily at session start (to load cross-session context) and at session end (to persist the completed conversation).

### Context Window Strategy

The system uses a **budget-based context packing** approach. For each LLM call, the context window is allocated within a fixed token budget to balance completeness against cost.

| Context Component | Token Budget | Source |
|-------------------|-------------|--------|
| System prompt + tool definitions | ~1,500 tokens (fixed) | Static configuration |
| Retrieved knowledge base articles | ~2,000 tokens (up to 5 chunks x 400 tokens) | pgvector retrieval |
| Recent conversation history | ~1,500 tokens (last 10 messages) | Redis |
| Rolling summary of older history | ~500 tokens (if conversation > 10 turns) | PostgreSQL |
| Response budget | ~1,000 tokens | Reserved for LLM output |
| **Total per turn** | **~6,500 tokens** | |

This budget keeps each turn well within GPT-4o-mini's 128K context limit while optimizing for cost -- paying for 6,500 tokens per turn rather than naively stuffing the full conversation history (which could grow to 50K+ tokens in long sessions).

### Rolling Summary

When a conversation exceeds 10 turns, the system compresses older messages into a rolling summary. This prevents unbounded context growth while preserving the information the agent needs.

The summary is generated by GPT-4o-mini with a structured prompt that captures four elements:
1. **Customer's issue** -- what the customer originally asked about
2. **Actions taken** -- which tools were called and what data was retrieved
3. **Current state** -- where the conversation stands (resolved? pending? escalated?)
4. **Relevant data** -- order numbers, account details, or policy references discovered during the conversation

The summary replaces messages 1 through N-10 in the context window. Only the most recent 10 messages are kept verbatim. This approach costs approximately $0.001 per summary (a short GPT-4o-mini call) but saves $0.01+ per turn in reduced context length for long conversations.

### Cross-Session Memory

For returning customers, the system provides continuity across sessions. At session start, the system loads the last 3 conversation summaries for the authenticated user from PostgreSQL:

```sql
SELECT summary, status, resolution_type, created_at
FROM conversation_summaries
WHERE user_id = $1
ORDER BY created_at DESC
LIMIT 3;
```

This enables responses like "I see you contacted us about order #12345 last week -- is this about the same issue?" Cross-session memory is loaded only for authenticated users and only if conversations exist within the last 30 days. The lookup is a simple indexed query on `user_id`, not an embedding-based search, because it retrieves the user's own history rather than searching for similar conversations.

:::note Design Decision
Cross-session memory is scoped to summaries, not full message histories. Loading full histories of prior conversations would bloat the context window and increase cost. Summaries provide sufficient context for continuity at a fraction of the token cost.
:::

---

## Hallucination Mitigation

In a customer support context, hallucinations are not just inaccurate -- they are actively harmful. A fabricated order number, an invented refund policy, or a hallucinated tracking link erodes customer trust and can create legal liability. The system employs five layers of defense against hallucinations.

### Hallucination Prevention Pipeline

```mermaid
graph TB
    LLM[LLM Response Generated] --> V1[Tool Result Validation<br/>Did the tool actually return this data?]
    V1 -->|Pass| V2[Citation Verification<br/>Is the response grounded in retrieved chunks?]
    V1 -->|Fail| REJECT[Reject and Regenerate]
    V2 -->|Pass| V3[Confidence Scoring<br/>Is confidence above 0.6?]
    V2 -->|Fail| FLAG[Flag as Ungrounded]
    V3 -->|Pass| SEND[Send to Customer]
    V3 -->|Fail| ESCALATE[Escalate to Human]
    FLAG --> ESCALATE
```

### Layer 1: Fabricated Order Data Prevention

The agent must never invent order details -- order numbers, tracking numbers, delivery dates, or refund amounts. The mitigation is structural: **all order data must originate from tool calls**.

After the LLM generates a response, the system validates that every order-related claim corresponds to data returned by a tool call in the current turn. If the response references an order number that was not returned by `lookup_order` or `get_order_status`, the response is rejected and regenerated with an explicit instruction: "Only reference order data returned by the tools above."

This validation is rule-based (regex extraction of order numbers and cross-referencing with tool results), not LLM-based, ensuring it cannot itself be fooled.

### Layer 2: Policy Hallucination Prevention

The FAQ Agent must not invent return policies, refund timelines, warranty terms, or any other policy information. The mitigation is prompt-level grounding.

The system prompt includes an explicit constraint: **"Only answer based on the retrieved knowledge base articles. If the articles do not contain the answer, respond that you do not have that information and offer to connect the customer with a human agent."** Temperature is set to 0.1 to minimize creative generation and maximize extractive responses from the retrieved context.

### Layer 3: Confidence Scoring

Every agent response includes a confidence score derived from the LLM's self-assessment and the retrieval quality (average similarity score of retrieved chunks). Responses are routed based on confidence:

| Confidence Range | Action |
|-----------------|--------|
| 0.6 -- 1.0 | Send response to customer |
| 0.4 -- 0.6 | Send response with disclaimer: "Based on my understanding..." and suggest human agent option |
| Below 0.4 | Do not send response; escalate to human agent |

The 0.6 threshold was tuned on production data. Setting it higher (e.g., 0.8) caused 40% of routine FAQ questions to escalate unnecessarily, overwhelming the human agent queue. Setting it lower (e.g., 0.3) allowed confident-sounding but incorrect answers through, which generated customer complaints.

### Layer 4: Citation Verification

For FAQ responses, the system verifies that the response content is actually entailed by the retrieved knowledge base chunks. After generating a response, the system embeds the response and computes cosine similarity against each retrieved chunk. If the maximum similarity between the response embedding and all retrieved chunk embeddings falls below 0.5, the response is flagged as potentially ungrounded -- the agent may be generating information not present in the knowledge base.

Flagged responses are either regenerated with a stricter prompt or escalated, depending on the confidence score from Layer 3.

### Layer 5: Tool Result Validation

Before incorporating tool results into a response, the system validates three conditions:

1. **The tool was actually called** -- the tool call ID in the response matches a tool call that was dispatched and received a response. This prevents the LLM from fabricating tool results in its output.
2. **The response schema matches** -- the tool result conforms to the expected JSON schema for that tool. Malformed or unexpected responses are rejected rather than passed to the LLM for interpretation.
3. **Data consistency checks** -- basic sanity checks on the data: order dates are not in the future, refund amounts are not negative, tracking numbers match the expected format for the carrier. These checks catch corrupted or test data from upstream systems before it reaches the customer.

:::warning Critical Design Principle
Hallucination mitigation layers are additive, not alternative. No single layer catches all hallucination types. Tool result validation catches fabricated data, citation verification catches ungrounded policy claims, and confidence scoring catches the cases where the model is uncertain but generates a response anyway. Removing any layer creates a gap.
:::

---

## Production Issues and Fixes

The following table documents production issues observed in customer support agent deployments, their root causes, and the fixes applied. These are the issues that do not appear in architecture diagrams but dominate on-call rotations.

| Issue | Symptoms | Root Cause | Fix |
|-------|----------|-----------|-----|
| Agent loops on ambiguous intent | Same classification repeated 3+ times; customer frustration rises; conversation exceeds 10 turns without progress | User query matches multiple intents with near-equal probability; the router oscillates between FAQ and Order agents each turn | Add a "confused" intent that triggers immediate escalation after 2 reclassifications; implement a priority ordering for tie-breaking (FAQ < Order < Return < Escalation) so ties resolve deterministically |
| Stale knowledge base answers | Agent gives outdated policy information (e.g., old return window); customer complaints about incorrect information | Knowledge articles were updated in the CMS but the embedding index was not refreshed | Implement webhook-triggered re-indexing: CMS publishes an event on article update, the indexing service re-embeds and upserts the article within 5 minutes; add `updated_at` freshness check in retrieval to prefer recently updated articles |
| PII leakage in logs | Customer PII (emails, phone numbers, addresses) found in observability logs during a compliance audit | Tool results containing PII were logged verbatim by the tracing middleware | Add PII scrubbing middleware to the logging pipeline; use regex-based redaction for emails, phone numbers, credit card numbers, and addresses before writing to any log sink; validate with automated PII scanning in CI |
| Cost spike on long conversations | Monthly LLM cost 3x the projected budget | 5% of conversations exceed 20 turns, each turn hitting GPT-4o with a growing context window; these long conversations account for 40% of total token spend | Add a per-conversation cost limit ($0.50); after the limit is reached, switch to summary mode (compress history, use GPT-4o-mini) or escalate to a human agent; alert on conversations exceeding 15 turns |
| WebSocket disconnection losing context | Customer reconnects after a network interruption; the agent has no memory of the prior conversation; customer must repeat their issue | Session state expired in Redis during the network interruption (TTL elapsed while the customer was disconnected) | Persist conversation checkpoints to PostgreSQL every 5 turns; on reconnect, attempt Redis recovery first, then fall back to PostgreSQL checkpoint; extend Redis TTL to 30 minutes for sessions with active WebSocket connections |
| Escalation queue flooding | Human agents overwhelmed with escalated conversations; wait times exceed 30 minutes; customer satisfaction drops | Confidence threshold set too high (0.8), causing the agent to escalate routine FAQ questions that it could answer correctly | Tune the confidence threshold down to 0.6 based on production accuracy data; add a "suggest but do not escalate" tier for medium confidence (0.4--0.6) where the agent provides its best answer along with an option to speak with a human |
| Semantic cache returning wrong answers | Customer receives an answer to a semantically similar but different question (e.g., asked about return policy for electronics, received answer about return policy for clothing) | Cosine similarity threshold for cache hits set too low (0.90), matching queries that are similar but not equivalent | Raise the similarity threshold to 0.95; add a category-matching constraint so cache hits only occur within the same intent category; log cache hit decisions for manual review during the first 2 weeks after threshold changes |

:::tip Operational Readiness
Before launching a customer support agent, build runbooks for each issue in this table. The first month of production will surface at least three of these problems. Having pre-written runbooks with specific metric thresholds and remediation steps reduces mean time to resolution from hours to minutes.
:::

---

## Trade-offs & Alternatives

| Decision | Rationale | Alternative | Why Not |
|----------|-----------|-------------|---------|
| Specialized agents per intent | Each agent uses the optimal model and tools for its domain; enables independent iteration and cost control | Single general-purpose agent handling all intents | Higher cost (every query hits the expensive model), harder to tune prompts (one prompt tries to cover FAQ, orders, returns), and tool sprawl in a single agent's context window |
| GPT-4o-mini for FAQ, GPT-4o for orders | 10x cost difference between models; FAQ is extractive and does not need complex reasoning | Use GPT-4o for everything | Blended cost jumps from $0.01 to $0.04+ per conversation; at 1.5M monthly conversations, that is $45K+ extra per month with no quality improvement on FAQ responses |
| pgvector for knowledge base | Runs inside existing PostgreSQL infrastructure; no additional managed service; sufficient for knowledge bases under 1M documents | Dedicated vector database (Pinecone, Qdrant) | Adds operational complexity and cost; pgvector handles the expected scale; migrate to a dedicated solution if vector search latency becomes a bottleneck |
| Redis for session state | Sub-millisecond reads; built-in TTL for session expiration; cluster mode for fault tolerance | Store sessions in PostgreSQL | Adds 5-10ms per read to every turn of every conversation; at 5,000 concurrent sessions, this latency compounds |
| Confidence-based escalation (threshold 0.6) | Prevents low-quality AI responses from reaching customers; preserves trust | Always attempt an answer regardless of confidence | Low-confidence answers are often wrong; incorrect answers from the AI are harder to recover from than a prompt escalation |
| LLM Gateway with circuit breakers | Provider-agnostic; enables failover, A/B testing, and cost optimization across providers | Direct integration with a single LLM provider | Single point of failure; no fallback during outages; vendor lock-in on pricing and availability |
| Namespace-based vector store isolation (multi-tenant) | Scales to thousands of tenants without operational overhead of separate instances | Separate vector store instance per tenant | Does not scale past a few hundred tenants; massive infrastructure overhead; most tenants have small knowledge bases that do not justify dedicated resources |

---

## Interview Tips

:::tip How to Present This (35 minutes)
- **Minutes 1-5**: Clarify requirements and state assumptions. Ask about scale, channels, integration surface, compliance. Explicitly state what is out of scope (voice, multi-language). This shows maturity -- juniors skip straight to architecture.
- **Minutes 5-15**: Draw the high-level architecture diagram. Walk through each layer: client, API, agent, tool, data, observability. Explain the Intent Router as the key architectural decision -- it is the cost optimization lever that makes the system economically viable.
- **Minutes 15-25**: Deep dive into 2-3 components. Pick the Intent Router (explain the model tiering strategy), the FAQ Agent (explain RAG, confidence thresholds, escalation logic), and the Escalation Agent (explain conversation summarization and handoff protocol). Use the sequence diagrams to walk through a happy path and an escalation path.
- **Minutes 25-30**: Discuss scaling (traffic patterns, auto-scaling, semantic caching, circuit breakers), cost analysis (per-conversation breakdown, monthly projection), and failure modes. Mention multi-tenant considerations if relevant to the interviewer's company.
- **Minutes 30-35**: Handle follow-up questions. Common ones: "How would you add voice support?" (separate ASR/TTS layer, same agent backend), "How do you prevent prompt injection?" (input filtering, tool sandboxing, least privilege on tool access), "How would you evaluate agent quality?" (Langfuse traces, human evaluation of sampled conversations, A/B testing prompt changes).
:::
