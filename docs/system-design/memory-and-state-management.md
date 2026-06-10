---
sidebar_position: 3
title: "Memory and State Management"
description: "Distributed state, checkpointing, and conversation threading for agentic systems"
---

# Memory and State Management

An agent without memory is stateless and forgetful -- every interaction starts from zero. Production agentic systems require sophisticated state management that spans in-context memory, persistent storage, checkpointing for recovery, and conflict resolution for concurrent access.

---

## State Architecture Overview

```mermaid
graph TB
    subgraph "Agent Runtime"
        AL[Agent Loop]
        IC[In-Context Window]
    end

    subgraph "Short-Term State"
        SM[Session Memory<br/>Redis / Memcached]
        WC[Workflow Checkpoints<br/>DynamoDB / PostgreSQL]
    end

    subgraph "Long-Term State"
        CM[Conversation History<br/>PostgreSQL / MongoDB]
        VS[Semantic Memory<br/>Vector Store]
        EP[Episodic Memory<br/>Event Log]
    end

    subgraph "Shared State"
        BB[Blackboard<br/>Shared KV Store]
        EV[Event Bus<br/>Kafka / Redis Streams]
    end

    AL --> IC
    AL --> SM
    AL --> WC
    AL --> CM
    AL --> VS
    AL --> EP
    AL --> BB
    AL --> EV
```

---

## Distributed State

In a horizontally scaled system, agent workers are stateless. All state lives in external stores, and any worker must be able to pick up any session.

### State Categories

| Category | Lifetime | Store | Access Pattern |
|----------|----------|-------|---------------|
| **Turn context** | Single LLM call | In-context window | Read-only, constructed per call |
| **Session state** | Minutes to hours | Redis with TTL | Frequent read/write, low latency |
| **Workflow state** | Hours to days | DynamoDB / PostgreSQL | Checkpoint on each step |
| **Conversation history** | Days to months | PostgreSQL / MongoDB | Append-heavy, paginated reads |
| **Semantic memory** | Indefinite | Vector store (Pinecone, pgvector) | Similarity search |
| **User profile** | Indefinite | PostgreSQL | Read-heavy, rare updates |

### Session State Schema

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class SessionState:
    session_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    ttl_seconds: int = 3600

    # Conversation
    messages: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""

    # Workflow
    current_step: int = 0
    plan: list[dict] = field(default_factory=list)
    step_results: dict[int, Any] = field(default_factory=dict)

    # Agent context
    active_tools: list[str] = field(default_factory=list)
    accumulated_cost: float = 0.0
    token_count: int = 0

    # Metadata
    version: int = 0  # For optimistic concurrency control
```

---

## Checkpointing Strategies

Checkpointing allows an agent to resume from the last successful step after a crash, rather than restarting from the beginning.

### When to Checkpoint

```mermaid
sequenceDiagram
    participant Agent
    participant Store as State Store
    participant LLM
    participant Tool

    Agent->>Store: Load checkpoint (or start fresh)
    Agent->>LLM: Step 1 - Plan
    LLM-->>Agent: Plan result
    Agent->>Store: Checkpoint after Step 1

    Agent->>Tool: Step 2 - Execute tool
    Tool-->>Agent: Tool result
    Agent->>Store: Checkpoint after Step 2

    Note over Agent,Store: Crash here!

    Agent->>Store: Recover from Step 2 checkpoint
    Agent->>LLM: Step 3 - Synthesize (skip Steps 1-2)
    LLM-->>Agent: Final result
    Agent->>Store: Mark complete
