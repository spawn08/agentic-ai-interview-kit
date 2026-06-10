---
sidebar_position: 4
title: Memory Systems
description: Why agents need memory, types of memory (short-term, long-term, episodic, semantic, working), memory architectures, and practical implementation with code.
---

# Memory Systems

Without memory, every agent interaction starts from scratch. The agent cannot learn from past mistakes, recall user preferences, or build on previous research. Memory transforms a stateless LLM into a system that **accumulates knowledge**, **maintains context**, and **improves over time**.

---

## Why Agents Need Memory

Consider an agent that helps you plan a trip. Without memory:

- It forgets your budget after you mention it
- It cannot recall that you prefer aisle seats
- It re-searches the same flights you already rejected
- Every session starts from zero, even if you talked yesterday

Memory solves these problems at different time scales:

| Time Scale | Problem Without Memory | Memory Solution |
|------------|----------------------|-----------------|
| Within a turn | Cannot reference earlier parts of a long response | Working memory |
| Within a session | Forgets context from 20 messages ago | Short-term memory (context window) |
| Across sessions | Cannot recall past conversations | Long-term memory (vector stores, databases) |
| Across tasks | Cannot learn from similar past tasks | Episodic memory |
| General knowledge | Cannot accumulate domain expertise | Semantic memory |

---

## Memory Types

The following taxonomy draws from cognitive science and maps directly to implementation patterns in agentic systems.

```mermaid
graph TD
    Memory["Agent Memory"]
    Memory --> STM["Short-Term Memory\n(Context Window)"]
    Memory --> WM["Working Memory\n(Scratchpad)"]
    Memory --> LTM["Long-Term Memory"]

    LTM --> Episodic["Episodic Memory\n(Past Experiences)"]
    LTM --> Semantic["Semantic Memory\n(Facts & Knowledge)"]
    LTM --> Procedural["Procedural Memory\n(Learned Skills)"]

    STM -.- STM_impl["Implementation:\nConversation history\nin the prompt"]
    WM -.- WM_impl["Implementation:\nState variables,\nscratchpad, plan"]
    Episodic -.- Ep_impl["Implementation:\nVector DB of past\ninteraction summaries"]
    Semantic -.- Sem_impl["Implementation:\nRAG over knowledge\nbases, embeddings"]
    Procedural -.- Proc_impl["Implementation:\nFine-tuned models,\nfew-shot examples"]

    style Memory fill:#1a535c,stroke:#0d3b40,color:#fff
    style STM fill:#4ecdc4,stroke:#1a535c,color:#000
    style WM fill:#4ecdc4,stroke:#1a535c,color:#000
    style LTM fill:#ff6b6b,stroke:#c0392b,color:#fff
    style Episodic fill:#ffe66d,stroke:#f4d35e,color:#000
    style Semantic fill:#ffe66d,stroke:#f4d35e,color:#000
    style Procedural fill:#ffe66d,stroke:#f4d35e,color:#000
```

### Short-Term Memory (Context Window)

The simplest form of memory: the conversation history that fits within the LLM's context window. Every message (user, assistant, tool results) is appended to the prompt.

**Characteristics:**
- Capacity is limited by the model's context window (4K to 1M+ tokens)
- Content is exact -- no lossy compression
- Disappears when the session ends
- Cost scales linearly with conversation length

**Challenge:** When the conversation exceeds the context window, you must decide what to keep and what to discard.

```python
def manage_context_window(messages: list, max_tokens: int = 120000) -> list:
    """Simple context window management with sliding window + system message preservation."""
    from tiktoken import encoding_for_model
    enc = encoding_for_model("gpt-4o")

    # Always keep the system message
    system_msgs = [m for m in messages if m["role"] == "system"]
    other_msgs = [m for m in messages if m["role"] != "system"]

    # Count tokens for system messages
    system_tokens = sum(len(enc.encode(m["content"])) for m in system_msgs)
    available_tokens = max_tokens - system_tokens

    # Keep as many recent messages as fit
    kept_messages = []
    running_tokens = 0
    for msg in reversed(other_msgs):
        msg_tokens = len(enc.encode(str(msg.get("content", ""))))
        if running_tokens + msg_tokens > available_tokens:
            break
        kept_messages.insert(0, msg)
        running_tokens += msg_tokens

    return system_msgs + kept_messages
```

### Working Memory (Scratchpad)

Working memory holds the agent's **current state** -- the plan it is executing, intermediate results, variables it is tracking, and its internal reasoning. Unlike short-term memory (which is the raw conversation), working memory is structured and purposeful.

```python
from pydantic import BaseModel, Field

class WorkingMemory(BaseModel):
    """Structured working memory for an agent."""
    current_goal: str = ""
    plan_steps: list[str] = Field(default_factory=list)
    current_step_index: int = 0
    intermediate_results: dict[str, str] = Field(default_factory=dict)
    observations: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    blocked_on: str | None = None

    def to_prompt_section(self) -> str:
        """Serialize working memory into a prompt section."""
        sections = [f"Current Goal: {self.current_goal}"]

        if self.plan_steps:
            plan_display = []
            for i, step in enumerate(self.plan_steps):
                marker = ">>>" if i == self.current_step_index else "   "
                status = "DONE" if i < self.current_step_index else "TODO"
                plan_display.append(f"{marker} [{status}] Step {i+1}: {step}")
            sections.append("Plan:\n" + "\n".join(plan_display))

        if self.intermediate_results:
            results = "\n".join(f"  - {k}: {v}" for k, v in self.intermediate_results.items())
            sections.append(f"Results So Far:\n{results}")

        if self.blocked_on:
            sections.append(f"BLOCKED: {self.blocked_on}")

        return "\n\n".join(sections)
```

:::tip Working Memory vs. Short-Term Memory
Short-term memory is the **raw conversation history**. Working memory is a **curated, structured summary** of what matters right now. Think of short-term memory as a tape recording and working memory as your notes.
:::

### Episodic Memory

Episodic memory stores **specific past experiences** -- previous conversations, task completions, errors encountered, and strategies that worked. It allows the agent to learn from its own history.

**Implementation pattern:** After each task, summarize the interaction and store it in a vector database. Before starting a new task, retrieve relevant past episodes.

```python
from datetime import datetime

class Episode(BaseModel):
    """A single episodic memory entry."""
    timestamp: datetime
    task_description: str
    approach_taken: str
    outcome: str  # "success", "partial", "failure"
    lessons_learned: str
    tools_used: list[str]
    embedding: list[float] | None = None  # For vector search

class EpisodicMemory:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def record_episode(self, episode: Episode):
        """Store an episode after task completion."""
        text = (
            f"Task: {episode.task_description}\n"
            f"Approach: {episode.approach_taken}\n"
            f"Outcome: {episode.outcome}\n"
            f"Lessons: {episode.lessons_learned}"
        )
        self.vector_store.add(
            text=text,
            metadata={
                "timestamp": episode.timestamp.isoformat(),
                "outcome": episode.outcome,
                "tools_used": episode.tools_used,
            },
        )

    def recall_relevant_episodes(self, current_task: str, top_k: int = 3) -> list[str]:
        """Retrieve past episodes relevant to the current task."""
        results = self.vector_store.search(query=current_task, top_k=top_k)
        return [r.text for r in results]
```

### Semantic Memory

Semantic memory stores **general facts and knowledge** independent of specific experiences. This is the agent's knowledge base -- company policies, product documentation, domain expertise.

**Implementation pattern:** RAG (Retrieval-Augmented Generation) -- embed documents into a vector store and retrieve relevant chunks at query time.

| Semantic Memory Source | How It Is Used |
|----------------------|----------------|
| Company knowledge base | Agent retrieves policies when answering HR questions |
| Product documentation | Agent looks up API specs when helping developers |
| User profile/preferences | Agent personalizes responses based on stored preferences |
| Domain ontologies | Agent reasons about relationships between concepts |

### Procedural Memory

Procedural memory stores **learned procedures and skills** -- essentially "how to do things." In LLM-based agents, this maps to:

- **Few-shot examples** stored and retrieved dynamically
- **Fine-tuned model weights** (the procedure is baked into the model)
- **Prompt templates** for specific task types
- **Learned tool-use patterns** (which tools work best for which tasks)

:::info Cognitive Science Parallel
This taxonomy mirrors human memory research. Humans have short-term memory (7 +/- 2 items), working memory (active manipulation of information), episodic memory (personal experiences), semantic memory (general knowledge), and procedural memory (riding a bike). Agent memory systems are inspired by -- but do not replicate -- these human systems.
:::