```

### Implementation

```python
class CheckpointManager:
    def __init__(self, store):
        self.store = store

    async def save_checkpoint(self, session_id: str, state: SessionState):
        """Save a checkpoint with optimistic concurrency control."""
        key = f"checkpoint:{session_id}"
        existing = await self.store.get(key)

        if existing and existing.version != state.version:
            raise ConcurrencyConflictError(
                f"State modified by another worker. "
                f"Expected version {state.version}, found {existing.version}."
            )

        state.version += 1
        state.updated_at = datetime.utcnow()
        await self.store.set(key, state, ttl=state.ttl_seconds)

    async def load_checkpoint(self, session_id: str) -> SessionState | None:
        """Load the most recent checkpoint for a session."""
        key = f"checkpoint:{session_id}"
        return await self.store.get(key)

    async def resume_from_checkpoint(self, session_id: str) -> tuple[SessionState, int]:
        """Load checkpoint and return (state, next_step_index)."""
        state = await self.load_checkpoint(session_id)
        if state is None:
            raise CheckpointNotFoundError(session_id)

        next_step = state.current_step + 1
        return state, next_step
```

### Checkpoint Granularity Trade-offs

| Granularity | Checkpoint After | Pros | Cons |
|-------------|-----------------|------|------|
| **Per-step** | Every agent step | Minimal rework on recovery | High write volume |
| **Per-phase** | Plan, Execute, Synthesize | Balanced | May redo some steps |
| **Per-transaction** | Only on meaningful state changes | Low write volume | More rework on recovery |
| **Periodic** | Every N seconds | Predictable write rate | Unpredictable rework |

:::tip
For most production systems, **per-step checkpointing** is the right default. The write overhead (one small write per step) is negligible compared to the LLM call latency, and it minimizes wasted computation on recovery.
:::

---

## Session Persistence

### Short-Lived Sessions (Chatbot)

For interactive chat, the session typically lasts minutes to hours. Redis with TTL is the standard choice.

```python
import json
import redis.asyncio as redis

class RedisSessionStore:
    def __init__(self, redis_url: str):
        self.client = redis.from_url(redis_url)

    async def save(self, session_id: str, state: SessionState):
        data = json.dumps(state.to_dict())
        await self.client.setex(
            f"session:{session_id}",
            state.ttl_seconds,
            data,
        )

    async def load(self, session_id: str) -> SessionState | None:
        data = await self.client.get(f"session:{session_id}")
        if data is None:
            return None
        return SessionState.from_dict(json.loads(data))

    async def extend_ttl(self, session_id: str, additional_seconds: int):
        await self.client.expire(
            f"session:{session_id}",
            additional_seconds,
        )