---

## Memory Architectures

How do you combine these memory types into a coherent system? Here are three common architectures.

### Architecture 1: Flat Memory (Context-Only)

The simplest approach. All memory lives in the conversation history. No external storage.

```mermaid
graph LR
    User["User Message"] --> Context["Context Window\n(All Messages)"]
    Context --> LLM["LLM"]
    LLM --> Response["Response"]
    Response --> Context

    style Context fill:#457b9d,stroke:#1d3557,color:#fff
```

**Use when:** Conversations are short, no cross-session persistence needed, cost is not a concern.

**Limitation:** Breaks down as conversation length exceeds the context window.

### Architecture 2: RAG-Augmented Memory

Conversation history is supplemented with retrieval from external knowledge stores.

```mermaid
graph TD
    User["User Message"] --> Retriever["Memory Retriever"]
    Retriever --> VectorDB["Vector Store\n(Semantic + Episodic)"]
    Retriever --> Context["Context Window"]
    ConvHistory["Conversation History\n(Short-Term)"] --> Context
    WorkMem["Working Memory\n(Scratchpad)"] --> Context
    VectorDB -->|"Relevant memories"| Context
    Context --> LLM["LLM"]
    LLM --> Response["Response"]
    Response --> ConvHistory
    Response -->|"End of task"| Summarizer["Summarizer"]
    Summarizer -->|"Store episode"| VectorDB

    style VectorDB fill:#e63946,stroke:#d62828,color:#fff
    style Context fill:#457b9d,stroke:#1d3557,color:#fff
    style LLM fill:#2a9d8f,stroke:#264653,color:#fff
```

**Use when:** You need cross-session memory, domain knowledge retrieval, or the conversation frequently exceeds the context window.

### Architecture 3: Hierarchical Memory with Consolidation

Inspired by how human memory works -- short-term memories are selectively consolidated into long-term storage, with periodic summarization and forgetting.

```mermaid
graph TD
    Input["New Information"]
    Input --> Buffer["Buffer Memory\n(Last N messages)"]
    Buffer -->|"Overflow"| Summarizer["Summarization\nEngine"]
    Summarizer --> Summary["Session Summary"]
    Summary --> Episodic["Episodic Store"]

    Buffer --> Context["Active Context"]
    Episodic -->|"Relevant retrieval"| Context
    Semantic["Semantic Store\n(Knowledge Base)"] -->|"Relevant retrieval"| Context
    Context --> LLM["LLM"]

    Episodic -->|"Periodic consolidation"| Semantic

    style Buffer fill:#f4a261,stroke:#e76f51,color:#000
    style Episodic fill:#e63946,stroke:#d62828,color:#fff
    style Semantic fill:#457b9d,stroke:#1d3557,color:#fff
    style LLM fill:#2a9d8f,stroke:#264653,color:#fff
```

---

## Implementing a Simple Memory System

Here is a practical, end-to-end implementation of a memory system that combines short-term context management with long-term vector storage.