```

### Long-Lived Sessions (Workflow)

For multi-day workflows (research agents, data pipeline agents), use a durable store like PostgreSQL.

```sql
CREATE TABLE agent_sessions (
    session_id    UUID PRIMARY KEY,
    user_id       UUID NOT NULL,
    state         JSONB NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active',
    version       INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user ON agent_sessions(user_id);
CREATE INDEX idx_sessions_status ON agent_sessions(status) WHERE status = 'active';

-- Optimistic concurrency control
CREATE OR REPLACE FUNCTION update_session(
    p_session_id UUID,
    p_state JSONB,
    p_expected_version INTEGER
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE agent_sessions
    SET state = p_state,
        version = version + 1,
        updated_at = now()
    WHERE session_id = p_session_id
      AND version = p_expected_version;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;
```

---

## Conversation Threading

Production agents often handle branching conversations -- where a user revisits a previous point, or where multiple sub-conversations run in parallel.

### Thread Model

```mermaid
graph TD
    R[Root Thread<br/>session_id: abc-123] --> T1[Thread 1: Research<br/>thread_id: t-001]
    R --> T2[Thread 2: Code Review<br/>thread_id: t-002]
    T1 --> T1A[Sub-thread: Source A<br/>thread_id: t-001-a]
    T1 --> T1B[Sub-thread: Source B<br/>thread_id: t-001-b]
    T2 --> T2A[Sub-thread: File analysis<br/>thread_id: t-002-a]
```

### Data Model

```python
@dataclass
class ConversationThread:
    thread_id: str
    parent_thread_id: str | None
    session_id: str
    messages: list[Message]
    status: str  # "active", "completed", "abandoned"
    metadata: dict

    def fork(self, new_thread_id: str) -> "ConversationThread":
        """Create a child thread that inherits context from this thread."""
        return ConversationThread(
            thread_id=new_thread_id,
            parent_thread_id=self.thread_id,
            session_id=self.session_id,
            messages=[],  # Child starts with empty messages
            status="active",
            metadata={"forked_from": self.thread_id},
        )

    def build_context(self, thread_store) -> list[Message]:
        """Build context by walking up the thread hierarchy."""
        context = []
        current = self
        while current is not None:
            context = current.messages + context
            if current.parent_thread_id:
                current = thread_store.get(current.parent_thread_id)
            else:
                current = None
        return context
```

---

## State Serialization

Agent state contains diverse types -- messages, tool results, embeddings, file references. Choosing the right serialization format affects performance and debuggability.

### Format Comparison

| Format | Size | Speed | Human-Readable | Schema Evolution |
|--------|------|-------|----------------|-----------------|
| **JSON** | Large | Moderate | Yes | Flexible (schemaless) |
| **MessagePack** | Small | Fast | No | Flexible (schemaless) |
| **Protocol Buffers** | Smallest | Fastest | No | Excellent (schema versioning) |
| **Pickle** | Variable | Fast | No | Fragile (Python-only) |

:::warning
Never use Python pickle for agent state serialization. It is insecure (arbitrary code execution on deserialization), fragile across Python versions, and not portable across languages. Use JSON for debuggability or Protocol Buffers for performance.
:::

### Versioned Serialization

```python
class StateSerializer:
    CURRENT_VERSION = 3

    def serialize(self, state: SessionState) -> bytes:
        data = {
            "_version": self.CURRENT_VERSION,
            "session_id": state.session_id,
            "messages": [m.to_dict() for m in state.messages],
            "plan": state.plan,
            "step_results": state.step_results,
            "metadata": state.metadata,
        }
        return json.dumps(data).encode("utf-8")

    def deserialize(self, raw: bytes) -> SessionState:
        data = json.loads(raw.decode("utf-8"))
        version = data.get("_version", 1)

        # Apply migrations for older versions
        if version < 2:
            data = self._migrate_v1_to_v2(data)
        if version < 3:
            data = self._migrate_v2_to_v3(data)

        return SessionState.from_dict(data)

    def _migrate_v1_to_v2(self, data: dict) -> dict:
        """v2 added the 'plan' field."""
        data.setdefault("plan", [])
        data["_version"] = 2
        return data

    def _migrate_v2_to_v3(self, data: dict) -> dict:
        """v3 renamed 'context' to 'metadata'."""
        data["metadata"] = data.pop("context", {})
        data["_version"] = 3
        return data
```

---

## Conflict Resolution

When multiple workers or agent branches update the same state concurrently, conflicts must be resolved deterministically.

### Strategies

| Strategy | How It Works | Best For |
|----------|-------------|----------|
| **Optimistic concurrency (versioning)** | Read version, write only if version matches | Low-contention updates |
| **Last-writer-wins** | Timestamp-based, latest write takes precedence | Append-only data |
| **Merge** | Application-specific merge logic | Concurrent tool results |
| **Lock-based** | Distributed lock (Redlock) before write | Critical sections |

### Optimistic Concurrency Example

```python
class OptimisticStateStore:
    async def update(self, session_id: str, updater_fn):
        """Read-modify-write with optimistic concurrency."""
        max_retries = 5
        for attempt in range(max_retries):
            state = await self.load(session_id)
            original_version = state.version

            # Apply the update
            updated_state = updater_fn(state)

            # Try to save with version check
            success = await self._compare_and_swap(
                session_id, updated_state, expected_version=original_version
            )
            if success:
                return updated_state

            # Version conflict -- retry with fresh state
            await asyncio.sleep(0.01 * (2 ** attempt))  # Exponential backoff

        raise ConflictError(f"Failed to update session {session_id} after {max_retries} attempts")
```

---

## TTL Policies

State that is never cleaned up eventually consumes all available storage. TTL (time-to-live) policies ensure state has a defined lifecycle.

### Recommended TTLs

| State Type | TTL | Rationale |
|-----------|-----|-----------|
| Active session state | 1-4 hours | User sessions rarely last longer |
| Workflow checkpoints | 7 days | Allow recovery from extended outages |
| Conversation history | 90 days | Compliance and user expectation |
| Tool result cache | 1-24 hours | Results go stale; balance freshness vs. cost |
| Semantic memory | No TTL (explicit deletion) | Long-term knowledge; managed by user |
| Rate limit counters | 1-60 minutes | Match the rate limit window |

### Tiered Expiration

```python
class TieredStateManager:
    """Move state through tiers as it ages."""

    def __init__(self, hot_store, warm_store, cold_store):
        self.hot = hot_store    # Redis: sub-ms latency
        self.warm = warm_store  # DynamoDB: single-digit-ms latency
        self.cold = cold_store  # S3: archival

    async def get(self, session_id: str) -> SessionState | None:
        # Check hot tier first
        state = await self.hot.get(session_id)
        if state:
            return state

        # Fall back to warm tier
        state = await self.warm.get(session_id)
        if state:
            # Promote back to hot tier
            await self.hot.set(session_id, state, ttl=3600)
            return state

        # Fall back to cold tier (slow)
        state = await self.cold.get(session_id)
        if state:
            await self.warm.set(session_id, state, ttl=86400 * 7)
            await self.hot.set(session_id, state, ttl=3600)
            return state

        return None

    async def archive(self, session_id: str):
        """Move completed session from hot to cold storage."""
        state = await self.hot.get(session_id)
        if state:
            await self.cold.put(session_id, state)
            await self.hot.delete(session_id)
```

:::info
Tiered storage is the same pattern used by databases (buffer pool -> SSD -> archive). Apply the same thinking: hot data in memory, warm data in fast persistent storage, cold data in cheap bulk storage.
:::

---

## Context Window Management

The LLM context window is the most constrained form of agent memory. Managing what goes into the context window is critical for both quality and cost.

### Strategies

```python
class ContextWindowManager:
    def __init__(self, max_tokens: int, tokenizer):
        self.max_tokens = max_tokens
        self.tokenizer = tokenizer

    def build_context(self, state: SessionState, system_prompt: str) -> list[dict]:
        """Build a context window that fits within the token budget."""
        budget = self.max_tokens
        context = []

        # 1. System prompt (always included)
        system_tokens = self._count_tokens(system_prompt)
        budget -= system_tokens
        context.append({"role": "system", "content": system_prompt})

        # 2. Reserve space for the response
        budget -= 1024  # Reserve for output

        # 3. Current turn (always included)
        current_turn = state.messages[-2:]  # Last user message + any assistant partial
        turn_tokens = sum(self._count_tokens(m["content"]) for m in current_turn)
        budget -= turn_tokens

        # 4. Recent conversation history (most recent first)
        history = state.messages[:-2]
        included_history = []
        for msg in reversed(history):
            msg_tokens = self._count_tokens(msg["content"])
            if budget - msg_tokens < 0:
                break
            included_history.insert(0, msg)
            budget -= msg_tokens

        # 5. If history was truncated, add a summary
        if len(included_history) < len(history) and state.summary:
            summary_msg = {"role": "system", "content": f"Conversation summary: {state.summary}"}
            summary_tokens = self._count_tokens(summary_msg["content"])
            if budget >= summary_tokens:
                context.append(summary_msg)

        context.extend(included_history)
        context.extend(current_turn)
        return context
```

---

## Interview Preparation

**Sample question:** "How would you manage state for an agent that handles multi-day research tasks with checkpointing?"

**Strong answer structure:**
1. **Externalized state** -- stateless workers, state in PostgreSQL (durable) with Redis cache (fast)
2. **Per-step checkpointing** -- save after each tool execution for minimal rework on recovery
3. **Optimistic concurrency** -- version field prevents lost updates from concurrent workers
4. **Tiered TTLs** -- active sessions in Redis (4h), checkpoints in PostgreSQL (7d), archives in S3
5. **Context window management** -- summarization for long histories, sliding window for recent turns
6. **Conversation threading** -- fork/join model for parallel research branches
7. **Versioned serialization** -- schema migrations so old checkpoints remain loadable