```python
"""
A practical memory system combining short-term (context window),
working memory (scratchpad), and long-term (vector store) memory.
"""

from openai import OpenAI
from datetime import datetime
import json
import hashlib

client = OpenAI()


class MemorySystem:
    """Unified memory system for an agent."""

    def __init__(
        self,
        max_short_term_messages: int = 50,
        embedding_model: str = "text-embedding-3-small",
    ):
        self.short_term: list[dict] = []
        self.max_short_term = max_short_term_messages
        self.embedding_model = embedding_model

        # Simple in-memory vector store (use Chroma/Pinecone in production)
        self.long_term_memories: list[dict] = []  # {text, embedding, metadata}

        # Working memory
        self.scratchpad: dict = {}

    # --- Short-Term Memory ---

    def add_message(self, role: str, content: str):
        """Add a message to short-term memory with overflow handling."""
        self.short_term.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

        # If overflow, summarize old messages and store in long-term
        if len(self.short_term) > self.max_short_term:
            self._consolidate_short_term()

    def _consolidate_short_term(self):
        """Summarize the oldest messages and move summary to long-term memory."""
        # Take the oldest half of messages
        split = len(self.short_term) // 2
        old_messages = self.short_term[:split]
        self.short_term = self.short_term[split:]

        # Summarize using the LLM
        conversation_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in old_messages
        )
        summary_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Summarize this conversation segment concisely, preserving key facts, decisions, and action items.",
                },
                {"role": "user", "content": conversation_text},
            ],
            max_tokens=500,
        )
        summary = summary_response.choices[0].message.content

        # Store summary in long-term memory
        self.store_long_term(
            text=summary,
            metadata={"type": "conversation_summary", "message_count": len(old_messages)},
        )

    # --- Long-Term Memory ---

    def store_long_term(self, text: str, metadata: dict | None = None):
        """Embed and store a memory in the long-term vector store."""
        embedding = self._embed(text)
        self.long_term_memories.append({
            "text": text,
            "embedding": embedding,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "id": hashlib.sha256(text.encode()).hexdigest()[:16],
        })

    def recall(self, query: str, top_k: int = 5) -> list[str]:
        """Retrieve the most relevant long-term memories for a query."""
        if not self.long_term_memories:
            return []

        query_embedding = self._embed(query)

        # Compute cosine similarities
        scored = []
        for mem in self.long_term_memories:
            sim = self._cosine_similarity(query_embedding, mem["embedding"])
            scored.append((sim, mem["text"]))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in scored[:top_k]]

    # --- Working Memory ---

    def set_scratchpad(self, key: str, value):
        """Store a value in working memory."""
        self.scratchpad[key] = value

    def get_scratchpad(self, key: str, default=None):
        """Retrieve a value from working memory."""
        return self.scratchpad.get(key, default)

    # --- Context Assembly ---

    def build_context(self, current_query: str, system_prompt: str) -> list[dict]:
        """Assemble the full context for an LLM call."""
        context = [{"role": "system", "content": system_prompt}]

        # Add relevant long-term memories
        memories = self.recall(current_query, top_k=3)
        if memories:
            memory_text = "\n\n".join(f"- {m}" for m in memories)
            context.append({
                "role": "system",
                "content": f"Relevant memories from past interactions:\n{memory_text}",
            })

        # Add working memory if present
        if self.scratchpad:
            scratchpad_text = json.dumps(self.scratchpad, indent=2)
            context.append({
                "role": "system",
                "content": f"Current working memory:\n{scratchpad_text}",
            })

        # Add short-term conversation history
        for msg in self.short_term:
            context.append({"role": msg["role"], "content": msg["content"]})

        return context

    # --- Utilities ---

    def _embed(self, text: str) -> list[float]:
        """Generate an embedding for the given text."""
        response = client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
```

### Using the Memory System

```python
# Initialize
memory = MemorySystem(max_short_term_messages=30)

# Store some long-term knowledge
memory.store_long_term(
    text="User prefers concise responses and dislikes bullet points.",
    metadata={"type": "user_preference"},
)
memory.store_long_term(
    text="In the last session, the user was researching flights to Tokyo for March 2026.",
    metadata={"type": "episode"},
)

# Set working memory for the current task
memory.set_scratchpad("current_task", "Find hotels in Tokyo")
memory.set_scratchpad("budget", "$200/night")

# Add conversation messages
memory.add_message("user", "Can you find me a hotel in Shinjuku?")

# Build context for the LLM
context = memory.build_context(
    current_query="hotels in Shinjuku, Tokyo",
    system_prompt="You are a travel planning assistant.",
)
# The context now includes: system prompt, relevant memories (Tokyo trip from last session,
# user preferences), working memory (budget), and the conversation history.
```

---

## LangGraph Memory and Checkpointing

LangGraph provides **built-in state persistence** through checkpointers -- pluggable backends that snapshot the entire graph state after every node execution. This enables short-term memory (within a thread), long-term memory (across threads), and time-travel debugging out of the box.

### In-Memory Checkpointing (Development)

`MemorySaver` stores state in process memory. Ideal for prototyping and tests.

```python
from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode


class ConversationState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


llm = ChatOpenAI(model="gpt-4o", temperature=0)


def agent_node(state: ConversationState) -> ConversationState:
    return {"messages": [llm.invoke(state["messages"])]}


graph = StateGraph(ConversationState)
graph.add_node("agent", agent_node)
graph.set_entry_point("agent")
graph.add_edge("agent", END)

# Compile with MemorySaver -- every invocation is checkpointed
memory = MemorySaver()
agent = graph.compile(checkpointer=memory)

# Turn 1
config = {"configurable": {"thread_id": "user-42"}}
agent.invoke(
    {"messages": [HumanMessage(content="My budget is $200/night.")]},
    config=config,
)

# Turn 2 -- the agent remembers the budget from turn 1
agent.invoke(
    {"messages": [HumanMessage(content="Find me a hotel in Shinjuku.")]},
    config=config,
)
```

Each `thread_id` maintains an independent conversation. Switching `thread_id` starts a fresh context, while reusing the same ID resumes exactly where the agent left off.

### PostgreSQL Checkpointing (Production)

For production deployments, swap `MemorySaver` for `PostgresSaver` to persist state across process restarts and horizontal scaling.

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

DB_URI = "postgresql://user:pass@localhost:5432/agent_memory"


async def build_production_agent():
    async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
        await checkpointer.setup()  # creates tables on first run

        agent = graph.compile(checkpointer=checkpointer)

        # State is now durable -- survives restarts, deployable behind a load balancer
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content="Book the Shinjuku hotel.")]},
            config={"configurable": {"thread_id": "user-42"}},
        )
        return result
```

### Cross-Thread (Long-Term) Memory with LangGraph Store

For memories that persist **across conversations** (user preferences, facts learned over time), LangGraph provides `InMemoryStore` (dev) and database-backed stores (production). These work alongside checkpointers.

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

# Store a user preference (accessible from any thread)
store.put(
    namespace=("user_preferences", "user-42"),
    key="travel",
    value={"preferred_seat": "aisle", "budget": 200, "currency": "USD"},
)

# Retrieve in any future graph invocation
items = store.search(namespace=("user_preferences", "user-42"))
prefs = items[0].value if items else {}
# {'preferred_seat': 'aisle', 'budget': 200, 'currency': 'USD'}
```

### Choosing a Checkpointer

| Backend | Persistence | Use Case |
|---------|-------------|----------|
| `MemorySaver` | In-process only | Unit tests, prototyping, notebooks |
| `SqliteSaver` | Local file | Single-server deployments, CLI tools |
| `PostgresSaver` | Durable, multi-process | Production APIs, horizontally scaled services |

:::tip When to Use What
Use **checkpointers** for within-session and across-session conversation state (short-term memory). Use **stores** for cross-thread knowledge like user profiles and accumulated facts (long-term memory). Combine both for a full memory architecture.
:::

---

## Memory Design Decisions

When designing a memory system for your agent, consider these trade-offs:

| Decision | Option A | Option B | Guidance |
|----------|----------|----------|----------|
| **Storage** | In-memory | Persistent (vector DB) | Use persistent for production; in-memory for prototyping |
| **Retrieval** | Recency-based | Relevance-based (embedding similarity) | Combine both: weight by recency * relevance |
| **Consolidation** | Keep everything | Summarize and compress | Summarize when context window pressure is high |
| **Scope** | Per-user memory | Shared across users | Per-user for personalization; shared for organizational knowledge |
| **Update** | Append-only | Mutable (can edit/delete) | Append-only is simpler; mutable needed for corrections |

:::warning Privacy Considerations
Long-term memory stores can contain sensitive user data. Implement:
- Data retention policies (auto-delete after N days)
- User control (ability to view and delete their stored memories)
- Encryption at rest
- PII detection and redaction before storage
See [Guardrails and Safety](./guardrails-and-safety.md) for more.
:::

---

## Summary

- **Short-term memory** is the conversation history within the context window -- exact but limited.
- **Working memory** is the agent's structured scratchpad for the current task -- plans, intermediate results, state.
- **Long-term memory** persists across sessions via vector stores and databases.
- **Episodic memory** recalls past experiences; **semantic memory** retrieves general knowledge; **procedural memory** encodes learned skills.
- **Consolidation** (summarizing old context into long-term storage) is essential for long-running agents.
- Always consider **privacy, cost, and retrieval quality** when designing memory systems.

---

## Further Reading

- [What Are AI Agents?](./what-are-agents.md) -- The agent loop where memory is consumed and updated.
- [Planning and Reasoning](./planning-and-reasoning.md) -- How working memory supports the planning process.
- [Guardrails and Safety](./guardrails-and-safety.md) -- Privacy and PII handling in memory systems.
